---
name: review-walk
description: Review a PR, local changes, or a commit range in seven steps (scope, map, cleanup, logic, rules, comments, walk), one status file per step under <repo>/tmp/review-walk/<run>/, and draft comments in the reviewer's own voice into a pending GitHub review that the reviewer submits. A new round shows each file's diff since the reviewer last viewed it. Use for "review pr <n>", "review-walk continue <run>", a code review of a branch or range, or when flow or deliver asks for a review verdict.
---

# review-walk

Example. `review-walk pr 42` makes `<repo>/tmp/review-walk/pr-42-01/` with seven step files.
The agent maps the files into groups, finds cleanup, logic, and repo-rule issues, and drafts 15
short comments in your voice. You say yes, and they go into your pending review on GitHub. You walk
the PR there, mark files viewed, edit or delete drafts, and submit. The author pushes again.
`review-walk pr 42` then makes `pr-42-02`, which shows only what changed in each file after you
viewed it, and marks the unchanged files viewed again on GitHub after you say yes.

## Contract

- The review is report-only. Never edit, commit, stash, switch, or reset the user's checkout.
  `git fetch` gets objects and `FETCH_HEAD` only.
- Never submit or publish a review. The user does it on GitHub.
- Every GitHub write (`post`, `remark`) needs the user's yes in chat for that run.
- Every finding quotes a line that is in `diff.patch` on the new side. A finding with no quote is
  dropped.
- Judge the change on its own merits. Messy code around it does not excuse a new defect.
- No findings about secrets in plain text in a public comment. Tell the user in chat instead.
- No style nits that a linter or formatter owns.

## Run folder

`<repo-root>/tmp/review-walk/<run>/`. `<run>` is `pr-<n>-NN`, `local-NN`, or
`range-<base7>-<head7>-NN`, where `NN` counts rounds of the same target. The script adds `/tmp/`
to `.git/info/exclude`, so no one else sees the folder.

```sh
W=<skill-dir>/scripts/review_walk.py
python3 $W start <pr-number|url|local|base..head>   # makes the run and writes 01-scope.md
python3 $W status [<run>]                            # status, ready, and stale for each step
python3 $W post <run> <run>/comments.json            # drafts into your pending review
python3 $W viewed <run>                              # records viewed marks for the next round
python3 $W remark <run>                              # marks unchanged-since-view files viewed
```

Run the script from the repo root. To continue in a new chat, run `status` and take the first
ready step.

## Status line

Line 1 is `Status: open | active <agent> | done <revision> | skipped <reason> | blocked <question>`.
Line 2 is `Uses: <step>@<revision>, ...`. The revision is
`tail -n +2 <file> | shasum | cut -c1-12`. A step is ready when every step it uses is done or
skipped, and stale when a revision in its `Uses:` line is no longer current. Redo a stale step, or
confirm that it still holds.

## Steps

| File | Who | Uses | Holds |
|---|---|---|---|
| `01-scope.md` | script | none | target, base, head, every file with its state: new to you, changed since view, unchanged since view, whitespace only |
| `02-map.md` | chair | 01 | files in groups by feature, in reading order, one line of purpose per group |
| `03-cleanup.md` | seat | 02 | readability findings from the cleanup part of the lens |
| `04-logic.md` | seat | 02 | correctness, limits, and performance findings from the logic part of the lens |
| `05-rules.md` | seat | 02 | findings from the repo's private rules file |
| `06-comments.md` | chair | 03, 04, 05 | the verdict, and the comments in the reviewer's voice |
| `07-walk.md` | user, chair | 06 | viewed marks, the user's own comments, what was submitted |

1. **Scope.** Run `start`. In a new round, review only the files that are new to you or changed
   since view, and read `since-view.patch` for the second kind. If `unchanged.txt` is not empty,
   tell the user the count and run `remark` after a yes.
2. **Map.** Put every file of `01-scope.md` into exactly one group. Use the PR body and the code
   to name each group, for example `s1 storage`, `s2 api routes`, `mig migrations`. Order the
   groups so a reader meets a type before its users. End with `Files: <mapped> of <total>`, and
   the two numbers must be equal.
3. **Cleanup, logic, rules.** These three steps are independent. With seats, give each one to a
   `review.deep` seat. With one session, do them in order. Each step reads `02-map.md`,
   `diff.patch`, and the full new version of each changed function, plus:
   - 03 reads the cleanup part of the lens, `minimize-reader-load`, and the repo's own convention
     files.
   - 04 reads the logic part of the lens, `engineering-standards`, and the `review` paths of each
     domain in `~/.flow/domains.md` whose `Signals:` line matches a changed file.
   - 05 reads `~/.review-walk/rules/<repo>.md`. `<repo>` is the folder name above the git common
     dir. With no rules file, the step is `skipped no rules for <repo>`.
   The lens is `references/lenses/backend.md` for server code. A file type with no lens gets only
   step 05.
   Each finding is one row: `| file:line | quoted new-side line | problem | kind | proof |`.
   `kind` is `fix` (a proved defect or a rule break), `ask` (a question, or a defect that is not
   proved), or `note` (optional cleanup or a reminder). `proof` names the input or the caller that
   triggers it, or `not confirmed`.
4. **Comments.** Merge the three steps. Drop duplicates, drop what the user already said in an
   earlier round or in a pending comment, and drop what a linter owns. Write each comment in the
   voice of `~/.review-walk/voice.md`, with the file-level or line-level choice it gives. With no
   voice file, write short plain comments: one clause, a question when the fix is a guess, no
   praise, no severity labels, and "potential issue, not confirmed:" before an unproved defect. Write
   `comments.json` as a list of `{path, body, first, last}`, where `first` and `last` are exact
   quotes from the new side and a file-level comment has no `first`.
   Line 3 of `06-comments.md` is `Verdict: APPROVE | REQUEST CHANGES | NEEDS DISCUSSION`. Any
   `fix` makes it REQUEST CHANGES, and an open `ask` about behavior makes it NEEDS DISCUSSION.
   Show the comments in chat, grouped by the groups of step 02. For a PR, run `post` only after
   the user says yes.
5. **Walk.** The user reads the PR on GitHub, edits or deletes drafts, adds their own comments,
   marks files viewed, and submits. Then run `viewed` and write in `07-walk.md` the count of viewed
   files and whether the review was submitted. For a local or range target, this step is skipped.

## Roles

The chair does steps 01, 02, 06, and 07, because they need the user. Steps 03 to 05 can go to
`review.deep` seats, as [orchestration.json](orchestration.json) declares. A seat writes only its
own step file and ends by setting line 1. Before the chair accepts a seat's step, it checks that
every quote is in `diff.patch`.

## Rules for each repo

`~/.review-walk/rules/<repo>.md` holds what the team of that repo cares about, from its own past
reviews. It stays out of this public skill, because it names internal code. This skill owns the format and the upkeep of those files. A rule that the repo's own docs already state points to that doc and is not
copied. Add a rule when the user or a teammate's review raises the same point on a third PR.

## Callers

`flow` step 06 and `deliver` read the verdict on line 3 of `06-comments.md`, from a range run on
`<base>..<head>`. They fix each `fix` comment and run a new round.
`pr-walkthrough` explains a change before review and never judges it.

## Output

In chat, give the verdict with its counts, then the comments by group, each with its `file:line`.
Then give the run folder and the next step.
