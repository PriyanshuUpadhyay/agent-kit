"""Run: python3 test_review_walk.py. Builds a throwaway repo and checks the two parts that can go wrong
quietly: the diff since view must hide base-branch merges, and anchors must land on new-side lines."""
import os, subprocess, tempfile
from pathlib import Path

import review_walk as rw


def sh(*cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout.strip()


def commit(files, msg):
    for name, text in files.items():
        Path(name).write_text(text)
    sh("git", "add", "-A")
    sh("git", "commit", "-qm", msg)
    return sh("git", "rev-parse", "HEAD")


def test_since_view_hides_base_merges():
    base1 = commit({"a.ts": "one\ntwo\nthree\nfour\nfive\n", "b.ts": "x\n"}, "base")
    sh("git", "switch", "-qc", "feature")
    head1 = commit({"a.ts": "one\nTWO\nthree\nfour\nfive\n", "b.ts": "x\ny\n"}, "pr change")
    sh("git", "switch", "-q", "main")
    base2 = commit({"a.ts": "one\ntwo\nthree\nfour\nFIVE\n"}, "develop change")
    sh("git", "switch", "-q", "feature")
    sh("git", "merge", "-q", "--no-edit", "main")
    head2 = commit({"b.ts": "x\ny\nz\n"}, "second pr change")

    prev = {"target": {"base": base1}, "viewed": {"a.ts": head1, "b.ts": head1}}
    now = {"base": base2, "head": head2}
    assert rw.since_view(prev, now, "a.ts") == "", "a develop-only change must not show as changed since view"
    b = rw.since_view(prev, now, "b.ts")
    assert "+z" in b and "+y" not in b, b


def test_anchor_uses_new_side_lines():
    patch = ("diff --git a/a.ts b/a.ts\n--- a/a.ts\n+++ b/a.ts\n@@ -1,3 +1,4 @@\n one\n-two\n+TWO\n+extra\n three\n")
    assert rw.anchor(patch, "a.ts", "TWO") == (None, 2)
    assert rw.anchor(patch, "a.ts", "TWO", "three") == (2, 4)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as d:
        os.chdir(d)
        sh("git", "init", "-qb", "main")
        sh("git", "config", "user.email", "t@t")
        sh("git", "config", "user.name", "t")
        test_since_view_hides_base_merges()
        test_anchor_uses_new_side_lines()
    print("ok")
