"""Run: python3 test_flow_run.py  (uses a temporary repo and a temporary HOME)."""
import fcntl
import json
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))  # python3 -I does not add the script's folder
import flow_run  # noqa: E402

SCRIPT = Path(__file__).with_name("flow_run.py")
CALLERS_MEMORY_LIMIT = 1_000_000


def test_skip_text_encoding():
    import ast
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    missing = [call.lineno for node in tree.body if isinstance(node, ast.FunctionDef)
               and node.name in ("test_skip_lock", "test_skip_rejects_force")
               for call in ast.walk(node) if isinstance(call, ast.Call)
               and isinstance(call.func, ast.Attribute) and call.func.attr in ("read_text", "write_text")
               and not any(kw.arg == "encoding" for kw in call.keywords)]
    assert not missing, f"skip test reads or writes without UTF-8 encoding at {missing}"


def test_review_read_encoding():
    """take and approved read 06-review.md, which holds UTF-8 block text; macOS reads UTF-8 under any
    locale, so this parses the code instead of running it under LC_ALL=C."""
    import ast
    tree = ast.parse(Path(SCRIPT).read_text(encoding="utf-8"))
    missing = [call.lineno for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in ("take", "approved")
               for call in ast.walk(node) if isinstance(call, ast.Call)
               and isinstance(call.func, ast.Attribute) and call.func.attr == "read_text"
               and not any(kw.arg == "encoding" for kw in call.keywords)]
    assert not missing, f"take or approved reads without UTF-8 encoding at {missing}"


def test_command_wrong_count(run, folder):
    for command, args in (("start", ("extra",)), ("start", ("--profile",)), ("status", (folder, "extra")),
                          ("take", ()), ("take", (folder, "01-frame", "a", "extra")),
                          ("done", ()), ("skip", ()), ("skip", (folder,)),
                          ("skip", (folder, "02-design"))):
        out = run(command, *args)
        usage = next(line.strip() for line in flow_run.__doc__.splitlines()
                     if line.strip().split()[:1] == [command])
        assert out.returncode == 1 and usage in out.stderr, out.stderr
        assert "Traceback" not in out.stderr, out.stderr
    assert run("status").returncode == 0, "status without a folder must use the latest run"


def test_done_wrong_count(run, folder):
    for args in ((folder,), (folder, "01-frame", "extra")):
        out = run("done", *args)
        assert out.returncode == 1 and "done <folder> <step>" in out.stderr, out.stderr
        assert "--force" not in out.stderr and "Traceback" not in out.stderr, out.stderr


def test_skip_plain_reason(run, folder):
    file = folder / "02-design.md"
    original = file.read_text(encoding="utf-8")
    events = (folder / "events.log").read_text(encoding="utf-8")
    try:
        out = run("skip", folder, "02-design", "\x1bno\nUI\tchange\x7f")
        assert out.returncode == 0, out.stderr
        text = file.read_text(encoding="utf-8")
        assert text.splitlines()[0] == "Status: skipped no UI change", text
        assert text.split("\n", 1)[1] == original.split("\n", 1)[1], "skip must preserve line 2 and the body"
        lines = (folder / "events.log").read_text(encoding="utf-8").splitlines()
        assert len(lines) == len(events.splitlines()) + 1 and lines[-1].endswith("\tskip no UI change"), lines
        assert "\x1b" not in out.stdout and "\x7f" not in out.stdout
    finally:
        file.write_text(original, encoding="utf-8")
        (folder / "events.log").write_text(events, encoding="utf-8")


def fill(f, evidence="evidence"):
    """Check every todo of a step file with evidence, as an agent would."""
    f.write_text("".join(l.replace("- [ ]", "- [x]").rstrip() + (f" {evidence}\n" if l.startswith("- [") and l.rstrip().endswith(":") else "\n")
                         for l in f.read_text(encoding="utf-8").splitlines()), encoding="utf-8")


def test_take_force(run, folder):
    file = folder / "01-frame.md"
    original = file.read_text()
    assert run("take", folder, "01-frame", "agent-a").returncode == 0
    refused = run("take", folder, "01-frame", "agent-b")
    assert refused.returncode != 0 and "active for agent-a" in refused.stderr
    for args, who in (([folder, "01-frame", "agent-b", "--force"], "agent-b"),
                      (["--force", folder, "01-frame", "agent-c"], "agent-c"),
                      ([folder, "01-frame", "--force", "agent-d"], "agent-d")):
        out = run("take", *args)
        assert out.returncode == 0, out.stderr
        assert file.read_text().startswith(f"Status: active {who}\n")
        assert (folder / "01-frame.lock").exists()
        assert (folder / "events.log").read_text().splitlines()[-1].endswith(f"\t01-frame\ttake {who}")
    file.write_text(original)


def test_take_requires_who(run, folder):
    file = folder / "01-frame.md"
    original = file.read_text()
    events = (folder / "events.log").read_text()
    for args in ((folder, "01-frame"), (folder, "01-frame", "--force")):
        out = run("take", *args)
        assert out.returncode != 0, "take without who must refuse the claim"
        assert "who" in out.stderr and "Traceback" not in out.stderr, out.stderr
        assert file.read_text() == original
        assert (folder / "events.log").read_text() == events


def test_done_rejects_force(run, folder):
    file = folder / "01-frame.md"
    original = file.read_text(encoding="utf-8")
    events = (folder / "events.log").read_text(encoding="utf-8")
    try:
        fill(file)
        filled = file.read_text(encoding="utf-8")
        for args in ((folder, "01-frame", "--force"), ("--force", folder, "01-frame")):
            out = run("done", *args)
            assert out.returncode == 1, "done must refuse --force"
            assert "done <folder> <step>" in out.stderr and "Traceback" not in out.stderr, out.stderr
            assert file.read_text(encoding="utf-8") == filled
            assert (folder / "events.log").read_text(encoding="utf-8") == events
    finally:
        file.write_text(original, encoding="utf-8")
        (folder / "events.log").write_text(events, encoding="utf-8")


