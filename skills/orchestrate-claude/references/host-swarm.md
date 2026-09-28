# Orchestrate from Claude — Swarm host reference

This reference is active under the `[agent-host: herdr]` host contract.
Set `SWARM_ADAPTER=herdr` under Herdr (`HERDR_ENV=1`).
Set `SWARM_ADAPTER=tmux` inside tmux.

## Session

Create the swarm session and record the orchestrator pane.

```sh
export SWARM_SESSION_ID=$(swarm session new lane)
export SWARM_AGENT_ID=orchestrator
swarm agent add orchestrator orchestrator
```

The command `swarm agent add orchestrator orchestrator` records the chair pane so that a child finish notification rings the chair.

## Seats

Spawn each seat with `swarm launch`.

```sh
swarm launch <id> <role> --cwd <abs path> [-- <extra>]
```

The route owns model, effort, sandbox, and approval settings.
Seat identifiers must carry the run id.
Never pass `SWARM_*` environment variables on the command line.

## Work

Write long briefs to a file, and make the ask prompt a one-line pointer to that file.
When you run rounds, write `round: N` on the first line of the ask.

Send the ask prompt to a seat.

```sh
printf '%s' '<ask>' | swarm send <id> ask
```

A reply arrives as a `swarm: new message` prompt in the chair pane.
Read the inbox, read the body file under `$SWARM_HOME/.swarm`, and acknowledge the message.

```sh
swarm inbox
# Read runs/<session>/<seq>.txt under $SWARM_HOME/.swarm
swarm ack <seq>
```

Discard any summary if its first line does not match the current round.
Completion is the accepted inbox message, and you must never read the screen for completion.

## Report-only seats

The seat brief must forbid repository edits, commits, worker spawns, and user notifications.
The seat writes only its attributed result to scratch and sends that result with `swarm finish`.

## Uptake

The sweep command re-rings an ask at most once, 60 seconds after the first ring, and only while
the child has not read its inbox.
The `swarm-orchestrator` skill owns how to run the sweep.

If a child pane dies, the orchestrator receives a summary message from that child.

## Close-out

Run `swarm close <id>` for every seat that this run spawned.

```sh
swarm close <id>
```

Confirm the closure with the pane list of the active host.

## Open items

Two open items exist today.
1. No Stop-hook gate covers swarm seats (the old completion gate was removed with herdr-ops).
2. The sandboxed-Codex drop box is not on the swarm path.
