---
name: ink
description: Draw pictures, generative plates, and short films where every frame is made by code (Canvas 2D, p5.js, three.js, WebGL or WebGPU shaders, 3D models), from a story, a visual reference, or both. Use for a story reel, animated short, explainer, title sequence, loop, generative still or plate, dense comic or print-style illustration, or infinite zoom; for "make this in p5.js", "animate this story", "storyboard and code this", "draw every frame in JavaScript", "creative coding from this reference", "recreate this style in code", or "animate this like the reel"; and for extracting style, story, and motion rules from references without building. Keeps story, look, and motion apart, proves the look with style frames beside the reference, and proves the story with an animatic.
---

# ink

Every frame is drawn by code, from a story, a reference, or both. Three layers change for their own
reasons, so each one lives in its own place:

| Layer | Answers | Lives in |
|---|---|---|
| Story | what happens, in what order, for how long | `storyboard.md` and the shot list in code |
| Look | palette, light, line, tone, texture | `style-grammar.md` and one `look` token object |
| Motion | camera, transitions, local motion, boil | `storyboard.md`, scene and transition modules |

Example. "A paper boat survives a storm" has five beats. The look comes from the user's watercolour
reference. A whip pan carries the boat into the storm, and a match cut turns its sail into the
sunrise. A neon restyle changes only the look tokens.

## Contract

- Match a look only from pixels you inspected yourself. Without a reference, label the build a
  reference-free study. Keep evidence levels apart: `visible`, `stated`, `inferred`, `unknown`.
- Borrow techniques and high-level traits. Never copy characters, logos, signatures, exact
  compositions, or a living artist's exact personal style.
- Match density, not only palette. Measure the reference, write the numbers down, and meet them.
- Prove the look with style frames and the story with an animatic, both before production.
- Keep the layers apart. Scene code has no colour literals and no story timing.
- Render every frame from time and one seed (`?t=`). A stateful simulation steps at a fixed rate
  and keeps checkpoints.
- Choose tools for the look and the story. Dependencies, load time, 3D, and WebGPU are fine.
- Inspect rendered frames at each milestone. Code that runs does not prove the picture works.

## Routes

- `study`: one technique, transition, plate, or style frame.
- `prototype`: three style frames and the animatic.
- `production`: the full look, texture, lettering, export, and handoff.
- `analysis-only`: rules from references, with no build.

Default to `prototype` for anything with more than one beat. A polished multi-scene piece is not a
one-prompt task, so do not suggest it is.

## Steps

1. **Intake.** Story, references with a benchmark, a start, middle, and end frame per shot, form,
   size, fps, limits, and delivery. See [references.md](references/references.md).
2. **Analyse the references** and write `style-grammar.md` with measured numbers. See
   [references.md](references/references.md).
3. **Story sheet, shot list, transitions, scene graph.** See
   [story-and-motion.md](references/story-and-motion.md).
4. **Style frames** with the real drawing code, one of them the signature shot, scored beside the
   reference for at least two rounds. See [mark-making.md](references/mark-making.md) and
   [qa.md](references/qa.md).
5. **Animatic.** Flat shapes, final timing, real transitions. See [build.md](references/build.md).
6. **Detail passes** up to the style frames, with scenes in batches of about eight. See
   [mark-making.md](references/mark-making.md).
7. **QA, export, and handoff.** See [qa.md](references/qa.md) and [build.md](references/build.md).

A pattern file holds the mechanics of one reusable structure:
[recursive-zoom.md](references/patterns/recursive-zoom.md) covers worlds inside worlds. Add a
pattern file when a build solves a new one.

## Effort and cost

Draw style frames and detail passes at high or extra-high reasoning effort. A production reel takes
hours of render, look, and fix loops. One public 26-scene rebuild took about 5 h 40 min and 716,000
output tokens. Tell the user the likely cost before production.

## Output

Never return only a prompt. Return the build, the run command, the seed, and the QA log. Say what
matched, what changed to stay original, and what was not verified.
