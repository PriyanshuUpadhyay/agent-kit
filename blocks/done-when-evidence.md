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
| Page looks right on a phone | screenshot at 390 px | `tmp/shots/hero-390.png`; taste awaiting the user's review |
Result: two rows proved, one partial row named as partial.

## Check (script)
- none: the close table lives only in the step file, which holds this block's own Rules; `take 07-close` already refuses a run without APPROVE on HEAD.

## Check (judge)
- Does every done-when line of `01-frame.md` and every accepted constraint have its evidence in the `## Result` of `05-build.md`? Quote each done-when and its evidence.
- Does any done-when there still read "not run" or have no evidence? Quote it, or write "none".
- Is each piece of that evidence a command with its output, a path that exists, or "unverified" with a reason? Quote each piece.
- Is any partial check in that Result written as a completed proof? Quote the line.
