#!/usr/bin/env python3
"""Deterministic parts of a review-check run. The script owns the units and the verdict; the reviewer
only writes rows into 02-review.md.

Every rule in references/lens*.md and in the repo's rules file has an ID, a `Files:` glob, and an
optional `Applies:` regex. `start` writes checklist.json: for each unit, the ID of every rule whose
glob matches the unit's file and whose regex matches the unit's code, plus `REF` when a symbol the
unit defines or removes has references elsewhere. `verdict` refuses until each ID has a result.

  start <local|base..head> [--patch FILE]   make <repo>/tmp/review-check/<run>/ with 01-units.md
  verdict <run>                              gate the rows of 02-review*.md and write 03-verdict.md

`--patch` reviews that patch instead of the whole range, for example review-walk's diff since view.
`verdict` exits 1 when the gate fails, so a caller cannot read an APPROVE that no one earned.
"""
import fnmatch, hashlib, json, re, subprocess, sys
from pathlib import Path

KINDS = ("pass", "fix", "ask", "note", "n/a")
RULE = re.compile(r"^- `([A-Z][A-Z0-9-]*-\d+)` (.*)$")
REFS_CAP = 20  # a symbol with more references than this gets the first 20; the seat searches the rest
FUNC_KINDS = {"function", "method", "subroutine", "func", "procedure"}
PLAIN = ("--no-ext-diff", "--no-color", "--src-prefix=a/", "--dst-prefix=b/")  # user config may change these
GENERIC = {"", "n/a", "na", "none", "ok", "okay", "fine", "good", "looks fine", "looks good", "checked",
           "verified", "tested", "no issues", "lgtm", "-"}


def git(*args, check=True):
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit(f"git {' '.join(args[:3])}: {r.stderr.strip()}")
    return r.stdout


def repo_name():
    return Path(git("rev-parse", "--git-common-dir").strip()).resolve().parent.name


def home():
    root = Path(git("rev-parse", "--show-toplevel").strip())
    exclude = Path(git("rev-parse", "--git-common-dir").strip()).resolve() / "info" / "exclude"
    lines = exclude.read_text().splitlines() if exclude.exists() else []
    if "/tmp/" not in lines:  # local to this clone, so the team never sees it
        exclude.parent.mkdir(parents=True, exist_ok=True)
        exclude.write_text("\n".join(lines + ["/tmp/"]) + "\n")
    return root / "tmp" / "review-check"


def expand(pattern):
    """`**/*.{ts,py}` -> ["**/*.ts", "**/*.py"]."""
    m = re.search(r"\{([^{}]*)\}", pattern)
    if not m:
        return [pattern]
    return [x for alt in m.group(1).split(",") for x in expand(pattern[:m.start()] + alt + pattern[m.end():])]


def glob_match(path, globs):
    for g in (x for pattern in globs for x in expand(pattern)):
        # fnmatch's * also crosses "/", so "**/" only needs to allow a file at the repo root
        if fnmatch.fnmatch(path, g) or (g.startswith("**/") and fnmatch.fnmatch(path, g[3:])):
            return True
    return False


def globs_of(text):
    return [g.strip() for g in re.split(r",(?![^{]*\})", text)]  # a comma inside {a,b} is not a separator


def load_rules(files):
    """[{id, files, applies, source}] from every rule line; a file's `Files:` header is the default."""
    rules = []
    for f in files:
        default = ["**/*"]
        for line in f.read_text().splitlines():
            head = re.match(r"^Files: `([^`]+)`", line)
            if head:
                default = globs_of(head.group(1))
            m = RULE.match(line)
            if not m:
                continue
            globs = re.search(r"Files: `([^`]+)`", m.group(2))
            applies = re.search(r"Applies: `([^`]+)`", m.group(2))
            rules.append({"id": m.group(1), "source": f.name,
                          "files": globs_of(globs.group(1)) if globs else default,
                          "applies": re.compile(applies.group(1)) if applies else None})
    return rules


# Names other files can reach: exported bindings, top-level functions and types, and class members with
# a modifier. A plain `const x` inside a function is local, so it gets no REF.
DEFINES = re.compile(r"(?:\bexport\s+(?:default\s+)?(?:async\s+)?(?:const|let|var|function|class|type|interface|enum)\s+"
                     r"|^(?:async\s+)?(?:def|function|func|class|struct|enum|protocol|interface|type)\s+"
                     r"|^\s+(?:def|func)\s+"
                     r"|^\s*(?:(?:public|private|protected|static|async|override|readonly)\s+)+)([A-Za-z_]\w{2,})")


