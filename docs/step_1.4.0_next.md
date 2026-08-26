# step_1.4.0_next.md — d-tach v1.4.0 Build Plan

This document breaks the v1.4.0 planned work into ordered, testable steps.
Each step should map to one or more Codeberg issues created before starting.

Consult `roadmap.md` for background context.
Consult `project_guide.md` for architectural decisions and documented alternatives.
Consult `step_1.3.0_next.md` for the acceptance-run defect log these items came out of.

**Do not start until v1.3.0 has shipped.**

---

## Status at a Glance

| Step | Description | Status |
|---|---|---|
| 1 | `/ai/restore` accepts a KEYREF file, not just a live session | ⬜ Not started |
| 2 | OCR fallback for image-based PDFs — text only, quarantined output | ⬜ Not started |
| 3 | Standalone packaged installer (PyInstaller) | ⬜ Not started |

Steps 1 and 2 came out of the v1.3.0 Step 6 acceptance run (25-8-2026). Step 3 was
already committed to v1.4.0 in `roadmap.md` and is carried here unchanged.

---

## Background

Two gaps surfaced during the v1.3.0 acceptance run, both while doing a real piece of
work rather than a feature checklist. Neither blocked the release; both cost the tester
time and one of them nearly produced a wrong output.

**Restore is trapped inside a session.** `/ai/restore` can only reverse placeholders
that the same `/ai/extract` call created. Compose a document from two source files and
only one of them can be restored. Come back to an anonymized file a week later and
nothing can be restored at all, even though Document Mode exported a perfectly good
KEYREF CSV at the time. Document Mode's `/restore` already takes that CSV — AI Mode
simply never learned to.

