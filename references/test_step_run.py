"""Run: python3 test_step_run.py"""
import os, subprocess, sys, tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import step_run

SCRIPT = Path(__file__).with_name("step_run.py")
run = lambda *a: subprocess.run([sys.executable, SCRIPT, *map(str, a)], capture_output=True, text=True)


def test_stale_lock_recovery(folder, claimed):
    lock = folder / "02-look.lock"
    lock.write_text("")
    original = claimed.read_text()
    original_events = (folder / "events.log").read_text()
    refused = run("take", folder, "02-look", "agent-d")
    assert refused.returncode != 0
    assert claimed.read_text() == original and lock.exists()
    assert (folder / "events.log").read_text() == original_events
    out = run("take", folder, "02-look", "agent-d", "--force")
    assert out.returncode == 0, out.stderr
    assert claimed.read_text().startswith("Status: active agent-d\n") and not lock.exists()
    assert (folder / "events.log").read_text().splitlines()[-1].endswith("\t02-look\ttake agent-d")
    assert str(lock) in refused.stderr and "--force to clear it" in refused.stderr


def test_utf8_and_lock_context(folder):
    file = folder / "01-ask.md"
    original = file.read_text()
    original_events = (folder / "events.log").read_text()
    file.write_text(original + "合意\n", encoding="utf-8")
    read_text, write_text = Path.read_text, Path.write_text

    def ascii_read(path, *args, **kwargs):
        kwargs.setdefault("encoding", "ascii")
        return read_text(path, *args, **kwargs)

    def ascii_write(path, *args, **kwargs):
        kwargs.setdefault("encoding", "ascii")
        return write_text(path, *args, **kwargs)

    with redirect_stdout(StringIO()), patch.object(Path, "read_text", ascii_read), patch.object(Path, "write_text", ascii_write):
        step_run.take(folder, "01-ask", "合意", need=[])
        step_run.done(folder, "01-ask", rev="unicode")
    assert "合意" in file.read_text(encoding="utf-8")
    lock = folder / "01-ask.lock"
    lock.write_text("")
    try:
        try:
            step_run.take(folder, "01-ask", "a")
            raise AssertionError("take must refuse an existing lock")
        except SystemExit as error:
            assert error.__suppress_context__, "the lock refusal must hide FileExistsError"
    finally:
        lock.unlink()
    file.write_text(original)
    (folder / "events.log").write_text(original_events)


def test_cli_output(folder):
    file = folder / "01-ask.md"
    original = file.read_text()
    original_events = (folder / "events.log").read_text()
    env = {**os.environ, "PYTHONIOENCODING": "ascii"}
    out = subprocess.run([sys.executable, SCRIPT, "take", str(folder), "01-ask", "合意"],
                         env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "active \\u5408\\u610f" in out.stdout
    assert file.read_text(encoding="utf-8").startswith("Status: active 合意\n")
    file.write_text(original)
    child = subprocess.Popen([sys.executable, SCRIPT, "take", str(folder), "01-ask", "a"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    child.stdout.close()
    errors = child.stderr.read()
    assert child.wait() == 0 and not errors, errors
    file.write_text(original)
    (folder / "events.log").write_text(original_events)


def test_atomic_step_writes(folder):
    file = folder / "01-ask.md"
    original = file.read_text()
    original_events = (folder / "events.log").read_text()
    real_replace = os.replace
    previous = original
    replacements = []

    def check_replace(source, destination):
        nonlocal previous
        assert source == file.with_suffix(".md.tmp") and destination == file
        assert file.read_text(encoding="utf-8") == previous, "readers must keep seeing the complete old file"
        next_text = source.read_text(encoding="utf-8")
        assert next_text and next_text.startswith("Status: ")
        real_replace(source, destination)
        previous = next_text
        replacements.append(destination)

    with redirect_stdout(StringIO()), patch.object(step_run.os, "replace", check_replace):
        step_run.take(folder, "01-ask", "atomic", need=[])
        assert replacements == [file], "take must replace the file atomically"
        step_run.done(folder, "01-ask", rev="atomic")
        assert replacements == [file, file], "done must replace the file atomically"
    assert file.read_text(encoding="utf-8") == previous and not file.with_suffix(".md.tmp").exists()
    file.write_text(original)
    (folder / "events.log").write_text(original_events)


with tempfile.TemporaryDirectory() as tmp:
    skill = Path(tmp, "SKILL.md")
    skill.write_text("| File | Needs | Holds |\n|---|---|---|\n| `01-ask.md` | none | the question |\n"
                     "| `02-look.md` | ask | what the sources say |\n\nafter\n")
    folder = Path(tmp, "run")
    run("start", folder, skill)
    assert (folder / "02-look.md").read_text().splitlines()[1] == "Uses: 01-ask"
    assert run("take", folder, "02-look", "a").returncode != 0
    assert not (folder / "02-look.lock").exists()
    assert "the question" in run("done", folder, "01-ask").stderr
    f = folder / "01-ask.md"
    f.write_text(f.read_text().replace("- [ ] the question: ", "- [x] the question: why is the sky blue"))
    assert run("done", folder, "01-ask").returncode == 0 and f.read_text().startswith("Status: done ")
    test_utf8_and_lock_context(folder)
    test_cli_output(folder)
    test_atomic_step_writes(folder)
    out = run("take", folder, "02-look", "agent-b")
    assert out.returncode == 0 and "Uses: 01-ask@" in (folder / "02-look.md").read_text()
    assert "(ready)" not in run("status", folder).stdout.split("02-look")[1]
    assert "stale" not in run("status", folder).stdout
    f.write_text(f.read_text() + "a later edit\n")
    assert "02-look: active agent-b  (stale: 01-ask)" in run("status", folder).stdout
    events = [l.split("\t")[1:] for l in (folder / "events.log").read_text().splitlines()]
    assert events[0][0] == "01-ask" and events[0][1].startswith("done ") and events[1] == ["02-look", "take agent-b"]
    claimed = folder / "02-look.md"
    original = claimed.read_text()
    original_events = (folder / "events.log").read_text()
    out = run("take", folder, "02-look", "agent-c")
    assert out.returncode != 0
    assert out.stderr.strip() == "02-look is active for agent-b; use --force if that run is gone"
    assert claimed.read_text() == original
    assert (folder / "events.log").read_text() == original_events
    assert not (folder / "02-look.lock").exists()
    out = run("take", folder, "02-look", "agent-c", "--force")
    assert out.returncode == 0 and claimed.read_text().startswith("Status: active agent-c\n")
    assert not (folder / "02-look.lock").exists()
    assert run("take", folder, "02-look", "agent-c").returncode == 0
    test_stale_lock_recovery(folder, claimed)
    lock = folder / "02-look.lock"
    claimed.write_text(original.replace("Status: active agent-b", "Status: open"))
    children = [subprocess.Popen([sys.executable, SCRIPT, "take", str(folder), "02-look", who],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                for who in ("agent-d", "agent-e")]
    outputs = [child.communicate() for child in children]
    assert sorted(child.returncode for child in children) == [0, 1], outputs
    winner = ("agent-d", "agent-e")[next(i for i, child in enumerate(children) if child.returncode == 0)]
    assert claimed.read_text().startswith(f"Status: active {winner}\n")
    assert not lock.exists()
    print("ok")
