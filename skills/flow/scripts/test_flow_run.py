"""Run: python3 test_flow_run.py  (uses a temporary repo and a temporary HOME)."""
import json
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import flow_run

SCRIPT = Path(__file__).with_name("flow_run.py")


def fill(f, evidence="evidence"):
    """Check every todo of a step file with evidence, as an agent would."""
    f.write_text("".join(l.replace("- [ ]", "- [x]").rstrip() + (f" {evidence}\n" if l.startswith("- [") and l.rstrip().endswith(":") else "\n")
                         for l in f.read_text().splitlines()))


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
        assert not (folder / "01-frame.lock").exists()
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
        assert not (folder / "01-frame.lock").exists()


def test_atomic_skip(folder):
    file = folder / "02-design.md"
    original = file.read_text()
    real_replace = os.replace
    replaced = []

    def check_replace(source, destination):
        assert file.read_text() == original, "skip must preserve the old file until replacement"
        assert source.parent == file.parent and source.suffix == ".tmp" and destination == file
        assert (folder / "02-design.lock").exists(), "skip must hold the step lock during replacement"
        real_replace(source, destination)
        replaced.append(destination)

    with redirect_stdout(StringIO()), patch.object(flow_run.step_run.os, "replace", check_replace):
        flow_run.skip(folder, "02-design", "no", "UI")
    assert replaced == [file], "skip must replace the file atomically"
    assert file.read_text().startswith("Status: skipped no UI\n")
    file.write_text(original)


def test_skip_lock(run, folder):
    file = folder / "02-design.md"
    original = file.read_text()
    events = (folder / "events.log").read_text()
    lock = folder / "02-design.lock"
    lock.write_text("")
    try:
        out = run("skip", folder, "02-design", "no", "UI")
        assert out.returncode == 1 and "is being claimed; try again" in out.stderr, out
        assert file.read_text() == original and lock.exists()
        assert (folder / "events.log").read_text() == events
    finally:
        lock.unlink()


def test_callers_after_claim(run, folder):
    file = folder / "04-impact.md"
    original = file.read_text()
    lock = folder / "04-impact.lock"
    lock.write_text("")
    try:
        out = run("take", folder, "04-impact", "a")
        assert out.returncode == 1 and "is being claimed; try again" in out.stderr, out
        assert file.read_text() == original, "a refused claim must not write callers"
    finally:
        lock.unlink()
    seen = []

    def write_callers(path):
        assert file.read_text().startswith("Status: active a\n"), "the claim must finish before callers are written"
        seen.append(path)

    with redirect_stdout(StringIO()), patch.object(flow_run, "write_callers", write_callers):
        flow_run.take(folder, "04-impact", "a")
    assert seen == [folder]
    file.write_text(original)


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

    test_take_force(run, folder)
    test_take_requires_who(run, folder)
    test_closed_stdout(repo, env, folder)

    blocked = run("take", folder, "05-build", "a")
    assert blocked.returncode != 0 and "needs 04-impact, 02-design" in blocked.stderr

    # Only design, contracts, and impact can be skipped, and only with a reason.
    assert "cannot be skipped" in run("skip", folder, "05-build", "small").stderr
    assert "needs a reason" in run("skip", folder, "02-design").stderr
    test_skip_lock(run, folder)
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
    assert run("take", folder, "04-impact", "a").returncode == 0
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
    print("ok")
