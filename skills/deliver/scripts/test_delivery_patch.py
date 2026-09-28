#!/usr/bin/env python3
import importlib.util
import json
import io
import contextlib
import pathlib
import subprocess
import sys
import tempfile
import unittest


sys.dont_write_bytecode = True
SCRIPT = pathlib.Path(__file__).with_name("delivery-patch.py")
SPEC = importlib.util.spec_from_file_location("delivery_patch", SCRIPT)
PATCHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCHER)

BASELINE_BINARY = bytes([0, 1, 2, 255, 10])
CURRENT_BINARY = bytes([0, 1, 3, 255, 10, 7])


class DeliveryPatchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temporary.name)
        self.baseline = self.root / "baseline"
        self.repo = self.root / "repo"
        self.out = self.root / "delivery.patch"
        for tree in (self.baseline, self.repo):
            (tree / "src").mkdir(parents=True)
        self.write("src/changed.py", "one\ntwo\n", "one\nTWO\nthree\n")
        self.write("src/also changed.txt", "alpha\n", "alpha\nbeta\n")
        self.write("unchanged.md", "stable\n", "stable\n")

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, relative, baseline_text, current_text):
        (self.baseline / relative).write_text(baseline_text)
        (self.repo / relative).write_text(current_text)

    def files(self):
        return ["src/changed.py", "src/also changed.txt", "unchanged.md"]

    def run_tool(self, files=None, extra=None):
        argv = [
            "--baseline", str(self.baseline), "--repo", str(self.repo),
            "--out", str(self.out), "--json", *(extra or []), *(files or self.files()),
        ]
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(io.StringIO()):
            code = PATCHER.main(argv)
        return code, stream.getvalue().strip()

    def apply_into_copy(self, files=None):
        target = self.root / "applied"
        for relative in files or self.files():
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((self.baseline / relative).read_bytes())
        check = subprocess.run(
            ["git", "apply", "--check", "-p1", "--binary", str(self.out)],
            cwd=str(target), capture_output=True,
        )
        self.assertEqual(check.returncode, 0, check.stderr.decode())
        subprocess.run(
            ["git", "apply", "-p1", "--binary", str(self.out)],
            cwd=str(target), capture_output=True, check=True,
        )
        return target

    def test_patch_reproduces_working_tree_and_counts_lines(self):
        code, output = self.run_tool()
        self.assertEqual(code, 0)
        result = json.loads(output)
        self.assertEqual(result["files"], 3)
        self.assertEqual(sorted(result["changed"]), ["src/also changed.txt", "src/changed.py"])
        self.assertEqual((result["added"], result["removed"], result["net"]), (3, 1, 2))
        self.assertEqual(result["apply_proof"], "pass")
        applied = self.apply_into_copy()
        for relative in self.files():
            self.assertEqual((applied / relative).read_bytes(), (self.repo / relative).read_bytes())

    def test_headers_use_repository_paths_without_temporary_fragments(self):
        self.assertEqual(self.run_tool()[0], 0)
        text = self.out.read_text()
        for relative in ("src/changed.py", "src/also changed.txt"):
            self.assertIn(f"diff --git a/{relative} b/{relative}\n", text)
            self.assertIn(f"--- a/{relative}", text)
            self.assertIn(f"+++ b/{relative}", text)
        for fragment in ("a/baseline/", "b/current/", str(self.root), "/tmp/", "/var/folders"):
            self.assertNotIn(fragment, text)

    def test_failed_reproduction_exits_two_and_writes_no_patch(self):
        original = PATCHER.stage_tree

        def corrupting(source, files, destination):
            original(source, files, destination)
            if destination.name == "proof":
                (destination / "src/changed.py").write_text("tampered\n")

        PATCHER.stage_tree = corrupting
        try:
            code, _ = self.run_tool()
        finally:
            PATCHER.stage_tree = original
        self.assertEqual(code, 2)
        self.assertFalse(self.out.exists())

    def test_file_missing_from_baseline_exits_three(self):
        (self.baseline / "src/changed.py").unlink()
        code, _ = self.run_tool()
        self.assertEqual(code, 3)
        self.assertFalse(self.out.exists())

    def test_space_named_and_binary_files_round_trip(self):
        (self.baseline / "asset bundle.bin").write_bytes(BASELINE_BINARY)
        (self.repo / "asset bundle.bin").write_bytes(CURRENT_BINARY)
        code, output = self.run_tool(files=[*self.files(), "asset bundle.bin"])
        self.assertEqual(code, 0)
        result = json.loads(output)
        self.assertIn("asset bundle.bin", result["changed"])
        self.assertIn("GIT binary patch", self.out.read_text(errors="replace"))
        applied = self.apply_into_copy(files=[*self.files(), "asset bundle.bin"])
        for relative in ("asset bundle.bin", "src/also changed.txt"):
            self.assertEqual((applied / relative).read_bytes(), (self.repo / relative).read_bytes())

    def test_missing_side_message_names_the_v1_limit(self):
        (self.repo / "unchanged.md").unlink()
        with self.assertRaises(PATCHER.PatchError) as raised:
            PATCHER.build(self.baseline, self.repo, self.files(), self.out)
        self.assertIn("absent from one side is not supported", str(raised.exception))
        self.assertEqual(raised.exception.code, 3)


if __name__ == "__main__":
    unittest.main()
