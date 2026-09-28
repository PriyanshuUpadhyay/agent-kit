"""Stdlib test harness for enumerate_units (no pytest dependency).

Run: python3 test_enumerate_units.py
"""
import sys
import traceback
from contextlib import contextmanager


@contextmanager
def raises(exc):
    try:
        yield
    except exc:
        return
    except Exception as e:  # noqa: BLE001
        raise AssertionError(f"expected {exc.__name__}, got {type(e).__name__}: {e}")
    raise AssertionError(f"expected {exc.__name__}, nothing raised")


# ---------------------------------------------------------------------------
# Task 1 — diff parsing
# ---------------------------------------------------------------------------
from enumerate_units import parse_diff

DIFF = """diff --git a/src/pay.py b/src/pay.py
--- a/src/pay.py
+++ b/src/pay.py
@@ -10,3 +10,5 @@ def refund(x):
 context_line
-old_removed
+new_a
+new_b
 trailing
@@ -40,0 +42,1 @@
+added_later
"""


def test_parse_diff_collects_added_newside_lines():
    files = parse_diff(DIFF)
    assert set(files) == {"src/pay.py"}
    f = files["src/pay.py"]
    # added lines: 11,12 (after context at 10) and 42
    assert f["changed"] == {11, 12, 42}
    assert (10, 14) in f["hunks"] and (42, 42) in f["hunks"]
    assert f["removed"] == 1
    assert "new_a" in f["text"] and "added_later" in f["text"]


def test_parse_diff_strips_mnemonic_prefixes():
    # `git diff` with diff.mnemonicPrefix=true emits i/ w/ (not a/ b/); the path must
    # still normalize to src/pay.py so ctags can find the file (else units silently
    # degrade from function-level to hunk-level).
    mnemonic = DIFF.replace("a/src/pay.py", "i/src/pay.py").replace("b/src/pay.py", "w/src/pay.py")
    files = parse_diff(mnemonic)
    assert set(files) == {"src/pay.py"}


# ---------------------------------------------------------------------------
# Task 2 — ctags extraction + changed-line mapping
# ---------------------------------------------------------------------------
from enumerate_units import ctags_symbols, map_file_units

FAKE_CTAGS = (
    '{"_type":"tag","name":"refund","kind":"function","line":10,"end":20}\n'
    '{"_type":"tag","name":"helper","kind":"function","line":30,"end":35}\n'
)


def test_ctags_symbols_parses_json_lines():
    syms = ctags_symbols("x.py", runner=lambda fp: FAKE_CTAGS)
    assert ("refund", 10, 20) in syms and ("helper", 30, 35) in syms


def test_ctags_absent_returns_none():
    def boom(fp):
        raise FileNotFoundError
    assert ctags_symbols("x.py", runner=boom) is None


def test_map_changed_lines_to_enclosing_function():
    syms = [("refund", 10, 20), ("helper", 30, 35)]
    units = map_file_units("x.py", changed={12, 13, 31}, hunks=[(12, 13), (31, 31)], symbols=syms)
    by_sym = {u["symbol"]: u for u in units}
    assert by_sym["refund"]["lines"] == [12, 13]
    assert by_sym["helper"]["lines"] == [31]
    assert all(u["kind"] == "function" for u in units)


# ---------------------------------------------------------------------------
# Task 3 — hunk fallback + reconciliation
# ---------------------------------------------------------------------------
from enumerate_units import reconcile, CoverageError


def test_uncovered_lines_become_unmapped_chunks():
    syms = [("refund", 10, 20)]
    units = map_file_units("x.py", changed={12, 50}, hunks=[(12, 12), (50, 50)], symbols=syms)
    kinds = {u["kind"] for u in units}
    assert "unmapped_chunk" in kinds
    covered = set()
    for u in units:
        covered |= set(u["lines"])
    assert covered == {12, 50}


def test_no_symbols_falls_back_entirely_to_hunks():
    units = map_file_units("x.py", changed={3, 4}, hunks=[(3, 4)], symbols=None)
    assert units and all(u["kind"] == "unmapped_chunk" for u in units)
    assert sorted(l for u in units for l in u["lines"]) == [3, 4]


def test_reconcile_passes_when_all_covered_and_raises_when_not():
    units = [{"symbol": "f", "new_range": [1, 9], "lines": [3], "kind": "function"}]
    reconcile({3}, units)  # no raise
    with raises(CoverageError):
        reconcile({3, 99}, units)


