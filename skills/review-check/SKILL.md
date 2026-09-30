---
name: review-check
description: Judge a commit range or uncommitted changes with a script-enforced verdict. A script splits the diff into units (changed functions, hunks, removed code), a checklist gives each unit every rule whose file glob and regex match it plus a reference check, seats answer each rule with a quoted row, and the script gives APPROVE, REQUEST CHANGES, or NEEDS DISCUSSION only when every rule of every unit has a result. Use when flow, deliver, or review-walk needs a review verdict, or for "check this range". Not for a GitHub PR walk with comments in your voice, which review-walk owns.
---

# review-check

Example. deliver finishes on `feat-x` and runs `review-check a1b2c3d..HEAD`. The script finds 14
units in 6 files. For `index.ts` `hunk 2365-2380` it lists 23 checks: the lens rules whose `Files:`
glob and `Applies:` regex match the hunk, among them `C-7` (magic number), the TypeScript and
Cloudflare rules that match, the repo's `T-` rules, and `REF`, with the 3 places that call the
changed method. Four seats work at the same time, one for each aspect. `verdict` prints
`INCOMPLETE (14 of 14 units, 301 of 305 checks ...)` and names the four missing IDs. The seats
answer them, and the result is `REQUEST CHANGES`, because `C-7` found `bytes / 32000` next to a
helper that already does that math.

## Contract

- The review is report-only. Never edit, commit, stash, switch, or reset the user's checkout.
- Only `verdict` writes the verdict. A reviewer never writes `03-verdict.md` or states a verdict that
  the script did not print.
- Every unit gets at least one row, and every rule ID in its checklist gets a result. A missing
  lens, rules file, or ctags language never skips a unit.
- The session that wrote the change never fills the checklist. In `flow`, `deliver`, and `pair`,
  the rows come from new seats.
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
| `01-units.md` | script | target, rules file or `none`, and every unit with its file, symbol, range, and count of checks |
| `checklist.json` | script | for each unit, the rule IDs that apply and, under `refs`, the places that name a symbol the unit defines or removes |
| `02-review.md` | reviewer | one or more rows for each unit |
| `03-verdict.md` | script | line 3 is `Verdict: <word> (<n> of <m> units, <c> of <t> checks; <fix>, <ask>, <note>; rules: <file>)`, then each gap or kept row |

`head/` holds the new version of each changed file. Read full functions there, not in a checkout
that can move.

## Review

For each unit, read its full range in `head/`, the diff hunks, and every place that
`checklist.json` lists under `refs`. Then check the unit against each rule ID in its checklist.
The rules live in `references/lens.md`, `references/lens-<name>.md`, and the repo's rules file that
`01-units.md` names. Also read `minimize-reader-load`, `engineering-standards`, the repo's own
convention docs, and the `review` paths of each domain in `~/.flow/domains.md` whose `Signals:`
line matches the file. A defect that no rule names is still a finding, with rule `-`.

`REF` means the change can break a place that names its symbol. Check each listed place against
the new signature, return shape, and meaning. For a removed symbol, each listed place is a
leftover reference.

Write each row as `| unit | rule | file:line | quote | kind | problem | proof |`.

- `rule` is one ID, a comma list of IDs for a `pass` or an `n/a` row, or `-`.
- `kind` is `pass` (the unit follows the rule), `n/a` (the rule cannot apply, for example "no SQL
  in this hunk"), `fix` (a proved defect or a rule break), `ask` (a question, or a defect that is
  not proved), or `note` (optional cleanup).
- `quote` is an exact part of one line. A `pass` or `n/a` quotes a line of its unit. Other kinds
  quote a line of the diff, new or removed.
- `proof` names the input, caller, or rule text that triggers the problem. For a `pass`, it names
  the case that was checked, for example "empty list returns before the loop". For an `n/a`, it
  says why the rule cannot apply. A bare "ok" fails the gate.
- Escape a `|` inside a cell as `\|`.

Any `fix` gives REQUEST CHANGES. Else any `ask` gives NEEDS DISCUSSION. Else the verdict is
APPROVE.

## Rule files

Each rule is one line: ``- `ID` flag → ask. Files: `<glob>, <glob>`. Applies: `<regex>`. Source: …``.
`Files:` is optional and falls back to the file's own `Files:` header line. `Applies:` is one
Python regex on the unit's code, new and removed; with none, the rule applies to every unit of a
matching file. A regex must never skip a unit that can break the rule, so leave it out when in
doubt. Add a `lens-<name>.md` for a new language or platform in the same shape.

## Seats

With seats, start one seat for each aspect on the route the table gives, as
[orchestration.json](orchestration.json) declares. The seats work at the same time, and each seat
answers its own IDs for every unit. A `pass` or `n/a` row may list many IDs with one quote and one
proof, so write one row for each group of IDs, not one row for each ID.

| Seat | Route | IDs | Writes |
|---|---|---|---|
| lens | `review.check` | `C-`, `L-` | `02-review-lens.md` |
| language | `review.check` | the IDs from `lens-<name>.md` | `02-review-lang.md` |
| repo | `review.check` | the IDs from the repo's rules file | `02-review-repo.md` |
| refs | `review.deep` | `REF`, and any finding it meets | `02-review-refs.md` |

REF stays on `review.deep`, because it judges a changed signature, return shape, or meaning at
each caller, and it must search past the first 20 references on its own.

`verdict` reads every `02-review*.md`. With one session and no seats, write `02-review.md` alone,
but only when that session did not write the change.

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
