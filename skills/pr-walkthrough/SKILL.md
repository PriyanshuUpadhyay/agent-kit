---
name: pr-walkthrough
description: Explain what a pull request or diff does so a reviewer understands it before judging it. Plain-language walkthrough ordered by logic, worked examples, and every claim cited to a real diff line. It never judges a change; review-pr does that. Use when someone wants to understand, make sense of, or be walked through a PR or diff they are reviewing, even when they do not say the word explain.
---

# pr-walkthrough — help a reviewer understand a PR from first principles

This workflow is report-only comprehension. It may write only temporary walkthrough artifacts.
Workers follow the active runtime adapter's `Worker contract` section.

The user's repository is read-only in the strongest sense: this walkthrough leaves their working
tree, index, refs, object store, config, and worktree metadata byte-for-byte untouched. Never check
a PR out in place; never run `git checkout`, `git switch`, `git stash`, `git reset`, `git fetch`, or
`git worktree` against it. Post-change files come from a self-contained clone under `$PRDIR`,
removed in step 5. Every git command that writes anything carries `git -C "$HEAD_DIR"`.

Your job: turn an opaque diff into a clear mental model so a human can *actually review* the change instead of rubber-stamping or rejecting it out of confusion. You explain **what** it does and **why**, in plain language, grounded in the real diff. You are not the judge — `review-pr` judges the same change and returns verdicts and a recommendation; `council` decides good/bad. Comprehension first, judgment second, artifacts kept apart. Mixing the two destroys the value of both: a comprehension artifact that smuggles in verdicts anchors the reviewer (and, if fed to the council, corrupts judge independence).

Two failure modes define this skill, and the whole design exists to prevent them:
1. **Hallucinated-but-formatted citations.** A polished `[file:42]` that points at nothing has *more* authority than an honest "I'm not sure" — so the reviewer stops spot-checking exactly when they shouldn't. Defense: cite only from the real diff, then verify mechanically (step 4). This is non-negotiable; without it the skill is just another confident summarizer.
2. **Drift into judgment / noise.** Severity scores, approve/reject, bug-hunting, whole-repo tangents, padding. Noise is the #1 documented complaint about AI review tools. Defense: scope guardrails + anti-patterns below. High signal, low volume.

## 0. Resolve the target — fail closed

Normalize the user's request into one target before running any command. `PR_TARGET` is a PR number,
a PR URL, `owner/repo#number`, a branch name, or the literal `local` for an unpushed change. Take it
from the arguments supplied with the invocation; when the invocation supplies none, take it from the
user's request text.

```bash
PR_TARGET="<the normalized target>"
test -n "$PR_TARGET" || { echo "no walkthrough target: ask for a PR number, URL, branch, or local"; exit 1; }
case "$PR_TARGET" in
  *'#'*)
    PR_REPO=${PR_TARGET%#*}
    PR_NUMBER_INPUT=${PR_TARGET##*#}
    case "$PR_REPO" in */*) ;; *) echo "invalid owner/repo#number target"; exit 1;; esac
    case "$PR_NUMBER_INPUT" in ''|*[!0-9]*) echo "invalid PR number"; exit 1;; esac
    PR_ARGS=(--repo "$PR_REPO" "$PR_NUMBER_INPUT")
    ;;
  *) PR_ARGS=("$PR_TARGET") ;;
esac
```

With no resolvable target, stop and ask. Do not guess the newest PR or the current branch.

## 1. Get the diff — it is the ground truth

Fetch the real diff and save it to a fresh temporary directory, so two concurrent walkthroughs never
collide and stale content cannot bleed into the draft. Also set `SKILL_ROOT` to the directory
containing this loaded `SKILL.md`; resolve it from the active skill discovery path.

`$HEAD_DIR` is the post-change tree the citation rule reads (§3, §4). It is a **separate clone**
inside `$PRDIR` with its own `.git`, so it works the same whether or not you stand in the PR's
repository, and it cannot reach the user's object store, refs, or worktree metadata.

