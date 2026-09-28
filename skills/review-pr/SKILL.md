---
name: review-pr
description: Judge a PR, local changes, or a commit range for correctness, behavior ownership, redundant boundaries, LLM and schema contracts, code quality, and security, with per-function coverage and evidence-gated findings, ending in APPROVE, REQUEST CHANGES, or NEEDS DISCUSSION. Use for PR review and redundancy audits. It judges a change and does not explain one; pr-walkthrough explains first.
---

## Ownership boundary

This workflow is report-only. The chair and every review seat may inspect code and write only
run-scoped scratch artifacts. Workers follow the active runtime adapter's `Worker contract`
section. The user owns every resulting code change.

The user's repository is read-only in the strongest sense: this review leaves their working tree,
index, refs, object store, config, and worktree metadata byte-for-byte untouched. Never check a PR
out in place; never run `git checkout`, `git switch`, `git stash`, `git reset`, `git fetch`, or
`git worktree` against it. Post-change inspection state is a self-contained clone under `$RPDIR`,
removed in Phase 4. Every git command that writes anything carries `git -C "$HEAD_DIR"`; only
`gh pr diff` and `gh pr view` read the user's checkout, and then only to resolve the target.

Review the resolved target with provable per-function coverage — a PR, the literal `local` for
uncommitted working-tree changes, or a commit range `<base>..<head>`. A script guarantees every changed function is
reviewed (no skimming); you supply the reasoning; a verifier keeps findings honest.
Judge the change on its own merits — do NOT excuse new bugs because the surrounding code is messy.

Large PRs use a bounded reviewer pool. Coverage remains one verdict per unit, but seat count does
not scale with function count.

## Runtime requirements

Load `orchestration.json` through the active runtime adapter before dispatch. It defines the three
semantic roles, visible owned-seat requirement, durable artifact contract, refusal dispositions,
and result routing. The runtime adapter resolves roles and owns worker lifecycle. If the unit
reviewer and challenger cannot be independently routed, continue only under the declared
`reviewer-independence-unsatisfied` degradation and report it in the final review.

Keep all role briefs semantic. Runtime-specific prompt tuning, transport, visibility, completion
polling, notification delivery, and teardown are adapter responsibilities.

## Prompt composition

The stable epistemic seats live with this skill:

- Unit and ripple review: `references/personas/unit-reviewer.md`
- Behavior ownership and redundancy audit: `references/behavior-ownership-audit.md`
- Finding verification: `references/personas/challenger.md`
- Security pass: `references/personas/security-reviewer.md`

Append the `engineering-standards` skill contract to the unit-reviewer prompt as task-specific data
**only when `.standards.run` in `$RPDIR/triggers.json` is true**, never by reading this paragraph
and deciding. The script owns that decision, so a skip carries `.standards.evidence` and is
auditable. It supplies cited rules for request and response shapes, keys and indexes, query cost,
and retry and timeout behavior. It supplies rules only; this workflow keeps coverage and the final
verdict.

Always append the `minimize-reader-load` skill contract to the unit-reviewer prompt as task-specific data, for
every unit and every risk tag. A changed unit that adds or splits out a function, file,
or module that meets none of its conditions gets a FAIL finding. Its `file_line` and
`quoted_code` are the new definition, its `trigger` is the current caller count from repository
search, and its `why_not_prevented` names why each condition fails.

When the domain catalog that the `flow` skill names exists, also append to the unit-reviewer
prompt, as task-specific data, the `review` paths of each catalog domain whose `Signals:` line
matches a changed file in `diff.patch`, and the repo rules of the reviewed repo's flow profile.
They supply rules only; this workflow keeps coverage and the final verdict.

Compose each worker prompt from exactly one persona plus task-specific data. Append the assigned
unit records, relevant diff hunks, full-function or caller locations, absolute scratch path, and
the output schema required by that phase. For Phase 2c, append the behavior-ownership reference as
task-specific audit instructions to the unit-reviewer persona. Append the runner contract's relay
requirement last.
The persona defines how the seat reasons and proves its result; the runtime adapter's role
routing alone selects how the seat runs. End every composed seat prompt with the report-only boundary: inspect the repository,
write only the assigned scratch verdict, and do not edit code, apply findings, commit, or spawn an
agent.

