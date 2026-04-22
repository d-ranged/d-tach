# STEP_1.1.0.md — d-tach v1.1.0 Build Plan

This document breaks the v1.1.0 planned work into ordered, testable steps.
Each step should map to one or more Codeberg issues created before starting.

Consult `ORIGINAL_STEPS.md` for the full background and rationale on each item.
Consult `PROJECT_GUIDE.md` for architectural decisions and documented alternatives.

---

## Step 1 — Standardise Placeholder Format to [PLACEHOLDER]

**Codeberg issue to create first:**
`change: standardise placeholder format to [PLACEHOLDER] across all output`

**Goal:** All replacement tokens change from bare identifiers (`PERSON_1`) to
bracketed format (`[PERSON_1]`). This is a visible output change affecting every
mode and output type — do it first so tests only need updating once.

### Scope
- `app/services/anonymizer.py` — update replacement string construction
- `app/services/hash_encoder.py` — if hashed placeholders are formatted here
- All output modes: text, DOCX, PDF, Excel (if already present), key reference file
- `tests/` — update all test assertions that match bare placeholder strings
- `CHANGELOG.md` — entry for v1.1.0 noting this as a visible change

### ✅ Complete when
- All output uses `[PERSON_1]`, `[EMAIL_ADDRESS_1]` etc.
- All existing tests pass with updated assertions
- Key reference file uses the new format

---

## Step 2 — Branding and Theme System

**Codeberg issue to create first:**
`feature: add d-ranged branding and two-theme toggle`

**Goal:** Apply the d-ranged identity to the application. The default theme uses
SA green + Dutch orange (Dual Identity). Clicking the logo toggles to a neutral
professional theme and back. Decisions are recorded in `d-ranged/d-sign/THEME_GUIDE.md`
— consult that file for exact values before building.

**Prerequisite:** Logo finalised and `favicon.png` created before starting this step.
See THEME_GUIDE.md for current status.

### Assets
- Logo PNG: `d-ranged/logo/d-logo.png` — copy into `app/static/` as `d-logo.png`
- Favicon: `d-ranged/logo/favicon.png` — copy into `app/static/`
- SA green: `#007A4D` (primary accent)
- Dutch orange: `#C85A00` (hover and secondary)
- Full colour reference: `d-ranged/d-sign/THEME_GUIDE.md`

### Themes (2 total, toggle not cycle)
| ID | Name | Nav bg | Accent | State |
|---|---|---|---|---|
| T4 | Dual Identity | `#005738` | `#007A4D` SA green | Default |
| T1 | Neutral Professional | `#2c3e50` | `#4a6fa5` muted blue | Logo-click toggle |

### What to build
- Copy `d-logo.png` and `favicon.png` into `app/static/`
- Add logo `<img>` to `base.html` nav — clickable, top-left
- JavaScript click handler on logo toggles `data-theme` on `<html>` between
  `T4` and `T1`
- CSS custom properties (`--accent`, `--nav-bg`, `--accent-hover`) scoped to
  `[data-theme="T4"]` and `[data-theme="T1"]`
- Persist selected theme in `localStorage`
- Theme preference does NOT need to go into `UserSettings` — `localStorage` only

### Guard rails
- Do not change layout, spacing, or font choices — colour and logo only
- If either theme looks unprofessional in the actual app, revert to T1 only
- The neutral theme (T1) must always be clean and usable as the default fallback

### ✅ Complete when
- Logo appears in the nav and looks right at default size
- Clicking logo toggles between T4 and T1 visibly
- Theme persists on page reload
- Both themes pass a visual check in the actual app
- No regressions in existing functionality

---

## Step 3 — Fix PDF Replacement Text Font Size

**Codeberg issue to create first:**
`fix: PDF replacement text uses wrong font size`

**Goal:** Replacement text in anonymized PDFs matches the font size of the original
text it replaced, so output looks consistent.

### What to change
- `app/services/document_processor.py` — in the PDF redaction path:
  - Before calling `add_redact_annot()`, read the font size of the original span
    from `page.get_text("dict")`
  - Pass that size to `add_redact_annot()` via the `fontsize` parameter

