"""Partition a PR diff into review units with a script-enforced coverage guarantee.

v1 enumerator: universal-ctags function ranges intersected with changed lines, with a
hunk-as-unit fallback. The Haiku LLM-mapper described in the design spec is intentionally
DEFERRED -- hunk-as-unit already closes the coverage partition, so the mapper is a future
refinement for finer granularity in ctags-unknown languages, never load-bearing for the
coverage invariant.
"""
import json
import re
import subprocess

_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
_FUNC_KINDS = {"function", "method", "subroutine", "func", "procedure"}


def parse_diff(diff_text):
    files = {}
    cur = None
    new_ln = 0
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            p = line[4:].strip().split("\t")[0]
            if p[:2] in ("a/", "b/", "i/", "w/", "c/", "o/"):  # git default + mnemonicPrefix
                p = p[2:]
            cur = None if p == "/dev/null" else p
            if cur:
                files.setdefault(cur, {"changed": set(), "hunks": [], "removed": 0,
                                       "text": "", "removed_text": "", "line_text": {}})
        elif line.startswith("@@"):
            m = _HUNK_RE.match(line)
            if m and cur:
                new_ln = int(m.group(1))
                span = int(m.group(2)) if m.group(2) else 1
                files[cur]["hunks"].append((new_ln, new_ln + max(span, 1) - 1))
        elif cur is not None:
            if line.startswith("+") and not line.startswith("+++"):
                files[cur]["changed"].add(new_ln)
                files[cur]["text"] += line[1:] + "\n"
                files[cur]["line_text"][new_ln] = line[1:]
                new_ln += 1
            elif line.startswith("-") and not line.startswith("---"):
                files[cur]["removed"] += 1
                files[cur]["removed_text"] += line[1:] + "\n"
            elif line.startswith(" "):
                new_ln += 1
            # "\ No newline at end of file" and blank markers: ignore
    return files


def _default_ctags_runner(filepath):
    proc = subprocess.run(
        ["ctags", "--output-format=json", "--fields=+ne", "-f", "-", filepath],
        capture_output=True, text=True, timeout=30,
    )
    return proc.stdout


def ctags_symbols(filepath, runner=_default_ctags_runner):
    try:
        out = runner(filepath)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    syms = []
    for line in out.splitlines():
        try:
            tag = json.loads(line)
        except ValueError:
            continue
        if tag.get("_type") != "tag" or tag.get("kind") not in _FUNC_KINDS:
            continue
        start = tag.get("line")
        if not start:
            continue
        end = tag.get("end") or start
        syms.append((tag["name"], int(start), int(end)))
    return syms


class CoverageError(Exception):
    pass


def classify_change(name, new_range, changed, removed_text):
    """`added` only if the whole function range is new (no surviving context/removed lines
    inside) AND the symbol name is absent from the removed-line text; else `modified`.
    Catches full-body rewrites: a swapped body keeps the def line as context (range not
    fully changed) or rewrites the def (name appears in removed_text) -> modified either way."""
    s, e = new_range
    fully_new = set(range(s, e + 1)) <= set(changed)
    return "added" if (fully_new and name not in removed_text) else "modified"


def map_file_units(filepath, changed, hunks, symbols, removed_text=""):
    changed = set(changed)
    units = []
    covered = set()
    if symbols:
        for name, s, e in symbols:
            lines = sorted(l for l in changed if s <= l <= e)
            if lines:
                units.append({"symbol": name, "new_range": [s, e], "lines": lines,
                              "kind": "function",
                              "change_type": classify_change(name, (s, e), changed, removed_text)})
                covered |= set(lines)
    uncovered = changed - covered
    for hs, he in hunks:
        hl = sorted(l for l in uncovered if hs <= l <= he)
        if hl:
            units.append({"symbol": f"{filepath}@{hs}-{he}", "new_range": [hs, he],
                          "lines": hl, "kind": "unmapped_chunk", "change_type": "modified"})
            covered |= set(hl)
    leftover = sorted(changed - covered)
    if leftover:
        units.append({"symbol": f"{filepath}@{leftover[0]}-{leftover[-1]}",
                      "new_range": [leftover[0], leftover[-1]], "lines": leftover,
                      "kind": "unmapped_chunk", "change_type": "modified"})
    return units


