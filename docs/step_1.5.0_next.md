# step_1.5.0_next.md — d-tach v1.5.0 Build Plan

This document breaks the v1.5.0 planned work into ordered, testable steps.
Each step should map to one or more Codeberg issues created before starting.

Consult `roadmap.md` for background context.
Consult `project_guide.md` for architectural decisions and documented alternatives.
Consult `step_1.4.0_completed.md` for what shipped in v1.4.0 and the release notes.

**Parked.** After v1.4.0 and its videos (October 2026) d-tach is in a quiet period.
Work here starts when a real use-case gap or an outside issue or PR asks for it, not
on a schedule.

---

## Status at a Glance

| Step | Description | Status |
|---|---|---|
| 1 | OCR fallback for image-based PDFs, [#78](https://codeberg.org/d-ranged/d-tach/issues/78) | ⏳ Open to contributors |
| 2 | PyMuPDF 2.0: lift the `<2` pin or keep it | ⏳ Not started |

Step 1 moved here from v1.4.0 on 9-10-2026. Step 2 came out of the v1.4.0 release,
23-10-2026.

---

## Step 1 — OCR Fallback for Image-Based PDFs

**Codeberg issue:** [#78](https://codeberg.org/d-ranged/d-tach/issues/78). The issue holds
the full design and is the source of truth. A contributor comments there first, to agree
the engine and the output shape before starting.

### Why

v1.3.0 writes nothing for a PDF it can't read, such as a scanned page. That is right: a
complete failure is better than a partial anonymization. But the file still has to be
dealt with by hand, and scanned letters and signed declarations are often the most
sensitive documents.

### The rule this must not break

OCR must never make output that looks anonymized and isn't. A name lost to a
low-resolution scan, a stamp or a signature would do exactly that. So OCR adds a clearly
labelled side channel and leaves the main output as strict as today.

### Design, in short

- Off by default. A setting under Settings > Folder output, plus a per-run toggle
- Results go to `anonymized-ocr-unverified/`, mirroring the source tree, never into
  `anonymized/`
- Always `.txt`: `Verklaring.pdf` gives `Verklaring.pdf.txt`
- A banner in every file: machine-read from an image, no formatting kept, check by eye
- Counted separately in the folder summary
- AI Mode: `/ai/extract` still returns 422 by default. With OCR on, it returns the text
  with a mandatory warning, and the banner is prefixed to `anonymized_text`
- Return bounding boxes as well as text, so a later step can black out names in the
  scanned page itself

### Engine

To confirm with a spike on real Dutch and English scans. `rapidocr-onnxruntime` is the
best fit for the packaged build: about 50–80 MB, no separate install, no PyTorch. Whoever
takes this must check the engine in the packaged build, not only from source, and run
the smoke test (`packaging/smoke_test.py`) on both platforms.

### ✅ Complete when

- With OCR off, an image-based PDF behaves exactly as in v1.3.0.
- With OCR on, its text lands in `anonymized-ocr-unverified/<name>.pdf.txt` with a
  banner, and nothing is written into `anonymized/`.
- The folder summary shows OCR files on their own line.
- `/ai/extract` returns the text with a warning the caller can't silently drop.
- Tests for each, and the README states the limitation, not just the feature.

---

## Step 2 — PyMuPDF 2.0

### Background

PyMuPDF 2.0 came out 19-10-2026. On import it loads a new layout module that needs
onnxruntime and data files PyInstaller doesn't ship, so the frozen build died on start
and the first v1.4.0 Build run failed its smoke test on both platforms. v1.4.0 pinned
`pymupdf>=1.27,<2` ([#87](https://codeberg.org/d-ranged/d-tach/issues/87)).

The pin is fine for now, but 1.x will stop getting fixes at some point.

### Questions to answer

- What does 2.0 add to the build size once onnxruntime and the layout data are bundled?
- Can the layout module be switched off, so 2.0 behaves like 1.x?
- Does its layout analysis help Step 1? 🟠 If OCR uses `rapidocr-onnxruntime`,
  onnxruntime is in the build anyway, which would make 2.0 cheaper to take
- Does the typographic apostrophe defect below still happen on 2.0?

### ✅ Complete when

- A decision is written here: keep the pin, or lift it with the PyInstaller changes
  that need.
- If lifted, the packaged build passes the smoke test on both platforms.

---

## Carried From Earlier Releases — Not Yet Scoped

Real, but none warranted a release of its own. Confirm each is still reproducible
before scoping.

From the v1.3.0 acceptance run:

- **PDF extraction mangles typographic apostrophes.** `pymupdf` renders `’` as U+FFFD,
  so extracted text reads "Saxion�s" and "the IND�s". Output quality, not privacy.
- **Inconsistent detection of a repeated organisation name.** In one acceptance
  document an organisation was hashed in most positions but appeared in the clear in a
  possessive form. 🟠 May share a root cause with defect 11 (possessive spans); needs a
  reproduction before it can be called.
- **`expand_archives_enabled` is dead config.** Read nowhere. Remove it or wire it up.
- **Short and dictionary-word known values.** A roster containing a surname that is
  also a common word matches far too much. Flag these at import time rather than
  letting the user discover it in the output. v1.4.0's name rules (#76) cover class list
  names. Check what is left for manual known values.
- **Case sensitivity should differ for body text and filenames.** One setting currently
  governs both, and the right answer is not the same for each.
- **Single-token PERSON detection against a surname-only roster.** When the imported
  roster holds surnames only, a lone detected token is more likely a surname than a
  first name, and the placeholder should reflect that.
- **Tutorial / help affordance.** There is no in-app explanation of what the modes are
  for. New users have to be told.

From the v1.4.0 release:

- **macOS: closing d-tach crashed once on first start.** Seen once on one test Mac, not
  again since. Listed as a known issue in the v1.4.0 release notes. Needs a reproduction.

---

## Backlog — Explicitly Not v1.5.0

- Interface translation (i18n). Significant scope, touches every template string.
  Revisit when there are real non-English-speaking users asking for it.
- Batch summary log — machine-readable JSON/CSV run summary written to the processed
  folder.

Both are described in `roadmap.md`.
