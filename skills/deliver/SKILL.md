---
name: deliver
description: Explicit autonomous delivery of one named task. Use only when the user invokes deliver and wants the agent to drive the task to a checkable exit condition without stopping. Never select it for an ordinary implementation request, and never for chunk-by-chunk work, which `pair` owns.
disable-model-invocation: true
---

# Deliver

You own the exit condition. State it, then drive to it without stopping.

Deliver runs in supervised mode. The agent picks the next step and edits without asking, and it
stops only before a merge, a push, or another irreversible action, or when it is blocked on input
only the user can give.

1. State the exit condition as a checkable predicate before the first change: tests green, the
   repro fixed, the feature exercised on the real surface. Show it in one line and start. Do not
   wait for approval of the predicate.
2. Each iteration makes the smallest change the evidence justifies, verifies it against the
   predicate, commits when it advanced, and discards a change that did not help. A change that
   "might help" is reverted, not left to ride. Order the work per the
   `sequence-verifiable-units` skill, and judge each check per the `prove-it-works` skill.
3. A mid-run discovery is yours when it blocks the predicate. Fix it, such as a broken helper or a
   flaky check, in its own commit, then return to the predicate. Do not park reversible work for
   the user. Report any other defect in the final result and leave it unfixed.
4. Keep one task file `<YYYY-MM-DD>-<slug>.md` in the task-file folder that the active runtime
   adapter names, with the predicate, the iterations run, one evidence line per iteration, and the
   next step. Read it first after a `/clear`, a `/compact`, or a resume, and make the first reply a
   status block.
5. Stop only when the predicate is met, or when blocked on user input. A plateau is not a stop,
   so change the approach. A genuine dead end is reported with the evidence, not spun on. Never
   relax the predicate to declare victory.

The active host contract decides who types. Under a Fable chair the edits go to a routed coding
seat, every worker is a visible foreground pane, and the chair verifies each returned diff itself.
Notifications are chair-owned.

**Reply:** the exit condition, the iterations run, what landed with its hashes, what was
discarded, and the final predicate state with its proof.
