# step_1.1.0.md — d-tach v1.1.0 Build Plan

This document breaks the v1.1.0 planned work into ordered, testable steps.
Each step should map to one or more Codeberg issues created before starting.

Consult `original_steps.md` for the full background and rationale on each item.
Consult `project_guide.md` for architectural decisions and documented alternatives.

---

## Status at a Glance

| Step | Description | Status |
|---|---|---|
| 1 | Standardise Placeholder Format to [PLACEHOLDER] | ✅ Done — PR #28 merged |
| 2 | Branding and Theme System | ✅ Done — PR #30 merged |
| 3 | Fix PDF Replacement Text Font Size | ❌ Dropped — failed, reverted |
| 4 | Excel File Anonymization | **← Next** |
| 5 | Key Reference Export Improvements | Pending |
| 6 | Launcher and UX Polish | Pending |
| 7 | Anonymized Subfolder Output Mode | Pending |

---

## Step 1 ✅ — Standardise Placeholder Format to [PLACEHOLDER]

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

## Step 2 ✅ — Branding and Theme System

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

## Step 3 ❌ — Fix PDF Replacement Text Font Size

**Codeberg issue:** #31
**Status: ❌ Failed — dropped from v1.1.0. Reverted to pre-Step-3 state on main.**

**Original goal:** Replacement text in anonymized PDFs matches the font size of the
original text, so output looks consistent.

### What was attempted

Three approaches were tried on branch `fix/issue-31-pdf-replacement-font-size`:

1. **Detected font size passed to `add_redact_annot()`** — PyMuPDF squishes the text
   to fit the original bounding box when the placeholder is longer than the original.
   Replaced "1234567" with "[NUMERIC_ID_1]" produced 4pt text.

2. **Blank-then-insert** — `add_redact_annot(rect)` with no text whites out the
   original; `insert_text()` after `apply_redactions()` renders unconstrained. Removed
   the squishing but caused placeholders to overflow into adjacent content.

3. **Blank-then-insert with width scaling** — `_compute_insertion()` helper used
   `fitz.Font("helv").text_length()` for exact Helvetica metrics to compute the largest
   font size that fits the placeholder within the original rect. Overflow was eliminated
   in theory, but the output on real documents was still worse than the original
   hardcoded approach: readability degraded and visual quality was unacceptable on the
   fixture set.

### Why it failed

The fundamental tension: placeholders like `[NUMERIC_ID_1]` are much longer than the
values they replace (e.g. a 6-digit student number). There is no way to render a 14-char
string in the space of 6 digits at a readable size. The original hardcoded `fontsize=11`
was imperfect but produced visually consistent output; all attempts to match or adapt the
font size made it worse on real documents.

### What was learnt

- `add_redact_annot(rect, text, fontsize)` is not suitable when placeholder is longer
  than original — PyMuPDF clips/squishes to fit the bbox.
- Blank-then-insert (`add_redact_annot` + `insert_text`) avoids squishing but requires
  exact width control; approximations are not reliable enough.
- `fitz.Font("helv").text_length()` gives exact metrics for width calculation but does
  not solve the underlying problem that short originals leave too little space.
- Shortening placeholder labels (e.g. `[ID_1]` instead of `[NUMERIC_ID_1]`) would
  reduce the length mismatch and is the most promising path — see roadmap.md.
- The pre-Step-3 state (hardcoded `fontsize=11`, `add_redact_annot` with text) was
  visually superior to all attempted improvements for real documents.

### See also

roadmap.md — "PDF in-place text replacement" section for future approach notes.

---

## Step 4 — Excel File Anonymization ← Next

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

## Step 7 — Anonymized Subfolder Output Mode

**Codeberg issue to create first:**
`feature: anonymized subfolder output mode for folder processing`

**Goal:** When processing a folder, instead of placing `ANON_` and `CHECKED_` prefixed
files alongside originals in the same directory, create a dedicated `anonymized/`
subfolder at the root of the chosen folder. The subfolder mirrors the original directory
structure exactly. All processed output goes there, keeping the original folder clean
and avoiding any intermingling.

**Before (prefix mode — unchanged default):**
```
folder/
  report.docx
  ANON_report.docx
  subfolder/
    notes.docx
    ANON_notes.docx
```

**After (subfolder mode — new):**
```
folder/
  report.docx
  subfolder/
    notes.docx
  anonymized/
    report.docx          ← anonymized version, no prefix
    subfolder/
      notes.docx         ← anonymized version, no prefix
    KEYREF_folder.csv    ← key reference at root of anonymized/
```

### Rules

- All files are included in `anonymized/` regardless of whether PII was detected —
  the folder represents the complete processed output, ready to hand over.
- Files with no PII detected: copied as-is (content unchanged, no `CHECKED_` prefix —
  the folder separation makes the distinction clear).
- Files with PII detected: anonymized version saved with the original filename.
- Key reference file (when enabled): `KEYREF_<foldername>.csv` at root of `anonymized/`.
- If name-checking is enabled: anonymized filenames are used inside `anonymized/`;
  original folder and filenames are untouched.
- Folder names inside `anonymized/`: if name-checking detects PII in a folder name,
  use the anonymized folder name in the `anonymized/` mirror; original folder untouched.
- `anonymized/` itself is never processed recursively — skip it if it exists.

### What to build

**`UserSettings`**
- Add `output_mode` field: `'prefix'` (default, existing behaviour) or `'subfolder'`
- Persist and restore alongside existing settings

**`FolderProcessor`**
- Add `_subfolder_output_path(original_file: Path, chosen_folder: Path) -> Path` helper:
  computes the mirror path inside `anonymized/`
  e.g. `chosen/sub/file.docx` → `chosen/anonymized/sub/file.docx`
- When `output_mode == 'subfolder'`: write output to the mirror path instead of
  prefixing in place; create intermediate directories as needed
- When `output_mode == 'prefix'`: no change to existing logic

**`FileProcessor`**
- When `output_mode == 'subfolder'`: output filename = original filename (no `ANON_`
  or `CHECKED_` prefix); the path alone distinguishes it
- When `output_mode == 'prefix'`: existing prefix logic unchanged

**Frontend — Document Mode**
- Add output mode toggle (radio buttons or select) alongside the existing folder path input:
  `⊙ Prefix files (default)   ○ Subfolder (anonymized/)`
- Toggle feeds into the POST body; backend reads and passes to `FolderProcessor`

**Key reference (folder mode)**
- When subfolder mode: save `KEYREF_<foldername>.csv` inside `anonymized/`
  (not alongside originals)

### ✅ Complete when

- Processing a folder in subfolder mode produces `anonymized/` with a full mirrored
  structure
- Files inside have no `ANON_`/`CHECKED_` prefix
- Files without PII are present in `anonymized/` as clean copies
- `KEYREF_` (when enabled) is at root of `anonymized/`
- Original folder is completely untouched
- UI toggle persists via `UserSettings` and is restored on next launch
- Prefix mode still works and all existing tests pass

---

## Release — v1.1.0

Once all seven steps are complete and tested:

1. Bump `__version__` in `app/__init__.py`
2. Update version badge in `README.md`
3. Add v1.1.0 entry to `CHANGELOG.md`
4. Commit: `Update version to v1.1.0`
5. Tag: `git tag v1.1.0 -m "Release v1.1.0"`
6. Push commits and tag: `git push && git push origin v1.1.0`
7. Codeberg → Releases → New Release → select tag → paste CHANGELOG entry → publish