```bash
SAFE=$(printf '%s' "$PR_TARGET" | tr -cd 'A-Za-z0-9' | cut -c1-40)       # a URL / owner/repo#num / branch
mkdir -p /tmp/pr-walkthrough
PRDIR=$(mktemp -d "/tmp/pr-walkthrough/pr-${SAFE:-local}-XXXXXX")
HEAD_DIR="$PRDIR/head"
# GitHub PR (number, URL, or branch):
gh pr diff "${PR_ARGS[@]}" > "$PRDIR/diff.patch"
gh pr view "${PR_ARGS[@]}" --json number,url,title,body,files,commits,headRefName,headRepository > "$PRDIR/meta.json"  # repo identity in meta.json, not the dirname
PR_NUMBER=$(gh pr view "${PR_ARGS[@]}" --json number --jq .number)
BASE_REPO=$(gh pr view "${PR_ARGS[@]}" --json url --jq .url | sed -E 's#/pull/[0-9]+.*##')   # host-agnostic base repo URL
gh repo clone "$BASE_REPO" "$HEAD_DIR" -- --no-checkout --filter=blob:none --quiet       # drop --filter on a host without partial clone
git -C "$HEAD_DIR" fetch --no-tags --quiet origin "refs/pull/$PR_NUMBER/head"            # the base repo serves fork heads too
git -C "$HEAD_DIR" checkout --quiet --detach FETCH_HEAD
test -d "$HEAD_DIR/.git" || { echo "no post-change tree"; exit 1; }
```

For the literal `local`, run this block instead. It includes tracked staged and unstaged changes plus
every non-ignored untracked file. The live tree is already the post-change tree and remains read-only.
```bash
git ls-files --others --exclude-standard -z > "$PRDIR/untracked.zlist"
git diff HEAD > "$PRDIR/diff.patch"
while IFS= read -r -d '' path; do
  status=0
  git diff --no-index -- /dev/null "$path" > "$PRDIR/untracked.patch" || status=$?
  if [ "$status" -gt 1 ] || [ ! -s "$PRDIR/untracked.patch" ]; then
    echo "cannot diff untracked path: $path"
    exit 1
  fi
  cat "$PRDIR/untracked.patch" >> "$PRDIR/diff.patch"
done < "$PRDIR/untracked.zlist"
rm -f "$PRDIR/untracked.zlist" "$PRDIR/untracked.patch"
HEAD_DIR=$(git rev-parse --show-toplevel)
```
For a local branch or commit range instead, use `git diff <base>...<head>` and the same live
`$HEAD_DIR`.

A number, URL, or branch stays as one argument. The normalization above turns
`owner/repo#number` into `--repo owner/repo number`, and every `gh pr` command uses the same
`$PR_ARGS` array. A fork PR needs no separate path because `refs/pull/<number>/head` lives in the
base repository.

Write `explanation.md` into `$PRDIR` too. If you genuinely cannot obtain the diff, stop and say so — the core promise (every claim cited) can't be honored without it. Everything you assert must trace to this file or to the PR title/description/commits.

> **Confirm the PR's base.** `gh pr diff` uses the PR's real base branch; do not eyeball a `git diff` against `develop`/`main` if the PR targets a different branch — the file/line counts will be wrong.

## 2. Read for intent first, then structure by logic

Skim the diff, title, description, and commit messages to answer **what problem, what approach** *before* explaining any code — intent-first is what every strong reviewer and tool does. Then:

- **Order by dependency/logic, never alphabetically by file.** Group related changes into cohorts the way the author reasoned: schema/data → core logic → call sites → UI → tests. A file-by-file dump is the thing reviewers hate.
- **Triage noise out.** Mark lock files, generated/codegen/protobuf output, vendored code, and minified bundles as "viewed, skipped" — don't explain them. Concentrate on the substantive core.
- **Trace one critical path.** Pick the most important change and follow it input → transforms → output, noting boundaries, validation, permissions, and surprising conditionals. This trace is the spine of the explanation *and* the source material for any diagram.

