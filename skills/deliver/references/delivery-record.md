# Delivery record contract

The record is the only editable delivery truth. Boards, status views, lane briefs, reports, and close
summaries refer to its stable IDs or are generated from it. Do not keep a second live copy of a
requirement, decision, stage state, or closure count.

## Path and identity

Store the record at:

```text
~/.local/state/deliver/<repository-id>/<task-slug>.md
```

`repository-id` is the first twelve hexadecimal characters of SHA-256 over the canonical absolute
repository root. `task-slug` matches `[a-z0-9][a-z0-9-]*`. Keep the file below 16 MiB. The file and
its path from the state root must not be symbolic links.

## Header

Use one flat YAML header. All fields are required.

```yaml
---
schema_version: 1
delivery_id: <repository-id>/<task-slug>
repository_root: <canonical-absolute-path>
git_common_dir: <canonical-absolute-path>
goal: <one-line-member-outcome>
status: active
current_stage: 1
revision: 1
owner_session: <session-or-run-id>
base_head: <7-to-40-hex-commit-or-unborn>
explicit_invocation: true
commit_authority: not-granted
commit_request: none
created_at: <ISO-8601>
updated_at: <ISO-8601>
---
```

`status` is `active`, `blocked`, or `closed`. `current_stage` is 1 through 14. Increase `revision`
for each accepted record update. `commit_authority` is `not-granted` or `granted`. `granted` needs
the exact current commit request in `commit_request`; `not-granted` requires `commit_request: none`.

## Global sections

```markdown
## REQUIREMENTS
- R1: WHEN <trigger> THE SYSTEM SHALL <observable result>

## DECISIONS
- ASK <name>: REQUEST|ANSWERED|CONFIRMED-DEFAULT: <exact decision and source>

## EVIDENCE
- CLAIM <id>: {"path":"<repository-relative-path>","digest":"<sha256>"}
```

Requirement IDs are stable and unique. Add a new ID instead of renumbering an accepted ID. Each
claim has one repository-relative source path and its current SHA-256 digest. Direction-changing
choices use current-run authority. `UNRESOLVED`, `INFERRED`, and `DEFAULTED` are not authority.

## Stage sections

Each stage uses this shape:

```markdown
## STAGE 01 — The outcome first
- STATUS: PASS
- <REQUIRED-FIELD>: <artifact pointer, digest, command result, count, or signed decision>
- GATE-EVIDENCE: <the exact observation that passed this stage>
```

A field is a pointer to its canonical artifact or a generated value. It is not a copied second
artifact. `STATUS: PASS` is valid only after the work and gate evidence exist.

### 01 — The outcome first

Required fields:

- `BLIND-BRIEF`: problem, environment, ruled behavior, and no architecture.
- `ACCEPTANCE-BAR`: journey, safety, loud failure, and endpoint.
- `OWNER-SIGNATURE`: current owner acceptance of the stable requirement IDs.
- `GATE-EVIDENCE`: exact signed source or current response.

The global `REQUIREMENTS` section must contain at least one stable `R<number>` row.

### 02 — One shared language

Required fields:

- `ONTOLOGY`: canonical vocabulary artifact and digest.
- `GENERATED-VIEW`: readable output derived from the ontology.
- `VOCABULARY-SWEEP`: executed command with `exit 0`.
- `GATE-EVIDENCE`: sweep command and result.

### 03 — The pattern pass

Required fields:

- `DOMAIN-CENSUS`: finite list of applicable problem domains.
- `PLAYBOOK-LIBRARY`: cited current pattern source for each domain.
- `PATTERN-DECISIONS`: one standard-pattern or justified-novel sentence per design decision.
- `GATE-EVIDENCE`: census count equals playbook count.

### 04 — Design on boards

Required fields:

- `SIGNED-BOARD`: canonical board source, digest, and signature.
- `WORKED-EXAMPLES`: boundary examples that carry the design decisions.
- `KILL-LIST`: deliberate exclusions.
- `WALK-VIEWS`: generated clean views used for sign-off.
- `GATE-EVIDENCE`: signed chapters and sources.

### 05 — Enumerate before you build

Required fields:

- `CASE-MATRIX`: cases, requirement IDs, and named proof.
- `INPUT-MATRICES`: input classes crossed with applicable situations.
- `CONSERVATION-LAWS`: permanent balancing invariants.
- `GATE-EVIDENCE`: zero undecided cells.

The checker rejects `UNDECIDED` in this stage.

### 06 — Model the data first

Required fields:

- `DATA-MODEL`: authoritative and derived stores with lifetimes.
- `MODULE-MAP`: one writer, readers, and one home for each judgment.
- `REBUILD-PROOF`: executed discard-and-rebuild proof with `exit 0`.
- `GATE-EVIDENCE`: each judgment maps to one owner.

### 07 — The requirement ledger

Required fields:

