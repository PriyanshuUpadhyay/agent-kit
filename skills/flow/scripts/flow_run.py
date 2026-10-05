#!/usr/bin/env python3
"""Make and take flow steps. Run from inside the repo.

  start                        make tmp/flow/<date>-<branch>/ with the seven step files
  status [<folder>]            print each step's status and whether it is ready
  take <folder> <step> [<who>] mark the step active and print the skills the catalog gives it
  done <folder> <step>         set the step done, only when every todo is checked with evidence

`start` writes the full text of each step's skills into that step's file, because an agent that gets
only a path often does not open it (Sonnet workers opened 0 of 4 pointer skills, 2026-10-04 and
2026-10-05), and every agent reads the step file it works on, on every provider. `take` prints them
again.
"""

import datetime
import hashlib
import re
import subprocess
import sys
from pathlib import Path

STEPS = {  # step file: (catalog key, steps it needs)
    "01-frame": ("frame", []),
    "02-design": ("design", ["01-frame"]),
    "03-contracts": ("contracts", ["01-frame"]),
    "04-impact": ("impact", ["03-contracts"]),
    "05-build": ("build", ["04-impact", "02-design"]),
    "06-review": ("review", ["05-build"]),
    "07-close": ("close", ["06-review"]),
}
CAP = 15000  # characters per skill; engineering-standards is about 10k
RULES_HEAD = "## Rules for this step (written by flow_run.py start; apply them, keep this section)"
RESULT_HEAD = "## Result"
TODO_HEAD = "## Todo (check a box only with its evidence after the colon; `done` refuses an empty one)"
TODOS = {  # each item names the file that owns the rule
    "01-frame": ["Goal, user, and out of scope (flow)", "Done-when, each one checkable (flow)",
                 "Lane, fast or full, and why (flow)"],
    "02-design": ["UX flow and screens, or the reason no UI changes (flow)"],
    "03-contracts": ["APIs, data model, and integrations that change (flow)",
                     "Standards rows that apply (engineering-standards)", "Decision check for the topic (decisions)"],
    "04-impact": ["Existing features that change, or independent (flow)"],
    "05-build": ["Task file path and Base commit (pair or deliver)",
                 "Failing check first: command and its failing output (prove-it-works)",
                 "Standards rows for each behavior, or none and why (engineering-standards)",
                 "Scope: each file touched and the part of the change that names it (AGENTS.md)",
                 "Dead code: what this change made unused, removed; older dead code, named (AGENTS.md)",
                 "Check passes: command and its passing output (prove-it-works)"],
    "06-review": ["review-check range, verdict, and each fix row with its fix or reason (review-check)"],
    "07-close": ["Each done-when of 01-frame with its evidence (prove-it-works)"],
}


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()


def flow_home():
    return Path.home() / ".flow"


def repo_name():
    return Path(git("rev-parse", "--path-format=absolute", "--git-common-dir")).parent.name


def status_of(folder, step):
    return (folder / f"{step}.md").read_text().splitlines()[0].removeprefix("Status: ")


def ready(folder, step):
    return all(status_of(folder, u).split()[0] in ("done", "skipped") for u in STEPS[step][1])


def start():
    root = git("rev-parse", "--show-toplevel")
    if not root:
        raise SystemExit("not in a git repository")
    branch = git("branch", "--show-current") or "detached"
    folder = Path(root) / "tmp" / "flow" / f"{datetime.date.today()}-{branch.replace('/', '-')}"
    exclude = Path(git("rev-parse", "--path-format=absolute", "--git-common-dir")) / "info" / "exclude"
    try:  # a sandboxed agent may not write inside .git
        exclude.parent.mkdir(exist_ok=True)
        if "/tmp/" not in (exclude.read_text().splitlines() if exclude.exists() else []):
            with exclude.open("a") as f:
                f.write("/tmp/\n")
    except OSError as error:
        print(f"note: could not add /tmp/ to {exclude}: {error}", file=sys.stderr)
    if not folder.exists():
        folder.mkdir(parents=True)
        for step in STEPS:
            extra = f"Worktree: {root}\nBranch: {branch}\n" if step == "01-frame" else ""
            paths = skill_paths(step)
            (folder / f"{step}.md").write_text(
                f"Status: open\nUses:\n{extra}Take with: python3 {Path(__file__).resolve()} take {folder} {step} <agent>\n"
                f"Skills read: {', '.join(paths) or 'none'}\n\n{RULES_HEAD}\n{skills_text(paths)}\n"
                f"{TODO_HEAD}\n" + "".join(f"- [ ] {item}: \n" for item in TODOS[step]) + f"\n{RESULT_HEAD}\n")
    print(folder)
    print(f"Each step file holds its rules, a todo list, and a result section. Close a step with: python3 {Path(__file__).resolve()} done <folder> <step>")