FAMILY = {ext: fam for fam, exts in {
    "js": "ts tsx js jsx mjs cjs mts cts vue svelte", "py": "py pyi", "go": "go", "swift": "swift m h",
    "rs": "rs", "jvm": "java kt", "rb": "rb", "sql": "sql"}.items() for ext in exts.split()}


def family(path):
    return FAMILY.get(Path(path).suffix.lstrip("."), Path(path).suffix)


def references(symbols, head, own, lang):
    """{symbol: ["file:line", ...]} for each symbol that another place in the tree names."""
    out = {}
    for sym in sorted(symbols):
        found = git("grep", "-n", "-w", "-I", "-e", sym, *([head] if head else []), check=False).splitlines()
        hits = [":".join(h.removeprefix(f"{head}:").split(":")[:2]) for h in found]
        # the same name in another language is another symbol, for example Python `encode` and JS `.encode`
        hits = [h for h in hits if h not in own and family(h.split(":")[0]) == lang]
        if hits:
            out[sym] = hits[:REFS_CAP]
    return out


def revision(path):
    return hashlib.sha1("".join(path.read_text().splitlines(True)[1:]).encode()).hexdigest()[:12]


def local_patch():
    patch = git("diff", *PLAIN, "HEAD")
    for path in git("ls-files", "--others", "--exclude-standard", "-z").split("\0"):
        if path:  # exit code 1 means "files differ", which is the normal case here
            patch += git("diff", *PLAIN, "--no-index", "--", "/dev/null", path, check=False)
    return patch


def parse_diff(patch):
    """{path: {"new": {line: text}, "added": set, "removed": [text], "hunks": [(start, end, removes)]}}.
    A deleted file is keyed by its old path and has no new side."""
    files, cur, old, n = {}, None, None, 0
    for line in patch.splitlines():
        if line.startswith("--- "):
            old = line[4:].split("\t")[0].removeprefix("a/")
        elif line.startswith("+++ "):
            p = line[4:].split("\t")[0]
            cur = old if p == "/dev/null" else p.removeprefix("b/")
            files[cur] = {"new": {}, "added": set(), "removed": [], "hunks": [], "deleted": p == "/dev/null"}
        elif line.startswith("@@") and cur:
            m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
            n = int(m.group(1))
            files[cur]["hunks"].append([n, n + max(int(m.group(2) or 1), 1) - 1, False])
        elif cur and files[cur]["hunks"] and line[:1] in ("+", " "):
            files[cur]["new"][n] = line[1:]
            if line[0] == "+":
                files[cur]["added"].add(n)
            n += 1
        elif cur and files[cur]["hunks"] and line[:1] == "-":
            files[cur]["removed"].append(line[1:])
            files[cur]["hunks"][-1][2] = True
    return files


