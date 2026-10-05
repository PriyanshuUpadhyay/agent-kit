"""Run: python3 test_flow_run.py  (uses a temporary repo and a temporary HOME)."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).with_name("flow_run.py")

with tempfile.TemporaryDirectory() as tmp:
    home, repo = Path(tmp, "home"), Path(tmp, "app")
    (home / ".flow" / "app").mkdir(parents=True)
    rule = Path(tmp, "rule.md")
    rule.write_text("RULE TEXT 42\n")
    (home / ".flow" / "domains.md").write_text(f"## any\n- build: {rule}\n## web\n- build: {rule}, /nope.md\n")
    (home / ".flow" / "app" / "profile.md").write_text("Domains: any\nRepo rules: none\n")
    repo.mkdir()
    env = {**os.environ, "HOME": str(home)}
    run = lambda *a: subprocess.run([sys.executable, SCRIPT, *a], cwd=repo, env=env, capture_output=True, text=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)

    folder = Path(run("start").stdout.splitlines()[0])
    assert "RULE TEXT 42" in (folder / "05-build.md").read_text()
    assert "RULE TEXT 42" not in (folder / "02-design.md").read_text()
    assert sorted(p.name for p in folder.glob("0*.md"))[0] == "01-frame.md"
    assert "Branch: main" in (folder / "01-frame.md").read_text()
    assert "Take with:" in (folder / "05-build.md").read_text()
    assert "/tmp/" in (repo / ".git" / "info" / "exclude").read_text()

    blocked = run("take", str(folder), "05-build")
    assert blocked.returncode != 0 and "needs 04-impact, 02-design" in blocked.stderr

    for step in ("01-frame", "02-design", "03-contracts", "04-impact"):
        f = folder / f"{step}.md"
        f.write_text(f.read_text().replace("Status: open", "Status: done abc"))
    out = run("take", str(folder), "05-build", "agent-b")
    assert out.returncode == 0 and "RULE TEXT 42" in out.stdout
    text = (folder / "05-build.md").read_text()
    assert text.startswith("Status: active agent-b") and f"Skills read: {rule}" in text and text.rstrip().endswith("## Result")
    assert "(ready)" in run("status", str(folder)).stdout or "05-build: active agent-b" in run("status", str(folder)).stdout
    refused = run("done", str(folder), "05-build")
    assert refused.returncode != 0 and "Failing check first" in refused.stderr
    f = folder / "05-build.md"
    body = f.read_text()
    f.write_text(body.replace("- [ ] Task file path and Base commit (pair or deliver): ", "- [x] Task file path and Base commit (pair or deliver): "))
    assert "no evidence" in run("done", str(folder), "05-build").stderr
    filled = "".join(l.replace("- [ ]", "- [x]").replace("- [x]", "- [x]").rstrip() + (" evidence\n" if l.startswith(("- [ ]", "- [x]")) else "\n")
                     for l in f.read_text().splitlines())
    f.write_text(filled)
    closed = run("done", str(folder), "05-build")
    assert closed.returncode == 0 and f.read_text().startswith("Status: done ")
    print("ok")