def status(folder=None):
    if folder is None:
        folders = sorted(p for p in Path(git("rev-parse", "--show-toplevel"), "tmp", "flow").glob("2*/"))
        if not folders:
            raise SystemExit("no flow folder")
        folder = folders[-1]
    folder = Path(folder)
    print(folder)
    for step in STEPS:
        print(f"{step}: {status_of(folder, step)}{'  (ready)' if status_of(folder, step) == 'open' and ready(folder, step) else ''}")


def skill_paths(step):
    """The catalog paths for this step: the `any` section, each profile domain, and the repo rules."""
    key = STEPS[step][0]
    profile = flow_home() / repo_name() / "profile.md"
    domains, repo_rules = {"any"}, []
    if profile.exists():
        text = profile.read_text()
        if m := re.search(r"^Domains:\s*(.+)$", text, re.M):
            domains |= {d.strip() for d in m.group(1).split(",") if d.strip()}
        if m := re.search(r"^Repo rules:\s*(.+)$", text, re.M):
            repo_rules = [r.strip() for r in m.group(1).split(",") if r.strip() and r.strip() != "none"]
    else:
        print(f"note: no profile at {profile}; the flow skill's start rule says what to do", file=sys.stderr)
    paths, section = [], None
    for line in (flow_home() / "domains.md").read_text().splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
        elif section in domains and line.startswith(f"- {key}:"):
            paths += [p.strip() for p in line.split(":", 1)[1].split(",") if p.strip()]
    root = Path(git("rev-parse", "--show-toplevel"))
    return list(dict.fromkeys(paths)) + [str(root / r) for r in repo_rules]


def take(folder, step, who="agent"):
    folder = Path(folder)
    if step not in STEPS:
        raise SystemExit(f"unknown step {step}; steps are {', '.join(STEPS)}")
    if not ready(folder, step):
        waiting = [u for u in STEPS[step][1] if status_of(folder, u).split()[0] not in ("done", "skipped")]
        raise SystemExit(f"{step} is not ready; it needs {', '.join(waiting)}")
    file = folder / f"{step}.md"
    text = file.read_text()
    file.write_text(f"Status: active {who}\n" + text.split("\n", 1)[1])
    print(f"{step} is active. Apply the rules below, write the result under '{RESULT_HEAD}', and set it done.")
    print(text.split(RULES_HEAD, 1)[1].split(RESULT_HEAD, 1)[0] if RULES_HEAD in text else skills_text(skill_paths(step)))


def done(folder, step):
    file = Path(folder) / f"{step}.md"
    text = file.read_text()
    todo = text.split(TODO_HEAD, 1)[1].split(RESULT_HEAD, 1)[0] if TODO_HEAD in text else ""
    open_items = [l for l in todo.splitlines() if l.startswith("- [ ]")]
    empty = [l for l in todo.splitlines() if l.startswith("- [x]") and not l.split(":", 1)[-1].strip()]
    if open_items or empty:
        raise SystemExit(f"{step} is not done:\n" + "\n".join(open_items + [f"no evidence: {l}" for l in empty]))
    rest = text.split("\n", 1)[1]
    revision = hashlib.sha1(rest.encode()).hexdigest()[:12]
    file.write_text(f"Status: done {revision}\n{rest}")
    print(f"{step}: done {revision}")


def skills_text(paths):
    parts = []
    for path in paths:
        p = Path(path).expanduser()
        if not p.exists():
            parts.append(f"===== {path} (missing) =====")
            continue
        text = p.read_text()
        cut = f" (first {CAP} characters; read the file for the rest)" if len(text) > CAP else ""
        parts.append(f"===== {path}{cut} =====\n{text[:CAP]}")
    return "\n".join(parts)


if __name__ == "__main__":
    commands = {"start": start, "status": status, "take": take, "done": done}
    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        raise SystemExit(__doc__)
    commands[sys.argv[1]](*sys.argv[2:])
