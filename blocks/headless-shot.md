# headless-shot
Concept: Take page screenshots with Playwright's chrome-headless-shell, and know its limits.
Serves: design, build, review
Source: style-frames-concept block (split out 2026-10-09); blocks trial 2026-10-09, rounds 1 and 2 (downscaled view, tall shots found 2 defects)

## Rules
- Command: `<chrome-headless-shell> --headless --screenshot=/abs/out.png --window-size=W,H file:///abs/path/index.html`. Widths are 1440,900 and 390,844 and 375,812.
- Find `<chrome-headless-shell>` with `npx playwright install chromium-headless-shell`, which prints the folder it downloads to; the binary is inside it.
- Put a frame beside the reference at the same scale with `magick ref.png frame.png -resize x900 +append compare-NN.png`.
- Limit: the screenshot is one viewport tall. For a long page, also shoot with a taller window (for example 1440,4000) or scroll with an anchor URL.
- Limit: an image viewer may show a 375 px shot downscaled. Crop the part you judge at 100 % (`magick out.png -crop 375x400+0+0 crop.png`) before you judge small text.
- Limit: it runs no real clicks or clipboard. Say "not tested in a real browser" for those.
- Use this binary, not a desktop Chrome app.

## Example
Initial state: `index.html` exists. Action: shoot 1440,900 and 375,812, then crop the 375 shot's diagram at 100 %. Result: the crop shows label size truly, and the report names the clipboard as not tested.

## Check (script)
- `ls tmp/shots/` lists each screenshot path that a step file names: no claimed shot is missing.

## Check (judge)
- Does each claim about small text cite a 100 % crop, not a full downscaled shot? Quote the claim and the crop path.
- Are untested interactions (real clicks, clipboard) named as not tested in a real browser? Quote the line.
