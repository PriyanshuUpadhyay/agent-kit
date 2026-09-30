---
name: reference-driven-creative-coding
description: Build code-drawn creative-coding pieces (Canvas 2D, p5.js, three.js, WebGL or WebGPU shaders, 3D models) that tell a story or match a visual reference, such as an animated short, story reel, explainer, title sequence, looping background, generative still or plate, dense comic or print-style illustration, or infinite zoom. Keeps the story (beats, shots, transitions), the look (palette, line, texture taken from references), and the motion apart, so a new beat, scene, or style never forces a rewrite. Produces reference notes, a style grammar with measured numbers, style frames checked beside the reference, a storyboard and shot list, a scene graph, an animatic, a visual QA log, and an export handoff. Use for "make this in p5.js", "animate this story", "storyboard and code this", "creative coding from this reference", "recreate this style in code", or "animate this like the reel", and for extracting style, story, and motion rules from references without building.
---

# Reference-driven creative coding

Turn a story, a visual reference, or both into a creative-coding build that someone can inspect and
extend. Keep three layers apart, because each changes for its own reasons:

| Layer | Answers | Comes from | Lives in |
|---|---|---|---|
| Story | what happens, in what order, for how long | the brief, a script, or a reference's structure | `storyboard.md` and the shot list in code |
| Look | palette roles, line, shape, texture, type | visual references, or a labelled original choice | `style-grammar.md` and one `look` token object |
| Motion | camera in each shot, transitions between shots, local motion | references and story intent | `storyboard.md`, scene and transition modules |

Example: a 30 s reel, "a paper boat survives a storm". The story is five beats (calm, wind, wave,
capsize, sunrise). The look comes from the user's watercolour reference. The motion is a slow push-in,
a whip pan into the storm, and a match cut from the boat's sail to the rising sun. A neon restyle
swaps only the look tokens. A new beat adds one shot entry and at most one scene module.

## Contract

- Match a look only from evidence. A claim that the build matches a style needs an accessible visual
  reference (image, video, frame set, URL, or artwork) whose pixels you inspected yourself. Captions,
  creator claims, filenames, and earlier summaries do not replace inspection. Without a reference,
  choose an original look, label the build a reference-free study, and keep the look swappable.
- Keep evidence levels apart: `visible`, `stated`, `inferred`, `unknown`. A creator's process claim
  is evidence of the claim, not of the hidden workflow.
- Turn references into reusable rules. Do not copy protected logos, characters, signatures, or a
  living artist's exact personal style. Keep high-level traits (palette relationships, shape
  language, texture methods, spatial rhythm, motion grammar) and make original content.
- Prove the look and the story before production, each on its own. Style frames drawn with the real
  drawing code prove the look. An animatic (every beat, flat placeholder shapes, final timing, real
  transitions) proves the story. A beautiful frame in a story that does not read is wasted work, and
  a story drawn in flat clip-art shapes has no look yet.
- Match density, not only palette. Measure the reference's layers per mass, line swell and colour,
  tone marks, texture, and depth layers, write the numbers into the style grammar, and meet them.
  Recipes and starting numbers are in [mark-making.md](references/mark-making.md).
- Keep the layers in their own places. Scene code reads colours from look tokens and has no colour
  literals. The shot list owns when and how long, and scene code has no story timing. Transitions own
  how two shots meet. The layer table above says where each thing lives.
- Choose tools for the look and the story, not for a small build. Dependencies, a loading screen,
  3D models, shaders, and WebGPU are acceptable when they make the piece better. The toolbox is in
  [implementation.md](references/implementation.md).
- Keep one seed and derive every value from time and the seed, so any frame can be re-rendered alone.
  A stateful simulation steps with a fixed time step and keeps checkpoints instead.
- Inspect real rendered frames at each milestone. Code that runs does not prove the visual works.
- Return source files, run instructions, controls, export path, a provenance note, QA evidence, and
  the known differences from the references.

## Route the request

- `study`: one technique, one transition, one generative plate, or one style frame (a halftone pass,
  a match cut, a morph).
- `prototype`: style frames plus the animatic. The whole story in flat shapes with final timing and
  transitions, and the look proved on three frames.
- `production`: the full look, texture, lettering, export, and edit handoff.
- `analysis-only`: extract story, style, and motion rules from references without building.

Default to `prototype` for anything with more than one beat. A polished multi-scene piece is not a
one-prompt task, so do not suggest it is.

## Required inputs

1. The story: a logline or brief, the beats, the characters, props, and places, and any words on
   screen. If the user gives none ("make something cool"), propose a 3-5 beat story in one line each
   and build that. Do not default to a pattern you used before.
