---
name: flow
description: Run one feature through six steps (frame, design, contracts, impact, build, close), with one status file per step under ~/.flow and the domain skills that the repo profile names for each step. Use when the user says "flow continue <repo>/<folder>" or "flow start", or names a ~/.flow step file.
---

# Flow

Use a flow for a feature that changes many files. Do not use it for a one-line change.

## Start or continue

The user says "flow continue <repo>/<folder>". The folder is `~/.flow/<repo>/<YYYY-MM-DD>-<branch>/`.
`<repo>` is the name that the user types. If the user does not type it, it is the name of the
folder above the git common dir (`git rev-parse --git-common-dir`), not the worktree folder name.

1. If `~/.flow/<repo>/profile.md` does not exist, stop. Read the repo's build files, such as
   `Package.swift`, `package.json`, or `wrangler.toml`, and suggest the domains. Draft at most
   three skill paths per step from the skill packs that the user keeps. Show the draft, and write
   `~/.flow/<repo>/profile.md` only after the user confirms it. Tell the user that the new profile
   is not in version control yet.
2. If the folder does not exist, make it and make the six step files below, each with
   `Status: open`.
3. Read `01-frame.md`. If `Worktree:` or `Branch:` is not the current worktree and branch, stop and
   tell the user. If two open folders exist for one branch, stop and tell the user.
4. Take the step that the user gave you. With one pane only, take the first ready step.
5. Read the skill paths for that step in the profile. Read only those. When a tool that the
   profile names is missing, set the status to `unavailable <tool>` and tell the user.
6. Write only your step's file. Line 1 is the status.

## Status line

`Status: open | active <agent> | done <revision> | skipped <reason> | unavailable <tool>`

- The revision of `05-build` is the commit that you checked.
- The revision of any other step is the hash of its file below line 1:
  `tail -n +2 <file> | shasum | cut -c1-12`.
- Line 2 of each step is `Uses: <step>@<revision>, ...` for each step that it needs.
- A step is ready when each step that it needs is done or skipped.
- A step is stale when a revision in its `Uses:` line is no longer the current one. Its owner
  does it again or confirms that it still holds.

## Steps

| File | Needs | Holds |
|---|---|---|
| `01-frame.md` | none | `Worktree:`, `Branch:`, goal, user, out of scope, done-when |
| `02-design.md` | frame | UX flow and screens, or `skipped: no UI` |
| `03-contracts.md` | frame | APIs, data model, integrations, and the result of the `decisions` skill's check for the topic |
| `04-impact.md` | contracts | the existing features that change, or "independent" |
| `05-build.md` | impact, and design unless skipped | only the task-file path of the `pair` or `deliver` run that the user started |
| `06-close.md` | build | the done-when of `01-frame.md`, each with its evidence |

At close, move the folder to `~/.flow/<repo>/_closed/<folder>/`. Release is a separate action
that the user asks for.

## Owners

The flow owns the step list, the order, the status, and the profiles. `pair` or `deliver` owns
the plan, the chunks, and the commits; the flow never starts `deliver` by itself.
`prove-it-works` owns the choice of check and the evidence. `sequence-verifiable-units` owns the
unit order. `decisions` owns the ADRs. The flow never pushes.

## Trial log

This skill is on trial. At the end of each step file, add two lines:

- `Skills read: <paths>`
- `Helped: yes | no, <one example>`

Also add a line for each stall, wrong skill, or repeated manual step. These lines decide if the
skill stays, changes, or is removed.