- `TRACE-LEDGER`: every declared requirement ID mapped to design, code owner, and proof owner.
- `TRACE-CHECK`: bidirectional orphan detector with `exit 0`.
- `STANDINS`: declared test stand-ins and their owed upgrade, or `none`.
- `GATE-EVIDENCE`: zero requirement and code orphans.

The checker requires every declared requirement ID in `TRACE-LEDGER`.

### 08 — The plan as a contract

Required fields:

- `EXECUTE-CONTRACT`: entry gates, build laws, lane rules, and close gates.
- `STATUS-TABLE`: generated fourteen-row owner view.
- `LIVE-POINTER`: next unit, its facts, open choices, and waits.
- `ARCHIVE`: byte-faithful superseded blocks.
- `ENTRY-TEST`: fresh-session entry probe with `exit 0`.
- `GATE-EVIDENCE`: entry probe result.

### 09 — Orchestration

Required fields:

- `HOST-EVIDENCE`: active runtime adapter and host-visible pane evidence.
- `LANE-CONTRACTS`: disjoint file owners, role, permission, bans, proof, and report path.
- `LANE-REPORTS`: attributed durable report IDs and digests.
- `RETURN-VERIFICATION`: `DECLARED <n> VERIFIED <n>` with equal positive counts.
- `GATE-EVIDENCE`: byte verification for every returned file.

A route label is not host evidence. No product edit may exist before this stage passes.

### 10 — Implementation discipline

Required fields:

- `DIFF`: verified product diff digest and owned file list.
- `LINE-DELTA`: `ADDED <n> REMOVED <n> NET <signed-n>`.
- `IMPACT-VERDICTS`: before and after verdict for every affected surface.
- `LEAST-CODE`: `YES` plus the deletion or simplification considered.
- `GENERATED-SOURCE-CHECK`: confirmation that canonical sources, not generated views, changed.
- `GATE-EVIDENCE`: all lane reports accepted against actual bytes.

The checker verifies that `NET = ADDED - REMOVED`.

### 11 — Verification in layers

Required fields:

- `PROOF-RUN`: complete shape and requirement commands with `exit 0`.
- `RED-PROOF`: `PASS R<n> RED-EXIT <nonzero> GREEN-EXIT 0 COMMAND <command>`.
- `COVERAGE-MAP`: named function or requirement population and accounted count.
- `CONSERVATION-PROOF`: executed invariant command with `exit 0`.
- `FULL-READ`: complete-code review question and verdict.
- `MEMBER-WALK`: real journey command or observation with `exit 0`.
- `REHEARSAL`: clean production-like run with `exit 0`.
- `GATE-EVIDENCE`: proof manifest digest and results.

### 12 — The live integrity layer

Required fields:

- `DOCTOR-COMMAND`: independent re-derivation command.
- `DOCTOR-EXIT`: integer `0`.
- `ERROR-SHAPE`: one renderer and its source, location, message, and offending-input fields.
- `STALENESS-SIGNAL`: member-visible last success, age, and rejected count.
- `GATE-EVIDENCE`: doctor result on real data.

### 13 — The close ritual

Required fields:

- `FINDINGS`: enumerated census artifact and digest.
- `CLOSURE`: `FOUND <n> FIXED <n> DEFERRED <n> OPEN 0`.
- `DEFERRED-OWNERS`: `none` or one owner and reason per deferred new-scope item.
- `INDEPENDENT-REVIEW`: `PASS` plus attributed reviewer result and digest.
- `REPUBLISHED`: generated views rebuilt from source with `exit 0`.
- `CLOSE-REPORT`: owner-facing outcome, proof, new issue, and one question or `none`.
- `GATE-EVIDENCE`: enumerated counts and review result.

The checker requires `FOUND = FIXED + DEFERRED` and `OPEN 0`.

### 14 — The improvement loop

Required fields:

- `SURPRISES`: enumerated unexpected defect IDs, or `none`.
- `INSTRUMENT-REPAIRS`: repaired instrument per surprise, or `none` when there was no surprise.
- `PERMANENT-TESTS`: new proof per surprise, or `none` when there was no surprise.
- `METHOD-UPDATE`: generator, template, playbook, or other inherited method update, or `none` when
  there was no surprise.
- `GATE-EVIDENCE`: defect class closure, not only case closure.

When `SURPRISES` is not `none`, none of the other three fields may be `none`.

## Update and recovery

Take an exclusive lock before updating a record. Re-read its revision and content digest under the
lock. If another session advanced it, reload and reverify affected evidence before writing. Publish
through a temporary file and atomic replacement. Never edit a generated view by hand.

A failed stage keeps all prior passed evidence. Set the header to the failed stage and `blocked`,
record the exact failure in `GATE-EVIDENCE`, and stop. Resume at that stage after current evidence is
restored. Set `status: closed` only for a passing stage 14 record.