## When to use / when NOT
- USE for: judging a PR, a local uncommitted diff, or a commit range, such as the commits of a
  finished `pair` or `deliver` run, for correctness, behavior ownership,
  redundant validation or machinery, LLM/schema contracts, security, and code quality, with
  provable per-function coverage. This workflow produces verdicts and a recommendation.
- NOT for: understanding what a PR *does* before judging it — that is `pr-walkthrough`, which
  explains and never judges, while this workflow judges and never narrates. Running both is
  normal: comprehend first, judge second, and keep the two artifacts separate so the narrative
  cannot anchor the verdicts.

## Target resolution (fail closed, before any command)
Normalize the user's request into one review target first. `PR_TARGET` is a PR number, a PR URL,
`owner/repo#number`, a branch name, the literal `local` for uncommitted working-tree changes, or a
commit range `<base>..<head>` in the repository of the current directory. A branch name cannot
hold `..`, so the range form is unambiguous.
Take it from the arguments supplied with the invocation; when the invocation supplies none, take it
from the user's request text.
```bash
PR_TARGET="<the normalized target>"
test -n "$PR_TARGET" || { echo "no review target: ask for a PR number, URL, branch, or local"; exit 1; }
case "$PR_TARGET" in
  *'#'*)
    PR_REPO=${PR_TARGET%#*}
    PR_NUMBER_INPUT=${PR_TARGET##*#}
    case "$PR_REPO" in */*) ;; *) echo "invalid owner/repo#number target"; exit 1;; esac
    case "$PR_NUMBER_INPUT" in ''|*[!0-9]*) echo "invalid PR number"; exit 1;; esac
    PR_ARGS=(--repo "$PR_REPO" "$PR_NUMBER_INPUT")
    ;;
  *..*)
    RANGE_BASE=$(git rev-parse --verify --quiet "${PR_TARGET%%..*}^{commit}") || { echo "range base is not a commit"; exit 1; }
    RANGE_HEAD=$(git rev-parse --verify --quiet "${PR_TARGET#*..}^{commit}") || { echo "range head is not a commit"; exit 1; }
    ;;
  *) PR_ARGS=("$PR_TARGET") ;;
esac
```
With no resolvable target, stop and ask. Do not guess the newest PR, the current branch, or the
working tree.