def reconcile(changed, units):
    covered = set()
    for u in units:
        covered |= set(u["lines"])
    missing = set(changed) - covered
    if missing:
        raise CoverageError(f"uncovered changed lines: {sorted(missing)}")


_RISK_KEYWORDS = {
    "auth": ["auth", "login", "token", "session", "password", "passwd", "jwt", "oauth",
             "permission", "acl", "credential", "secret", "entitlement"],
    "money": ["payment", "refund", "charge", "price", "invoice", "billing", "amount",
              "currency", "balance", "transaction"],
    "persistence": ["sql", "select ", "insert ", "update ", "delete ", "query", "schema",
                    "repository", "db.", "session.add", "cursor"],
    "migration": ["migration", "alter table", "create table", "drop table", "backfill"],
    "concurrency": ["async", "await", "lock", "mutex", "thread", "goroutine", "atomic",
                    "semaphore", "sync.", "concurrent"],
    "parsing": ["parse", "regex", "re.compile", "json.loads", "decode", "tokeniz"],
    "serialization": ["serialize", "deserialize", "marshal", "pickle", "to_dict", "from_dict",
                      "json.dumps"],
    "retries": ["retry", "backoff", "reconnect", "max_attempts"],
    "caching": ["cache", "memoize", "ttl", "invalidate", "redis"],
    "external_api": ["http", "requests.", "fetch(", "axios", "api_key", "endpoint", "webhook"],
    "fs_net": ["open(", "os.remove", "socket", "tempfile", "shutil", "pathlib", "subprocess"],
    "time": ["datetime", "time.", "timezone", "utcnow", "sleep(", "deadline", "expires",
             "timeout"],
    "error_handling": ["except", "raise", "try:", "catch", "finally", "throw", "panic"],
}

_CONCURRENCY_RE = re.compile(
    r"\b(async|await|lock|mutex|thread|goroutine|atomic|semaphore|sync\.)\b", re.IGNORECASE)


def risk_tags(filepath, text):
    hay = (filepath + "\n" + text).lower()
    return sorted(tag for tag, kws in _RISK_KEYWORDS.items() if any(k in hay for k in kws))


def lenses(text, change_type=None):
    base = ["contract", "boundary", "errors"]
    if _CONCURRENCY_RE.search(text):
        base.append("concurrency")
    if change_type == "modified":
        base.append("regression")
    return base


def should_isolate(line_count, tags, kind=None):
    # every changed function gets its own reviewer (no batching) so per-function regressions
    # aren't diluted; only unmapped chunks fall back to the size/risk threshold.
    if kind == "function":
        return True
    return line_count > 15 or bool(tags)


def build_worklist(diff_text, symbol_lookup=ctags_symbols):
    files = parse_diff(diff_text)
    units = []
    counter = 0
    for filepath, info in files.items():
        symbols = symbol_lookup(filepath)
        file_units = map_file_units(filepath, info["changed"], info["hunks"], symbols,
                                    info.get("removed_text", ""))
        reconcile(info["changed"], file_units)
        tags = risk_tags(filepath, info["text"])
        line_text = info.get("line_text", {})
        for u in file_units:
            counter += 1
            size = len(u["lines"])
            unit_text = "\n".join(line_text.get(l, "") for l in u["lines"])
            units.append({
                "id": f"u{counter}",
                "file": filepath,
                "symbol": u["symbol"],
                "kind": u["kind"],
                "change_type": u["change_type"],
                "new_range": u["new_range"],
                "lines": u["lines"],
                "size": size,
                "risk_tags": tags,
                "lenses": lenses(unit_text, u["change_type"]),
                "isolate": should_isolate(size, tags, u["kind"]),
            })
    return {
        "units": units,
        "summary": {
            "file_count": len(files),
            "unit_count": len(units),
            "isolate_count": sum(1 for u in units if u["isolate"]),
        },
    }


def _default_grep_runner(symbol, repo_root):
    proc = subprocess.run(
        ["git", "-C", repo_root, "grep", "-n", "-F", f"{symbol}("],
        capture_output=True, text=True, timeout=30,
    )
    return proc.stdout


