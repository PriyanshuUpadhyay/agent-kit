"""Run: python3 test_land.py"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("land.py")


class LandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.main = self.root / "main"
        self.main.mkdir()
        self.git(self.main, "init", "-q", "-b", "main")
        for key, value in (("user.name", "Test"), ("user.email", "test@example.invalid"),
                           ("commit.gpgsign", "false"), ("core.hooksPath", "/dev/null")):
            self.git(self.main, "config", key, value)
        (self.main / "shared.txt").write_text("base\n", encoding="utf-8")
        self.git(self.main, "add", "shared.txt")
        self.git(self.main, "commit", "-qm", "base")
        self.base = self.git(self.main, "rev-parse", "HEAD").strip()
        self.one, self.two = self.root / "one", self.root / "two"
        for worktree in (self.one, self.two):
            self.git(self.main, "worktree", "add", "-qb", worktree.name, str(worktree))
        self.decl = self.root / "decl.json"

    def git(self, worktree, *args):
        return subprocess.run(["git", "-C", str(worktree), *args], check=True,
                              capture_output=True, text=True).stdout

    def commit(self, worktree, file, message):
        (worktree / file).write_text(message + "\n", encoding="utf-8")
        self.git(worktree, "add", "--", file)
        self.git(worktree, "commit", "-qm", message)

    def run_land(self, declared, frozen=(), order=None, base=None):
        self.decl.write_text(json.dumps({"worktrees": {str(w): f for w, f in declared.items()},
                                         "frozen_interfaces": list(frozen)}), encoding="utf-8")
        args = [sys.executable, str(SCRIPT), str(self.decl),
                *map(str, order or (self.one, self.two))]
        if base is not None:
            args += [f"--base={base}"]
        return subprocess.run(args, cwd=self.main, capture_output=True, text=True)

    def refuse(self, result, reason):
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(reason, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_disjoint_order_and_commits(self):
        self.commit(self.one, "one.txt", "first fix")
        self.commit(self.two, "two.txt", "second fix")
        result = self.run_land({self.one: ["one.txt"], self.two: ["two.txt"]},
                               order=(self.two, self.one))
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(lines[0], f"1. {self.two}")
        self.assertTrue(lines[1].endswith(" second fix"))
        self.assertEqual(lines[2], f"2. {self.one}")
        self.assertTrue(lines[3].endswith(" first fix"))

    def test_overlap(self):
        for worktree in (self.one, self.two):
            self.commit(worktree, "shared.txt", worktree.name)
        self.refuse(self.run_land({self.one: ["shared.txt"], self.two: ["shared.txt"]}),
                    "changed by both")

    def test_undeclared(self):
        self.commit(self.one, "extra.txt", "extra fix")
        self.refuse(self.run_land({self.one: [], self.two: []}), "outside its declared files")

    def test_frozen(self):
        self.commit(self.one, "shared.txt", "changed interface")
        self.refuse(self.run_land({self.one: ["shared.txt"], self.two: []}, ["shared.txt"]),
                    "frozen interface")

    def test_staged_and_unstaged(self):
        self.commit(self.one, "one.txt", "first fix")
        (self.one / "shared.txt").write_text("unstaged\n", encoding="utf-8")
        self.refuse(self.run_land({self.one: ["one.txt"], self.two: []}), "shared.txt")
        self.git(self.one, "add", "shared.txt")
        self.refuse(self.run_land({self.one: ["one.txt"], self.two: []}), "shared.txt")

    def test_rename_checks_old_path(self):
        self.git(self.one, "mv", "shared.txt", "renamed.txt")
        self.git(self.one, "commit", "-qm", "rename")
        self.refuse(self.run_land({self.one: ["renamed.txt"], self.two: []}), "shared.txt")

    def test_filename_with_newline(self):
        name = "line\nbreak.txt"
        self.commit(self.one, name, "odd file")
        result = self.run_land({self.one: [name], self.two: []})
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_base_override(self):
        self.commit(self.one, "one.txt", "first fix")
        result = self.run_land({self.one: [], self.two: []}, order=(self.one,), base="HEAD")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("first fix", result.stdout)
        result = self.run_land({self.one: ["one.txt"], self.two: []}, base=self.base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("first fix", result.stdout)

    def test_merge_base_with_main_head(self):
        self.commit(self.main, "main.txt", "main moved")
        self.commit(self.one, "one.txt", "first fix")
        result = self.run_land({self.one: ["one.txt"], self.two: []})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("first fix", result.stdout)
        self.assertNotIn("main moved", result.stdout)

    def test_frozen_deletion(self):
        self.git(self.one, "rm", "shared.txt")
        self.git(self.one, "commit", "-qm", "delete interface")
        self.refuse(self.run_land({self.one: ["shared.txt"], self.two: []}, ["shared.txt"]),
                    "frozen interface")

    def test_bad_base(self):
        self.refuse(self.run_land({self.one: [], self.two: []}, base="--bad-revision"),
                    "Git failed")

    def test_bad_declaration(self):
        self.refuse(self.run_land({self.one: "one.txt", self.two: []}), "list of file paths")

    def test_missing_worktree_declaration(self):
        self.refuse(self.run_land({self.one: []}), "has no declared files")


if __name__ == "__main__":
    unittest.main()
