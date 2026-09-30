"""Run: python3 test_review_check.py. Builds a throwaway repo and checks that the verdict is earned:
a unit with no row, a made-up quote, or a bare "ok" pass blocks it, and a language with no ctags
support still gets units."""
import os, subprocess, sys, tempfile
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
                   "keep.py": "x = 1\ncheck()\ny = 2\n"}, "base")
    head = commit({"pane.swift": "func resize() {\n  a()\n  b()\n}\n", "gone.py": None,
                   "keep.py": "x = 1\ny = 2\n"}, "change")
    rc.start(f"{base}..{head}")
    run = next(Path("tmp/review-check").iterdir())
    units = {u["file"]: u for u in __import__("json").loads((run / "units.json").read_text())}
    assert set(units) == {"pane.swift", "gone.py", "keep.py"}, units  # swift has no ctags parser here
    assert units["gone.py"]["symbol"] == "deleted file"
    s, g, k = units["pane.swift"]["id"], units["gone.py"]["id"], units["keep.py"]["id"]

    rows(run, f"| {s} | pane.swift:3 | `b()` | pass | | b() runs after a(), no shared state |")
    assert rc.verdict(run.name) == 1, "two units have no row"

    rows(run, f"| {s} | pane.swift:3 | `b()` | pass | | ok |",
         f"| {g} | gone.py:1 | `def guard` | pass | | no caller imports guard |",
         f"| {k} | keep.py:2 | `check()` | pass | | check() had no side effect |")
    assert rc.verdict(run.name) == 1, "a bare ok is not a proof"

    rows(run, f"| {s} | pane.swift:3 | `c()` | fix | made up | x |")
    assert rc.verdict(run.name) == 1, "a quote that is not in the diff"

    rows(run, f"| {s} | pane.swift:3 | `b()` | pass | | b() runs after a(), no shared state |",
         f"| {g} | gone.py:1 | `def guard` | pass | | no caller imports guard |",
         f"| {k} | keep.py:2 | `check()` | fix | removed check() drops the guard | caller main() |")
    assert rc.verdict(run.name) == 0
    lines = (run / "03-verdict.md").read_text().splitlines()
    assert lines[0].startswith("Status: done ") and lines[2].startswith("Verdict: REQUEST CHANGES (3 of 3 units; 1 fix"), lines


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as d:
        os.chdir(d)
        sh("git", "init", "-qb", "main")
        sh("git", "config", "user.email", "t@t")
        sh("git", "config", "user.name", "t")
        main()
    print("ok")
