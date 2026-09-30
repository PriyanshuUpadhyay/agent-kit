"""Run: python3 test_review_check.py. Builds a throwaway repo and checks that the verdict is earned:
a unit with no row, a rule with no result, a made-up quote, or a bare "ok" pass blocks it; a
language with no ctags support still gets units; a changed function that others call gets REF."""
import json, os, subprocess, sys, tempfile
from pathlib import Path

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
         f"| {h} | REF | util.py:2 | `return 2` | fix | helper now returns 2 | app.py:2 expects 1 |")
    assert rc.verdict(run.name) == 0
    lines = (run / "03-verdict.md").read_text().splitlines()
    assert lines[0].startswith("Status: done ") and lines[2].startswith("Verdict: REQUEST CHANGES (3 of 3 units"), lines



if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as d:
        os.chdir(d)
        sh("git", "init", "-qb", "main")
        sh("git", "config", "user.email", "t@t")
        sh("git", "config", "user.name", "t")
        main()
    print("ok")