2. Visual references with provenance. Record what each one informs: look, motion, structure, or more.
   Name one or two of them as the benchmark, with what to learn from it and what not to take. For
   each shot, ask for or extract a start, a middle, and an end frame. Pixels carry a look that words
   cannot, such as a halftone or a line weight.
3. The form: still, loop, linear short, journey, interactive or scroll-driven, or reel background.
4. Aspect ratio, duration, and fps.
5. Content limits: subject, words, brand assets, things that must or must not appear.
6. The delivery target when known: one HTML file, source folder, frames, WebM, or MP4.

Fill low-risk gaps with defaults and record them: 1080x1920 for a vertical reel, 30 fps, 6-12 s for a
loop, 15-45 s for a short. Exact brand copy, logos, likenesses, and publishing destinations are
load-bearing, so ask for them.

## Workflow

1. **Acquire and inspect references.** Inspect a whole video and extract frames at scene boundaries,
   motion extremes, and loop seams. Inspect stills at full resolution and useful crops. Record each
   reference in `reference-notes.md`, then run the passes in
   [reference-analysis.md](references/reference-analysis.md).
2. **Write the story.** Put a story sheet at the top of `storyboard.md`: logline, structure, entities,
   and beats, each beat with its intent (what the viewer should notice or feel). Pick the structure
   and the driver (playback, scroll, or gates) from
   [storyboard-and-motion.md](references/storyboard-and-motion.md).
3. **Write the style grammar.** Create `style-grammar.md` with numbers measured from the reference,
   and turn it into one `look` token object. A scene that needs a different look (a flashback, a
   dream) gets a named variant of the same token keys, not new literals.
4. **Style frames.** Render three frames with the real drawing code, one of them the signature shot
   (a `study` needs only one).
   Add a model sheet (poses, expressions) when a character recurs. Build each mass with the mass
   stack in [mark-making.md](references/mark-making.md). Put each frame beside the matching reference
   crop and score it with the reference match in [visual-qa.md](references/visual-qa.md). Do at least
   two rounds, and start production scenes only when no trait scores a miss.
5. **Storyboard, shot list, and scene graph.** One row per shot: time range, beat, scene, focal
   subject, camera, transition in and the story reason for it, the exit and entry vector of each
   continuity cut, and a verification frame. Choose each transition from the catalogue in the
   storyboard reference, and apply its seam law to continuity cuts. Write `scene-graph.md` with nesting,
   masks, coordinate spaces, and lifetimes.
6. **Animatic.** Build the shot list, scene modules as flat shapes, the transitions, the timing, and
   the loop seam if there is one. Follow [implementation.md](references/implementation.md). Render
   the key frame of every beat, the midpoint of every transition, and the seam. Fix readability,
   pacing, crop, and continuity before any detail.
7. **Detail passes.** Bring every scene up to the approved style frames, one system at a time and
   always through the look tokens: mass stacks, line hierarchy, tone marks, depth layers and masks,
   surface texture, secondary motion and boil, lettering, final colour. Add scenes in batches of
   about eight. Re-render the same decisive frames after each pass so regressions show. Do not hide
   a mismatch under texture.
8. **Visual QA.** Follow [visual-qa.md](references/visual-qa.md). Inspect full-size frames, not only
   a contact sheet, and read back the exported file.
9. **Export and edit handoff.** Keep the coded artwork apart from editorial layers (presenter
   cutout, captions, titles, sound) unless the user asks for one monolithic build.

Deliver the source and exact run command, the seed and parameter preset, still and export controls,
frame or capture instructions, duration, fps, dimensions, loop and alpha behaviour, editor notes with
safe areas, and `reference-notes.md`, `style-grammar.md`, `storyboard.md`, `scene-graph.md`, and the
QA log.

## Effort and cost

Draw style frames and detail passes at high or extra-high reasoning effort. One public build came
out as a flat "Flash" look at medium effort and as watercolor at extra-high effort with a brush
library; it changed both at once, so the cause is not isolated. A production reel is hours of
render, look, and fix loops. One public 26-scene riso rebuild took about 5 h 40 min and 716,000
output tokens. Tell the user the likely cost before production.

## Patterns

A pattern file holds hard-won mechanics for one structure. Load it only when the story needs that
structure. When a build solves a new reusable structural problem, add a pattern file here and one
line to this list.

- [recursive-zoom.md](references/patterns/recursive-zoom.md): worlds nested inside worlds, infinite
  zoom, portal transitions, and a seamless loop by self-similarity.

Candidates without a pattern file yet (several windows, text mode, card stacks, voted chapters, a
live model on a fixed spine) are listed under "Web-native media ideas" in the storyboard reference.

## Output discipline

Never return only a prompt. Return a working artifact or a concrete build package unless the route
is `analysis-only`. Say what was matched, what was changed to stay original, what was not verified,
and what to do next.
