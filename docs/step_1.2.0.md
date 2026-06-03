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
| 2 | Known Values — user-managed list of names always anonymized | ⬜ Not started |
| 3 | Acceptance Testing | ⬜ Not started |

---

## Background

v1.2.0 introduces the **Restore** feature: given any file containing d-tach placeholders
and a KEYREF CSV, replace all placeholders with their original values.

The primary use case is **AI-output round-tripping**: the user anonymizes a document,
sends the anonymized content to an AI tool, and the AI returns new content (a letter,
feedback report, or summary) that still references `[PERSON_1]`, `[ORG_1]` etc. The user
then runs Restore on that AI-generated file to produce a final document with real values
inserted — without the real values ever having been shared with the AI.

This is distinct from "restoring the original" — the original document is never the input
to Restore. Restore acts on new content that was written using the placeholder vocabulary.

This feature was planned in `roadmap.md` as "De-anonymization (reverse lookup)". The UI
name is **Restore** — simpler and non-technical.

PDF is not supported and is not planned. AI tools return text and markdown, not PDFs.
The use case for restoring a PDF does not arise. See `roadmap.md` for the rationale.

A parallel PDF research track runs **outside this project** — focused on improving the
visual quality of anonymized PDF output, not on restore. See the section at the bottom
of this file.

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

## Step 2 — Known Values (User-Managed PII List)

**Codeberg issue to create first:**
`feature: known values list — user-managed names always anonymized`

**Goal:** The user can maintain a persistent list of strings (typically names or IDs that
the NER model consistently misses) that are always anonymized, regardless of whether
Presidio detects them. Adding, viewing, and removing entries is done in the UI.

**Background:** Uncommon names — particularly those from less-represented languages or
cultures — are often missed by spaCy's NER models, which are trained predominantly on
English and Dutch text corpora. A student named Egidijus Ukrinas may not be detected
as a PERSON even in a full-sentence context. The known values list is the user's
escape hatch: declare it once, and it is caught from that point forward.

### Design decisions

**Storage:** A flat list of strings in `user_settings.json` under `"known_values"`.
Persisted via `UserSettings`, restored on launch. Global — applies to every run.
Case-insensitive matching at detection time (stored in original casing for display).

**Pipeline position:** Applied as a pre-pass before Presidio NER, inside
`_build_ad_hoc_recognizers()`. Each known value is converted to an exact
case-insensitive regex pattern with a high confidence score (0.99) and entity type
`PERSON`. This ensures hashing applies consistently using the PERSON rules when
hashing is enabled. Values that do not look like names (e.g. an ID string) receive
entity type `NUMERIC_ID` or `PERSON` at the user's discretion — for v1.2.0 always
use `PERSON` and note in the UI that this is the entity type used.

**Scope:** Applies in both Text Mode and Document Mode (same shared list). Also
applied in filename and folder name anonymization when check_file_names is enabled.

**Partial names:** Each entry is treated as an independent token. If the user adds
"Egidijus Ukrinas" as a single entry AND "Egidijus" as a separate entry, both are
stored. The multi-word entry is matched first (longest-first ordering, consistent
with existing anonymizer behaviour).

### What to build

**`UserSettings`**
- Add `known_values: list[str]` property backed by `user_settings.json`
- Default: empty list
- Getter returns the list; setter replaces the list and saves

**`Anonymizer`** (or route-level `_build_ad_hoc_recognizers`)
- `build_known_value_recognizers(known_values: list[str]) -> list[PatternRecognizer]`
  — one recognizer per entry, case-insensitive exact match, confidence 0.99, type PERSON
- Called from `_build_ad_hoc_recognizers()` in `file_processor.py`; recognizers are
  prepended so they run before NER-based detections

**`ProcessingSettings`**
- Add `known_values: list[str]` field (default empty list)
- Routes populate this from `user_settings.known_values` at request time

