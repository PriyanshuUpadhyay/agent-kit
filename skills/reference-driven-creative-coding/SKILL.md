---
name: reference-driven-creative-coding
description: Build p5.js or Canvas creative-coding pieces that tell a story or match a visual reference, such as an animated short, story reel, explainer, title sequence, looping background, generative still, or infinite zoom. Keeps the story (beats, shots, transitions), the look (palette, line, texture taken from references), and the motion apart, so a new beat, scene, or style never forces a rewrite. Produces reference notes, a style grammar, a storyboard and shot list, a scene graph, an animatic, a visual QA log, and an export handoff. Use for "make this in p5.js", "animate this story", "storyboard and code this", "creative coding from this reference", "recreate this style in code", or "animate this like the reel", and for extracting style, story, and motion rules from references without building.
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
- Prove the story before the detail. Build an animatic first: every beat, flat placeholder shapes,
  final timing, real transitions. A beautiful frame in a story that does not read is wasted work.
- Keep the layers in their own places. Scene code reads colours from look tokens and has no colour
  literals. The shot list owns when and how long, and scene code has no story timing. Transitions own
  how two shots meet. The layer table above says where each thing lives.
- Keep one seed and derive every value from time and the seed, so any frame can be re-rendered alone.
- Inspect real rendered frames at each milestone. Code that runs does not prove the visual works.
- Return source files, run instructions, controls, export path, a provenance note, QA evidence, and
  the known differences from the references.

## Route the request

- `study`: one technique or one transition (a halftone pass, a match cut, a morph).
- `prototype`: the animatic. The whole story in flat shapes with final timing and transitions.
- `production`: the full look, texture, lettering, export, and edit handoff.
- `analysis-only`: extract story, style, and motion rules from references without building.

Default to `prototype` for anything with more than one beat. A polished multi-scene piece is not a
one-prompt task, so do not suggest it is.

## Required inputs

1. The story: a logline or brief, the beats, the characters, props, and places, and any words on
   screen. If the user gives none ("make something cool"), propose a 3-5 beat story in one line each
   and build that. Do not default to a pattern you used before.
2. Visual references with provenance. Record what each one informs: look, motion, structure, or more.
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
3. **Write the style grammar.** Create `style-grammar.md` and turn it into one `look` token object.
   A scene that needs a different look (a flashback, a dream) gets a named variant of the same token
   keys, not new literals.
4. **Storyboard, shot list, and scene graph.** One row per shot: time range, beat, scene, focal
   subject, camera, transition in and the story reason for it, the exit and entry vector of each
   continuity cut, and a verification frame. Choose each transition from the catalogue in the
   storyboard reference, and apply its seam law to continuity cuts. Write `scene-graph.md` with nesting,
   masks, coordinate spaces, and lifetimes.
5. **Animatic.** Build the shot list, scene modules as flat shapes, the transitions, the timing, and
   the loop seam if there is one. Follow [implementation.md](references/implementation.md). Render
   the key frame of every beat, the midpoint of every transition, and the seam. Fix readability,
   pacing, crop, and continuity before any detail.
6. **Detail passes.** Add one system at a time, always through the look tokens: silhouettes and
   fills, contour hierarchy, depth and masks, texture, secondary motion, lettering, final colour.
   Re-render the same decisive frames after each pass so regressions show. Do not hide a mismatch
   under texture.
7. **Visual QA.** Follow [visual-qa.md](references/visual-qa.md). Inspect full-size frames, not only
   a contact sheet, and read back the exported file.
8. **Export and edit handoff.** Keep the coded artwork apart from editorial layers (presenter
   cutout, captions, titles, sound) unless the user asks for one monolithic build.

Deliver the source and exact run command, the seed and parameter preset, still and export controls,
frame or capture instructions, duration, fps, dimensions, loop and alpha behaviour, editor notes with
safe areas, and `reference-notes.md`, `style-grammar.md`, `storyboard.md`, `scene-graph.md`, and the
QA log.

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
