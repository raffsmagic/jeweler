# Changelog

jeweler (the library) and its model are versioned separately. Library versions follow semver;
the model is v1, v2, ... and a new model ships in a new minor library version.

## 0.1.0 (unreleased): model v1

- First release. `score(text)` and `threshold` with model v1 built in; `score(text, model)` for another model
  file; `gated`, `rawScore`, `parseJewel` and the `Jewel` types; the raw model as `jeweler/model.json`.
- Model v1 is trained on public text only (the research notes call it Jewel 3; earlier research models were
  trained on private text and are not published).
- The runtime treats whitespace exactly as Python does (U+001C-U+001F and U+0085 are whitespace, U+FEFF is not)
  and reads `\w` in the email check as Unicode, so it scores exactly like the trained model.
- Trimming is linear: a crafted copy with millions of spaces can't stall the app.
- Tests: parity with Python on 416 synthetic texts, the gate, hostile input, and a packed-install check.