## Phase 0 — Fetch the diff and build the post-change tree (ground truth)
Write everything to a unique run-scoped scratch directory supplied by the active runtime. Derive
the same absolute `$RPDIR` from the review target plus the runtime's unique run identity in every
phase, so concurrent reviews cannot collide and later phases cannot drift to a different directory.
`$HEAD_DIR` is the post-change tree every later phase reads. It is a **separate clone** inside
`$RPDIR` with its own `.git`, so it works the same whether or not the user stands in the PR's
repository, and it cannot reach their object store, refs, or worktree metadata.
```bash
test -n "$RPDIR" || { echo "no run-scoped scratch directory"; exit 1; }
case "$RPDIR" in */review-pr/*) ;; *) echo "unsafe scratch directory"; exit 1;; esac
rm -rf "$RPDIR" && mkdir -p "$RPDIR"
gh pr diff "${PR_ARGS[@]}" > "$RPDIR/diff.patch"
gh pr view "${PR_ARGS[@]}" --json number,url,title,body,files,headRefName,headRepository > "$RPDIR/meta.json"  # repo identity stays in meta.json, not the dirname
HEAD_DIR="$RPDIR/head"        # run-scoped clone; the user's repository is never written to
PR_NUMBER=$(gh pr view "${PR_ARGS[@]}" --json number --jq .number)
BASE_REPO=$(gh pr view "${PR_ARGS[@]}" --json url --jq .url | sed -E 's#/pull/[0-9]+.*##')   # host-agnostic base repo URL
gh repo clone "$BASE_REPO" "$HEAD_DIR" -- --no-checkout --filter=blob:none --quiet       # drop --filter on a host without partial clone
git -C "$HEAD_DIR" fetch --no-tags --quiet origin "refs/pull/$PR_NUMBER/head"            # the base repo serves fork heads here too
git -C "$HEAD_DIR" checkout --quiet --detach FETCH_HEAD
test -d "$HEAD_DIR/.git" || { echo "no post-change tree"; exit 1; }
```
`$PR_TARGET` may be a number, a URL, a branch, or `owner/repo#number`. The normalization above
turns the repository-qualified form into `--repo owner/repo number`; every `gh pr` command uses the
same `$PR_ARGS` array. `gh pr view --json number,url` then supplies the PR number and base repository
URL that `refs/pull/<number>/head` lives in, so a fork PR needs no separate path.
**Local mode** — when `$PR_TARGET` is `local` (review UNCOMMITTED changes), use the block below
instead. No `gh`, and **no second tree** — the working tree is already the post-change "head",
so ctags reads the live files and the diff's new-side line numbers are already correct. It stays
read-only: inspect it, write nothing into it.
```bash
test -n "$RPDIR" || { echo "no run-scoped scratch directory"; exit 1; }
case "$RPDIR" in */review-pr/*) ;; *) echo "unsafe scratch directory"; exit 1;; esac
rm -rf "$RPDIR" && mkdir -p "$RPDIR"
git ls-files --others --exclude-standard -z > "$RPDIR/untracked.zlist"
git diff HEAD > "$RPDIR/diff.patch"   # tracked staged + unstaged changes
while IFS= read -r -d '' path; do
  status=0
  git diff --no-index -- /dev/null "$path" > "$RPDIR/untracked.patch" || status=$?
  if [ "$status" -gt 1 ] || [ ! -s "$RPDIR/untracked.patch" ]; then
    echo "cannot diff untracked path: $path"
    exit 1
  fi
  cat "$RPDIR/untracked.patch" >> "$RPDIR/diff.patch"
done < "$RPDIR/untracked.zlist"
rm -f "$RPDIR/untracked.zlist" "$RPDIR/untracked.patch"
#   ...or `git diff --staged`        (staged only)
HEAD_DIR=$(git rev-parse --show-toplevel)   # the live tree already IS the post-change state
```
There is no PR title/body in local mode — skip `meta.json` and note "local changes" in the
compiled output. Everything downstream (enumerate → gate → seats) is diff-agnostic and runs
unchanged. In every later phase, re-derive `$RPDIR` and `$HEAD_DIR` with the same lines above
before using them.
**Range mode** — when target resolution set `RANGE_BASE` and `RANGE_HEAD`, use the block below
instead. `git diff` only reads the user's repository. The post-change tree is a new repository
under `$RPDIR`, fetched at the head commit, so an uncommitted edit in the user's checkout never
reaches the review.
```bash
test -n "$RPDIR" || { echo "no run-scoped scratch directory"; exit 1; }
case "$RPDIR" in */review-pr/*) ;; *) echo "unsafe scratch directory"; exit 1;; esac
rm -rf "$RPDIR" && mkdir -p "$RPDIR"
git diff "$RANGE_BASE" "$RANGE_HEAD" > "$RPDIR/diff.patch"
HEAD_DIR="$RPDIR/head"        # run-scoped repository at the head commit
mkdir "$HEAD_DIR"
git -C "$HEAD_DIR" init --quiet
git -C "$HEAD_DIR" fetch --quiet --no-tags "$(git rev-parse --show-toplevel)" "$RANGE_HEAD"
git -C "$HEAD_DIR" checkout --quiet --detach FETCH_HEAD
```
Skip `meta.json` and note the range in the compiled output. In every later phase, set
`HEAD_DIR="$RPDIR/head"` again; do not run this block twice.
Treat `diff.patch` as the final review contract. Do not infer PR scope from the latest commit or
working-tree status; a later revert can cancel an earlier branch change.

