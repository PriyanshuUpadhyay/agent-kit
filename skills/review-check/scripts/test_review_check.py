"""Run: python3 test_review_check.py. Builds a throwaway repo and checks that the verdict is earned:
a unit with no row, a rule with no result, a made-up quote, a quote at the wrong line, or a bare "ok"
proof blocks it; a language with no ctags support still gets units; a changed function that others
call gets REF; the build gate owns the IDs the repo's lint config proves, and only for this head."""
import json, os, shutil, subprocess, sys, tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import review_check as rc


def sh(*cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout.strip()


def commit(files, msg):
    for name, text in files.items():
        if text is None:
            Path(name).unlink()
        else:
            Path(name).parent.mkdir(parents=True, exist_ok=True)
            Path(name).write_text(text)
    sh("git", "add", "-A")
    sh("git", "commit", "-qm", msg)
    return sh("git", "rev-parse", "HEAD")


def rows(run, *lines):
    (run / "02-review.md").write_text("Status: done x\nUses: 01-units@x\n\n" + "".join(l + "\n" for l in lines))


def main():
    base = commit({"pane.swift": "func resize() {\n  a()\n}\n", "gone.py": "def guard():\n    return 1\n",
                   "util.py": "def helper():\n    return 1\n", "app.py": "from util import helper\nhelper()\n"}, "base")
    head = commit({"pane.swift": "func resize() {\n  a()\n  b()\n}\n", "gone.py": None,
                   "util.py": "def helper():\n    return 2\n"}, "change")
    rc.start(f"{base}..{head}")
    run = next(Path("tmp/review-check").iterdir())
    units = {u["file"]: u for u in json.loads((run / "units.json").read_text())}
    checklist = json.loads((run / "checklist.json").read_text())
    assert set(units) == {"pane.swift", "gone.py", "util.py"}, units  # swift has no ctags parser here
    assert units["gone.py"]["symbol"] == "deleted file"
    s, g, h = units["pane.swift"]["id"], units["gone.py"]["id"], units["util.py"]["id"]
    assert "REF" in checklist[h]["rules"] and "app.py:1" in checklist[h]["refs"]["helper"], checklist[h]

    def all_rules(uid, quote):  # one n/a row may cover many rules with one reason
        ids = ", ".join(checklist[uid]["rules"]) or "-"
        return f"| {uid} | {ids} | x | `{quote}` | n/a | | the test code has no case these rules name |"

    rows(run, f"| {s} | - | pane.swift:3 | `b()` | pass | | b() runs after a(), no shared state |",
         f"| {g} | - | gone.py:1 | `def guard` | pass | | no caller imports guard |",
         f"| {h} | - | util.py:2 | `return 2` | pass | | app.py ignores the return value |")
    assert rc.verdict(run.name) == (1 if any(c["rules"] for c in checklist.values()) else 0), "rules without a result"

    rows(run, all_rules(s, "b()"), all_rules(g, "def guard"), all_rules(h, "return 2"),
         f"| {s} | - | pane.swift:3 | `b()` | pass | | ok |")
    assert rc.verdict(run.name) == 1, "a bare ok is not a proof"

    rows(run, all_rules(s, "b()"), all_rules(g, "def guard"), all_rules(h, "return 2"),
         f"| {s} | - | pane.swift:3 | `c()` | fix | made up | x |")
    assert rc.verdict(run.name) == 1, "a quote that is not in the diff"

    rows(run, all_rules(s, "b()"), all_rules(g, "def guard"), all_rules(h, "return 2"),
         f"| {h} | REF | util.py:1 | `return 2` | fix | helper now returns 2 | app.py:2 expects 1 |")
    assert rc.verdict(run.name) == 1, "the quote is in the diff, but not at the line the row names"

    rows(run, all_rules(s, "b()"), all_rules(g, "def guard"), all_rules(h, "return 2"),
         f"| {h} | REF | util.py:2 | `return 2` | ask | helper now returns 2 | ok |")
    assert rc.verdict(run.name) == 1, "a bare ok is not a proof on an ask row either"

    rows(run, all_rules(s, "b()"), all_rules(g, "def guard"), all_rules(h, "return 2"),
         f"| {h} | REF | util.py:2 | `return 2` | fix | helper now returns 2 | app.py:2 expects 1 |")
    assert rc.verdict(run.name) == 0
    lines = (run / "03-verdict.md").read_text().splitlines()
    assert lines[0].startswith("Status: done ") and lines[2].startswith("Verdict: REQUEST CHANGES (3 of 3 units"), lines
    assert lines[2].endswith("build: none)"), lines[2]


def test_build_gate():
    """The repo's lint config decides which rule IDs the build owns, and the verdict counts them only from
    build.json for this head."""
    rules = Path.home() / ".review-check" / "rules" / f"{Path.cwd().name}.md"
    rules.parent.mkdir(parents=True, exist_ok=True)
    rules.write_text("Files: `**/*.ts`\n\nCI: `Lint` runs `true`; config `.oxlintrc.json`\n")
    config = {"ignorePatterns": ["vendor"], "rules": {
        "@typescript-eslint/no-floating-promises": "error", "@typescript-eslint/await-thenable": "error",
        "no-fallthrough": ["error", {"commentPattern": "skip"}]}}  # options: the fixtures do not speak for it
    base = commit({".oxlintrc.json": json.dumps(config), "a.ts": "const m = new Map();\nexport const v = m.get(1)!;\n",
                   "vendor/b.ts": "export {};\n"}, "lint base")
    head = commit({"a.ts": "const m = new Map();\nexport const v = m.get(1)!;\nexport async function f() { await g(); }\n",
                   "vendor/b.ts": "export async function f() { await g(); }\n"}, "lint change")
    rc.start(f"{base}..{head}")
    run = Path("tmp/review-check") / f"range-{base[:7]}-{head[:7]}-01"
    units = {u["file"]: u["id"] for u in json.loads((run / "units.json").read_text())}
    checklist = json.loads((run / "checklist.json").read_text())
    a, v = checklist[units["a.ts"]], checklist[units["vendor/b.ts"]]
    assert set(a["tool"]) == {"TS-1", "TS-24"} and not {"TS-1", "TS-24"} & set(a["rules"]), a
    assert "TS-6" not in a["rules"], "Scope: added, and the `!` is on a line the change did not add"
    assert not v["tool"] and "TS-24" in v["rules"], "an ignored path keeps its IDs with the seats"

    def answers(*extra):
        rows(run, *(f"| {uid} | {', '.join(c['rules']) or '-'} | x | `f()` | n/a | | the test code has no such case |"
                    for uid, c in checklist.items()), *extra)

    answers()
    assert rc.verdict(run.name) == 1, "no build.json"
    (run / "build.json").write_text(json.dumps({"head": base, "digest": None, "source": "check-run", "name": "Lint",
                                                "conclusion": "success", "tail": []}))
    assert rc.verdict(run.name) == 1, "a build result for another head"
    (run / "build.json").write_text(json.dumps({"head": head, "digest": None, "source": "check-run", "name": "Lint",
                                                "conclusion": "success", "tail": []}))
    answers(f"| {units['a.ts']} | TS-24 | a.ts:3 | `await g()` | pass | | g returns a promise |")
    assert rc.verdict(run.name) == 1, "a seat row for an ID the build owns"
    answers()
    assert rc.verdict(run.name) == 0
    assert (run / "03-verdict.md").read_text().splitlines()[2].startswith("Verdict: APPROVE"), "build pass counts tool IDs"
    Path("a.ts").write_text("dirty\n")
    try:
        rc.build(run.name, "--run")
        raise AssertionError("--run on a dirty tree")
    except SystemExit as e:
        assert "clean checkout" in str(e), e
    sh("git", "checkout", "--", "a.ts")
    rc.build(run.name, "--run")  # the CI command is `true`
    assert json.loads((run / "build.json").read_text())["conclusion"] == "success"
    (run / "build.json").write_text(json.dumps({"head": head, "digest": None, "source": "command", "name": "true",
                                                "conclusion": "failure", "tail": ["a.ts(3,30): error TS2304"]}))
    assert rc.verdict(run.name) == 0
    line3 = (run / "03-verdict.md").read_text().splitlines()[2]
    assert line3.startswith("Verdict: REQUEST CHANGES") and line3.endswith("build: fail)"), line3


def test_answers():
    """Only a whole new line at the ask's location lets an answer close it."""
    previous = Path.cwd()
    with tempfile.TemporaryDirectory() as d:
        try:
            os.chdir(d)
            sh("git", "init", "-qb", "main")
            sh("git", "config", "user.email", "t@t")
            sh("git", "config", "user.name", "t")
            base = commit({"util.py": "def helper():\n    return 1\n"}, "answer base")
            head = commit({"util.py": "def helper():\n    return 2\n"}, "answer change")
            rc.start(f"{base}..{head}")
            run = Path("tmp/review-check") / f"range-{base[:7]}-{head[:7]}-01"
            assert json.loads((run / "target.json").read_text())["patch"] is False

            def ask(run, quote):
                checklist = json.loads((run / "checklist.json").read_text())
                uid, checks = next(iter(checklist.items()))
                rows(run, f"| {uid} | {', '.join(checks['rules']) or '-'} | x | `{quote}` | n/a | | "
                     "the test code has no case these rules name |",
                     f"| {uid} | - | util.py:2 | `{quote}` | ask | may change a caller | caller expects 1 |")

            ask(run, "return 2")
            answer = "- util.py `return 2`: user approved the return value in the contract\n"
            (run / "answers.md").write_text(answer)
            assert rc.verdict(run.name) == 0
            verdict = (run / "03-verdict.md").read_text()
            assert verdict.splitlines()[2].startswith("Verdict: APPROVE"), verdict
            assert "0 fix, 0 ask, 0 note, 1 answered" in verdict, verdict
            assert "Answered: util.py `return 2` closes 1 asks" in verdict, verdict
            assert "- answered `util.py:2` may change a caller (answer: user approved" in verdict, verdict
            assert f"answers@{rc.revision(run / 'answers.md')}" in verdict.splitlines()[1], verdict
            approved_uses = verdict.splitlines()[1]

            review = run / "02-review.md"
            escaped_problem = "\x1b[31mmay change a caller"
            review.write_text(review.read_text().replace("may change a caller", escaped_problem))
            output = StringIO()
            with redirect_stdout(output):
                assert rc.verdict(run.name) == 0
            assert "\x1b" not in output.getvalue(), "terminal output must remove the ESC byte from a row"
            assert "[31mmay change a caller" in output.getvalue()
            assert escaped_problem in (run / "03-verdict.md").read_text(), "the verdict file must keep the exact row text"
            ask(run, "return 2")

            (run / "answers.md").write_text("- util.py `return 2`: user approved `helper`: returns 2\n")
            assert rc.verdict(run.name) == 0
            verdict = (run / "03-verdict.md").read_text()
            assert verdict.splitlines()[2].startswith("Verdict: APPROVE"), "answer code followed by a colon must close the ask"
            assert "Answered: util.py `return 2` closes 1 asks" in verdict, verdict

            unicode_answer = "- util.py `return 2`: user approved the value — 合意\n"
            (run / "answers.md").write_text(unicode_answer, encoding="utf-8")
            read_text = Path.read_text

            def ascii_default(path, *args, **kwargs):
                kwargs.setdefault("encoding", "ascii")
                return read_text(path, *args, **kwargs)

            with patch.object(Path, "read_text", ascii_default):
                assert rc.answers(run / "answers.md") == [("util.py", "return 2", "user approved the value — 合意")]
                assert rc.revision(run / "answers.md") == rc.hashlib.sha1(unicode_answer.encode("utf-8")).hexdigest()[:12]

            for text in ("ok", "fix: ok", "Fix: ok", "FIX: ok", "fix:ok", "fix:", "FIX:   ", " Fix: ok. "):
                (run / "answers.md").write_text(f"- util.py `return 2`: {text}\n")
                assert rc.verdict(run.name) == 1, "a bare ok is not an answer, even with fix:"
                verdict = (run / "03-verdict.md").read_text()
                assert "an answer needs" in verdict and "INCOMPLETE" in verdict, verdict
                assert approved_uses != verdict.splitlines()[1], "an edit to the first answer line changes Uses"

            for text in ("- util.py `return`: user approved this value\n",
                         "- other.py `return 2`: user approved this value\n"):
                (run / "answers.md").write_text(text)
                assert rc.verdict(run.name) == 0
                verdict = (run / "03-verdict.md").read_text()
                assert "NEEDS DISCUSSION" in verdict and "closes 0 asks" in verdict, verdict
            ask(run, "return 1")
            (run / "answers.md").write_text("- util.py `return 1`: user approved the old value\n")
            assert rc.verdict(run.name) == 0
            verdict = (run / "03-verdict.md").read_text()
            assert "NEEDS DISCUSSION" in verdict and "closes 0 asks" in verdict, "removed lines cannot close asks"
            ask(run, "return 2")
            with (run / "02-review.md").open("a") as f:
                f.write("| u1 | - | util.py:2 | `return 2` | ask | another caller | second caller expects 1 |\n")
            (run / "answers.md").write_text(answer)
            assert rc.verdict(run.name) == 0
            verdict = (run / "03-verdict.md").read_text()
            assert "2 answered" in verdict and "closes 2 asks" in verdict, verdict
            ask(run, "return 2")
            (run / "answers.md").write_text("- util.py `return 2`: fix: test_helper fails at " + head[:7] + "\n")
            assert rc.verdict(run.name) == 0
            verdict = (run / "03-verdict.md").read_text()
            assert verdict.splitlines()[2].startswith("Verdict: REQUEST CHANGES"), verdict
            assert f"- fix `util.py:2` fix: test_helper fails at {head[:7]} (proof: caller expects 1)" in verdict, verdict
            for text in (f"Fix:test_helper fails at {head[:7]}", f"FIX: test_helper fails at {head[:7]}"):
                (run / "answers.md").write_text(answer + f"- util.py `return 2`: {text}\n")
                assert rc.verdict(run.name) == 0
                verdict = (run / "03-verdict.md").read_text()
                assert verdict.splitlines()[2].startswith("Verdict: REQUEST CHANGES"), verdict
                assert f"- fix `util.py:2` {text} (proof: caller expects 1)" in verdict, verdict

            (run / "answers.md").write_text(answer)
            assert rc.verdict(run.name) == 0
            rc.start(f"{base}..{head}")
            rerun = Path("tmp/review-check") / f"range-{base[:7]}-{head[:7]}-02"
            assert (rerun / "answers-before.md").read_text() == answer
            ask(rerun, "return 2")
            assert rc.verdict(rerun.name) == 0
            verdict = (rerun / "03-verdict.md").read_text()
            assert verdict.splitlines()[2].startswith("Verdict: NEEDS DISCUSSION"), verdict
            assert "History: util.py `return 2`: user approved" in verdict, verdict
            changed = commit({"util.py": "def helper():\n    return 3\n"}, "answer line changed")
            target_file = rerun / "target.json"
            metadata = json.loads(target_file.read_text())
            metadata["target"] += " — 合意"
            target_file.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
            (rerun / "03-verdict.md").write_text((rerun / "03-verdict.md").read_text() + "— 合意\n", encoding="utf-8")
            with patch.object(Path, "read_text", ascii_default):
                try:
                    rc.start(f"{head}..{changed}")
                    raise AssertionError("UTF-8 predecessor files must still block an open ask")
                except SystemExit as e:
                    assert rerun.name in str(e), e
            Path("util.py").write_text("def helper():\n    return 4\n")
            folders = set(Path("tmp/review-check").iterdir())
            result = rerun / "03-verdict.md"
            open_verdict = result.read_text()
            for prior_verdict in (None, "Status: blocked gate failed\nUses:\nVerdict: INCOMPLETE\n", open_verdict):
                if prior_verdict is None:
                    result.unlink()
                else:
                    result.write_text(prior_verdict)
                for target in (f"{head}..{changed}", "local"):
                    try:
                        rc.start(target)
                        raise AssertionError("a new range above an unfinished review must be refused")
                    except SystemExit as e:
                        assert rerun.name in str(e) and "answers.md" in str(e) and f"verdict {rerun.name}" in str(e), e
                    assert set(Path("tmp/review-check").iterdir()) == folders, "a refused start creates no folder"
            patch_file = Path("tmp/part.patch")
            patch_file.write_text(sh("git", "diff", *rc.PLAIN, head, changed) + "\n")
            rc.start(f"{head}..{changed}", "--patch", str(patch_file))
            partial = Path("tmp/review-check") / f"range-{head[:7]}-{changed[:7]}-01"
            assert json.loads((partial / "target.json").read_text())["patch"] is True
            assert not (partial / "answers-before.md").exists(), "--patch bypasses guard and carry-forward"
            ask(partial, "return 3")
            assert rc.verdict(partial.name) == 0
            newer = partial.stat().st_mtime + 10
            os.utime(partial, (newer, newer))
            latest_answer = "- util.py `return 2`: user approved the value in an earlier answer\n"
            (rerun / "answers.md").write_text(latest_answer)
            assert rc.verdict(rerun.name) == 0
            rc.start(f"{head}..{changed}")
            new_run = Path("tmp/review-check") / f"range-{head[:7]}-{changed[:7]}-02"
            assert (new_run / "answers-before.md").read_text() == latest_answer
            ask(new_run, "return 3")
            (new_run / "answers.md").write_text(answer)
            assert rc.verdict(new_run.name) == 0
            verdict = (new_run / "03-verdict.md").read_text()
            assert verdict.splitlines()[2].startswith("Verdict: NEEDS DISCUSSION"), verdict
            assert "Answered: util.py `return 2` closes 0 asks" in verdict, verdict
            assert "History:" not in verdict, verdict
            (rerun / "answers.md").unlink()
            (rerun / "answers.md").write_text(latest_answer)
            newer = new_run.stat().st_mtime + 10
            os.utime(rerun, (newer, newer))
            assert rerun.stat().st_mtime > new_run.stat().st_mtime
            later = commit({"util.py": "def helper():\n    return 4\n"}, "after open patch ask")
            folders = set(Path("tmp/review-check").iterdir())
            try:
                rc.start(f"{changed}..{later}")
                raise AssertionError("the descendant run with an open ask must block a new range")
            except SystemExit as e:
                assert new_run.name in str(e), "the guard must choose the descendant run despite the older run's mtime"
            assert set(Path("tmp/review-check").iterdir()) == folders
            (new_run / "answers.md").write_text("- util.py `return 3`: user approved the value in the contract\n")
            assert rc.verdict(new_run.name) == 0
            rc.start(f"{changed}..{later}")
            after_patch = Path("tmp/review-check") / f"range-{changed[:7]}-{later[:7]}-01"
            assert (after_patch / "answers-before.md").read_text() == (new_run / "answers.md").read_text()
            ask(after_patch, "return 4")
            assert rc.verdict(after_patch.name) == 0
            rc.start(f"{changed}..{later}")
            same_head = Path("tmp/review-check") / f"range-{changed[:7]}-{later[:7]}-02"
            ask(same_head, "return 4")
            assert rc.verdict(same_head.name) == 0
            assert "0 fix, 1 ask" in (same_head / "03-verdict.md").read_text()
            Path("util.py").write_text("def helper():\n    return 5\n")
            folders = set(Path("tmp/review-check").iterdir())
            try:
                rc.start("local")
                raise AssertionError("local must refuse an open ask at the same head")
            except SystemExit as e:
                assert same_head.name in str(e) and "answers.md" in str(e), e
            assert set(Path("tmp/review-check").iterdir()) == folders
            same_head_answer = "- util.py `return 4`: user approved the value in the contract\n"
            (same_head / "answers.md").write_text(same_head_answer)
            assert rc.verdict(same_head.name) == 0
            assert "Verdict: APPROVE" in (same_head / "03-verdict.md").read_text()
            rc.start("local")
            local = Path("tmp/review-check/local-01")
            assert (local / "answers-before.md").read_text() == same_head_answer
        finally:
            os.chdir(previous)


def test_catalog():
    """Rule IDs are unique, every regex compiles, and every `Check:` has bad, good, and exception fixtures."""
    catalog = rc.load_rules(sorted((HERE.parent / "references").glob("lens*.md")))
    ids = [r["id"] for r in catalog]
    assert len(ids) == len(set(ids)), sorted(i for i in ids if ids.count(i) > 1)
    for r in catalog:
        assert r["scope"] in (None, "added"), r["id"]
        for c in r["check"]:
            tool, _, name = c.partition(":")
            fixtures = HERE.parent / "fixtures" / tool / name
            assert tool == "oxlint" and all(list(fixtures.glob(f"{k}.*")) for k in ("bad", "good", "exception")), c


def test_fixtures():
    """Each `Check:` rule hits every `// expect` line of bad.* and nothing in good.* or exception.*, with the
    oxlint on PATH (for a repo's own version: PATH=<repo>/node_modules/.bin:$PATH)."""
    if not shutil.which("oxlint"):
        print("fixtures skipped: oxlint is not on PATH")
        return
    root = HERE.parent / "fixtures" / "oxlint"
    for r in rc.load_rules(sorted((HERE.parent / "references").glob("lens*.md"))):
        for c in r["check"]:
            rule = c.partition(":")[2]
            for f in sorted((root / rule).iterdir()):
                out = subprocess.run(["oxlint", "--type-aware", "-A", "all", "-D", rule, "-f", "json", str(f)],
                                     cwd=root, capture_output=True, text=True).stdout
                hits = {d["labels"][0]["span"]["line"] for d in json.loads(out)["diagnostics"]}
                want = {i for i, l in enumerate(f.read_text().splitlines(), 1) if "// expect" in l}
                assert hits == want, (r["id"], f.name, hits, want)


if __name__ == "__main__":
    test_catalog()
    test_fixtures()
    with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as home:
        os.chdir(d)
        os.environ["HOME"] = home  # the repo rules file is read from ~/.review-check
        sh("git", "init", "-qb", "main")
        sh("git", "config", "user.email", "t@t")
        sh("git", "config", "user.name", "t")
        main()
        test_build_gate()
        test_answers()
    print("ok")