### ✅ Complete when
- Anonymized PDFs show replacement text at the same size as surrounding content
- No layout distortion on a representative sample of test PDFs

---

## Step 4 — Excel File Anonymization

**Codeberg issue to create first:**
`feature: Excel file (.xlsx) anonymization`

**Goal:** `.xlsx` files processed the same way as DOCX — PII detected in cell
string values, replaced with placeholders, output saved with `ANON_` or
`CHECKED_` prefix. Formulas and formatting preserved.

### What to build
- `openpyxl>=3.1` added to `requirements.txt`
- `DocumentProcessor` — add `load_xlsx`, `save_xlsx_with_replacements`,
  `save_xlsx_copy` methods (same pattern as DOCX and PDF)
- `FileProcessor` — add `.xlsx` to the list of supported extensions
- `FolderProcessor` — add `.xlsx` to recursive file discovery
- Tests covering: cell with name anonymized, cell with no PII unchanged,
  formula cell untouched, formatting preserved

### ✅ Complete when
- A `.xlsx` file with a name in a cell produces `ANON_` output with placeholder
- Formula cells are not touched
- Cell formatting is preserved
- Folder batch processing includes `.xlsx` files

---

## Step 5 — Key Reference Export Improvements

**Codeberg issue to create first:**
`feature: key reference export — folder mode and text mode export button`

**Goal:** Make the key reference usable for batch runs and easy to save from
Text Mode.

### What to build

**Folder mode:**
- When key reference toggle is enabled and a folder is processed, save a single
  consolidated `KEYREF_<folder-name>.csv` at the root of the selected folder
- Format: two-column CSV — `Placeholder, Original value`
- Readable by non-technical users (opens in Excel)

**Text Mode and single-file:**
- Add an **Export** button alongside the on-screen key reference table
- Clicking it saves the current key reference as a `.txt` or `.csv` file
- The in-UI table remains — export is additive

### ✅ Complete when
- Folder processing with key reference enabled produces a consolidated CSV
- Text Mode has a working export button
- Single-file key reference behaviour unchanged

---

## Step 6 — Launcher and UX Polish

**Codeberg issue to create first:**
`fix: launcher scripts, macOS tkinter fallback, README macOS instructions`

**Goal:** Bundle the remaining UX and launcher fixes. These are independent of
each other but small enough to ship together.

### 6a — Launcher scripts open browser automatically

- `launch.bat` — after starting Flask, call `start http://localhost:5000`
  (add `timeout /t 2 /nobreak` before to allow Flask to bind)
- `launch.sh` — after starting Flask, call `open http://localhost:5000` (macOS)
  or `xdg-open http://localhost:5000` (Linux)

### 6b — macOS tkinter graceful fallback

- `launch.sh` — after pip install during setup, run
  `python3 -c "import tkinter" 2>/dev/null` and if it fails, print a clear
  one-line warning: `"Note: tkinter not found — Browse buttons will be disabled.
  To enable, run: brew install python-tk@3.x"`. Continue setup; warning only.
- `app/routes/browse_routes.py` — wrap the `tkinter` import in try/except;
  if it fails, return a clear error from the browse endpoints; JS hides
  Browse buttons and shows a small inline note

### 6c — README macOS instructions

- Update macOS installation section to show `bash launch.sh` as the primary
  instruction
- Note `chmod +x` as optional for users who want to double-click in future

### ✅ Complete when
- Launcher scripts open the browser automatically after Flask starts
- macOS users without tkinter see a warning at setup and a graceful fallback
  in the app — no crash
- README macOS section uses `bash launch.sh` as primary instruction
- All existing tests pass

---

## Release — v1.1.0

Once all six steps are complete and tested:

1. Bump `__version__` in `app/__init__.py`
2. Update version badge in `README.md`
3. Add v1.1.0 entry to `CHANGELOG.md`
4. Commit: `Update version to v1.1.0`
5. Tag: `git tag v1.1.0 -m "Release v1.1.0"`
6. Push commits and tag: `git push && git push origin v1.1.0`
7. Codeberg → Releases → New Release → select tag → paste CHANGELOG entry → publish