**New API routes — `document_routes.py` and/or a dedicated `settings_routes.py`**
- `GET /settings/known-values` — returns the current list as JSON
- `POST /settings/known-values` — body: `{"value": "Egidijus Ukrinas"}` — appends and saves
- `DELETE /settings/known-values` — body: `{"value": "Egidijus Ukrinas"}` — removes and saves

**UI — both `document_mode.html` and `text_mode.html`** (or a shared component)
- A collapsible "Known names" panel in the settings bar, alongside the existing toggles
- A text input labelled "Add name" with an Add button (Enter key also submits)
- Each saved name renders as a tag/chip with an × to remove; click × calls the DELETE route
- Panel loads current list on page open via GET route
- Empty state shows a brief placeholder: "No known names yet — add names that are
  consistently missed by the anonymizer"

### Guard rails

- Duplicate values are silently ignored (case-insensitive comparison before storing)
- Empty string rejected at the route level
- Values are stored as the user typed them (original casing) for readability in the UI;
  matching at runtime is always case-insensitive
- No limit on list size in v1.2.0 — revisit if performance becomes a concern

### ✅ Complete when

- A name added via the UI is anonymized in the next run in both Text and Document modes
- A name added is detected in filenames when check_file_names is enabled
- The name persists after app restart
- Removing a name from the UI stops it being detected in the next run
- Duplicate prevention works (adding same name twice results in one entry)
- All existing tests pass; new tests cover recognizer creation and round-trip persistence

---

## Step 3 — Acceptance Testing

**Codeberg issue to create first:**
`test: acceptance testing — v1.2.0 restore and known values`

**Goal:** Manual test run covering the Restore tab and Known Values list end-to-end,
after Steps 1 and 2 are merged to main.

### Pre-test setup

- `git pull main` — confirm on latest main
- `pip install -r requirements.txt`
- Launch app; confirm it loads
- Run `pytest` — must pass before starting manual tests
- Prepare test files:
  - One DOCX previously anonymized by d-tach (contains `[PERSON_N]`, `[EMAIL_N]` etc.)
  - The corresponding `KEYREF_` CSV from that run
  - One `.md` file with placeholders (simulate AI-returned content referencing placeholders)
  - One `.xlsx` with placeholder cells
  - One DOCX or folder containing a name you know the NER misses

### Test cases — Restore

| Check | Expected |
|---|---|
| DOCX + KEYREF → restored | All placeholders replaced; file opens cleanly in Word |
| `.md` + KEYREF → restored | Correct replacement; line structure preserved |
| `.xlsx` + KEYREF → restored | Placeholder cells contain original values |
| AI-output `.md` with placeholders + KEYREF → restored | Placeholders in new AI content replaced with real values |
| KEYREF with extra entries not in doc | No error; extra entries ignored |
| Unsupported file type | Clear error message in UI |
| Restore tab in nav | Navigable from Text Mode and Document Mode tabs |
| Last-used paths | Restored on next launch |

### Test cases — Known Values

| Check | Expected |
|---|---|
| Add a name the NER misses (e.g. uncommon first + last name) | Name anonymized in next Document Mode run |
| Same name detected in Text Mode | Name anonymized when pasted text is processed |
| Name survives app restart | Still in list and still detected after closing and reopening |
| Remove name from UI | Next run does not detect/replace it |
| Add same name twice | Only one entry stored |
| Name detected in filename | Anonymized in output filename when check_file_names is enabled |

### Test cases — Regression

| Check | Expected |
|---|---|
| Document Mode anonymization | Still works correctly |
| Text Mode anonymization | Still works correctly |
| `pytest` | All tests pass |

### ✅ Complete when

- All test cases above pass
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

## v1.3.0

See `step_1.3.0.md` for the full build plan.

Summary: system tray app, configurable port, language management (on-demand model
download). These three are co-designed — the tray makes d-tach a persistent background
process, which makes RAM cost of loaded spaCy models concrete, which drives the language
management work.

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