## 3. Write the explanation — auto-scale to the diff, don't pad

There is **no quick/deep toggle** — you can see the diff size, so scale the output yourself. Emit only the sections that carry weight; a tiny PR collapses to a few, a large one expands. Documented thresholds (guidance, not rigid law — use judgment):

| Diff scale | Emit |
|---|---|
| **Tiny** (~1 file, <~30 lines) | Header + What + the merged walkthrough. Often 3-5 sentences total. |
| **Medium** (handful of files / one feature) | + Why, logical-cohort walkthrough, Concepts if any, Open questions |
| **Large / flow-heavy** (many files, cross-component) | + critical-path trace, a diagram (if triggered), worked example, evidence/tests |

> **Citation rule — get line numbers right on the FIRST draft (do not draft, then re-number).**
> `$HEAD_DIR` holds the PR head from §1, so its files already carry the correct
> (new-side) line numbers. Cite by locating the symbol in the **`$HEAD_DIR` source file** —
> `rg -n 'symbolName' "$HEAD_DIR/<path>"` (or open the file) — NOT from the diff hunk or your
> file-reading output, whose numbers are patch-file positions and will be wrong.
> Cite the repository-relative path (drop the `$HEAD_DIR` prefix), so the number is the one the
> reviewer sees in their own checkout. The diff tells you *what*
> changed and which files; the `$HEAD_DIR` file gives the number to cite. Always write the
> **path-qualified** path (`apps/dataplane/src/index.ts:4420`, not `index.ts:4420`) — repos
> have many same-named files, and a bare basename is ambiguous. For *removed* lines (not in the
> `$HEAD_DIR` file), cite the diff hunk and label it "deleted".

Sections (include the ones that earn their place, in this order):

