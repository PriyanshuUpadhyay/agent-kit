---
name: research
description: Research one question and write a short evidence-backed report, shown in full in the reply and kept as a file. Use when the user says research, look into, find out, compare, find me, writeups, articles, good reads, or asks what others do. Calls the `web-search` skill for a wide forum search. A Fable chair sends the web part to a `search.web` seat.
---

# Research

Answer one question from evidence. Keep the report as a file, and put the whole report in the
reply.

## 1. Pin the question

Write the question in one line, and the decision it serves in one line. Show both and start. If two
readings of the question lead to different work, ask one question first.

## 2. Gather local first

In this order:

1. the repository at hand;
2. its docs;
3. prior reports under `~/.claude/reports/`;
4. council logs under `~/.claude/council-log/`.

Then the web. Under a Fable chair, one `search.web` seat does the web part and writes its notes to
a file; any other session uses its own search and fetch tools. Either way the web part follows the
Depth rule in `web-search`: name the known answers as baseline only, seed the under-discussed
candidates, and dig below the first page of results.

For each decision, track the open question, primary evidence, contrary evidence, and remaining
gap in the report. Inspect the source's actual method or code before accepting its headline.
Separate independent origins from pages that repeat one origin. Page counts and agreeing agents
do not establish correctness. If evidence is thin, name the gap instead of making the claim
stronger; the user does not need to ask for a second, deeper pass.

## 3. Call `web-search` when the question is wide

Invoke the `web-search` skill when any of these is true:

- the user says intensive, wide, forums, or community;
- the question is about practice or opinion rather than fact;
- this session's own fetches are blocked;
- the local step or a first web pass returned only the answers the user already knew.

Its report is one source among the others, not the answer.

## 4. Write the report

Write `~/.claude/reports/<YYYY-MM-DD>-<slug>.md`, under 800 words, in plain words, in this order:

1. **Answer** — the answer first, in two or three sentences.
2. **Evidence** — each claim with its link.
3. **What is contested** — where the sources disagree.
4. **Sources** — newest first, with dates.

Check that every link resolves before you finish; an HTTP status check is enough. Mark a link that
does not resolve, and drop the claim that rests on it alone.

Example. The question is "does anyone run two coding agents on one repository". You read two prior
reports, then fetch six pages. One returns 404. The report keeps five links, marks the sixth
"(link dead)", and the reply shows the whole report.

## 5. Reply

Open the reply with the first screen in `~/.claude/references/plan-layout.md`. Then put the whole
report below it, from its `#` title down, and give the file path in one line.

## Guards

- Never invent a quote. Quote only text you read.
- Mark "(snippet only)" when a page could not be opened and only its search snippet was available.
- Prefer 2025-2026 sources. Say so when the best source is older.
- Do not edit any repository. This skill reads and writes its own report only.
