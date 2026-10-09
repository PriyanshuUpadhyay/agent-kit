# done-when-evidence
Concept: Close maps each done-when of the frame to its evidence, or marks it unverified.
Serves: close
Source: skills/flow/SKILL.md (step table, 07-close row, and the APPROVE gate below it); references/plan-layout.md:31-33 (Verification); skills/prove-it-works/SKILL.md:46 (below step 4 is unproven)

## Rules
- `07-close.md` lists every done-when of `01-frame.md`, each with its evidence.
- Use a table or a numbered list: requirement, check, evidence. Every requirement and every accepted constraint has a row.
- Evidence reads "not run" until you get it. A row with no proof reads "unverified" and says why.
- Keep a partial check apart from a completed proof.
- Close needs the review verdict APPROVE on the current head. An `INCOMPLETE` verdict is no review.

## Example
Initial state: `01-frame.md` has three done-when lines.
Action: write in `07-close.md`:
| Done-when | Check | Evidence |
|---|---|---|
| Hero states the tool in 20 words | word count script | `checks/hero.mjs -> PASS 18 words` |
| Diagram 2 matches `docs/architecture.md` | diagram-correctness table | `06-review.md` rows 1-7, all cited |
| Page looks right on a phone | screenshot at 390 px | `shots/hero-390.png`; taste awaiting the user's review |
Result: two rows proved, one partial row named as partial.

## Check (script)
- Count the done-when lines of `<flow-folder>/01-frame.md` and the rows of the table in `<flow-folder>/07-close.md`; the two numbers match: every done-when has a row.
- `rg -n 'not run' <flow-folder>/07-close.md` prints nothing: no row waits for its check.
- Line 3 of the last review-check run's `03-verdict.md` starts with `Verdict: APPROVE`, and its `target.json` head equals `git rev-parse HEAD`: the review approved the current head.

## Check (judge)
- Is each row's evidence a command with its output, a path that exists, or "unverified" with a reason? Quote each row's evidence.
- Is any partial check written as a completed proof? Quote the row.