1. **Header** — change-type (feature / bugfix / refactor / docs / tests / chore) + a 1-5 review-effort estimate from file count × logic complexity. Orients the reviewer's depth in one line.
2. **What** — the net change in 1-2 plain sentences. The gist, gettable without reading the whole PR.
3. **Why** — the problem + the chosen approach (and alternatives if discernible). If the author didn't state intent, reconstruct it from the diff **and flag it**: "intent not stated; inferred from …". Never silently invent a motive.
4. **Walkthrough** — the logical cohorts, each: one-line what-changed + an inline citation. This *is* the whole body for small PRs; only split a separate step-by-step out when the diff is large enough that grouping ≠ steps. Don't emit both for a 40-line PR.
5. **Concepts** (conditional) — only for a genuinely non-obvious idea the reviewer needs. Lead with a **concrete example before the abstract**, plain language. If you find yourself reaching for jargon, that's the spot you haven't actually explained — drill in or flag it (jargon masks ignorance; it doesn't demonstrate rigor). Default to zero — don't manufacture filler concepts.
6. **Diagram** (conditional — see §3a).
7. **Worked example** (conditional) — for the central changed behavior, a sample input → output using real values/paths from the diff where possible. Makes an abstract change concrete.
8. **Evidence / tests** — which test(s) exercise the change. Note if a test fails on pre-change behavior (the strongest proof). Treat "compiles + tests pass" as *insufficient* proof of correctness, and say so when correctness is unproven.
9. **Open questions / comprehension friction** — a short labeled list (question / unclear / context-needed) of what you could NOT determine from the diff. Friction is a property of the code; surfacing it is high-value even unresolved. Keep these strictly about *understanding*, not quality verdicts — the moment a "question" becomes "this looks buggy", it's leaked into the reviewer's lane.

Conciseness is itself a guardrail: an explanation that needs many paragraphs is usually telling you the *PR* is over-complex — flag that rather than burying the reviewer.

### 3a. Diagrams — only when a picture beats prose

Draw a Mermaid diagram **only** when execution flow makes a relationship hard to hold in prose, i.e. the change does ≥1 of:
- alters the **order/sequence of calls across ≥3 participants** (services, modules, async steps),
- adds / removes / reorders a **branch, guard, or async step**,
- changes a **state machine / lifecycle / retry-error** flow,
- has cross-component / blast-radius / security-reachability implications.

**Skip** diagrams for single-file, one-line, typo, rename, isolated-leaf, or pure data/config changes — the diff tells the whole story and a diagram is just noise. Don't add diagrams decoratively to look thorough.

Pick the type from the shape of the change (deterministic):
- **sequence** — A-talks-to-B-over-time (calls, async, auth, events). Mermaid `->>` sync / `-->>` return / `-)` async, activation bars, `alt`/`opt`/`loop`/`par`.
- **flowchart** — what-decision-next (branches, guards, decision trees).
- **stateDiagram** — lifecycle / status / retry transitions.
- **erDiagram** — schema / data-model changes.

Use the diagram's "every branch must lead somewhere" property to force edge cases explicit. Layer flowchart-overview + sequence-detail only for genuinely complex flows.

## 4. Validate every citation mechanically — then present

Prompt discipline catches a *missing* citation; it cannot catch a *fabricated* one. So after drafting, verify programmatically (this is the load-bearing step; "enforce, don't suggest"):

```bash
python3 "$SKILL_ROOT/scripts/validate_citations.py" \
  "$PRDIR/diff.patch" "$PRDIR/explanation.md"
```

The script extracts every `path:line` / `path:line-line` citation from your draft and checks it lands inside a real changed hunk of that file. If you followed the §3 citation rule (path-qualified numbers from the `$HEAD_DIR` source) this is a confirmation, not a redo. For each citation flagged invalid:
- **fix it** if you meant a real nearby line, or
- **drop the claim** if it can't be grounded. Unverifiable → deleted, not softened.

Two failure modes the validator reports, and what they mean:
- *"file not in this PR's diff"* on a path-qualified citation usually means a **wrong path or a bare basename** — qualify it (`apps/dataplane/src/index.ts:NN`), don't strip to `index.ts:NN`.
- *"line outside changed hunks"* means a wrong **number** — you likely used a patch-file line instead of the `$HEAD_DIR` source line (§3 rule).

**Passing the validator means the cited line is *changed*, not that it's the *right* line** — a wrong number can still land inside some hunk by luck. So after the validator is green, sanity-check that each cited line actually says what your claim says.

When you must reference unchanged surrounding code to explain a hunk, cite it too but label it "context, not part of this change" — the validator accepts a `--context` file of such `path:line` references; otherwise keep them minimal and clearly marked. Re-run until clean, then present the explanation to the **human reviewer** (see scope on council coupling).

## 5. Drop the run-scoped clone

The clone is self-contained, so removing the directory removes all of it. The guard keeps a
local-mode `$HEAD_DIR` — the user's own checkout — out of the removal path:

```bash
case "$HEAD_DIR" in "$PRDIR"/*) rm -rf "$HEAD_DIR";; esac
```

## Scope guardrails — strictly THIS PR

- Explain relationships **among the changed files** and their immediate touchpoints only. Never sprawl into whole-codebase analysis or re-explain unchanged code (that's the Greptile/Cody anti-pattern the user explicitly wants to avoid).
- When surrounding context is genuinely needed, pull the **minimum** (a signature, a contract) and mark it "context, not part of this change".
- If the PR is large/ambiguous, ask the reviewer what to focus on first ("the auth path?"), then explore only that.
- **Stay decoupled from the council/review.** This runs **before** the quality review, as a human-only artifact. Do NOT pipe the walkthrough into `review-pr`/`council` — one narrative anchors the judges and corrupts their independence. The only slice that may optionally cross is a neutral **term/symbol glossary** (definitions, no interpretation), and only when asked, flagged as such.
- Don't collide with author-side "write me a PR description" — this is reviewer comprehension of an existing PR.