def test_atomic_skip(folder):
    file = folder / "02-design.md"
    original = file.read_text()
    real_replace = os.replace
    replaced = []

    def check_replace(source, destination):
        assert file.read_text() == original, "skip must preserve the old file until replacement"
        assert source.parent == file.parent and source.suffix == ".tmp" and destination == file
        with (folder / "02-design.lock").open("a") as contender:
            try:
                fcntl.flock(contender.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                pass
            else:
                raise AssertionError("skip must hold the step lock during replacement")
        real_replace(source, destination)
        replaced.append(destination)

    with redirect_stdout(StringIO()), patch.object(flow_run.step_run.os, "replace", check_replace):
        flow_run.skip(folder, "02-design", "no", "UI")
    assert replaced == [file], "skip must replace the file atomically"
    assert file.read_text().startswith("Status: skipped no UI\n")
    file.write_text(original)


def test_skip_lock(run, folder):
    file = folder / "02-design.md"
    original = file.read_text(encoding="utf-8")
    events = (folder / "events.log").read_text(encoding="utf-8")
    with flow_run.step_run.step_lock(folder, "02-design"):
        out = run("skip", folder, "02-design", "no", "UI")
        assert out.returncode == 1 and "02-design is locked by a running skip; wait for it" in out.stderr, out
        assert file.read_text(encoding="utf-8") == original
        assert (folder / "events.log").read_text(encoding="utf-8") == events


def test_skip_rejects_force(run, folder):
    file = folder / "02-design.md"
    original = file.read_text(encoding="utf-8")
    events = (folder / "events.log").read_text(encoding="utf-8")
    try:
        for args in ((folder, "02-design", "no", "UI", "--force"),
                     ("--force", folder, "02-design", "no", "UI")):
            file.write_text(original.replace("Status: open", "Status: active dead-owner"), encoding="utf-8")
            out = run("skip", *args)
            assert out.returncode == 1, "skip must refuse --force"
            assert "skip accepts no --force" in out.stderr and "Traceback" not in out.stderr, out.stderr
            assert file.read_text(encoding="utf-8") == original.replace("Status: open", "Status: active dead-owner")
            assert (folder / "events.log").read_text(encoding="utf-8") == events
    finally:
        file.write_text(original, encoding="utf-8")
        (folder / "events.log").write_text(events, encoding="utf-8")


def test_callers_after_claim(run, folder):
    file = folder / "04-impact.md"
    original = file.read_text()
    with flow_run.step_run.step_lock(folder, "04-impact"):
        out = run("take", folder, "04-impact", "a")
        assert out.returncode == 1 and "is locked by a running take" in out.stderr, out
        assert file.read_text() == original, "a refused claim must not write callers"
    seen = []

    def write_callers(path):
        assert file.read_text().startswith("Status: active a\n"), "the claim must finish before callers are written"
        try:
            flow_run.skip(folder, "04-impact", "racing skip")
            raise AssertionError("skip must refuse during the callers write")
        except SystemExit as error:
            assert "is locked by a running skip" in str(error), error
        seen.append(path)

    with redirect_stdout(StringIO()), patch.object(flow_run, "write_callers", write_callers):
        flow_run.take(folder, "04-impact", "a")
    assert seen == [folder]
    file.write_text(original)


def test_callers_timeout(folder):
    file, contracts = folder / "04-impact.md", folder / "03-contracts.md"
    original = file.read_text(encoding="utf-8")
    original_contracts = contracts.read_text(encoding="utf-8")
    calls = []
    real_run = subprocess.run

    def slow_grep(args, **kwargs):
        if args[:2] == ["git", "grep"]:
            calls.append((args, kwargs))
            if len(calls) == 1:
                raise subprocess.TimeoutExpired(args, flow_run.SEARCH_EACH_SECONDS)
            kwargs["stdout"].write(b"app.py:1:other_name()\n")
            return subprocess.CompletedProcess(args, 0)
        return real_run(args, **kwargs)

    try:
        contracts.write_text(original_contracts + "`other_name()`\n", encoding="utf-8")
        with patch.object(flow_run.subprocess, "run", slow_grep):
            flow_run.write_callers(folder)
        assert len(calls) >= 2, "a timed out search must not stop later names"
        assert all(options.get("timeout") == flow_run.SEARCH_EACH_SECONDS and not options.get("text") for _, options in calls)
        text = file.read_text(encoding="utf-8")
        assert "callers: git grep timed out" in text and "app.py:1:other_name()" in text
    finally:
        file.write_text(original, encoding="utf-8")
        contracts.write_text(original_contracts, encoding="utf-8")


def callers_stub_output(folder, name, stub_body):
    import tracemalloc
    file, contracts = folder / "04-impact.md", folder / "03-contracts.md"
    original, original_contracts = file.read_text(encoding="utf-8"), contracts.read_text(encoding="utf-8")
    try:
        contracts.write_text(f"`{name}()`", encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            stub = Path(directory) / "git"
            stub.write_text(f"#!{sys.executable}\nimport sys\n{stub_body}", encoding="utf-8")
            stub.chmod(0o755)
            with patch.object(flow_run, "git", return_value=str(folder)), \
                    patch.dict(os.environ, {"PATH": directory + os.pathsep + os.environ["PATH"]}):
                tracemalloc.start()
                try:
                    flow_run.write_callers(folder)
                    _, peak = tracemalloc.get_traced_memory()
                finally:
                    tracemalloc.stop()
        return peak, file.read_text(encoding="utf-8")
    finally:
        file.write_text(original, encoding="utf-8")
        contracts.write_text(original_contracts, encoding="utf-8")


def test_callers_large_output(folder):
    peak, text = callers_stub_output(folder, "many_hits",
                                    "for index in range(10000):\n"
                                    "    print(f'app.py:{index + 1}:many_hits() ' + 'x' * 500)\n")
    assert "### many_hits (10000 places)" in text and f"... and {10000 - flow_run.MAX_HITS} more" in text, text
    hits = [line for line in text.splitlines() if line.startswith("app.py:")]
    assert len(hits) == flow_run.MAX_HITS and hits[-1].startswith(f"app.py:{flow_run.MAX_HITS}:")
    assert all(len(hit) <= flow_run.HIT_CHARS for hit in hits)
    assert peak < CALLERS_MEMORY_LIMIT, f"caller search held the full output in memory: peak {peak} bytes"


def test_callers_long_line(folder):
    peak, text = callers_stub_output(folder, "long_hit",
                                    "sys.stdout.buffer.write(b'bundle.js:1:long_hit() ')\n"
                                    "for _ in range(50):\n"
                                    "    sys.stdout.buffer.write(b'x' * 1024 * 1024)\n"
                                    "sys.stdout.buffer.write(b'\\n\\napp.py:2:long_hit()\\napp.py:3:long_hit()')\n")
    assert "### long_hit (3 places)" in text, text
    hits = [line for line in text.splitlines() if line.startswith(("bundle.js:", "app.py:"))]
    assert len(hits) == 3 and len(hits[0]) == flow_run.HIT_CHARS, hits
    assert hits[1:] == ["app.py:2:long_hit()", "app.py:3:long_hit()"], hits
    assert peak < CALLERS_MEMORY_LIMIT, f"caller search held a whole line in memory: peak {peak} bytes"


def test_callers_long_stderr(folder):
    peak, text = callers_stub_output(folder, "failed_hit",
                                    "for _ in range(50):\n"
                                    "    sys.stderr.buffer.write(b'x' * 1024 * 1024)\n"
                                    "sys.exit(128)\n")
    prefix = "callers: git grep failed: "
    errors = [line for line in text.splitlines() if line.startswith(prefix)]
    assert len(errors) == 1 and len(errors[0]) <= len(prefix) + flow_run.LINE_CHUNK, "git grep error line exceeds its chunk limit"
    assert "0 places" not in text
    assert peak < CALLERS_MEMORY_LIMIT, f"caller search held a whole stderr line in memory: peak {peak} bytes"


def test_callers_stderr_utf8_cut(folder):
    _, text = callers_stub_output(folder, "failed_hit",
                                  "sys.stderr.buffer.write(('€' * 2000).encode('utf-8'))\n"
                                  "sys.exit(128)\n")
    errors = [line for line in text.splitlines() if line.startswith("callers: git grep failed: ")]
    assert len(errors) == 1 and errors[0].endswith("€") and "\\x" not in errors[0], repr(errors)[-80:]


def test_callers_stdout_utf8_cut(folder):
    with patch.object(flow_run, "HIT_CHARS", flow_run.LINE_CHUNK):
        _, text = callers_stub_output(folder, "long_hit",
                                      "sys.stdout.buffer.write(('€' * 2000 + '\\n').encode('utf-8'))\n")
    hits = [line for line in text.splitlines() if line.startswith("€")]
    assert "### long_hit (1 places)" in text, text
    assert len(hits) == 1 and hits[0].endswith("€") and "\\x" not in hits[0], repr(hits)[-80:]


def test_callers_failure(folder):
    file = folder / "04-impact.md"
    original = file.read_text(encoding="utf-8")
    def failed_grep(args, **kwargs):
        kwargs["stderr"].write(b"\x1b[31mcorrupt index\nextra detail")
        return subprocess.CompletedProcess(args, 128)
    try:
        with patch.object(flow_run, "git", return_value=str(folder)), \
                patch.object(flow_run.subprocess, "run", side_effect=failed_grep):
            flow_run.write_callers(folder)
        text = file.read_text(encoding="utf-8")
        assert "callers: git grep failed: [31mcorrupt index" in text, text
        assert "0 places" not in text and "extra detail" not in text and "\x1b" not in text
    finally:
        file.write_text(original, encoding="utf-8")


def test_callers_deadline(folder):
    file, contracts = folder / "04-impact.md", folder / "03-contracts.md"
    original, original_contracts = file.read_text(encoding="utf-8"), contracts.read_text(encoding="utf-8")
    try:
        contracts.write_text("`one_name()` `two_name()` `three_name()`", encoding="utf-8")
        with patch.object(flow_run, "git", return_value=str(folder)), \
                patch("time.monotonic", side_effect=[0, 119, 120]), \
                patch.object(flow_run.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, b"", b"")) as search:
            flow_run.write_callers(folder)
        assert search.call_count == 1, "the total deadline must stop later searches"
        assert "callers: search stopped after 120 s, 2 names not searched" in file.read_text(encoding="utf-8")
        assert search.call_args.kwargs["timeout"] == 1, "each search must use the remaining total budget"
    finally:
        file.write_text(original, encoding="utf-8")
        contracts.write_text(original_contracts, encoding="utf-8")


def test_callers_name_cap(folder):
    file, contracts = folder / "04-impact.md", folder / "03-contracts.md"
    original, original_contracts = file.read_text(encoding="utf-8"), contracts.read_text(encoding="utf-8")
    try:
        contracts.write_text(" ".join(f"`name_{i}()`" for i in range(flow_run.NAME_CAP + 3)), encoding="utf-8")
        with patch.object(flow_run, "git", return_value=str(folder)), \
                patch.object(flow_run.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, b"", b"")) as search:
            flow_run.write_callers(folder)
        assert search.call_count == flow_run.NAME_CAP
        assert "... and 3 more names not searched" in file.read_text(encoding="utf-8")
    finally:
        file.write_text(original, encoding="utf-8")
        contracts.write_text(original_contracts, encoding="utf-8")


