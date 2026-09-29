# Behavior ownership and redundancy audit

## Goal

Give each changed behavior one explicit owner. Find layers that repeat the same decision, state,
queue, retry, cleanup, adapter, or contract without protecting a separate boundary.

This is not a line-count exercise. Two similar checks can both be necessary when they protect
independent boundaries. One small helper can still be redundant when another layer already owns its
complete behavior.

## 1. Establish the final change

Use the final base-to-head diff in `diff.patch` as the PR contract. Do not infer PR scope from the
latest commit or `git status`. A later deletion can cancel an earlier branch change and leave no
base-relative change in that path.

Build a path inventory for source, configuration, dependencies, generated bindings, documentation,
and deleted or moved files. Check the final inventory for test, fixture, scratch, debug, log, copied
secret, merge marker, and local-only artifacts, and for paths outside the PR title or commit
subjects. Record each check under `## Inventory check` in `$RPDIR/ownership-audit.md`, with its
`file:line` hits or `none`. Local mode has no title, so record the scope check as `not checked`.

## 2. Trace behaviors, not helpers

Name each cross-file behavior in domain terms, then trace it from input to final side effect or
consumer. Examples are `reject a duplicate upload id`, `serialize one sandbox job`, `derive stored
file metadata`, and `delete all user attachment objects`.

For each behavior, record this matrix in `$RPDIR/ownership-audit.md`:

| Behavior | Candidate layers | Owner | Why this layer owns it | Non-owner remnants | Evidence |
|---|---|---|---|---|---|

The owner is normally the layer closest to the durable state, external system, security boundary,
or complete consumer contract. A shared module is not an owner only because it is shared.

## 3. Test common duplication classes

Search the changed path and its direct callers for these classes:

- Validation and policy: schema plus service guards, identifier reservation plus create-only write,
  or prompt/output policy plus deterministic mutation.
- Concurrency and failure: multiple queues, locks, semaphores, retries, timeouts, or cleanup modes
  around the same operation.
- State and lifecycle: duplicated readiness, cache, persistence, alarm, retention, or deletion
  ownership.
- Representation and transport: repeated media detection, metadata derivation, path construction,
  conversion, signing, or response projection.
- Module and deployment ownership: a shared package with one application consumer, an adapter in
  the wrong service, copied credentials, or duplicate bindings and dependencies.

Measure current consumers with repository search before calling a helper shared or dead. Follow
imports through re-exports. Check configuration and lockfiles when code moves across package or
service boundaries.

## 4. Distinguish redundancy from defense in depth

Call two layers redundant only when all of these are true:

1. They decide the same behavior from equivalent inputs.
2. They produce the same accepted or rejected outcome and failure policy.
3. Removing one leaves the other owner on every reachable path.
4. The removed layer does not protect an independent trust, durability, race, or resource boundary.

Example of redundancy: a client mints a UUIDv7, an initiate route reserves it, and a later
create-only object write already rejects the same collision. If no current feature needs a pending
row, the reservation adds a request but no separate guarantee.

Counterexample: an HTTP `Content-Length` limit rejects an oversized request early, while a streaming
byte counter rejects a body that lies about its length. The checks look similar, but they protect
different failure boundaries and both can remain.

A whole-job FIFO and a backend command lock can also both remain when one orders jobs and the other
orders commands inside a job. An extra semaphore around the same whole-job scope is redundant.

Do not treat a prompt rule as a security boundary. A deterministic security check can be valid
defense in depth when untrusted output can cross a real credential or authorization boundary.

## 5. Prove each simplification

Before reporting a layer as removable, state:

- the exact guarantee it currently provides;
- the surviving owner and every path that reaches it;
- one failure, retry, race, deletion, or boundary case;
- the smallest removal or move that leaves the guarantee intact.

If you cannot prove all four points, return a question instead of a finding. Do not propose a new
abstraction unless it serves multiple current consumers or isolates a real external boundary.

Map each supported finding to the changed worklist unit that contains the redundant layer. Add the
finding to that unit's verdict with all duplicate implementations, consumer-count evidence, and a
concrete removal. The ownership matrix is supporting scratch evidence, not a new gate identity.

## 6. Report the audit

Report the number of mapped behaviors and name every behavior with competing owners. If no
redundancy survives verification, say that every mapped behavior has one supported owner. Keep
optional cleanup separate from correctness or maintainability findings.
