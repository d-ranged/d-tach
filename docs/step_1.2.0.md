# step_1.2.0.md — d-tach v1.2.0 Build Plan

This document breaks the v1.2.0 planned work into ordered, testable steps.
Each step should map to one or more Codeberg issues created before starting.

Consult `roadmap.md` for background on items deferred from v1.1.0.
Consult `project_guide.md` for architectural decisions and documented alternatives.

---

## Status at a Glance

| Step | Description | Status |
|---|---|---|
| 1 | Restore Tab — DOCX, Text, Markdown, Excel | ⬜ Not started |
| 2 | Restore — PDF support (best-effort) | ⬜ Not started |
| 3 | Acceptance Testing — all features | ⬜ Not started |

---

## Background

v1.2.0 introduces the **Restore** feature: given an anonymized file and its corresponding
KEYREF CSV, revert all placeholders back to their original values. This closes the loop on
the anonymization workflow — users can round-trip a document through d-tach and recover the
original for authorised parties.

This feature was planned in `roadmap.md` as "De-anonymization (reverse lookup)". The UI
name is **Restore** — simpler and non-technical.

A parallel PDF research track runs **outside this project** — see the separate research
project section at the bottom of this file.

---

## Step 1 — Restore Tab (DOCX, Text, Markdown, Excel)

**Codeberg issue to create first:**
`feature: restore tab — reverse anonymization using KEYREF file`

**Goal:** Add a Restore tab to the UI. The user selects an anonymized file and a KEYREF
CSV produced by d-tach. The tool replaces all `[PLACEHOLDER_N]` tokens with their original
values and saves a restored copy.

### Supported file types

| Type | Support | Notes |
|---|---|---|
| `.docx` | ✅ Full | Find-and-replace via python-docx |
| `.txt` / `.md` | ✅ Full | Plain string replacement |
| `.xlsx` | ✅ Full | Cell string replacement via openpyxl |
| `.pdf` | ➡️ Step 2 | Separate step — see below |

### User flow

1. User opens the Restore tab
2. Selects the anonymized file (file picker or typed path)
3. Selects the KEYREF CSV (file picker or typed path)
4. Clicks Restore
5. A restored file is saved alongside the input with a `RESTORED_` prefix
6. Completion message shows replacement count and output path

### KEYREF format

The KEYREF CSV produced by d-tach has two columns: `Placeholder, Original value`.
The restore function reads this as `{placeholder: original}` and applies it as a
find-and-replace pass. No NLP, no model loading — pure string substitution.

### What to build

**`DocumentProcessor`**
- `load_keyref_csv(path: Path) -> dict[str, str]` — reads the KEYREF CSV,
  returns `{placeholder: original}` mapping
- `restore_docx(input_path, output_path, replacements: dict[str, str]) -> int` —
  iterates all runs in all paragraphs and tables; exact string replacement;
  returns replacement count
- `restore_xlsx(input_path, output_path, replacements: dict[str, str]) -> int` —
  iterates all string cells in all sheets; exact string replacement
- `restore_text(input_path, output_path, replacements: dict[str, str]) -> int` —
  reads file as string, applies all replacements, writes output

**`FileProcessor`**
- `restore_file(input_path, keyref_path, output_dir) -> FileResult` — routes to
  the correct restore method by extension; saves with `RESTORED_` prefix;
  returns `FileResult` with replacement count

**New route — `restore_routes.py`**
- `GET /restore` — renders the Restore tab template
- `POST /restore` — receives `input_file` and `keyref_file` paths;
  calls `FileProcessor.restore_file()`; returns completion summary

**New template — `restore_mode.html`**
- Extends `base.html`
- Two file path inputs: "Anonymized file" and "KEYREF file", each with a Browse button
- A single Restore button
- Completion area showing replacement count and output file path

**Navigation — `base.html`**
- Add Restore tab to the nav alongside Text Mode and Document Mode

**`UserSettings`**
- Persist last-used input path and KEYREF path for the Restore tab (convenience only)

### Guard rails

- Exact string match only — no fuzzy matching, no NLP
- Placeholder present in KEYREF but not in the document: skip silently
- Input file type unsupported (e.g. PDF before Step 2): return a clear error; do not process
- Original file is never modified — always write to a new `RESTORED_` file
- Existing `RESTORED_` output is overwritten silently (same behaviour as anonymization)

### ✅ Complete when

- DOCX file with `[PERSON_1]` etc. + KEYREF CSV → `RESTORED_` file has original values
- `.md` and `.txt` files restored correctly
- `.xlsx` file with placeholder cells restored correctly
- KEYREF with unmapped placeholders: skipped without error
- Unsupported file type: clear error shown in UI
- Restore tab appears in nav and is navigable from other tabs
- Last-used paths restored from `UserSettings` on next launch
- All existing tests pass

---

## Step 2 — Restore: PDF Support (Best-Effort)

**Codeberg issue to create first:**
`feature: restore tab — PDF support (best-effort)`

**Goal:** Extend the Restore tab to accept PDF files. The restored PDF replaces placeholder
text with original values using PyMuPDF. Visual quality will be imperfect — the UI says so
clearly.

**Dependency:** Step 1 must be complete before this step starts.

### Why PDF is a separate step

When d-tach anonymized the PDF, `add_redact_annot()` physically destroyed the original
text. Restoring means inserting the original value back into the same bounding box — which
has the same font-fitting problems as the original anonymization. The result may look
inconsistent when the original text is a different width than the placeholder.

This is best-effort. It is better than nothing and allows PDFs to participate in the
restore workflow, but visual inconsistency should be expected.