def find_callers(symbol, repo_root, grep_runner=_default_grep_runner):
    try:
        out = grep_runner(symbol, repo_root)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return []
    callers = []
    for line in out.splitlines():
        parts = line.split(":", 2)
        if len(parts) >= 2:
            callers.append(f"{parts[0]}:{parts[1]}")
    return callers


def changed_signature_symbols(worklist):
    out = []
    for u in worklist["units"]:
        if u["kind"] == "function" and u["lines"] and u["lines"][0] == u["new_range"][0]:
            out.append(u["symbol"])
    return out


CALLER_CAP = 20  # bound the ripple pass so it can't flood when crossing into unchanged code


def changed_function_symbols(worklist):
    """Every changed function symbol (added OR modified), public only — the ripple pass
    enumerates callers of all of them, not just signature changes (a body-only change can
    still break callers' assumptions). Leading-underscore (private) names are skipped."""
    out, seen = [], set()
    for u in worklist["units"]:
        if u.get("kind") != "function":
            continue
        name = u["symbol"]
        if name.startswith("_") or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def _symbol_change_type(worklist, symbol):
    types = [u.get("change_type") for u in worklist["units"]
             if u.get("symbol") == symbol and u.get("kind") == "function"]
    if "modified" in types:
        return "modified"
    return "added" if types else None


def caller_reports(worklist, repo_root, grep_runner=_default_grep_runner):
    """Per changed public symbol: its callers (capped), how many were dropped, and whether the
    symbol was added vs modified (so the reviewer picks a mechanical-arity vs behavioral check)."""
    reports = []
    for sym in changed_function_symbols(worklist):
        found = find_callers(sym, repo_root, grep_runner=grep_runner)
        reports.append({
            "symbol": sym,
            "change_type": _symbol_change_type(worklist, sym),
            "callers": found[:CALLER_CAP],
            "dropped": max(0, len(found) - CALLER_CAP),
        })
    return reports


_GENERIC_EVIDENCE = {"", "n/a", "na", "none", "looks fine", "ok", "okay", "tested",
                     "verified", "fine", "good", "checked", "no issues"}


def pass_is_earned(verdict):
    if verdict.get("status") != "PASS":
        return True
    ev = verdict.get("evidence") or {}
    items = (ev.get("boundary_inputs") or []) + (ev.get("error_branches") or [])
    vals = [str(x).strip().lower() for x in items]
    vals = [v for v in vals if v not in _GENERIC_EVIDENCE]
    return len(vals) > 0


def gate(worklist, verdicts):
    violations = []
    by_unit = {v.get("unit_id"): v for v in verdicts}
    for u in worklist["units"]:
        v = by_unit.get(u["id"])
        if v is None:
            violations.append(f"unit {u['id']} has no verdict")
        elif not pass_is_earned(v):
            violations.append(f"unit {u['id']} has an unearned PASS (no concrete evidence)")
    return violations


# --- seat triggers -----------------------------------------------------------
# The unit pool, the ripple pass, and the coverage gate are unconditional. The verification
# and security seats are risk-triggered: they run when the diff or the collected verdicts
# carry one of the objective signals below, and are otherwise skipped with the counts that
# justified the skip, so a skip is auditable instead of a judgment call.

SECURITY_TRIGGER_TAGS = ("auth", "money", "persistence", "migration", "serialization",
                         "parsing", "external_api", "fs_net")
# These tags select candidate rules; each rule's scope still decides applicability.
STANDARDS_TRIGGER_TAGS = ("persistence", "migration", "serialization", "external_api",
                         "auth", "concurrency", "retries", "time", "parsing")
CHALLENGER_LARGE_UNIT_LINES = 25  # one verdict covering a big hunk is where a miss costs most
OPEN_STATUSES = {"FAIL", "QUESTION"}


def _open_statuses(verdicts):
    return [v for v in verdicts if str(v.get("status", "")).upper() in OPEN_STATUSES]


def _tag_trigger(worklist, trigger_tags, seat):
    units = worklist["units"]
    hits = sorted({tag for u in units for tag in u.get("risk_tags", ())} & set(trigger_tags))
    tagged = [u["id"] for u in units if set(u.get("risk_tags", ())) & set(trigger_tags)]
    if hits:
        return {"run": True, "reasons": hits,
                "evidence": f"{len(tagged)}/{len(units)} units carry risk tag(s) "
                            f"{', '.join(hits)}"}
    return {"run": False, "reasons": [],
            "evidence": f"0/{len(units)} units carry any of the {seat} risk tags "
                        f"({', '.join(trigger_tags)})"}


