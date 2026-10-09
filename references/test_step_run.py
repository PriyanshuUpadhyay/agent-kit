"""Run: python3 test_step_run.py"""
import os, subprocess, sys, tempfile, threading, time
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
    assert out.returncode != 0, "--force must preserve a fresh lock"
    assert claimed.read_text() == original and lock.exists()
    assert (folder / "events.log").read_text() == original_events
    old = time.time() - step_run.STALE_LOCK_SECONDS - 1
    os.utime(lock, (old, old))
    out = run("take", folder, "02-look", "agent-d", "--force")
    assert out.returncode == 0, out.stderr
    assert claimed.read_text().startswith("Status: active agent-d\n") and not lock.exists()
    assert (folder / "events.log").read_text().splitlines()[-1].endswith("\t02-look\ttake agent-d")
    assert str(lock) in refused.stderr
    assert f"use take --force after {step_run.STALE_LOCK_SECONDS} s" in refused.stderr


def test_utf8_and_lock_context(folder):
    file = folder / "02-look.md"
    original = file.read_text()
    dependency = folder / "01-ask.md"
    original_dependency = dependency.read_text(encoding="utf-8")
    dependency.write_text(original_dependency + "合意\n", encoding="utf-8")
    original_events = (folder / "events.log").read_text()
    file.write_text(original + "合意\n", encoding="utf-8")
    env = dict(os.environ, LC_ALL="C", PYTHONUTF8="0", PYTHONCOERCECLOCALE="0", PYTHONIOENCODING="ascii")
    out = subprocess.run([sys.executable, SCRIPT, "take", str(folder), "02-look", "合意"],
                         env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "active \\u5408\\u610f" in out.stdout
    assert "Uses: 01-ask@" in file.read_text(encoding="utf-8")
    assert (folder / "events.log").read_text(encoding="utf-8").splitlines()[-1].endswith("\t02-look\ttake 合意")
    out = subprocess.run([sys.executable, SCRIPT, "status", str(folder)],
                         env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "02-look: active \\u5408\\u610f" in out.stdout
    file.write_text(file.read_text(encoding="utf-8").replace("- [ ] what the sources say: ",
                                                         "- [x] what the sources say: 合意"), encoding="utf-8")
    out = subprocess.run([sys.executable, SCRIPT, "done", str(folder), "02-look"],
                         env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
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
    dependency.write_text(original_dependency, encoding="utf-8")
    (folder / "events.log").write_text(original_events)


def test_done_lock(folder):
    file = folder / "01-ask.md"
    original = file.read_text(encoding="utf-8")
    events = (folder / "events.log").read_text(encoding="utf-8")
    lock = folder / "01-ask.lock"
    lock.write_text("")
    try:
        out = run("done", folder, "01-ask")
        assert out.returncode == 1 and "is being claimed; try again" in out.stderr, out
        assert f"use done --force after {step_run.STALE_LOCK_SECONDS} s" in out.stderr
        assert file.read_text(encoding="utf-8") == original and lock.exists()
        assert (folder / "events.log").read_text(encoding="utf-8") == events
    finally:
        lock.unlink()


def test_done_force(folder):
    file = folder / "01-ask.md"
    original = file.read_text()
    events = (folder / "events.log").read_text()
    lock = folder / "01-ask.lock"
    try:
        for args in ((folder, "01-ask", "--force"), ("--force", folder, "01-ask")):
            lock.write_text("")
            out = run("done", *args)
            assert out.returncode == 1 and lock.exists(), "done must preserve a fresh lock"
            old = time.time() - step_run.STALE_LOCK_SECONDS - 1
            os.utime(lock, (old, old))
            out = run("done", *args)
            assert out.returncode == 0, out.stderr
            assert file.read_text().startswith("Status: done ") and "done --force" not in file.read_text()
            assert not lock.exists()
    finally:
        lock.unlink(missing_ok=True)
        file.write_text(original)
        (folder / "events.log").write_text(events)


def test_force_preserves_replacement_lock(folder):
    lock = folder / "01-ask.lock"
    lock.write_text("")
    old = time.time() - step_run.STALE_LOCK_SECONDS - 1
    os.utime(lock, (old, old))
    real_stat = Path.stat
    winner = None
    claims = []
    calls = 0

    def replace_before_break(path, *args, **kwargs):
        nonlocal winner, calls
        result = real_stat(path, *args, **kwargs)
        if path == lock:
            calls += 1
        if path == lock and calls == 1:
            with patch.object(Path, "stat", real_stat):
                winner = step_run.step_lock(folder, "01-ask", force=True)
                winner.__enter__()
                claims.append("winner")
        return result

    try:
        with patch.object(Path, "exists", lambda path: os.path.exists(path)), patch.object(Path, "stat", replace_before_break):
            try:
                with step_run.step_lock(folder, "01-ask", force=True):
                    claims.append("loser")
            except SystemExit:
                pass
        assert claims == ["winner"], "a stale observation must not clear a replacement lock"
        assert lock.exists(), "the winning lock must remain"
    finally:
        if winner is not None:
            winner.__exit__(None, None, None)
        lock.unlink(missing_ok=True)


def test_lock_removed_before_stat(folder):
    lock = folder / "01-ask.lock"
    lock.write_text("")
    real_exists = Path.exists

    def released(path):
        result = real_exists(path)
        if path == lock:
            lock.unlink(missing_ok=True)
        return result

    with patch.object(Path, "exists", released):
        with step_run.step_lock(folder, "01-ask", force=True):
            assert real_exists(lock)
    assert not lock.exists()


def test_concurrent_forced_takes(folder):
    file = folder / "01-ask.md"
    original = file.read_text()
    events = (folder / "events.log").read_text()
    lock = folder / "01-ask.lock"
    lock.write_text("")
    old = time.time() - step_run.STALE_LOCK_SECONDS - 1
    os.utime(lock, (old, old))
    observed = threading.Barrier(2)
    first_held, second_done = threading.Event(), threading.Event()
    real_stat, real_rename, real_unlink = Path.stat, os.rename, Path.unlink
    real_write = step_run.write_step
    results = {}

    def stat_stale(path, *args, **kwargs):
        result = real_stat(path, *args, **kwargs)
        if path == lock:
            observed.wait(timeout=5)
        return result

    def rename_after_claim(source, destination):
        if source == lock and threading.current_thread().name == "second":
            assert first_held.wait(timeout=5)
        return real_rename(source, destination)

    def unlink_after_claim(path, *args, **kwargs):
        if path == lock and threading.current_thread().name == "second":
            assert first_held.wait(timeout=5)
        return real_unlink(path, *args, **kwargs)

    def hold_claim(path, text):
        if threading.current_thread().name == "first":
            first_held.set()
            assert second_done.wait(timeout=5)
        real_write(path, text)

    def take(who):
        try:
            step_run.take(folder, "01-ask", who, force=True)
            results[who] = "claimed"
        except SystemExit:
            results[who] = "busy"
        except BaseException as error:
            results[who] = error
        finally:
            if who == "second":
                second_done.set()

    try:
        with redirect_stdout(StringIO()), patch.object(Path, "exists", lambda path: os.path.exists(path)), \
                patch.object(Path, "stat", stat_stale), patch.object(os, "rename", rename_after_claim), \
                patch.object(Path, "unlink", unlink_after_claim), patch.object(step_run, "write_step", hold_claim):
            workers = [threading.Thread(target=take, args=(who,), name=who) for who in ("first", "second")]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(timeout=10)
            assert not any(worker.is_alive() for worker in workers)
        assert results == {"first": "claimed", "second": "busy"}, results
        assert file.read_text().startswith("Status: active first\n")
        assert not lock.exists() and not list(folder.glob("*.stale"))
    finally:
        lock.unlink(missing_ok=True)
        file.write_text(original)
        (folder / "events.log").write_text(events)


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
    with subprocess.Popen([sys.executable, SCRIPT, "take", str(folder), "01-ask", "a"],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE) as child:
        child.stdout.close()
        errors = child.stderr.read()
        assert child.wait() == 0 and not errors, errors
    file.write_text(original)
    (folder / "events.log").write_text(original_events)


def test_removed_take_lock(folder):
    file = folder / "01-ask.md"
    original = file.read_text(encoding="utf-8")
    events = (folder / "events.log").read_text(encoding="utf-8")
    write_step = step_run.write_step

    def remove_lock(path, text):
        write_step(path, text)
        (folder / "01-ask.lock").unlink()

    try:
        with redirect_stdout(StringIO()), patch.object(step_run, "write_step", remove_lock):
            step_run.take(folder, "01-ask", "removed-lock")
        assert file.read_text(encoding="utf-8").startswith("Status: active removed-lock\n")
    finally:
        file.write_text(original, encoding="utf-8")
        (folder / "events.log").write_text(events, encoding="utf-8")


def test_atomic_step_writes(folder):
    file = folder / "01-ask.md"
    original = file.read_text()
    original_events = (folder / "events.log").read_text()
    real_replace = os.replace
    previous = original
    replacements = []
    sources = []

    def check_replace(source, destination):
        nonlocal previous
        assert source.parent == file.parent and source.suffix == ".tmp" and destination == file
        assert (folder / "01-ask.lock").exists(), "take and done must hold the step lock during replacement"
        assert file.read_text(encoding="utf-8") == previous, "readers must keep seeing the complete old file"
        next_text = source.read_text(encoding="utf-8")
        assert next_text and next_text.startswith("Status: ")
        real_replace(source, destination)
        previous = next_text
        replacements.append(destination)
        sources.append(source)

    with redirect_stdout(StringIO()), patch.object(step_run.os, "replace", check_replace):
        step_run.take(folder, "01-ask", "atomic", need=[])
        assert replacements == [file], "take must replace the file atomically"
        step_run.done(folder, "01-ask", rev="atomic")
        assert replacements == [file, file], "done must replace the file atomically"
    assert file.read_text(encoding="utf-8") == previous and not file.with_suffix(".md.tmp").exists()
    assert len(set(sources)) == 2 and not any(source.exists() for source in sources), "each write needs its own temporary file"
    file.write_text(original)
    (folder / "events.log").write_text(original_events)


def test_step_mode(folder):
    file = folder / "01-ask.md"
    original = file.read_text()
    events = (folder / "events.log").read_text()
    try:
        file.chmod(0o644)
        with redirect_stdout(StringIO()):
            step_run.take(folder, "01-ask", "mode")
        assert file.stat().st_mode & 0o777 == 0o644, "take must preserve the step file mode"
        new = folder / "new.md"
        step_run.write_step(new, "new step\n")
        assert new.stat().st_mode & 0o777 == 0o644
    finally:
        file.write_text(original)
        (folder / "events.log").write_text(events)


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
    test_done_lock(folder)
    test_done_force(folder)
    test_force_preserves_replacement_lock(folder)
    test_lock_removed_before_stat(folder)
    test_concurrent_forced_takes(folder)
    test_step_mode(folder)
    test_utf8_and_lock_context(folder)
    test_cli_output(folder)
    test_removed_take_lock(folder)
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