## Phase 1 — Enumerate review units (script owns coverage)
```bash
(cd "$HEAD_DIR" && python3 <skill-dir>/scripts/enumerate_units.py enumerate "$RPDIR/diff.patch") > "$RPDIR/worklist.json"
python3 <skill-dir>/scripts/enumerate_units.py triggers "$RPDIR/worklist.json" > "$RPDIR/triggers.json"
```
Enumeration runs *inside* `$HEAD_DIR` so ctags reads post-change files. This is the anti-skim
core: every changed line lands in exactly one unit. Do NOT edit the
worklist. (If `universal-ctags` isn't installed, units fall back to hunk granularity — coverage
still holds; `brew install universal-ctags` gives function-level units.)
`triggers.json` holds the objective seat decisions; `.security` and `.standards` are final from
here, `.challenger` is recomputed in Phase 3 once verdicts exist. Unit coverage, the ripple pass,
and the gate are unconditional and never consult it.

## Phase 2 — Review every unit (bounded visible pool)
Read `worklist.json`. Start at most `min(4, unit count)` named foreground reviewers
(`pr-unit-1`…`pr-unit-4`) and partition unit ids deterministically across them. Each reviewer
processes its assigned units serially in **Per-Unit Review Mode** and emits a separate verdict
object for every unit. Do not merge functions into one judgment: bounded concurrency changes pane
count, not the one-verdict-per-function coverage contract. Reuse the same visible pool for
`unmapped_chunk` batches and ripple checks.
Give each worker its unit record(s) + the relevant diff hunks. For any unit with
`"change_type": "modified"` the worker MUST read the **full `new_range`** from that file under
`$HEAD_DIR` and follow the unit-reviewer persona's **regression** lens (the worklist already lists it).
Hand each spawned worker the **fully-expanded absolute** `$RPDIR` and `$HEAD_DIR` paths
(e.g. `/tmp/review-pr/pr-1234-<id>/`) — never an unexpanded `$RPDIR`/`$HEAD_DIR` string, which a
worker would re-derive against its own run identity and resolve to the wrong directory. Workers
READ their unit's diff from `$RPDIR`, read code only under `$HEAD_DIR`, and **return** verdicts;
the orchestrator is the sole writer. Collect one verdict per unit
id into `$RPDIR/verdicts.json` (a JSON array of the worker verdict objects).

## Phase 2b — Cross-cutting passes (regressions outside one function)
```bash
python3 <skill-dir>/scripts/enumerate_units.py callers "$RPDIR/worklist.json" --repo-root "$HEAD_DIR" > "$RPDIR/callers.json"
```
`callers.json` is a list of `{symbol, change_type, callers:[file:line...], dropped}` for **every**
changed public function — not just signature changes — because a body-only change can break callers
that the diff never touched. For each entry, run the unit-reviewer persona's ripple mode with the
symbol, `change_type`, and caller list.
- If `dropped > 0` the caller list was capped (20/symbol) — note in the report that the tail was
  not reviewed.
Collect one ripple object per changed symbol into `$RPDIR/ripple-verdicts.json`. Keep ripple
objects separate from code-unit verdicts: they are keyed by `symbol`, never receive a `unit_id`,
and never enter `worklist.json`, `verdicts.json`, or the code-unit gate inputs.

Separately, the **invariant audit** — for each REMOVED **or MODIFIED** block, state what it
guaranteed (null check, lock, ordering, retry, validation) and confirm the new code preserves it.
Add any survivors as findings in `verdicts.json`.

## Phase 2c — Audit behavior ownership and redundancy

Follow `references/behavior-ownership-audit.md`. Trace every changed cross-file behavior from its
input to durable state, external side effect, or final consumer. Write the behavior-to-owner matrix
to `$RPDIR/ownership-audit.md`. Search direct callers, re-exports, configuration, dependencies, and
deployment bindings before deciding that a layer is shared, dead, or misplaced.

