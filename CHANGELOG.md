# Changelog

jeweler (the library) and its model are versioned separately. Library versions follow semver;
the model is v1, v2, ... and a new model ships in a new minor library version.

## 0.2.0 (2026-11-12): model v1

From the first app's review (thanks, Classy):
- Anything that isn't a string (`null`, `undefined`, a number) now scores `null` and `gated` returns false, instead
  of crashing with "Cannot read properties of undefined". `rawScore` throws a TypeError saying text must be a string.
- The built-in model is frozen, so no caller can change its threshold or weights for everyone else.
- The model ships once: the separate `jeweler/model.json` export is gone (the raw file is `models/jeweler-v1.json`
  in the repo). Installed size 298 KB → 172 KB, download 104 KB → 58 KB. Breaking only for that export.
- README: it's an ES module (`require` needs Node 22.12+), and accented or non-Latin letters aren't understood yet.

## 0.1.0 (2026-11-11): model v1

- First release. `score(text)` and `threshold` with model v1 built in; `score(text, model)` for another model
  file; `gated`, `rawScore`, `parseJewel` and the `Jewel` types; the raw model as `jeweler/model.json` (removed in 0.2.0).
- Model v1 is trained on public text only (the research notes call it Jewel 3; earlier research models were
  trained on private text and are not published).
- The runtime treats whitespace exactly as Python does (U+001C-U+001F and U+0085 are whitespace, U+FEFF is not)
  and reads `\w` in the email check as Unicode, so it scores exactly like the trained model.
- Trimming is linear: a crafted copy with millions of spaces can't stall the app.
- Tests: parity with Python on 416 synthetic texts, the gate, hostile input, and a packed-install check.