# ---------------------------------------------------------------------------
# Task 4 — risk tagging, lens gating, isolate threshold
# ---------------------------------------------------------------------------
from enumerate_units import risk_tags, lenses, should_isolate


def test_risk_tags_fire_on_sensitive_paths_and_content():
    assert "money" in risk_tags("src/billing/refund.py", "amount = charge(card)")
    assert "auth" in risk_tags("x.py", "verify jwt token for session")
    assert risk_tags("util/strings.py", "return s.strip()") == []


def test_lenses_add_concurrency_only_when_warranted():
    assert lenses("return a + b") == ["contract", "boundary", "errors"]
    assert "concurrency" in lenses("async def f(): await lock.acquire()")


def test_should_isolate_threshold():
    assert should_isolate(16, []) is True
    assert should_isolate(3, ["money"]) is True
    assert should_isolate(3, []) is False


# ---------------------------------------------------------------------------
# Task 5 — worklist assembly + enumerate CLI
# ---------------------------------------------------------------------------
import json
import os
import subprocess as _sp
import sys as _sys
from enumerate_units import build_worklist

WL_DIFF = """diff --git a/src/pay.py b/src/pay.py
--- a/src/pay.py
+++ b/src/pay.py
@@ -10,2 +10,3 @@ def refund(amount):
 ctx
+    charge(amount)
+    log(amount)
"""


def test_build_worklist_tags_and_ids():
    wl = build_worklist(WL_DIFF, symbol_lookup=lambda fp: [("refund", 10, 20)])
    assert wl["summary"]["unit_count"] == 1
    u = wl["units"][0]
    assert u["id"] == "u1" and u["file"] == "src/pay.py" and u["symbol"] == "refund"
    assert u["size"] == 2 and "money" in u["risk_tags"] and u["isolate"] is True
    assert u["lenses"][:3] == ["contract", "boundary", "errors"]


def test_enumerate_cli_reads_stdin():
    script = os.path.join(os.path.dirname(__file__), "enumerate_units.py")
    out = _sp.run([_sys.executable, script, "enumerate", "-"],
                  input=WL_DIFF, capture_output=True, text=True)
    data = json.loads(out.stdout)
    assert data["units"][0]["file"] == "src/pay.py"


# ---------------------------------------------------------------------------
# Task 6 — call-site propagation
# ---------------------------------------------------------------------------
from enumerate_units import find_callers, changed_signature_symbols


def test_find_callers_parses_git_grep():
    fake = "src/a.py:42:    refund(x)\nsrc/b.py:9:  y = refund(z)\n"
    cs = find_callers("refund", ".", grep_runner=lambda s, r: fake)
    assert cs == ["src/a.py:42", "src/b.py:9"]


def test_changed_signature_symbols_flags_def_line_changes():
    wl = {"units": [
        {"symbol": "refund", "kind": "function", "new_range": [10, 20], "lines": [10, 11]},
        {"symbol": "helper", "kind": "function", "new_range": [30, 40], "lines": [35]},
    ]}
    assert changed_signature_symbols(wl) == ["refund"]


# ---------------------------------------------------------------------------
# Regression-coverage additions: change_type, per-unit lenses + isolate, ripple pass
# ---------------------------------------------------------------------------
from enumerate_units import classify_change, changed_function_symbols, caller_reports

ADDED_DIFF = """diff --git a/src/m.py b/src/m.py
--- a/src/m.py
+++ b/src/m.py
@@ -9,0 +10,3 @@
+def brand_new(x):
+    return x + 1
+
"""

MODIFIED_DIFF = """diff --git a/src/m.py b/src/m.py
--- a/src/m.py
+++ b/src/m.py
@@ -10,4 +10,4 @@ def existing(x):
 def existing(x):
-    return x >= 1
+    return x > 1
     ctx
"""

REWRITE_DIFF = """diff --git a/src/m.py b/src/m.py
--- a/src/m.py
+++ b/src/m.py
@@ -10,3 +10,3 @@
-def existing(x):
-    return x >= 1
+def existing(x):
+    return x > 1
"""


def test_parse_diff_captures_removed_text():
    f = parse_diff(DIFF)["src/pay.py"]
    assert "old_removed" in f["removed_text"]
    assert f["line_text"][11] == "new_a"


