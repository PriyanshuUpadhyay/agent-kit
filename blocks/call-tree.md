# call-tree
Concept: The impact step shows what changes as a short marked call tree with real paths.
Serves: impact
Source: html-plan pack: skills/html-plan/references/blocks.md:101-106 (doc-calls), :5 (+ - ~ convention); skills/flow/SKILL.md (step table, 04-impact row)

## Rules
- Write the tree as plain text in a fenced block in `04-impact.md`.
- One call per line. Column 0 is the mark: `+` new, `-` removed, `~` changed entrypoint, `?` proposed (the reader can strike it), a space for context.
- An entrypoint starts at column 2. Each level adds 2 spaces. A blank line starts a new entrypoint.
- `**bold**` marks a new symbol. A `+` row without bold is a new call to something that exists.
- End each line with `@ path:line` and, if needed, `-- one clause`. For a new function in a file that exists, cite the line it goes after.
- Keep one tree under about 15 rows.
- The step names the existing features that change, or says "independent".

## Example
Initial state: the repo has `site/index.html` and `site/main.js` with `initNav()`.
Action: write in `04-impact.md`:
```
~ <body>                                  @ site/index.html:12
+   <section id="flow"> **flowDiagram**   @ site/index.html:48   -- the diagram
~   initNav()                             @ site/main.js:3
+     **copyInstall()**                   @ site/main.js:21      -- new click handler
?     trackCopy()                         @ site/main.js:30      -- strike if not wanted
```
Result: the reader sees two new symbols, one changed entrypoint, and one optional call. Impact: "independent; no other page uses `main.js`."

## Check (script)
- `awk '/^```/{f=!f;next} f && NF && !/^[-+~? ] .*@ [^ ]+:[0-9]+/' <flow-folder>/04-impact.md` prints nothing: every tree row has a mark in column 0 and an `@ path:line`.
- `awk '/^```/{f=!f;next} f && NF' <flow-folder>/04-impact.md | wc -l` prints about 15 or less: the tree stays short.
- For each `@ path:line` of an existing file, `rg -n '<symbol>' <path>` shows the symbol at that line: each citation is real.

## Check (judge)
- Does `04-impact.md` name the existing features that change, or say "independent"? Quote the line.
