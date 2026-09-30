---
name: review-check
description: Judge a commit range or uncommitted changes with a script-enforced verdict. A script splits the diff into units (changed functions, hunks, removed code), the reviewer writes one quoted row per unit, and the script gives APPROVE, REQUEST CHANGES, or NEEDS DISCUSSION only when every unit has a row. Use when flow, deliver, or review-walk needs a review verdict, or for "check this range". Not for a GitHub PR walk with comments in your voice, which review-walk owns.
---

# review-check

Example. deliver finishes on `feat-x` and runs `review-check a1b2c3d..HEAD`. The script finds 14
units in 6 files, among them `Pane.swift` `hunk 40-58`, because ctags cannot read Swift here. The
seats write rows for 13 units. `verdict` prints `INCOMPLETE (13 of 14 units ...)` and names the
missing unit, so the chair reviews it and runs `verdict` again. The result is `REQUEST CHANGES
(14 of 14 units; 2 fix, 0 ask, 1 note; rules: none)`, and deliver fixes the two `fix` rows.

## Contract

- The review is report-only. Never edit, commit, stash, switch, or reset the user's checkout.
- Only `verdict` writes the verdict. A reviewer never writes `03-verdict.md` or states a verdict that
  the script did not print.
- Every unit gets at least one row. A missing lens, rules file, or ctags language never skips a
  unit.
- Judge the change on its own merits. Messy code around it does not excuse a new defect.
- No style nits that a linter or formatter owns.

## Run

```sh
C=<skill-dir>/scripts/review_check.py
python3 $C start <base>..<head>     # or `local` for uncommitted changes; --patch FILE for a part
python3 $C verdict <run>            # exits 1 with the gaps, or writes 03-verdict.md
```

Run it from the repo root. The run folder is `<repo-root>/tmp/review-check/<run>/`, where `<run>`
is `range-<base7>-<head7>-NN` or `local-NN`, as `references/run-folder.md` describes.

| File | Who | Holds |
|---|---|---|
| `01-units.md` | script | target, rules file or `none`, and every unit with its file, symbol, and range |
| `02-review.md` | reviewer | one or more rows for each unit |
| `03-verdict.md` | script | line 3 is `Verdict: <word> (<n> of <m> units; <fix>, <ask>, <note>; rules: <file>)`, then each gap or kept row |

`head/` holds the new version of each changed file. Read full functions there, not in a checkout
that can move.

## Review

For each unit, read its full range in `head/`, the diff hunks, and its callers. Check it against:

- both parts of [references/lens.md](references/lens.md), and `lens-<language>.md` if one exists,
- `minimize-reader-load` for each new function, file, or module,
- `engineering-standards`, and the `review` paths of each domain in `~/.flow/domains.md` whose
  `Signals:` line matches the file,
- the repo's rules file that `01-units.md` names, and the repo's own convention docs.

Write each row as `| unit | file:line | quote | kind | problem | proof |`.

- `kind` is `pass`, `fix` (a proved defect or a rule break), `ask` (a question, or a defect that is
  not proved), or `note` (optional cleanup).
- `quote` is an exact part of one line. A `pass` quotes a line of its unit. Other kinds quote a
  line of the diff, new or removed.
- `proof` names the input, caller, or rule that triggers the problem. For a `pass`, it names the
  case that was checked, for example "empty list returns before the loop". A bare "ok" fails the
  gate.
- Escape a `|` inside a cell as `\|`.

Any `fix` gives REQUEST CHANGES. Else any `ask` gives NEEDS DISCUSSION. Else the verdict is
APPROVE.

## Seats

With seats, split the units into up to four sets and give each set to a `review.deep` seat, as
[orchestration.json](orchestration.json) declares. Each seat writes `02-review-<n>.md`, and
`verdict` reads all of them. With one session, write `02-review.md` alone.

## Rules for each repo

`~/.review-check/rules/<repo>.md` holds what the team of that repo cares about, from its own past
reviews. `<repo>` is the folder name above the git common dir. It stays out of this public skill,
because it names internal code. This skill owns the format and the upkeep of those files. A rule
that the repo's own docs already state points to that doc and is not copied. Add a rule when a
review raises the same point on a third PR.

## Callers

`flow` step 06, `deliver`, and `review-walk` step 03 read line 3 of `03-verdict.md`. A caller treats
`INCOMPLETE`, or a verdict file older than its range, as no review.

## Output

In chat, give line 3 of `03-verdict.md`, then each `fix`, `ask`, and `note` row with its
`file:line`, then the run folder.