def test_classify_change_added_vs_modified():
    # brand-new: whole range is changed lines, name absent from removed text
    assert classify_change("brand_new", (10, 12), {10, 11, 12}, "") == "added"
    # modified: a surviving context line inside the range (not every line changed)
    assert classify_change("existing", (10, 13), {11}, "") == "modified"
    # full-body rewrite: every range line is changed BUT the name appears in removed text
    assert classify_change("existing", (10, 12), {10, 11, 12},
                           "def existing(x):\n    return x >= 1\n") == "modified"


def test_worklist_change_type_and_regression_lens():
    added = build_worklist(ADDED_DIFF, symbol_lookup=lambda fp: [("brand_new", 10, 12)])["units"][0]
    assert added["change_type"] == "added"
    assert "regression" not in added["lenses"]

    mod = build_worklist(MODIFIED_DIFF, symbol_lookup=lambda fp: [("existing", 10, 13)])["units"][0]
    assert mod["change_type"] == "modified"
    assert "regression" in mod["lenses"]

    rew = build_worklist(REWRITE_DIFF, symbol_lookup=lambda fp: [("existing", 10, 12)])["units"][0]
    assert rew["change_type"] == "modified" and "regression" in rew["lenses"]


def test_every_function_unit_isolates_even_when_small():
    # tiny, no risk tag -> would be batched under the old size rule; now isolates because fn.
    u = build_worklist(ADDED_DIFF, symbol_lookup=lambda fp: [("brand_new", 10, 12)])["units"][0]
    assert u["kind"] == "function" and u["size"] <= 15 and u["isolate"] is True


def test_unmapped_chunk_still_batches_when_trivial():
    u = build_worklist(ADDED_DIFF, symbol_lookup=lambda fp: None)["units"][0]
    assert u["kind"] == "unmapped_chunk" and u["isolate"] is False


def test_changed_function_symbols_excludes_private_and_dedupes():
    wl = {"units": [
        {"symbol": "refund", "kind": "function", "change_type": "modified"},
        {"symbol": "refund", "kind": "function", "change_type": "added"},
        {"symbol": "_private", "kind": "function", "change_type": "modified"},
        {"symbol": "f@1-2", "kind": "unmapped_chunk", "change_type": "modified"},
    ]}
    assert changed_function_symbols(wl) == ["refund"]


def test_caller_reports_caps_and_reports_dropped():
    wl = {"units": [{"symbol": "refund", "kind": "function", "change_type": "modified"}]}
    fake = "".join(f"src/f{i}.py:{i}:  refund(z)\n" for i in range(25))
    reports = caller_reports(wl, ".", grep_runner=lambda s, r: fake)
    r = reports[0]
    assert r["symbol"] == "refund" and r["change_type"] == "modified"
    assert len(r["callers"]) == 20 and r["dropped"] == 5


# ---------------------------------------------------------------------------
# Task 7 — earned-PASS check + coverage gate
# ---------------------------------------------------------------------------
from enumerate_units import pass_is_earned, gate


def test_pass_requires_concrete_evidence():
    assert pass_is_earned({"unit_id": "u1", "status": "FAIL"}) is True
    assert pass_is_earned({"unit_id": "u1", "status": "PASS",
                           "evidence": {"boundary_inputs": ["amount=0"], "error_branches": []}}) is True
    assert pass_is_earned({"unit_id": "u1", "status": "PASS",
                           "evidence": {"boundary_inputs": [], "error_branches": []}}) is False
    assert pass_is_earned({"unit_id": "u1", "status": "PASS",
                           "evidence": {"boundary_inputs": ["n/a"], "error_branches": ["none"]}}) is False


def test_gate_flags_missing_verdicts_and_unearned_pass():
    wl = {"units": [{"id": "u1"}, {"id": "u2"}]}
    verdicts = [{"unit_id": "u1", "status": "PASS",
                 "evidence": {"boundary_inputs": [], "error_branches": []}}]
    violations = gate(wl, verdicts)
    assert any("u2" in v for v in violations)
    assert any("u1" in v for v in violations)
    good = [{"unit_id": "u1", "status": "PASS",
             "evidence": {"boundary_inputs": ["x=-1"], "error_branches": ["L12 raises"]}},
            {"unit_id": "u2", "status": "FAIL"}]
    assert gate(wl, good) == []


# ---------------------------------------------------------------------------
# Seat triggers — the verification and security seats are risk-triggered
# ---------------------------------------------------------------------------
from enumerate_units import (security_trigger, standards_trigger, challenger_trigger,
                             seat_triggers)

