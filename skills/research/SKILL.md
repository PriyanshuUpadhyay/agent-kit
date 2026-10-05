---
name: research
description: Research one question and write a short evidence-backed report, shown in full in the reply and kept as a file. Use when the user says research, look into, find out, compare, find me, writeups, articles, good reads, or asks what others do, and for "research continue <folder>". Calls the `web-search` skill for a wide forum search. A Fable chair sends the web part to a `search.web` seat.
---

# Research

Answer one question from evidence. Keep the report as a file, and put the whole report in the
reply.

## Start or continue

Research is a step run, so the kit's `references/step-run.md` owns the status line, pick-up,
close, and when a step waits for the user. "research <question>" starts a run in
`~/.claude/reports/<YYYY-MM-DD>-<slug>/`. "research continue <folder>" picks it up.

| File | Needs | Holds |
|---|---|---|
| `01-question.md` | none | the question in one line and the decision it serves in one line |
| `02-local.md` | question | what the local sources say, with paths |
| `03-web.md` | question | what the web says, with links, and the `web-search` report path if one ran |
| `04-test.md` | local, web | for a tool pick, each candidate's install, task, time, and result; else `skipped: not a tool pick` |
| `05-report.md` | local, web, test | the report path and the result of the link check |
| `06-close.md` | report | the reply as sent |

## 01-question

Write the question in one line, and the decision it serves in one line. Show both and go on. If two
readings of the question lead to different work, set the step to `waiting` with one question.

## 02-local

Read, in this order:

1. the repository at hand;
2. its docs;
3. prior reports under `~/.claude/reports/`;
4. council logs under `~/.claude/council-log/`.

For each decision, track the open question, primary evidence, contrary evidence, and remaining
gap in the report. Inspect the source's actual method or code before accepting its headline.
Separate independent origins from pages that repeat one origin. Page counts and agreeing agents
do not establish correctness. If evidence is thin, name the gap instead of making the claim
stronger; the user does not need to ask for a second, deeper pass.

## 03-web

Under a Fable chair, one `search.web` seat does the web part and writes its notes to
a file; any other session uses its own search and fetch tools. Either way the web part follows the
Depth rule and the blocked-site ladder (the brief's **method** item) in `web-search`: name the
known answers as baseline only, seed the under-discussed candidates, and dig below the first page
of results.

Invoke the `web-search` skill when any of these is true:

- the user says intensive, wide, forums, or community;
- the question is about practice or opinion rather than fact;
- this session's own fetches are blocked;
- the local step or a first web pass returned only the answers the user already knew.

Its report is one source among the others, not the answer.

## 04-test

When the question picks a tool, library, or service for later use, test the candidates on this
machine. Make a shortlist of at least three. Install each one in a scratch place, run the same real
task on each, record time and success, and remove the ones you do not pick. A candidate that is not
installed stays on the list, because install time is not a reason to drop it. A slower, tested
answer is preferred over a fast pick from reading alone. Ask before an install that changes state
outside a scratch place, such as a GUI permission or a system service.

## 05-report

Write `~/.claude/reports/<YYYY-MM-DD>-<slug>.md`, under 800 words, in plain words, in this order:

1. **Answer** — the answer first, in two or three sentences.
2. **Evidence** — each claim with its link.
3. **What is contested** — where the sources disagree.
4. **Sources** — newest first, with dates.

Check that every link resolves before you finish. An HTTP status shows only that the page opens,
so also find the claim's number or wording on the page you cite. Mark a link that does not resolve
or does not support its claim, and drop the claim that rests on it alone. When you convert a page,
PDF, or table to text, compare its headers, units, and values with the source and keep the page or
cell location in the citation. If the conversion lost structure, cite the original.

Example. The question is "does anyone run two coding agents on one repository". You read two prior
reports, then fetch six pages. One returns 404. The report keeps five links, marks the sixth
"(link dead)", and the reply shows the whole report.

## 06-close

Open the reply with the first screen in `~/.claude/references/plan-layout.md`. Then put the whole
report below it, from its `#` title down, and give the file path in one line.

## Guards

- Never invent a quote. Quote only text you read.
- Mark "(snippet only)" when a page could not be opened and only its search snippet was available.
- Prefer 2025-2026 sources. Say so when the best source is older.
- Do not edit any repository. This skill writes only its own report and its run folder.
