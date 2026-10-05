"""Run: python3 test_step_run.py"""
import subprocess, sys, tempfile
from pathlib import Path

SCRIPT = Path(__file__).with_name("step_run.py")
run = lambda *a: subprocess.run([sys.executable, SCRIPT, *map(str, a)], capture_output=True, text=True)
with tempfile.TemporaryDirectory() as tmp:
    skill = Path(tmp, "SKILL.md")
    skill.write_text("| File | Needs | Holds |\n|---|---|---|\n| `01-ask.md` | none | the question |\n"
                     "| `02-look.md` | ask | what the sources say |\n\nafter\n")
    folder = Path(tmp, "run")
    run("start", folder, skill)
    assert (folder / "02-look.md").read_text().splitlines()[1] == "Uses: 01-ask"
    assert run("take", folder, "02-look", "a").returncode != 0
    assert "the question" in run("done", folder, "01-ask").stderr
    f = folder / "01-ask.md"
    f.write_text(f.read_text().replace("- [ ] the question: ", "- [x] the question: why is the sky blue"))
    assert run("done", folder, "01-ask").returncode == 0 and f.read_text().startswith("Status: done ")
    out = run("take", folder, "02-look", "agent-b")
    assert out.returncode == 0 and "Uses: 01-ask@" in (folder / "02-look.md").read_text()
    assert "(ready)" not in run("status", folder).stdout.split("02-look")[1]
    assert "stale" not in run("status", folder).stdout
    f.write_text(f.read_text() + "a later edit\n")
    assert "02-look: active agent-b  (stale: 01-ask)" in run("status", folder).stdout
    events = [l.split("\t")[1:] for l in (folder / "events.log").read_text().splitlines()]
    assert events[0][0] == "01-ask" and events[0][1].startswith("done ") and events[1] == ["02-look", "take agent-b"]
    print("ok")
