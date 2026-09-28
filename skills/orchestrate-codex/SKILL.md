---
name: orchestrate-codex
description: Bind provider-neutral multi-agent workflow requirements to Codex orchestration mechanics. Use when a Codex root session runs a portable skill that requests isolated workers, routed models, durable results, or parallel fan-out.
---

# Orchestrate from Codex

Enforce the workflow's behavior contract independently of the route's filesystem capability. A
report-only seat must not edit the repository, apply findings, or commit, even when its runner has a
writable sandbox. It may write only its attributed scratch result.

Translate a portable workflow's roles, seats, permissions, and completion
contract into the active execution environment. Do not reinterpret the
workflow or duplicate its prompts here.

## Contract operations

Provide every version-1 orchestration operation declared by a portable workflow:

- resolve semantic roles and exhaust only their declared fallbacks;
- validate visibility, isolation, permission, durable-result, and teardown capabilities;
- create uniquely named visible leaves owned by the current run;
- dispatch seat briefs under one stage deadline;
- accept only attributed durable results;
- relay the workflow's refusal or degradation disposition to the chair; and
- close only leaves owned by the current run.

Read the workflow's `orchestration.json` as requirements, not suggestions. The workflow owns
topology, prompts, rounds, result routing, and refusal semantics. This adapter executes those
requirements and fails closed when the active host cannot satisfy them.

## Bind the environment

1. Require an injected `[agent-host: ...]` contract before creating workers.
   If none exists, continue serially only when the workflow permits it;
   otherwise report the missing orchestration capability and stop.
2. Load the host skill named by that contract. The host owns pane creation,
   transport, liveness, artifact collection, and teardown.
3. Resolve every requested workflow role with
   `swarm roles get <role>`. Preserve `runnerId`,
   `provider`, `mode`, `model`, `effort`, and `fallbackRunnerIds`. Reject an
   unresolved role or a route the active host cannot execute.
4. Give the host one leaf specification per seat: unique name, routed runner,
   cwd, permission level, input digest, prompt or brief, expected artifact,
   and deadline.
5. Accept only results validated by the host's durable completion channel.
   Close only workers created by this run.

This section binds an ORCHESTRATOR session. Under a visible host, Codex
collaboration workers are not an execution path for it: they run in-process and
are not visible panes. Never replace a failed visible seat with `spawn_agent`, a
headless CLI, or a background process. Outside a host, use Codex collaboration
only when the user has explicitly granted that scoped fallback and the workflow
does not require visibility.

A WORKER session follows its host worker contract instead: it is a leaf, never
creates panes or descendants, and never notifies the user. It reports one
consolidated result to the orchestrator and to nobody else.

## Task files

A skill that keeps a task file across `/clear` keeps it in `~/.claude/pair/`.