def security_trigger(worklist):
    return _tag_trigger(worklist, SECURITY_TRIGGER_TAGS, "security")


def standards_trigger(worklist):
    return _tag_trigger(worklist, STANDARDS_TRIGGER_TAGS, "standards")


def challenger_trigger(worklist, verdicts=(), ripple=(), redundancies=0):
    units = worklist["units"]
    counts = {
        "open_verdicts": len(_open_statuses(verdicts)) + len(_open_statuses(ripple)),
        "supported_redundancies": max(0, int(redundancies)),
        "signature_changes": len(changed_signature_symbols(worklist)),
        "large_units": sum(1 for u in units
                           if u.get("size", 0) >= CHALLENGER_LARGE_UNIT_LINES),
    }
    reasons = [f"{name}={value}" for name, value in counts.items() if value]
    if reasons:
        return {"run": True, "reasons": reasons, "counts": counts,
                "evidence": "; ".join(reasons)}
    return {"run": False, "reasons": [], "counts": counts,
            "evidence": f"0 FAIL/QUESTION verdicts, 0 supported redundancies, "
                        f"0 signature-change units, 0 units of "
                        f">={CHALLENGER_LARGE_UNIT_LINES} changed lines "
                        f"across {len(units)} units"}


def seat_triggers(worklist, verdicts=(), ripple=(), redundancies=0):
    return {
        "security": security_trigger(worklist),
        "standards": standards_trigger(worklist),
        "challenger": challenger_trigger(worklist, verdicts, ripple, redundancies),
    }


def _read_source(path):
    if path == "-":
        import sys
        return sys.stdin.read()
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def main(argv=None):
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="review-pr unit enumerator + gate")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_en = sub.add_parser("enumerate", help="diff -> worklist JSON")
    p_en.add_argument("diff", help="path to diff file, or - for stdin")
    p_ca = sub.add_parser("callers", help="worklist -> callers of signature-changed symbols")
    p_ca.add_argument("worklist", help="path to worklist JSON, or - for stdin")
    p_ca.add_argument("--repo-root", default=".")
    p_g = sub.add_parser("gate", help="fail if any unit lacks a verdict or has an unearned PASS")
    p_g.add_argument("worklist", help="path to worklist JSON, or - for stdin")
    p_g.add_argument("verdicts", help="path to verdicts JSON")
    p_t = sub.add_parser("triggers", help="worklist (+verdicts) -> risk-triggered seat decisions")
    p_t.add_argument("worklist", help="path to worklist JSON, or - for stdin")
    p_t.add_argument("--verdicts", help="path to verdicts JSON (omit before Phase 2)")
    p_t.add_argument("--ripple", help="path to ripple-verdicts JSON (omit before Phase 2b)")
    p_t.add_argument("--redundancies", type=int, default=0,
                     help="supported redundancy findings from the ownership audit")
    args = parser.parse_args(argv)
    if args.cmd == "enumerate":
        wl = build_worklist(_read_source(args.diff))
        print(json.dumps(wl, indent=2))
        return 0
    if args.cmd == "callers":
        wl = json.loads(_read_source(args.worklist))
        print(json.dumps(caller_reports(wl, args.repo_root), indent=2))
        return 0
    if args.cmd == "gate":
        wl = json.loads(_read_source(args.worklist))
        verdicts = json.loads(_read_source(args.verdicts))
        violations = gate(wl, verdicts)
        print(json.dumps({"violations": violations}, indent=2))
        return 1 if violations else 0
    if args.cmd == "triggers":
        wl = json.loads(_read_source(args.worklist))
        verdicts = json.loads(_read_source(args.verdicts)) if args.verdicts else []
        ripple = json.loads(_read_source(args.ripple)) if args.ripple else []
        print(json.dumps(
            seat_triggers(wl, verdicts, ripple, args.redundancies), indent=2))
        return 0
    return 2


if __name__ == "__main__":
    import sys
    sys.exit(main())
