# agent-kit

Workflow skills for coding agents (Claude Code, Codex, Antigravity). Each skill is a folder with a
`SKILL.md` that the agent loads when the task matches its description.

## Skills

| Skill | Use |
|---|---|
| `pair` | Write code with the user, one approved diff at a time |
| `deliver` | Drive one named task to a checkable exit condition, stop before a push or merge |
| `research` | Answer one question from evidence in a short report |
| `web-search` | Three visible seats search different parts of the web, the chair merges |
| `council` | A visible debate between Claude, GPT and Gemini voices that ends in a verdict |
| `review-pr` | Judge a diff for correctness, ownership and contracts |
| `pr-walkthrough` | Explain a diff in plain words before review |
| `decisions` | Record consequential choices as in-repo ADRs |
| `cleanup-gate` | A full cleanup pass, only on request |
| `engineering-standards` | Scoped engineering rules for design, code and review |
| `prove-it-works` | What counts as proof that a change works |
| `sequence-verifiable-units` | Order multi-step work so each step can be checked |
| `minimize-reader-load` | When code gets its own function, file or module |
| `reference-driven-creative-coding` | p5.js and Canvas pieces from a story or a visual reference |
| `orchestrate-claude`, `orchestrate-codex`, `orchestrate-agy` | Runtime adapters that bind the skills' worker needs to each agent CLI |

`references/plan-layout.md` is the plan shape that several skills point to.
`contracts/orchestration-requirements.schema.json` describes what a skill may ask of a runtime adapter.

## Install

Link the skills you want into your agent's skills folder, and the references next to them:

```sh
git clone https://github.com/PriyanshuUpadhyay/agent-kit ~/agent-kit
mkdir -p ~/.claude/skills ~/.claude/references
for s in ~/agent-kit/skills/*/; do ln -sfn "$s" ~/.claude/skills/"$(basename "$s")"; done
ln -sfn ~/agent-kit/references/plan-layout.md ~/.claude/references/plan-layout.md
```

Codex reads `~/.agents/skills` and Antigravity reads `~/.gemini/config/skills`.

## What the skills expect

- Skills that start workers (`council`, `web-search`, `research`) run them as visible panes through
  [swarm](https://github.com/PriyanshuUpadhyay/swarm).
- Skills write their files under `~/.claude/` (`pair/`, `reports/`, `council-log/`) and create
  those folders on first use.
- `council` calls `~/.claude/scripts/ensure-council-access.py`, which is not part of this kit yet.

## Public-safety gate

`scripts/public-safety.sh` runs [gitleaks](https://github.com/gitleaks/gitleaks) with
`.gitleaks.toml` plus a private word list that never enters the repo. Enable the pre-commit hook
with `git config core.hooksPath .githooks`.

## License

MIT