**An unreadable PDF stops the work dead.** v1.3.0 correctly refuses to write a PDF it
could not read, which is the right call (see Step 2's design note). But the file still
has to be dealt with, and the tester ends up doing by hand what the tool exists to do.
Scanned letters and signed declarations are exactly the documents that carry the most
sensitive content, so this is not an edge case.

---

## Step 1 — `/ai/restore` Accepts a KEYREF File

**Codeberg issue:** _create before starting_

### Background

`POST /ai/restore` requires a `session_id` and reads its replacement map from that
session alone. Sessions expire (`ai_session_timeout_minutes`), so the map is gone
within the hour, and it only ever described one document.

Document Mode already solves the durable half of this: with **Key reference** enabled
a run writes a `KEYREF_*.csv` next to its output, and `POST /restore` takes a
`keyref_path` and restores a whole file from it. The data is already in the right
shape. AI Mode just cannot read it.

### What this unblocks

- Composing one output from several source documents — currently only one document's
  placeholders survive the restore, and the rest are written out as raw tokens.
- Restoring an anonymized document in a later session, when the KEYREF was kept.
- Recovering when a session expires mid-task, without re-extracting the source and
  hoping the tokens come back identical.

### Design

Add an optional `keyref_path` to `POST /ai/restore`:

| Body | Behaviour |
|---|---|
| `session_id` only | Unchanged — restores from the live session map |
| `session_id` + `keyref_path` | Both maps merged; the session wins on conflict |
| `keyref_path` only | Restores from the CSV alone; no session required |
| Neither | 400, as now |

**Session wins on conflict** because it was produced by the document actually in hand,
while a KEYREF may be older and may have been written under a different secret.

Reuse the existing CSV reader rather than writing a second one. `restore_routes.py`
already parses KEYREF files for `POST /restore`; lift that into a shared helper so
exactly one implementation exists — the same rule `compose_replacements` follows.

Keep `output_path` working exactly as it does now. The privacy property that makes AI
Mode usable is that restored text can be written straight to disk without ever passing
back through the caller, and that must survive this change untouched.

### What to build

| Component | Description |
|---|---|
| KEYREF reader | Lift CSV parsing out of `restore_routes.py` into a shared service function |
| `ai_routes.restore` | Accept `keyref_path`; merge maps; relax the `session_id` requirement |
| Error handling | 404 for a missing file, 400 for an unparseable one — match `/restore`'s wording |
| Agent instructions | Update the generated AI Mode instructions in Settings to mention it |
| Tests | Merge precedence, keyref-only restore, missing file, malformed CSV, `output_path` still writes |

### A note on the alternative

A persistent local placeholder history in Settings was considered and **rejected for
now**. It would remove the need to pass a KEYREF at all, but it creates a single file
that maps every placeholder d-tach has ever produced back to a real name. That file
undoes the entire tool if it leaks, and it accumulates silently rather than by a
deliberate act. The CSV-per-run model keeps that decision in the user's hands each
time. Revisit only if the manual step proves to be the thing stopping people using
restore at all.

### ✅ Complete when

- An output composed from two extracted documents restores every placeholder from both.
- A file anonymized in an earlier session restores from its KEYREF with no live session.
- `output_path` still writes restored text straight to disk and returns no content.

---

## Step 2 — OCR Fallback for Image-Based PDFs

**Codeberg issue:** _create before starting_

### The rule this step must not break

**A complete failure is better than a partial anonymization.** This is settled and is
not up for renegotiation inside this step.

v1.3.0 defect 10 was exactly this: an image-based PDF was copied into the `anonymized/`
output with every name still legible, indistinguishable from properly processed files.
The fix was to write nothing at all. OCR reintroduces the same risk in a subtler form —
a name lost to a low-resolution scan, a stamp, a signature or a handwritten note means
d-tach produces output that *looks* anonymized and is not.

So OCR does not change the failure mode. It adds a clearly-labelled, quarantined side
channel and leaves the main output path exactly as strict as it is today.

### Scope

**In scope:** extracting text from image-based PDF pages so the content can be read and
anonymized at all.

**Out of scope:** preserving formatting. The output is plain text. Layout, tables,
letterheads and signatures are lost. This is accepted and stated up front.

**Out of scope:** producing a redacted PDF. Drawing boxes over the detected regions and
keeping the file a PDF is the better long-term answer for scanned letters, and it is
genuinely useful, but it is a larger piece of work. See "Deferred" below.

### Design — quarantined output

The core of this step is not the OCR call. It is making OCR output impossible to
mistake for a finished anonymized document.

- **Off by default.** A setting in Settings > Folder output, plus a per-run override on
  the Document Mode folder panel. With OCR off, behaviour is identical to v1.3.0:
  the file is reported unreadable and nothing is written.
- **Separate destination.** OCR results never go into `anonymized/`. They go to a
  sibling folder — `anonymized-ocr-unverified/` — mirroring the source tree.
- **Always `.txt`, never the source extension.** A scanned `Verklaring.pdf` produces
  `Verklaring.pdf.txt`. It cannot be opened as a PDF, cannot be attached in place of
  the original, and sorts away from real documents. Keeping the full original name
  including its extension makes the provenance obvious.
- **A banner in every file.** The first lines of every OCR output state that the text
  was machine-read from an image, that no formatting survived, and that it must be
  checked by eye before use. The banner is part of the file, not just the UI, because
  the UI is not there when someone opens the file three weeks later.
- **Counted separately.** The folder summary reports OCR files on their own line and
  never folds them into the anonymized count.
- **Distinct in the results list.** Their own section with their own heading, in the
  same visual register as the existing unreadable-PDF section — not alongside successes.

### Design — AI Mode

- `POST /ai/extract` on an image-based PDF continues to return **422** by default.
- With OCR enabled, it returns the extracted text with a mandatory entry in `warnings`
  saying the text was machine-read and may be incomplete.
- The warning must be impossible to miss in the response shape. An agent that ignores
  `warnings` should still be told: prefix the returned `anonymized_text` with the same
  banner that goes into the `.txt` file.

### Library choice

🟡 Assessment, to be confirmed with a real spike on the actual scanned documents.

| Option | Size | External install | Notes |
|---|---|---|---|
| `rapidocr-onnxruntime` | ~50–80 MB | None | ONNX-based, pip-installable, no PyTorch. Best fit for the v1.4.0 packaging goal |
| Tesseract + `pytesseract` | ~50–100 MB | **Yes** — separate Windows installer | More accurate on clean print. The external binary conflicts with a single-file installer |
| EasyOCR / PaddleOCR | 2 GB+ | None | Pulls in PyTorch. Far too heavy |
| Windows OCR API | 0 | None | Built into Windows 10/11, but Windows-only and an awkward API |

**Leaning to `rapidocr-onnxruntime`**, because Step 3 packages d-tach as a standalone
binary and an external Tesseract install would defeat that. Confirm accuracy on real
Dutch and English scans before committing — if it is materially worse than Tesseract on
the documents that actually matter, the packaging cost may be worth paying.

OCR models can ride the on-demand download mechanism built in v1.3.0 rather than
shipping in the binary.

### What to build

| Component | Description |
|---|---|
| `app/services/ocr.py` | New service wrapping the chosen engine; returns text per page |
| `UserSettings` | `ocr_enabled: bool = False`; OCR model download state |
| `_process_pdf` | Branch at the existing image-only-page detection to call OCR when enabled |
| `_extract_pdf` | Same branch for AI Mode; add the mandatory warning |
| Output writer | Write `.txt` with banner into `anonymized-ocr-unverified/` |
| `FolderProcessor` | Count and report OCR files as their own category |
| Document Mode UI | Setting, per-run toggle, separate results section |
| Settings UI | OCR section with the accuracy warning stated plainly |
| `README.md` | Document the limitation, not just the feature |
| Tests | Off by default; quarantine path; banner present; never in `anonymized/`; summary counts separate; AI Mode warning present |

### ✅ Complete when

- With OCR off, an image-based PDF behaves exactly as it does in v1.3.0.
- With OCR on, its text lands in `anonymized-ocr-unverified/<name>.pdf.txt`, with a
  banner, and nothing is written into `anonymized/`.
- The folder summary shows OCR files on a separate line from anonymized files.
- `/ai/extract` returns the text with a warning the caller cannot silently drop.

### Deferred — visual redaction of scanned pages

The better answer for a scanned letter, and the one to build once OCR is proven:

- OCR returns bounding boxes as well as text.
- `pymupdf`'s `add_redact_annot` can black out just the PII regions and draw the
  placeholder into the box.
- The file stays a PDF, formatting intact, names gone from the image.

This is a v1.5.0-shaped piece of work. It is recorded here so the OCR service in Step 2
is designed to return coordinates, not just a text blob — retrofitting that later would
mean rewriting the service.

---

## Step 3 — Standalone Packaged Installer (PyInstaller)

**Codeberg issue:** _create before starting_

Carried unchanged from `roadmap.md`. v1.3.0's on-demand language download makes this
feasible: the binary ships without models, at an estimated 80–150 MB, small enough for
Codeberg's free storage tier without a quota increase.

- **Target audience:** users without Python experience who cannot or will not run the
  launcher scripts.
- **Known challenges:** Flask static file paths under `sys._MEIPASS`, `tkinter`
  bundling on macOS, confirming actual binary size on a clean build.
- **Interaction with Step 2:** the OCR engine choice directly affects whether this
  stays a single-file install. Settle Step 2's library before building the spec.

See `roadmap.md` for the original planning note.

---

## Carried From the v1.3.0 Acceptance Run — Not Yet Scoped

Observations logged during Step 6 that are real but did not warrant fixing in a
patch release. Confirm each is still reproducible before scoping.

- **PDF extraction mangles typographic apostrophes.** `pymupdf` renders `’` as U+FFFD,
  so extracted text reads "Saxion�s" and "the IND�s". Output quality, not privacy.
- **Inconsistent detection of a repeated organisation name.** In one acceptance
  document an organisation was hashed in most positions but appeared in the clear in a
  possessive form. 🟠 May share a root cause with defect 11 (possessive spans); needs a
  reproduction before it can be called.
- **`expand_archives_enabled` is dead config.** Read nowhere. Remove it or wire it up.
- **Short and dictionary-word known values.** A roster containing a surname that is
  also a common word matches far too much. Flag these at import time rather than
  letting the user discover it in the output.
- **Case sensitivity should differ for body text and filenames.** One setting currently
  governs both, and the right answer is not the same for each.
- **Single-token PERSON detection against a surname-only roster.** When the imported
  roster holds surnames only, a lone detected token is more likely a surname than a
  first name, and the placeholder should reflect that.
- **Tutorial / help affordance.** There is no in-app explanation of what the modes are
  for. New users have to be told.

---

## Backlog — Explicitly Not v1.4.0

- Interface translation (i18n). Significant scope, touches every template string.
  Revisit when there are real non-English-speaking users asking for it.
- Batch summary log — machine-readable JSON/CSV run summary written to the processed
  folder.

Both are described in `roadmap.md`.