def test_callers_controls(repo, run, folder):
    file, app = folder / "04-impact.md", repo / "app.py"
    original, source = file.read_text(encoding="utf-8"), app.read_bytes()
    try:
        assert hasattr(flow_run.step_run, "plain") and flow_run.plain is flow_run.step_run.plain
        app.write_bytes(b"\t# \x1b]0;title\x07 \x7f \xc2\x80 parse_phone()\n")
        out = run("take", folder, "04-impact", "a")
        assert out.returncode == 0, out.stderr
        assert "]0;title" in out.stdout
        assert ":\t# " in out.stdout, "tab-indented hits must keep their indentation"
        assert not any(ord(c) < 32 and c not in "\n\t" or 127 <= ord(c) <= 159 for c in out.stdout), repr(out.stdout)
        assert "parse_phone" in file.read_text(encoding="utf-8")
    finally:
        app.write_bytes(source)
        file.write_text(original, encoding="utf-8")


def test_impact_closed_stdout(repo, env, folder):
    file = folder / "04-impact.md"
    original = file.read_text()
    file.write_text(original + "large output\n" * 10000)
    try:
        with subprocess.Popen([sys.executable, SCRIPT, "take", str(folder), "04-impact", "pipe"],
                              cwd=repo, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as child:
            with subprocess.Popen(["head", "-1"], stdin=child.stdout, stdout=subprocess.PIPE) as consumer:
                child.stdout.close()
                output, _ = consumer.communicate()
                assert consumer.returncode == 0 and output == b"Status: active pipe\n"
            errors = child.stderr.read()
            assert child.wait() == 0 and not errors, errors
        assert flow_run.CALLERS_HEAD in file.read_text(), "callers must be saved before printing to a closed pipe"
    finally:
        file.write_text(original)


def test_impact_utf8(repo, env, folder):
    file = folder / "04-impact.md"
    contracts = folder / "03-contracts.md"
    original = file.read_text(encoding="utf-8")
    original_contracts = contracts.read_text(encoding="utf-8")
    app = repo / "app.py"
    original_app = app.read_bytes()
    # Disable C-locale coercion, UTF-8 mode, and UTF-8 stream output independently.
    ascii_env = {**env, "LC_ALL": "C", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0", "PYTHONIOENCODING": "ascii"}
    try:
        app.write_bytes(original_app + "# 合意 parse_phone\n".encode("utf-8") + b"# \xff parse_phone\n")
        for note in ("", "合意\n"):
            file.write_text(original, encoding="utf-8")
            contracts.write_text(original_contracts + note, encoding="utf-8")
            out = subprocess.run([sys.executable, SCRIPT, "take", str(folder), "04-impact", "ascii-owner"],
                                 cwd=repo, env=ascii_env, capture_output=True, text=True)
            assert out.returncode == 0, out.stderr
            assert "\\u5408\\u610f" in out.stdout and "\\xff" in out.stdout and flow_run.CALLERS_HEAD in out.stdout
            assert file.read_text(encoding="utf-8").startswith("Status: active ascii-owner\n")
            assert flow_run.CALLERS_HEAD in file.read_text(encoding="utf-8")
    finally:
        file.write_text(original, encoding="utf-8")
        contracts.write_text(original_contracts, encoding="utf-8")
        app.write_bytes(original_app)


def test_closed_stdout(repo, env, folder):
    file = folder / "01-frame.md"
    original = file.read_text()
    file.write_text(original + "large output\n" * 10000)
    try:
        with subprocess.Popen([sys.executable, SCRIPT, "take", str(folder), "01-frame", "pipe"],
                              cwd=repo, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as child:
            with subprocess.Popen(["head", "-c", "10"], stdin=child.stdout, stdout=subprocess.PIPE) as consumer:
                child.stdout.close()
                output, _ = consumer.communicate()
                assert consumer.returncode == 0 and len(output) == 10
            errors = child.stderr.read()
            assert child.wait() == 0 and not errors, errors
    finally:
        file.write_text(original)


PARAMS = '[params]\nsource_of_truth = "docs/spec.md"\nsite = "site"\nshots = "tmp/shots"\n'


def blocks_start(tmp, name, catalog, repo_toml=PARAMS, *args, env=None):
    """Start a flow in a new repo whose catalog `any` section has the given step lines, with the kit's blocks."""
    home, repo = Path(tmp, name, "home"), Path(tmp, name, "app")
    (home / ".flow" / "app").mkdir(parents=True)
    (home / ".flow" / "domains.md").write_text("## any\n" + catalog, encoding="utf-8")
    (home / ".flow" / "app" / "profile.md").write_text("Domains: any\nRepo rules: none\n", encoding="utf-8")
    repo.mkdir(exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    if repo_toml is not None:
        (repo / ".blocks.toml").write_text(repo_toml, encoding="utf-8")
    run = lambda *a: subprocess.run([sys.executable, SCRIPT, *map(str, a)], cwd=repo,
                                    env={**os.environ, "HOME": str(home), **(env or {})}, capture_output=True, text=True)
    out = run("start", *args)
    folder = Path(out.stdout.splitlines()[0]) if out.returncode == 0 else None
    return out, folder, repo, run


def step_text(folder, step):
    return (folder / f"{step}.md").read_text(encoding="utf-8")


def test_block_in_step(tmp):
    """D1: a catalog step line naming block:<id> writes that block into the step file, and the
    Skills read line names the profile and the block with its content hash."""
    out, folder, repo, run = blocks_start(tmp, "d1", "- build: block:red-first-check\n")
    assert out.returncode == 0, out.stderr
    build = step_text(folder, "05-build")
    assert "===== block:red-first-check =====" in build and "Rank each claim on the ladder" in build, build
    skills = next(line for line in build.splitlines() if line.startswith("Skills read:"))
    assert "profile default" in skills, skills
    assert any(item.strip().startswith("block:red-first-check@") and len(item.strip().split("@")[1]) == 8
               for item in skills.split(",")), skills
    assert "Rank each claim on the ladder" not in step_text(folder, "02-design")
    # A second start on the folder writes nothing, even when the catalog now fails.
    (repo.parent / "home" / ".flow" / "domains.md").write_text("## any\n- build: block:nope\n", encoding="utf-8")
    again = run("start")
    assert again.returncode == 0 and step_text(folder, "05-build") == build, again.stderr


def test_block_alias_and_base(tmp):
    """D2: an alias expands to its members, duplicates drop, and base joins every step once."""
    out, folder, _, _ = blocks_start(tmp, "d2", "- design: block:tech-diagram, block:html-diagram\n- build: block:red-first-check\n")
    assert out.returncode == 0, out.stderr
    design = step_text(folder, "02-design")
    for block in ("first-principles", "tech-diagram-concept", "html-diagram"):
        assert design.count(f"===== block:{block} =====") == 1, (block, design)
    for step in ("01-frame", "04-impact", "05-build", "07-close"):
        assert step_text(folder, step).count("===== block:first-principles =====") == 1, step


def rule_lines(text):
    """The rule, todo, and check lines of a step file, without Example sections."""
    lines, example = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            example = line == "## Example"
        elif line.startswith("- ") and not example:
            lines.append(line)
    return sorted(lines)


def test_block_profile(tmp):
    """D3: the merged profile writes each alias as one block and folds base in, with the same rule and
    check lines as the split form, and drops the Example sections."""
    catalog = "- design: block:tech-diagram, block:style-frames, block:look-grammar\n"
    split, split_folder, _, _ = blocks_start(tmp, "d3-split", catalog)
    merged, merged_folder, _, _ = blocks_start(tmp, "d3-merged", catalog, PARAMS, "--profile", "merged")
    assert split.returncode == 0 and merged.returncode == 0, (split.stderr, merged.stderr)
    a, b = step_text(split_folder, "02-design"), step_text(merged_folder, "02-design")
    assert a.count("===== block:") == 6 and b.count("===== block:") == 3, b
    assert "===== block:tech-diagram =====" in b and "===== block:style-frames =====" in b, b
    assert "## Example" in a and "## Example" not in b
    assert "profile merged" in b.splitlines()[3], b.splitlines()[3]
    assert rule_lines(a) == rule_lines(b), set(rule_lines(a)) ^ set(rule_lines(b))
    assert rule_lines(step_text(split_folder, "06-review")) == rule_lines(step_text(merged_folder, "06-review"))


def test_block_params(tmp):
    """D4: {{name}} takes its value from the repo's .blocks.toml; a missing one stops start and names it."""
    out, folder, _, _ = blocks_start(tmp, "d4", "- review: block:diagram-correctness\n")
    assert out.returncode == 0, out.stderr
    review = step_text(folder, "06-review")
    assert "The source of truth is docs/spec.md." in review and "{{" not in review, review
    out, folder, repo, _ = blocks_start(tmp, "d4-missing", "- review: block:diagram-correctness\n", "")
    assert out.returncode == 1 and "{{source_of_truth}}" in out.stderr and "Traceback" not in out.stderr, out.stderr
    assert not (repo / "tmp" / "flow").exists(), "a failed start must not leave a folder"


def test_block_fail_closed(tmp):
    """D5: start stops with a one-line reason and makes no folder."""
    cases = [
        ("unknown", "- build: block:nope\n", PARAMS, (), "unknown block id nope"),
        ("off-empty", "- design: block:tech-diagram\n", PARAMS + '[off]\nhtml-diagram = " "\n', (), "[off] html-diagram needs a reason"),
        ("off-unknown", "- design: block:tech-diagram\n", PARAMS + '[off]\nnope = "x"\n', (), "unknown block id nope"),
        ("duplicate", "- build: block:red-first-check\n", PARAMS + '[add]\nbuild = ["red-first-check.md"]\n', (), "duplicate block id red-first-check"),
        ("profile", "- build: block:red-first-check\n", PARAMS, ("--profile", "nope"), "unknown profile nope"),
    ]
    Path(tmp, "duplicate", "app").mkdir(parents=True)
    Path(tmp, "duplicate", "app", "red-first-check.md").write_text("# red-first-check\n", encoding="utf-8")
    # An [add] path must stay inside the repo: absolute, `..`, and a symlink out are refused.
    for name, path in (("add-absolute", str(Path(tmp, "add-absolute", "outside.md"))),
                       ("add-parent", "../outside.md"), ("add-symlink", "link.md")):
        Path(tmp, name, "app").mkdir(parents=True)
        Path(tmp, name, "outside.md").write_text("# outside\nSECRET\n", encoding="utf-8")
        cases.append((name, "- build: block:red-first-check\n", PARAMS + f'[add]\nbuild = ["{path}"]\n', (),
                      f"[add] {path} leaves the repo"))
    Path(tmp, "add-symlink", "app", "link.md").symlink_to(Path(tmp, "add-symlink", "outside.md"))
    # A repo block whose id equals a kit alias name would mix with the alias.
    Path(tmp, "add-alias", "app", "docs").mkdir(parents=True)
    Path(tmp, "add-alias", "app", "docs", "tech-diagram.md").write_text("# tech-diagram\n", encoding="utf-8")
    cases.append(("add-alias", "- build: block:red-first-check\n", PARAMS + '[add]\nbuild = ["docs/tech-diagram.md"]\n', (),
                  "has id tech-diagram, which is an alias"))
    # A TOML syntax error or a wrong value type in the repo file names the file, with no traceback.
    # A top-level key goes before [params], or TOML puts it in that table.
    cases += [(f"type-{name}", "- build: block:red-first-check\n", toml, (), reason) for name, toml, reason in (
        ("syntax", "[params\nx = 1\n", ".blocks.toml is not valid TOML"),
        ("params", "params = 3\n", ".blocks.toml: params must be a table"),
        ("off", "off = 3\n" + PARAMS, ".blocks.toml: off must be a table"),
        ("add", "add = 3\n" + PARAMS, ".blocks.toml: add must be a table"),
        ("add-string", PARAMS + '[add]\nbuild = "docs/x.md"\n', "must be a list of paths"))]
    cases += [
        ("add-missing", "- build: block:red-first-check\n", PARAMS + '[add]\nbuild = ["docs/none.md"]\n', (), "[add] docs/none.md in"),
        ("add-step", "- build: block:red-first-check\n", PARAMS + '[add]\nship = ["docs/x.md"]\n', (), "[add] ship in"),
        ("table", "- build: block:red-first-check\n", PARAMS + "[extra]\nx = 1\n", (), "unknown table [extra]"),
    ]
    # Bytes that are not UTF-8 in the repo file or in an [add] block name the file, with no traceback.
    Path(tmp, "utf8-toml", "app").mkdir(parents=True)
    Path(tmp, "utf8-toml", "app", ".blocks.toml").write_bytes(PARAMS.encode() + b'x = "\xff"\n')
    cases.append(("utf8-toml", "- build: block:red-first-check\n", None, (), ".blocks.toml is not UTF-8"))
    Path(tmp, "utf8-add", "app", "docs").mkdir(parents=True)
    Path(tmp, "utf8-add", "app", "docs", "x.md").write_bytes(b"# x\n\xff\n")
    cases.append(("utf8-add", "- build: block:red-first-check\n", PARAMS + '[add]\nbuild = ["docs/x.md"]\n', (), "x.md is not UTF-8"))
    for name, catalog, repo_toml, args, reason in cases:
        out, _, repo, _ = blocks_start(tmp, name, catalog, repo_toml, *args)
        assert out.returncode == 1 and reason in out.stderr and "Traceback" not in out.stderr, (name, out.stderr)
        assert len(out.stderr.strip().splitlines()) == 1, (name, out.stderr)
        assert not (repo / "tmp" / "flow").exists(), name
    # A bad block catalog stops the load with a reason that names it.
    kit = Path(tmp, "kit")
    kit.mkdir()
    (kit / "a.md").write_text("# a\n", encoding="utf-8")
    for toml, reason in (('base = []\n[blocks]\na = "a.md"\n[aliases]\na = ["a"]\n[profiles.default]\n', "alias a is also a block id"),
                         ("[blocks\n", "blocks.toml is not valid TOML"),
                         ('[blocks]\na = "a.md"\n[aliases]\nb = ["nope"]\n[profiles.default]\n', "unknown block id nope in alias b"),
                         ('[blocks]\na = "a.md"\n[profiles.default]\nmerge = ["a"]\n', "merges a, which is not an alias")):
        (kit / "blocks.toml").write_text(toml, encoding="utf-8")
        with patch.object(flow_run, "BLOCKS", kit):
            try:
                flow_run.resolve_blocks(Path(tmp), {"build": ["a"]}, "default")
                raise AssertionError(f"start must stop: {reason}")
            except SystemExit as error:
                assert reason in str(error) and "\n" not in str(error), error


def test_block_repo_file(tmp):
    """The repo's [add] puts its own block into a step, and an [off] entry with a reason drops a block
    and says so in the step it would have joined."""
    Path(tmp, "repo-file", "app", "docs").mkdir(parents=True)
    Path(tmp, "repo-file", "app", "docs", "our-api.md").write_text(
        "# our-api\nConcept: x\n\n## Rules\n- OUR RULE 7\n\n## Check (script)\n- `true` runs: it proves nothing\n\n## Check (judge)\n", encoding="utf-8")
    out, folder, _, _ = blocks_start(tmp, "repo-file", "- design: block:tech-diagram\n",
                                     PARAMS + '[add]\nbuild = ["docs/our-api.md"]\n[off]\nhtml-diagram = "this repo draws SVG"\n')
    assert out.returncode == 0, out.stderr
    build = step_text(folder, "05-build")
    assert "===== block:our-api =====" in build and "OUR RULE 7" in build and "- [ ] block our-api script: `true` runs: it proves nothing: " in build, build
    design = step_text(folder, "02-design")
    assert "Off: html-diagram: this repo draws SVG" in design and "===== block:html-diagram" not in design, design
    assert "block html-diagram" not in design and "block html-diagram" not in step_text(folder, "06-review")


def test_block_ascii_locale(tmp):
    """start writes the UTF-8 block text (`…` in web-ui-basics) under an ASCII locale."""
    ascii_env = {"LC_ALL": "C", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0"}
    out, folder, _, _ = blocks_start(tmp, "ascii", "- build: block:web-ui-basics\n", env=ascii_env)
    assert out.returncode == 0, out.stderr
    assert "…" in step_text(folder, "05-build")


def test_block_checks(tmp):
    """D6: Check (script) lines become step todos; Check (judge) lines go to 06-review only, and done
    refuses a checked block todo with no evidence even when its command holds a colon."""
    out, folder, _, run = blocks_start(tmp, "d6", "- build: block:html-diagram\n")
    assert out.returncode == 0, out.stderr
    build, review = step_text(folder, "05-build"), step_text(folder, "06-review")
    todo = build.split(flow_run.TODO_HEAD)[1]
    script = "- [ ] block html-diagram script: `rg -o '<figure[ >]' site | wc -l` and `rg -o '<figcaption' site | wc -l` print the same number: each figure has a caption.: "
    assert script + "\n" in todo, todo
    assert "script: none:" not in todo, "a `- none:` line says why a block has no script check; it is no todo"
    judge ="At 375 px, does each arrow still point from its source to its target?"
    assert judge not in build, "a judge check must not be a build todo"
    assert "## Judge checks of blocks that ran" in review and judge in review.split("## Judge checks of blocks that ran")[1]
    assert "block first-principles judge: Does every fact in the result trace to a line in docs/spec.md?" in review, review
    assert review.count("block first-principles judge:") == 2, "base judge lines appear once per run"
    f = folder / "05-build.md"
    fill(f)
    text = f.read_text(encoding="utf-8")
    f.write_text(text.replace(script.replace("- [ ]", "- [x]").rstrip() + " evidence", script.replace("- [ ]", "- [x]").rstrip()), encoding="utf-8")
    refused = run("done", folder, "05-build")
    assert refused.returncode == 1 and "no evidence: - [x] block html-diagram script:" in refused.stderr, refused.stderr


with tempfile.TemporaryDirectory() as tmp:
    home, repo = Path(tmp, "home"), Path(tmp, "app")
    (home / ".flow" / "app").mkdir(parents=True)
    rule = Path(tmp, "rule.md")
    rule.write_text("RULE TEXT 42\n")
    (home / ".flow" / "domains.md").write_text(f"## any\n- build: {rule}\n## web\n- build: {rule}, /nope.md\n")
    (home / ".flow" / "app" / "profile.md").write_text("Domains: any\nRepo rules: none\n")
    repo.mkdir()
    env = {**os.environ, "HOME": str(home), "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    run = lambda *a: subprocess.run([sys.executable, SCRIPT, *map(str, a)], cwd=repo, env=env, capture_output=True, text=True)
    git = lambda *a: subprocess.run(["git", *a], cwd=repo, env=env, capture_output=True, text=True, check=True).stdout.strip()
    git("init", "-q", "-b", "main")
    (repo / "app.py").write_text("def parse_phone(s):\n    return s\n\nprint(parse_phone('1'))\n")
    git("add", "app.py")
    git("commit", "-q", "-m", "one")

    folder = Path(run("start").stdout.splitlines()[0])
    assert "RULE TEXT 42" in (folder / "05-build.md").read_text()
    assert "RULE TEXT 42" not in (folder / "02-design.md").read_text()
    assert sorted(p.name for p in folder.glob("0*.md"))[0] == "01-frame.md"
    assert "Branch: main" in (folder / "01-frame.md").read_text()
    assert "Take with:" in (folder / "05-build.md").read_text()
    assert "/tmp/" in (repo / ".git" / "info" / "exclude").read_text()
    # The folder carries its step graph on each Uses line, and 05-build names its revision rule,
    # so a reader without this script (the Swarm app) can draw the graph and judge stale.
    uses = {p.stem: p.read_text().splitlines()[1] for p in folder.glob("0*.md")}
    assert uses["01-frame"] == "Uses:" and uses["04-impact"] == "Uses: 03-contracts", uses
    assert uses["05-build"] == "Uses: 04-impact, 02-design" and uses["07-close"] == "Uses: 06-review", uses
    assert "\nRevision: HEAD\n" in (folder / "05-build.md").read_text()
    assert "Revision:" not in (folder / "06-review.md").read_text()
    # A catalog with no block item writes no block, no profile, and no judge section (old behaviour).
    assert all("block:" not in text and "Judge checks" not in text
               for text in (p.read_text(encoding="utf-8") for p in folder.glob("0*.md")))

    test_skip_text_encoding()
    test_review_read_encoding()
    test_command_wrong_count(run, folder)
    test_done_wrong_count(run, folder)
    test_take_force(run, folder)
    test_take_requires_who(run, folder)
    test_done_rejects_force(run, folder)
    test_closed_stdout(repo, env, folder)

    blocked = run("take", folder, "05-build", "a")
    assert blocked.returncode != 0 and "needs 04-impact, 02-design" in blocked.stderr

    # Only design, contracts, and impact can be skipped, and only with a reason.
    assert "cannot be skipped" in run("skip", folder, "05-build", "small").stderr
    assert "skip <folder> <step> <why>" in run("skip", folder, "02-design").stderr
    test_skip_plain_reason(run, folder)
    test_skip_lock(run, folder)
    test_skip_rejects_force(run, folder)
    test_atomic_skip(folder)
    assert run("skip", folder, "02-design", "no", "UI").returncode == 0
    assert (folder / "02-design.md").read_text().startswith("Status: skipped no UI\n")

    for step in ("01-frame", "03-contracts"):
        assert run("take", folder, step, "a").returncode == 0
        fill(folder / f"{step}.md")
        assert run("done", folder, step).returncode == 0, step
    c = folder / "03-contracts.md"
    c.write_text(c.read_text() + "`parse_phone()` rejects an empty string. `app.py` and `init` stay.\n")

    # take 04-impact writes the places that name each code name of the contracts.
    test_callers_after_claim(run, folder)
    test_impact_closed_stdout(repo, env, folder)
    test_impact_utf8(repo, env, folder)
    test_callers_timeout(folder)
    test_callers_long_stderr(folder)
    test_callers_stdout_utf8_cut(folder)
    test_callers_stderr_utf8_cut(folder)
    test_callers_large_output(folder)
    test_callers_long_line(folder)
    test_callers_failure(folder)
    test_callers_deadline(folder)
    test_callers_name_cap(folder)
    test_callers_controls(repo, run, folder)
    out = run("take", folder, "04-impact", "a")
    assert out.returncode == 0, out.stderr
    assert flow_run.CALLERS_HEAD in out.stdout, "take must print the complete impact file"
    assert out.stdout == (folder / "04-impact.md").read_text() + "\n"
    impact = (folder / "04-impact.md").read_text()
    assert "### parse_phone (2 places)" in impact and "app.py:1:" in impact and "### init" not in impact
    assert impact.index("## Callers") < impact.index("## Result")
    fill(folder / "04-impact.md")
    assert run("done", folder, "04-impact").returncode == 0

    out = run("take", folder, "05-build", "agent-b")
    assert out.returncode == 0 and "RULE TEXT 42" in out.stdout
    text = (folder / "05-build.md").read_text()
    assert text.startswith("Status: active agent-b") and f"Skills read: {rule}" in text and text.rstrip().endswith("## Result")
    assert "05-build: active agent-b" in run("status", folder).stdout
    refused = run("done", folder, "05-build")
    assert refused.returncode != 0 and "Failing check first" in refused.stderr
    f = folder / "05-build.md"
    f.write_text(f.read_text().replace("- [ ] Task file path and Base commit (pair or deliver): ",
                                       "- [x] Task file path and Base commit (pair or deliver): "))
    assert "no evidence" in run("done", folder, "05-build").stderr
    fill(f)
    head = git("rev-parse", "HEAD")
    assert run("done", folder, "05-build").returncode == 0 and f.read_text().startswith(f"Status: done {head[:12]}\n")

    # Close needs the review-check run's own APPROVE verdict on the current head.
    out = run("take", folder, "06-review", "a")
    assert out.returncode == 0 and "bring the open rows" not in out.stdout
    r = folder / "06-review.md"
    review_text = r.read_text()
    for count in (1, 2, 3):
        r.write_text(review_text + "".join(f"Run: tmp/review-check/range-{i}\n" for i in range(count)))
        out = run("take", folder, "06-review", "a")
        assert out.returncode == 0, out.stderr
        warning = f"06-review already lists {count} runs; bring the open rows to the user before a new range"
        assert out.stdout.splitlines().count(warning) == (1 if count >= 2 else 0)
        if count < 2:
            assert "bring the open rows" not in out.stdout
        assert r.read_text().startswith("Status: active a\n")
        assert [line for line in r.read_text().splitlines() if line.startswith("Run:")] == [
            f"Run: tmp/review-check/range-{i}" for i in range(count)], "take must keep one Run: line per round, newest last"
    r.write_text(review_text)
    review = Path(repo, "tmp", "review-check", "range-1")
    review.mkdir(parents=True)
    (review / "target.json").write_text(json.dumps({"head": head}))
    (review / "03-verdict.md").write_text("Status: done x\nUses:\nVerdict: REQUEST CHANGES (1 of 1 units; 1 fix)\n")
    fill(r)
    assert run("done", folder, "06-review").returncode == 0
    assert "needs a `Run:" in run("take", folder, "07-close", "a").stderr
    r.write_text(r.read_text() + "Run: tmp/review-check/range-1\n")
    assert "REQUEST CHANGES" in run("take", folder, "07-close", "a").stderr
    (review / "03-verdict.md").write_text("Status: done x\nUses:\nVerdict: NEEDS DISCUSSION (1 of 1 units; 1 ask)\n")
    assert "NEEDS DISCUSSION" in run("take", folder, "07-close", "a").stderr
    r.write_text(r.read_text() + "User accepted: ship it, the ask is a follow-up\n")
    refused = run("take", folder, "07-close", "a")
    assert refused.returncode != 0 and "NEEDS DISCUSSION" in refused.stderr, "User accepted: must not bypass the run's verdict"
    r.write_text(r.read_text().replace("User accepted: ship it, the ask is a follow-up\n", ""))
    (review / "03-verdict.md").write_text("Status: done x\nUses:\nVerdict: APPROVE (1 of 1 units; 0 fix)\n")

    # A new commit moves the build revision, so the review is stale and close refuses.
    (repo / "app.py").write_text((repo / "app.py").read_text() + "# fix\n")
    git("commit", "-q", "-am", "two")
    assert "06-review: done" in run("status", folder).stdout and "(stale: 05-build)" in run("status", folder).stdout
    assert "covers" in run("take", folder, "07-close", "a").stderr
    (review / "target.json").write_text(json.dumps({"head": git("rev-parse", "HEAD")}))
    assert run("take", folder, "07-close", "a").returncode == 0

    events = (folder / "events.log").read_text()
    assert "02-design\tskip no UI" in events and "07-close\ttake a" in events
    test_block_in_step(tmp)
    test_block_alias_and_base(tmp)
    test_block_profile(tmp)
    test_block_params(tmp)
    test_block_fail_closed(tmp)
    test_block_repo_file(tmp)
    test_block_checks(tmp)
    test_block_ascii_locale(tmp)
    print("ok")
