# Worked example — capture → batch-ask → record + reversal

A compact trace of the skill operating across one session. Illustrative, not normative.

## During the session (silent detect → WAL)
> **User:** Let's use Postgres for the store — we need real transactions across orders and inventory.

Appended to `.git/decisions-buffer.json` (had a real alternative): `{summary: "Postgres
for the data store", options_seen: ["Postgres","Mongo"], rationale: "need cross-table
transactions", is_reversal: false}`.

> **User:** For logging just grab pino, it's faster than winston.

Appended (real alternative, but cheap & local → will be Tier-1): `{summary: "pino over
winston", options_seen: ["pino","winston"], rationale: "perf"}`.

…work continues, no interruption. (If the session were compacted here, the WAL survives.)…

> **User:** Actually, scrap the Redis cache layer — it's adding ops burden and the DB is fast enough.

Appended as a **reversal** of the earlier-recorded ADR-0001 (Add Redis cache layer):
`{summary: "drop Redis cache layer", is_reversal: true, supersedes: "0001", rationale:
"ops burden, DB fast enough"}` — and per flush-trigger #2 (after a reversal), flush now.

## Breakpoint — flush
WAL is non-empty → batch-ask:

> I noticed these decisions. Which should I record? (and the one-line why)
>
>   1. Postgres for the data store   why: "need cross-table transactions"
>   2. pino over winston   why: "perf"
>   3. (reversal) drop Redis cache layer, was ADR-0001   why: "ops burden, DB fast enough"
>
> Reply e.g. "all" / "1 and 3" / "skip 2".

> **User:** all — and for #2, we lose winston's transport ecosystem, that's fine.

## Writes (tier chosen at write time)
- **#1 → Tier-2** `docs/decisions/0002-use-postgres-for-data-store.md` (significant:
  Considered Options Postgres/Mongo · Chosen because transactions · Good: ACID across
  orders/inventory · Bad: heavier ops than a document store).
- **#2 → Tier-1 stub** `docs/decisions/0003-pino-over-winston-for-logs.md` (cheap & local;
  one Y-statement: "…chose pino and neglected winston, to achieve lower overhead, accepting
  that we lose winston's transport ecosystem").
- **#3 → Tier-2 reversal** `docs/decisions/0004-drop-redis-cache-layer.md` with
  `supersedes: 0001`. The skill rewrites `0001`'s frontmatter to `status: superseded`,
  `superseded-by: 0004`, leaving its body intact.

Then the flushed flags are cleared from the WAL.

## Index after the flush (`docs/decisions/README.md`)
```
| #    | Title                        | Tier | Status     | Date       | Refs  |
|------|------------------------------|------|------------|------------|-------|
| 0004 | Drop Redis cache layer       | 2    | accepted   | 2026-06-01 | ↑0001 |
| 0003 | Pino over winston for logs   | 1    | accepted   | 2026-06-01 |       |
| 0002 | Use Postgres for data store  | 2    | accepted   | 2026-06-01 |       |
| 0001 | Add Redis cache layer        | 2    | superseded | 2026-05-30 | ~0004 |
```
Then the original `git commit` proceeds.
