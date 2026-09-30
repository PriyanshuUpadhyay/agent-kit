# Websites

A website is one more form. The contract, the routes, and the seven steps stay the same. This file
lists what changes in each step.

Example. The user screen-records a product site with a yellow page, a 3D handheld console as the
hero, an ink-splash loader, and a page transition that tears the screen. They ask for "a site like
this for my coffee brand". The shots become sections: loader, hero, three feature sections, footer.
The look becomes a `DESIGN.md` plus the 3D and texture rules in `02-look.md`. The style frames are
the hero at 1440 px and 390 px wide, beside the reference at the same widths. The coffee brand keeps
its own name, logo, product, and copy. The page borrows the loader idea, the density, and the motion
grammar.

## Scope

- Ink builds landing pages, portfolios, product and launch pages, scroll stories, a 3D or shader
  hero, a loader, and page transitions.
- Login, stored form data, a database, a CMS, and dashboards are app work, which the repo's own
  workflow owns. Ink can still deliver the hero or the loader as one component for that app.

## 1. Intake

- Sections replace shots. For each section, record its job (what the reader learns or does), its
  content, and its start, settled, and end state as the reader scrolls.
- Screen widths replace duration and fps. Default to 1440 px and 390 px, plus any width the user
  names.
- Record every driver the page uses: load, scroll, pointer (hover and cursor), and click. See
  Drivers in [story-and-motion.md](story-and-motion.md).
- A screen recording is the best site reference. Record one full scroll at each width. Extract
  frames at each section's settled state, at each transition midpoint, and across the loader.
- Research sources for sites: [threeui.com](https://threeui.com) (three.js site templates, some
  with their prompt), [21st.dev](https://21st.dev) (components and page templates), and the
  [GSAP showcase](https://gsap.com/showcase/). A template's prompt is a `stated` source. Its
  rendered page is the `visible` one.

## 2. Look

- Write `DESIGN.md` in the piece folder in the
  [DESIGN.md format](https://github.com/google-labs-code/design.md): colors, typography, spacing,
  rounded, and components as YAML tokens, then the prose sections. Check it with
  `npx @google/design.md lint DESIGN.md`, which also tests WCAG contrast of the component color
  pairs. The linter exits 0 and reports low contrast only as a warning, so read its findings. Any
  error and any `contrast-ratio` finding is a `miss`.
- `DESIGN.md` owns color, type, and spacing. `02-look.md` keeps what `DESIGN.md` cannot hold:
  light, 3D, texture, the mark budget, and the motion grammar. It names `DESIGN.md` for the rest,
  so each value has one home. The `look` token object loads the tokens from
  `npx @google/design.md export --format dtcg DESIGN.md`, which keeps typography. The `css-vars`
  format drops it.
- A `DESIGN.md` pulled from a live site (the
  [design-md-chrome](https://github.com/bergside/design-md-chrome) extension) or taken from a
  collection ([awesome-claude-design](https://github.com/VoltAgent/awesome-claude-design)) is
  `stated` evidence. Measure the rendered pages before you trust its values.
- When the `design-taste-frontend` skill (Taste Skill) is installed, read it for the layout and
  type rules that keep a page from looking like a template.

## 3. Story and motion

- The story sheet lists the sections in scroll order. Each section has one settled state that
  carries its key fact.
- The motion list names the loader, the section entrances, the scroll-linked motion, hover and
  cursor states, and the page transitions.
- For UI timing and easing, read a motion skill when one is installed, such as `animate` from
  Emil Kowalski's pack or `design-motion-principles`.

## 4. Style frames

Render three frames from the real page code: the hero at 1440 px, the hero at 390 px, and one
middle section at 1440 px. Put each beside the reference at the same width and score it as in
[qa.md](qa.md).

## 5. Animatic

Build a grey-box page: every section as flat boxes with the real text sizes, the final scroll
lengths, the loader, and the real transitions. Capture a scroll-through at both widths with
`?shot=<section>&u=` frames, and check that each settled state reads.

## 7. QA

Run these in addition to [qa.md](qa.md), at each width:

- No sideways scroll: `document.documentElement.scrollWidth <= innerWidth` in the page.
- Every link and control takes focus with Tab and shows a focus ring.
- Every section's content shows with `prefers-reduced-motion: reduce`.
- Text over an image, a video, or a 3D scene passes contrast in the screenshot, not only in
  `DESIGN.md`.
- The loader ends on the painted hero, never on a blank frame. Record the time to the first
  painted hero on a throttled connection.
