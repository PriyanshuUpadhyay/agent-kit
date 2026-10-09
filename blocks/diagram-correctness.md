# diagram-correctness
Concept: A reviewer proves each diagram tells the truth about its source, invents nothing, and reads on a phone.
Serves: review
Source: references/explain-formats.md:25-27, :36-37; html-plan pack: skills/html-plan/SKILL.md:82 (rule 8, real over drawn), :130 (no clipping, arrows do not cross labels); skills/ink/references/qa.md:73-75 (lettering), :49-51 (each key frame reads on its own); web-interface-guidelines pack: command.md:168-170 (finding format)

## Rules
- The source of truth is {{source_of_truth}}. First name the part of it that each diagram draws, with its path.
- Map each node and each arrow to one source line. Write one row per item: item, source `path:line`, `match` or `miss`.
- A node or an arrow with no source line is an invented component. It is a `miss`.
- Real over drawn: names on the diagram use the same words as the source.
- Every branch in the source leads somewhere in the diagram, including the edge cases.
- Read each label at 375 px wide at 100 % zoom. No label is clipped, and no arrow crosses a label. A moving part never hides a letter.
- The diagram reads on its own: a reader gets the caption's point from the picture without the body text.
- Write each finding as `path:line - issue`, grouped by file.

## Example
Initial state: the request-flow diagram has nodes CLI, agent, collector, store, and cache. The source is `docs/architecture.md:10-24`.
Action: build the table. CLI `:11 match`, agent `:13 match`, collector `:15 match`, store `:18 match`, cache: no line, `miss`. The arrow "retry x3" matches `:21`. Screenshot at 375 px: the "collector" label overlaps the retry arrow.
Result: two findings, `site/index.html:88 - node "cache" not in docs/architecture.md` and `site/index.html:95 - retry arrow crosses "collector" label at 375 px`.

## Check (script)
- For each source `path:line` in the tables of `<flow-folder>/06-review.md`, `rg -n '<item name>' <path>` shows the item at that line: each citation is real.
- `ls tmp/shots/` lists one 375 px screenshot per diagram, and each path is in its table: every diagram was seen at phone width.

## Check (judge)
- Does any node, arrow, or label say something that {{source_of_truth}} does not say? Quote the diagram text and the source line, or write "no source line".
- Does `06-review.md` hold one table per diagram, with one row per node and per arrow? Quote one table.
- Is each `miss` row followed by a fix row? Quote each miss and its fix.
- Were the tech-diagram-concept checks (node count, every branch ends, caption) run and recorded? Quote the record.