**Note:** If the PDF replace-text research project (below) produces a better approach
before this step is built, incorporate those findings here instead.

### What to build

**`DocumentProcessor`**
- `restore_pdf(input_path, output_path, replacements: dict[str, str]) -> int` —
  open PDF with `fitz`; for each page, search for each placeholder with
  `page.search_for(placeholder)`; for each match, blank with `add_redact_annot(rect)`,
  call `apply_redactions()`, then `insert_text()` with the original value into the
  same bbox; return replacement count
- Add `.pdf` routing to `FileProcessor.restore_file()`

**UI**
- Add `.pdf` to the Restore tab file picker `accept` attribute
- Permanent note below the file inputs:
  "PDF restore is best-effort — visual quality may vary depending on text length."

**Tests**
- Test PDF with known placeholder text → `RESTORED_` output contains original value
- Replacement count returned correctly
- Multi-page PDF: replacements applied on all pages

### ✅ Complete when

- PDF with `[PERSON_1]` → `RESTORED_` PDF has original name in the correct location
- Replacement count is accurate
- UI note about PDF visual quality is visible
- DOCX / text / xlsx restore unchanged (no regressions from Step 1)
- All existing tests pass

---

## Step 3 — Acceptance Testing

**Codeberg issue to create first:**
`test: acceptance testing — v1.2.0 restore feature`

**Goal:** Manual test run covering the Restore tab end-to-end, after Steps 1 and 2 are
merged to main.

### Pre-test setup

- `git pull main` — confirm on latest main
- `pip install -r requirements.txt`
- Launch app; confirm it loads
- Run `pytest` — must pass before starting manual tests
- Prepare test files:
  - One DOCX previously anonymized by d-tach (contains `[PERSON_N]`, `[EMAIL_N]` etc.)
  - The corresponding `KEYREF_` CSV from that run
  - One `.md` file with placeholders
  - One `.xlsx` with placeholder cells
  - One PDF previously anonymized by d-tach

### Test cases

| Check | Expected |
|---|---|
| DOCX + KEYREF → restored | All placeholders replaced; file opens cleanly in Word |
| `.md` + KEYREF → restored | Correct replacement; line structure preserved |
| `.xlsx` + KEYREF → restored | Placeholder cells contain original values |
| PDF + KEYREF → restored | Placeholders replaced; visual quality noted (may vary) |
| KEYREF with extra entries not in doc | No error; extra entries ignored |
| Unsupported file type | Clear error message in UI |
| Restore tab in nav | Navigable from Text Mode and Document Mode tabs |
| Last-used paths | Restored on next launch |
| Regression — Document Mode | Anonymization still works correctly |
| Regression — Text Mode | Text anonymization still works correctly |
| `pytest` | All tests pass |

### ✅ Complete when

- All test cases above pass (PDF visual quality noted but not a blocker)
- No regressions in Document or Text Mode
- `pytest` passes with no failures on main

---

## PDF Replace-Text Research Project (Separate — Not d-tach)

A standalone proof-of-concept, developed **outside** the d-tach codebase. Goal: find a
PDF text replacement approach that looks visually natural when the replacement text differs
in length from the original. Findings feed back into d-tach only if a clearly better
approach is found.

### Test PDF structure

Generate a PDF with **5 identical paragraphs**. Each paragraph contains the same sentences,
with target phrases of varying lengths marked for replacement — simulating d-tach's range
of real replacement widths: a short name (6 chars), an email address (25 chars), a student
number (7 digits), a phone number (12 chars), a longer organisation name. The 5 paragraphs
are identical so that differences in output are attributable solely to the technique applied.

### Output files

Generate **3 output PDF files**, each applying a different approach to all 5 paragraphs:

| File | Approach | Description |
|---|---|---|
| `output_approach_a.pdf` | `add_redact_annot` with text arg | Native PyMuPDF redact + fill. Text squished to fit bbox. Current d-tach approach. |
| `output_approach_b.pdf` | Blank redact + `insert_text` unconstrained | Clear the bbox, insert at original position without size constraint. Risks overflow. |
| `output_approach_c.pdf` | Blank redact + `insert_text` with computed font size | Clear bbox; compute largest font size where replacement fits using `fitz.Font().text_length()`. |

A fourth output is optional: if any of the libraries below offers a cleaner primitive,
produce `output_approach_d.pdf` using it.

### Libraries to research

- **PyMuPDF (fitz)** — already used in d-tach; check recent changelog for any new
  text replacement or reflow API (search: "replace", "reflow", "redact text")
- **pikepdf** — Python wrapper for qpdf; low-level PDF stream editing
- **pdfrw** — pure Python PDF manipulation; allows stream-level edits
- **reportlab** — PDF generation; could generate replacement overlays
- **pypdf** — maintained fork of PyPDF2; check for text replacement support
- **pdfminer.six / pdfplumber** — primarily extraction; check if any write-back path exists

### Deliverables

1. A Python script that generates the test PDF and all output files
2. A short markdown notes file recording which approach performed best per paragraph
3. A recommendation: adopt into d-tach, wait for a better library release, or abandon

---

## Release — v1.2.0

Once all steps including acceptance testing are complete:

1. Bump `__version__` in `app/__init__.py`
2. Update version badge in `README.md`
3. Add v1.2.0 entry to `CHANGELOG.md`
4. Commit: `Update version to v1.2.0`
5. Tag: `git tag v1.2.0 -m "Release v1.2.0"`
6. Push commits and tag: `git push && git push origin v1.2.0`
7. Codeberg → Releases → New Release → select tag → paste CHANGELOG entry → publish