A duplicate is a finding only when one surviving owner preserves the same guarantee on every path
and the other layer protects no independent trust, durability, race, or resource boundary. Map each
supported redundancy to the worklist unit that contains the removable layer and add it to that
unit's verdict. Keep uncertain ownership as a QUESTION. The matrix is supporting evidence and never
enters the code-unit gate as a new identity.

## Phase 3 — Verify findings (risk-triggered challenger, DEFAULT-REJECT)
After closing the unit pool, recompute the seat decisions from the collected results:
```bash
python3 <skill-dir>/scripts/enumerate_units.py triggers "$RPDIR/worklist.json" \
  --verdicts "$RPDIR/verdicts.json" --ripple "$RPDIR/ripple-verdicts.json" \
  --redundancies <supported redundancy count from Phase 2c> > "$RPDIR/triggers.json"
```
Run the challenger only when `.challenger.run` is true — a surviving FAIL or QUESTION, a supported
redundancy, a changed function signature, or a unit of 25+ changed lines. When it is false, skip the
seat and carry `.challenger.evidence` verbatim into the final report as the skip evidence; per-unit
coverage, the ripple pass, and the gate still run unchanged, so a skip narrows verification, never
coverage.

When it runs: ONE visible foreground `review.challenger` pane. Give it all FAIL findings PLUS a **risk-weighted sample of PASS
verdicts** (bias toward the largest hunks, signature changes, and deletions — where a missed bug
costs most). Also give it every FAIL or QUESTION from `$RPDIR/ripple-verdicts.json`. Compose the
prompt from the challenger persona, the selected verdict objects, the relevant diff and full-code
locations, `$RPDIR/ownership-audit.md`, and its output schema. Require the challenger to reject a
redundancy claim unless the surviving owner and an independent-boundary counterexample were both
checked.
Write code-unit adjustments back to `$RPDIR/verdicts.json` and ripple adjustments back to
`$RPDIR/ripple-verdicts.json`; do not merge their identity namespaces.
One-shot — no back-and-forth debate.

## Phase 4 — Gate + compile
```bash
python3 <skill-dir>/scripts/enumerate_units.py gate "$RPDIR/worklist.json" "$RPDIR/verdicts.json"
```
If the gate reports violations (a unit with no verdict, or an unearned PASS), the review is
INCOMPLETE — finish those units and re-run; do NOT present results yet. When the gate passes
(exit 0), close the challenger if it ran. Run a second `review.deep` seat in one visible foreground
pane with the security-reviewer persona, diff, changed-file context, and output schema **only when
`.security.run` in `$RPDIR/triggers.json` is true** — a changed file carries an auth, money,
persistence, migration, serialization, parsing, external_api, or fs_net risk tag. When it is false,
skip the seat and carry `.security.evidence` verbatim into the report. Then compile:
- Coverage line: "N units, all reviewed".
- Seats line: which risk-triggered seats ran, and the quoted trigger evidence for each skipped one.
- Domain rules line: each catalog or repo rule file that the unit reviewers got, or "no domain
  rules".
- Surviving findings grouped by severity, each with its evidence (file:line, quoted code, trigger).
- Surviving ripple findings and QUESTIONs, keyed by changed symbol, from
  `$RPDIR/ripple-verdicts.json`.
- Ownership line: "N behaviors mapped; M have competing owners", followed by each verified
  redundancy and its surviving owner.
- Open QUESTIONs.
- Recommendation: APPROVE / REQUEST CHANGES / NEEDS DISCUSSION.

Finally, drop the run-scoped clone. It is self-contained, so removing the directory removes all of
it. The guard keeps local mode, where `$HEAD_DIR` is the user's own checkout, out of the removal
path:
```bash
case "$HEAD_DIR" in "$RPDIR"/*) rm -rf "$HEAD_DIR";; esac
```

Anti-bloat reminders: no style/lint nits (defer to eslint/ruff/mypy); never review unchanged code;
high signal, not high volume.