def functions(path):
    """(name, start, end) from universal-ctags, or [] when it cannot read the file's language."""
    try:
        out = subprocess.run(["ctags", "--output-format=json", "--fields=+ne", "-f", "-", str(path)],
                             capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    tags = [json.loads(l) for l in out.splitlines() if l.startswith("{")]
    return [(t["name"], t["line"], t.get("end", t["line"])) for t in tags
            if t.get("_type") == "tag" and t.get("kind") in FUNC_KINDS and t.get("line")]


def units_of(path, info, source):
    """Every added line lands in exactly one unit: the innermost function around it, else its hunk.
    A hunk that only removes lines, and a deleted file, are units too, because removed code can
    drop a guarantee."""
    if info["deleted"]:
        return [{"file": path, "symbol": "deleted file", "range": [0, 0], "lines": []}]
    units, left = [], set(info["added"])
    for name, s, e in sorted(functions(source), key=lambda f: f[2] - f[1]):
        lines = sorted(l for l in left if s <= l <= e)
        if lines:
            units.append({"file": path, "symbol": name, "range": [s, e], "lines": lines})
            left -= set(lines)
    for s, e, removes in info["hunks"]:
        lines = sorted(l for l in left if s <= l <= e)
        if lines or (removes and not any(s <= l <= e for l in info["added"])):
            units.append({"file": path, "symbol": f"hunk {s}-{e}", "range": [s, e], "lines": lines})
            left -= set(lines)
    return units


def start(target, *opts):
    if target == "local":
        prefix, base, head = "local", git("rev-parse", "HEAD").strip(), None
        patch = local_patch()
    elif ".." in target:
        base, head = (git("rev-parse", "--verify", f"{p}^{{commit}}").strip() for p in target.split("..", 1))
        prefix = f"range-{base[:7]}-{head[:7]}"
        patch = git("diff", *PLAIN, base, head)
    else:
        raise SystemExit("target is `local` or `<base>..<head>`")
    if opts[:1] == ("--patch",):
        patch = Path(opts[1]).read_text()

    d = home()
    n = len(list(d.glob(f"{prefix}-[0-9][0-9]"))) + 1
    d = d / f"{prefix}-{n:02d}"
    (d / "head").mkdir(parents=True)
    (d / "diff.patch").write_text(patch)
    units = []
    for path, info in parse_diff(patch).items():
        src = d / "head" / path  # seats read full functions here, never from a moving checkout
        if not info["deleted"]:
            src.parent.mkdir(parents=True, exist_ok=True)
            src.write_text(Path(path).read_text() if head is None else git("show", f"{head}:{path}"))
        units += units_of(path, info, src)
    if not units:
        raise SystemExit("the diff has no changed lines to review")
    for i, u in enumerate(units, 1):
        u["id"] = f"u{i}"
    (d / "units.json").write_text(json.dumps(units, indent=2) + "\n")

    rules = Path.home() / ".review-check" / "rules" / f"{repo_name()}.md"
    catalog = load_rules(sorted((Path(__file__).resolve().parent.parent / "references").glob("lens*.md"))
                         + ([rules] if rules.exists() else []))
    diff = parse_diff(patch)
    checklist = {}
    for u in units:
        info = diff[u["file"]]
        src = d / "head" / u["file"]
        body = src.read_text(errors="replace").splitlines()[max(u["range"][0] - 1, 0):u["range"][1]] if src.exists() else []
        text = "\n".join(body + info["removed"])  # removed code counts, so a rule about what was dropped still fires
        ids = [r["id"] for r in catalog
               if glob_match(u["file"], r["files"]) and (r["applies"] is None or r["applies"].search(text))]
        added = [info["new"][n] for n in u["lines"]]
        symbols = {m.group(1) for line in added + info["removed"] for m in [DEFINES.search(line)] if m}
        if not u["symbol"].startswith(("hunk ", "deleted ")):
            symbols.add(u["symbol"])
        own = {f"{u['file']}:{n}" for n in range(u["range"][0], u["range"][1] + 1)}
        refs = references(symbols, head, own, family(u["file"]))
        if refs:
            ids.append("REF")
        checklist[u["id"]] = {"rules": ids, "refs": refs}
    (d / "checklist.json").write_text(json.dumps(checklist, indent=2) + "\n")
    body = [f"Target: {target}", f"Base: {base}", f"Head: {head or 'working tree'}",
            f"Rules: {rules if rules.exists() else 'none'}", "",
            f"Catalog: {len(catalog)} rules from lens*.md and the rules file.",
            f"{len(units)} units in {len({u['file'] for u in units})} files, "
            f"{sum(len(c['rules']) for c in checklist.values())} checks. `checklist.json` lists each unit's rule IDs "
            "and the references that `REF` must check.", "",
            "| Unit | File | Symbol | Range | Added lines | Checks |", "|---|---|---|---|---|---|",
            *(f"| {u['id']} | `{u['file']}` | `{u['symbol']}` | {u['range'][0]}-{u['range'][1]} | {len(u['lines'])} "
              f"| {len(checklist[u['id']]['rules'])} |" for u in units)]
    rest = "Uses:\n" + "\n".join(body) + "\n"
    (d / "01-units.md").write_text(f"Status: done {hashlib.sha1(rest.encode()).hexdigest()[:12]}\n{rest}")
    (d / "02-review.md").write_text(
        f"Status: open\nUses: 01-units@{revision(d / '01-units.md')}\n\n"
        "| Unit | Rule | file:line | Quote | Kind | Problem | Proof |\n|---|---|---|---|---|---|---|\n")
    print(d)


def rows(d):
    out = []
    for f in sorted(d.glob("02-review*.md")):
        for line in f.read_text().splitlines():
            if re.match(r"\|\s*u\d+\s*\|", line):
                cells = [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", line)[1:-1]]
                out.append((f.name, cells))
    return out


def verdict(name):
    d = home() / name
    units = {u["id"]: u for u in json.loads((d / "units.json").read_text())}
    diff = parse_diff((d / "diff.patch").read_text())
    rules = re.search(r"^Rules: (.*)$", (d / "01-units.md").read_text(), re.M).group(1)
    checklist = json.loads((d / "checklist.json").read_text())
    problems, seen, kept, done = [], set(), [], {uid: set() for uid in units}
    for src, cells in rows(d):
        if len(cells) != 7:
            problems.append(f"{src}: a row has {len(cells)} cells, not 7: {' | '.join(cells)}")
            continue
        uid, rule, loc, quote, kind, problem, proof = cells
        quote, kind = quote.strip("`"), kind.lower()
        ids = {r.strip().strip("`") for r in rule.split(",")} - {"-", ""}
        u = units.get(uid)
        if u is None or kind not in KINDS or not quote:
            problems.append(f"{uid}: unknown unit, kind not in {'/'.join(KINDS)}, or no quote")
            continue
        if kind in ("fix", "ask", "note") and len(ids) > 1:
            problems.append(f"{uid}: a {kind} row names one rule, or `-` for a finding that no rule owns")
            continue
        path = loc.split(":")[0].strip("`")
        if kind in ("pass", "n/a"):  # a quote from the unit, or from code the diff removed in that file
            src = d / "head" / u["file"]
            head = src.read_text().splitlines() if src.exists() else []
            scope = head[max(u["range"][0] - 1, 0):u["range"][1]] + diff[u["file"]]["removed"]
            if proof.lower().strip(". ") in GENERIC:
                problems.append(f"{uid} {rule}: a {kind} needs a proof that names the case checked or why the rule cannot apply")
                continue
        else:
            scope = [*diff.get(path, {}).get("new", {}).values(), *diff.get(path, {}).get("removed", [])]
        if not any(quote in line for line in scope):
            problems.append(f"{uid}: quote not found {'in the unit' if kind in ('pass', 'n/a') else f'in the diff of {path}'}: {quote!r}")
            continue
        seen.add(uid)
        done[uid] |= ids
        if kind in ("fix", "ask", "note"):
            kept.append((uid, loc, quote, kind, f"{rule}: {problem}" if ids else problem, proof))
    problems += [f"{uid}: no row ({u['file']} {u['symbol']})" for uid, u in units.items() if uid not in seen]
    missing = {uid: [r for r in checklist[uid]["rules"] if r not in done[uid]] for uid in units}
    problems += [f"{uid}: no result for {', '.join(m)}" for uid, m in missing.items() if m]
    checks = sum(len(c["rules"]) for c in checklist.values())
    checked = checks - sum(len(m) for m in missing.values())

    count = {k: sum(1 for r in kept if r[3] == k) for k in ("fix", "ask", "note")}
    if problems:
        status, word = "blocked gate failed", "INCOMPLETE"
    else:
        status = "done"
        word = "REQUEST CHANGES" if count["fix"] else "NEEDS DISCUSSION" if count["ask"] else "APPROVE"
    line3 = (f"Verdict: {word} ({len(seen)} of {len(units)} units, {checked} of {checks} checks; {count['fix']} fix, {count['ask']} ask, "
             f"{count['note']} note; rules: {'none' if rules == 'none' else Path(rules).name})")
    uses = ", ".join(f"{f.stem}@{revision(f)}" for f in [d / "01-units.md", *sorted(d.glob("02-review*.md"))])
    body = [line3, "", *(f"- {p}" for p in problems),
            *(f"- {k} `{loc}` {problem} (proof: {proof})" for _, loc, _, k, problem, proof in kept)]
    rest = f"Uses: {uses}\n" + "\n".join(body) + "\n"
    rev = f" {hashlib.sha1(rest.encode()).hexdigest()[:12]}" if status == "done" else ""
    (d / "03-verdict.md").write_text(f"Status: {status}{rev}\n{rest}")
    print(line3, *(f"- {p}" for p in problems), sep="\n")
    return 1 if problems else 0


if __name__ == "__main__":
    commands = {"start": start, "verdict": verdict}
    if len(sys.argv) < 3 or sys.argv[1] not in commands:
        raise SystemExit(__doc__)
    sys.exit(commands[sys.argv[1]](*sys.argv[2:]))
