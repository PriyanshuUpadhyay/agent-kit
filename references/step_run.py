#!/usr/bin/env python3
"""Step-run files for any skill with a step table (| File | Needs | Holds |). See step-run.md.

  start <folder> <SKILL.md>    make one step file per table row, each with a todo and a result section
  status <folder>              print each step's status and whether it is ready
  take <folder> <step> <who>   mark the step active and print its file
  done <folder> <step>         set the step done, only when every todo is checked with evidence
"""

import hashlib
import re
import sys
from pathlib import Path

TODO_HEAD = "## Todo (check a box only with its evidence after the colon; `done` refuses an empty one)"
RESULT_HEAD = "## Result"


def table(skill_md):
    """Rows of the first table whose header starts with | File | Needs | Holds |."""
    rows, inside = [], False
    for line in Path(skill_md).read_text().splitlines():
        if re.match(r"\|\s*File\s*\|\s*Needs\s*\|\s*Holds\s*\|", line):
            inside = True
        elif inside and line.startswith("|") and not line.startswith("|---"):
            cells = [c.strip().strip("`") for c in line.strip("|").split("|")]
            rows.append((cells[0].removesuffix(".md"), cells[1], cells[2]))
        elif inside and not line.startswith("|"):
            break
    if not rows:
        raise SystemExit(f"no | File | Needs | Holds | table in {skill_md}")
    return rows


def needs(folder, step):
    line = (Path(folder) / f"{step}.md").read_text().splitlines()[1]
    return [n.strip().split("@")[0] for n in line.removeprefix("Uses:").split(",") if n.strip()]


def revision(folder, step):
    rest = (Path(folder) / f"{step}.md").read_text().split("\n", 1)[1]
    return hashlib.sha1(rest.encode()).hexdigest()[:12]


def status_of(folder, step):
    return (Path(folder) / f"{step}.md").read_text().splitlines()[0].removeprefix("Status: ")


def steps(folder):
    return sorted(p.stem for p in Path(folder).glob("[0-9][0-9]-*.md"))


def ready(folder, step):
    return all(status_of(folder, n).split()[0] in ("done", "skipped") for n in needs(folder, step))


def start(folder, skill_md):
    folder = Path(folder)
    rows = table(skill_md)
    names = [r[0] for r in rows]
    folder.mkdir(parents=True, exist_ok=True)
    for name, need, holds in rows:
        file = folder / f"{name}.md"
        if file.exists():
            continue
        # A Needs cell names steps by their word ("question", "local, web"); map each to its file.
        need_files = [n for word in re.split(r",|\band\b", need) if word.strip() and word.strip() != "none"
                      for n in names if n.split("-", 1)[1].startswith(word.strip().split()[0])]
        file.write_text(f"Status: open\nUses: {', '.join(dict.fromkeys(need_files))}\n\n"
                        f"{TODO_HEAD}\n- [ ] {holds}: \n\n{RESULT_HEAD}\n")
    print(folder)


def status(folder):
    for step in steps(folder):
        s = status_of(folder, step)
        print(f"{step}: {s}{'  (ready)' if s == 'open' and ready(folder, step) else ''}")


def take(folder, step, who):
    if not ready(folder, step):
        raise SystemExit(f"{step} is not ready; it needs {', '.join(needs(folder, step))}")
    file = Path(folder) / f"{step}.md"
    text = file.read_text()
    uses = ", ".join(f"{n}@{revision(folder, n)}" for n in needs(folder, step))
    lines = text.split("\n")
    file.write_text("\n".join([f"Status: active {who}", f"Uses: {uses}", *lines[2:]]))
    print(file.read_text())


def done(folder, step):
    file = Path(folder) / f"{step}.md"
    text = file.read_text()
    todo = text.split(TODO_HEAD, 1)[1].split(RESULT_HEAD, 1)[0] if TODO_HEAD in text else ""
    open_items = [l for l in todo.splitlines() if l.startswith("- [ ]")]
    empty = [l for l in todo.splitlines() if l.startswith("- [x]") and not l.split(":", 1)[-1].strip()]
    if open_items or empty:
        raise SystemExit(f"{step} is not done:\n" + "\n".join(open_items + [f"no evidence: {l}" for l in empty]))
    rev = revision(folder, step)
    file.write_text(f"Status: done {rev}\n" + text.split("\n", 1)[1])
    print(f"{step}: done {rev}")


if __name__ == "__main__":
    commands = {"start": start, "status": status, "take": take, "done": done}
    if len(sys.argv) < 3 or sys.argv[1] not in commands:
        raise SystemExit(__doc__)
    commands[sys.argv[1]](*sys.argv[2:])
