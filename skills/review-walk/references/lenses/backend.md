# Backend lens

Step 03 reads the cleanup part and step 04 reads the logic part. Each line is "what to flag → what
to ask for". The repo rules file and the domain catalog's `review` paths add to this list and win
when they disagree. `engineering-standards` owns the rows for API shapes, keys and indexes, query
cost, retries, and timeouts, so cite its row id instead of restating it.

Example. A diff adds `function parseId(v: unknown): string` that trims and checks a value that
the same service wrote one call earlier. The cleanup part flags "validation of data we produced",
and the comment asks if the helper is needed, because our own code sets the value.

## Cleanup (step 03)

The goal is a change that the next reader can follow without holding extra state in their head.

- A helper, wrapper, or file with one caller and no domain name → inline it. `minimize-reader-load`
  owns the conditions.
- A shallow module whose interface is as big as its body → merge it into the caller (Ousterhout,
  deep modules).
- Validation, `unknown`, or a zod schema on data that our own code produced → type it and drop
  the check. Keep checks only at a trust boundary: user input, LLM output, a third-party API.
- A second type for a shape that already has one (a hand-written RPC interface next to the real
  class, a type that repeats a schema) → derive it from the owner.
- The same logic shape in two hunks → one shared piece, or say which one stays (Fowler, duplicated
  code).
- A boolean flag that adds a mode next to an older flag → one enum.
- A magic number or repeated literal → a named const next to its use.
- A name that does not say what the value holds → rename. A name that needs a comment to make
  sense → rename first, comment second.
- A non-obvious rule, invariant, or workaround with no comment → a one-line comment. A comment
  that restates the code → remove it.
- Debug routes, repair scripts, or feature flags that the change no longer needs → remove them.
- Speculative parameters, hooks, or config with no current caller → remove them (Fowler,
  speculative generality).
- One change that forces edits in many unrelated files → ask where the concept should live
  (Fowler, shotgun surgery).

## Logic (step 04)

The goal is a change that stays correct under real load, real failures, and real data.

- A storage, RPC, or network call inside a loop → one batched call. Name the loop bound.
- A list or query with no limit, or a limit with no signal to the caller → a bounded page and a
  cursor, or a truncation flag the consumer can act on.
- Two writes that must both happen, or neither → one transaction. A check, then a write, on a
  shared counter → one conditional statement (`engineering-standards` J1).
- A read-modify-write that two requests can interleave → name the race and the serializing owner.
- An error path that swallows the error, or turns "failed to read" into "empty" → fail loudly, or
  say why empty is safe (`engineering-standards` R4 for authorization reads).
- An outbound call with no timeout, or a retry with no budget → cite `engineering-standards` R1
  and R3.
- A loop whose exit depends on data (`for (;;)`, a date search) → a proven bound or a max
  iteration count.
- Memory that grows with user data (whole tables, whole files, full histories in one array) →
  stream, page, or cap it against the runtime limit.
- Text cut by a byte or UTF-16 index before it goes to an LLM or a user → cut by code point or
  grapheme so a multi-byte character stays whole.
- Time zones, day boundaries, and date math done by hand → the repo's date library.
- A migration that rewrites or rebuilds existing data or indexes → an additive change, or proof
  that the rewrite is bounded.
- A contract that a caller relies on (return shape, ordering, null meaning) that the change alters
  → name each caller that breaks. Search callers before you claim none break.
- Unproved defects stay questions. Mark them "potential issue, not confirmed:" and name the input
  that would trigger them.

## Frontend

No frontend lens yet. Add `frontend.md` here when the first frontend review needs it, and select it
from the domain catalog's `web-ui` signals.

Sources: John Ousterhout, *A Philosophy of Software Design* (deep modules, information hiding,
cognitive load); Martin Fowler, *Refactoring* ch. 3 (code smells); Google Engineering Practices,
"What to look for in a code review" (design, functionality, complexity, naming, comments).