QUIET_WL = {"units": [
    {"id": "u1", "kind": "function", "symbol": "render", "new_range": [10, 20],
     "lines": [15], "size": 1, "risk_tags": []},
]}
RISKY_WL = {"units": [
    {"id": "u1", "kind": "function", "symbol": "login", "new_range": [10, 20],
     "lines": [15], "size": 1, "risk_tags": ["auth", "time"]},
]}


def test_security_seat_skips_a_diff_with_no_security_risk_tag():
    decision = security_trigger(QUIET_WL)
    assert decision["run"] is False
    assert "0/1 units carry any of the security risk tags" in decision["evidence"]
    assert "auth" in decision["evidence"]


def test_security_seat_runs_on_a_security_risk_tag():
    decision = security_trigger(RISKY_WL)
    assert decision["run"] is True and decision["reasons"] == ["auth"]
    assert "1/1 units carry risk tag(s) auth" in decision["evidence"]


def test_standards_seat_runs_on_a_persistence_tag():
    wl = {"units": [dict(RISKY_WL["units"][0], risk_tags=["persistence"])]}
    decision = standards_trigger(wl)
    assert decision["run"] is True and decision["reasons"] == ["persistence"]
    assert "1/1 units carry risk tag(s) persistence" in decision["evidence"]


def test_standards_seat_skips_a_display_only_diff_with_counted_evidence():
    decision = standards_trigger(QUIET_WL)
    assert decision["run"] is False
    assert "0/1 units carry any of the standards risk tags" in decision["evidence"]


def test_standards_selection_from_behavior_diffs():
    cases = [
        ("retry_policy.py", "return min(2 ** attempt, 30)", True),
        ("client.py", "timeout = min(remaining, configured_timeout)", True),
        ("budget.py", "return deadline - now", True),
        ("access.py", "return read_entitlement(user)", True),
        ("login.py", "return bearer_challenge()", True),
        ("counter.py", "with lock: reserve()", True),
        ("payload.py", "return json.dumps(value)", True),
        ("view.py", "return title.upper()", False),
    ]
    for path, code, expected in cases:
        diff = (f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
                f"@@ -0,0 +1 @@\n+{code}\n")
        worklist = build_worklist(diff, symbol_lookup=lambda _: None)
        decision = seat_triggers(worklist)["standards"]
        assert decision["run"] is expected, (path, decision)


def test_challenger_skips_an_all_pass_low_risk_review_with_counted_evidence():
    decision = challenger_trigger(QUIET_WL, verdicts=[{"unit_id": "u1", "status": "PASS"}])
    assert decision["run"] is False
    assert decision["counts"] == {"open_verdicts": 0, "supported_redundancies": 0,
                                  "signature_changes": 0, "large_units": 0}
    assert "0 FAIL/QUESTION verdicts" in decision["evidence"]
    assert "across 1 units" in decision["evidence"]


def test_challenger_runs_on_open_verdicts_redundancy_signature_or_size():
    assert challenger_trigger(QUIET_WL, verdicts=[{"status": "FAIL"}])["run"] is True
    assert challenger_trigger(QUIET_WL, ripple=[{"status": "question"}])["run"] is True
    assert challenger_trigger(QUIET_WL, redundancies=1)["run"] is True
    big = {"units": [dict(QUIET_WL["units"][0], size=25)]}
    assert challenger_trigger(big)["run"] is True
    sig = {"units": [dict(QUIET_WL["units"][0], lines=[10])]}
    decision = challenger_trigger(sig)
    assert decision["run"] is True and "signature_changes=1" in decision["reasons"]


def test_triggers_cli_emits_both_seat_decisions():
    script = os.path.join(os.path.dirname(__file__), "enumerate_units.py")
    out = _sp.run([_sys.executable, script, "triggers", "-"],
                  input=json.dumps(RISKY_WL), capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    data = json.loads(out.stdout)
    assert data["security"]["run"] is True
    assert data["challenger"]["run"] is False
    assert set(data) == set(seat_triggers(RISKY_WL))


# ---------------------------------------------------------------------------
def _run():
    g = globals()
    tests = sorted(n for n in g if n.startswith("test_") and callable(g[n]))
    failed = 0
    for n in tests:
        try:
            g[n]()
            print(f"PASS {n}")
        except Exception:  # noqa: BLE001
            failed += 1
            print(f"FAIL {n}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run())
