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
| 4a | Excel File Anonymization (NER pass) | ✅ Done — issue #32 merged |
| 4b | Excel Column-Based Anonymization + Advanced Settings | ✅ Done — issue #34 merged |
| 5 | Key Reference Export Improvements | ✅ Done — issue #36 merged |
| 6 | Launcher and UX Polish | ✅ Done — issue #38 merged |
| 7 | Anonymized Subfolder Output Mode | ✅ Done — issue #40 merged |
| 8 | Consistent Hashing for All Entity Types | ✅ Done — issue #42 merged |
| 9 | Acceptance Testing — all features | 🔄 In progress — issue #44 |

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

## Step 4a ✅ — Excel File Anonymization (NER pass)

**Codeberg issue:** #32 — merged

**Goal:** `.xlsx` files processed the same way as DOCX — PII detected in cell
string values, replaced with placeholders, output saved with `ANON_` or
`CHECKED_` prefix. Formulas and formatting preserved.

### What was built
- `openpyxl>=3.1` added to `requirements.txt`
- `DocumentProcessor` — `load_xlsx`, `save_xlsx_with_replacements`, `save_xlsx_copy`
- `FileProcessor` — `_process_xlsx`, `.xlsx` in `SUPPORTED_EXTENSIONS`
- `FolderProcessor` — `.xlsx` in `SUPPORTED_EXTENSIONS`
- 19 tests covering NER replacement, formula/numeric cells untouched, formatting
  preserved, ANON_/CHECKED_ prefix, keyref, folder batch discovery

### Limitation identified after merge
The NER pass only processes string cells. Numeric cell values (e.g. student
numbers stored as integers) are invisible to it. Column-based anonymization
is required to cover these — see Step 4b below.

---

## Step 4b — Excel Column-Based Anonymization ← Next

**Codeberg issue to create first:**
`feature: Excel column-based anonymization and advanced settings panel`

**Goal:** Allow users to specify column names whose entire contents should be
anonymized, regardless of cell type (string or numeric). A collapsible
"Advanced settings" panel in Document Mode exposes these Excel-specific
controls without cluttering the main UI.

### Why this is needed

The NER pass in Step 4a operates on string cell text. Numeric identifiers
(e.g. a student number column of integers) are completely invisible to it.
Column-based anonymization solves this: "every value in this column is PII —
replace it all, regardless of type or content."

### Design decisions

**Two independent modes — either, both, or neither:**

| Mode | Default | Mechanism | What it targets |
|---|---|---|---|
| Generic NER | On | Presidio on string cell text | Names, emails, phones in text cells |
| Column-based | Off | Whole-cell exact match by header | Any cell type in named columns |

Each mode can be toggled on or off independently:
- **Both on:** column-based runs first, NER fills in the rest. No conflicting
  placeholders — column cells are replaced before NER runs over them.
- **NER only:** existing 4a behaviour. Numeric cells invisible; string cells
  scanned for names/emails/phones.
- **Column only:** only named columns are anonymized. NER does not run.
  Useful when you want precise control and no false positives.
- **Both off:** the `.xlsx` file is **skipped entirely** — no output file is
  created, the file appears as "skipped" in the completion summary. The user
  has explicitly opted out of Excel processing. Other file types (DOCX, PDF,
  Markdown) are unaffected.

**Placeholder format for column-based:**
Column name uppercased as entity type label.
- `stnum` column → `[STNUM_1]`, `[STNUM_2]` …
- `email` column → `[EMAIL_1]`, `[EMAIL_2]` …
- Same value in the same column → same placeholder (consistent mapping).
- Counter resets per column.

**Header row assumption:**
Column detection reads row 1 as headers (case-insensitive match). If a
specified column name is not found in any sheet's row 1, that column is
skipped and a warning is added to the `FileResult`. No crash. The UI
carries a permanent hint: "Column matching requires headers in row 1."

**No pandas required.** openpyxl column iteration is sufficient.

### What to build

**`FileResult`**
- Add `warnings: list[str]` field (optional, default empty list) for
  non-fatal issues such as "column 'stnum' not found in headers".

**`ProcessingSettings`**
- Add `excel_generic_enabled: bool = True` — controls whether NER runs
  on string cells in `.xlsx` files.
- Add `excel_column_names: list[str] = field(default_factory=list)` —
  column headers to anonymize by exact column match.

**`DocumentProcessor`**
- Add `extract_column_replacements(wb, column_names) -> tuple[dict[str, str], list[str]]`:
  reads row 1 of each sheet as headers; for each matching column collects
  all unique non-formula values; assigns placeholders `[COLNAME_N]`;
  returns `(exact_replacements, missing_column_names)`.
- Update `save_xlsx_with_replacements` signature to accept an optional
  `exact_replacements: dict[str, str] | None = None` parameter. A second
  internal pass applies these as whole-cell replacements (any cell type,
  specified columns only, formula cells skipped).

**`FileProcessor._process_xlsx`** — updated flow:
1. **If both modes off** (`not excel_generic_enabled` and `not excel_column_names`):
   return `FileResult(status="skipped")` immediately. No file written.
2. If `excel_column_names` non-empty: call `extract_column_replacements`,
   collect `exact_replacements` and `missing` warnings.
3. If `excel_generic_enabled`: extract string cell text, run NER, collect
   `substring_replacements` (same as 4a).
4. If both modes are on but neither produced any replacements: return clean result.
5. Save with `save_xlsx_with_replacements(wb, dest, substring_replacements,
   exact_replacements)`.
6. Build combined map for key reference (merge both dicts).
7. Attach any `missing` warnings to `FileResult.warnings`.

**`UserSettings`**
- Persist `excel_generic_enabled` (bool) and `excel_column_names`
  (comma-joined string, split on load).

**Frontend — Document Mode**
- Add a `<details>`/`<summary>` collapsible "Advanced settings" section
  below the main settings bar. No JavaScript needed.
- Inside: an "Excel" subsection containing:
  - Checkbox: "Generic anonymization (NER)" — checked by default.
  - Text input: "Column names to anonymize" — placeholder text
    `stnum, email, phone`.
  - Help note: "Comma-separated. Only works when row 1 contains column
    headers. Does not affect other file types."
- Both controls POST with the form and are restored from `UserSettings`
  on next launch.
- If any `FileResult.warnings` are present, surface them in the
  completion summary alongside the file counts.

**`document_routes.py`**
- Read `excel_generic_enabled` and `excel_column_names` from the POST body.
- Pass to `ProcessingSettings`.

### ✅ Complete when
- A `.xlsx` file where student numbers are integers in a `stnum` column
  produces `ANON_` output with `[STNUM_N]` placeholders in that column.
- Other columns not in the specified list are unaffected.
- Generic NER can be toggled off independently while column-based remains active.
- Column-based can be toggled off independently while NER remains active.
- Both modes active simultaneously: numeric column replaced AND names in
  text cells replaced by NER.
- **Both modes off: `.xlsx` files appear as "skipped" in the summary; no
  output file created; DOCX/PDF/Markdown in the same folder are unaffected.**
- Warning shown in completion summary if a specified column name is not
  found in row 1 headers.
- Advanced settings panel collapses correctly and settings persist on reload.
- All existing 122 tests still pass.

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

## Step 8 ✅ — Consistent Hashing for All Entity Types

**Codeberg issue to create first:**
`feature: consistent hashing for all entity types (not PERSON-only)`

**Goal:** When hashing is enabled with a secret, every detected PII entity
produces a deterministic, secret-keyed placeholder — not just PERSON names.
The same value + the same secret always maps to the same placeholder across
files and across sessions, making cross-document pseudonymization coherent.

### Why this is needed

**Current gap:** Hashing is enabled but only PERSON names are actually hashed.
All other entity types (emails, phone numbers, student numbers, BSN, etc.)
still use sequential counters (`[EMAIL_ADDRESS_1]`) even when hashing is on.
That counter resets per file, so `[EMAIL_ADDRESS_1]` in document A and
`[EMAIL_ADDRESS_1]` in document B may refer to completely different people.

Column-based anonymization has the same gap: `542348` always becomes
`[STNUM_1]` regardless of the hashing setting.

This undermines the core promise of hashing: consistent pseudonymization that
can be reversed with the secret.

### Design decisions

**Entities covered:**

| Entity type | Hashed? | Reason |
|---|---|---|
| PERSON (name) | ✅ Already (unchanged) | Name rules — first 2 chars + 4-char hash |
| EMAIL_ADDRESS | ✅ New | Unique identifier; cross-doc consistency matters |
| PHONE_NUMBER | ✅ New | May uniquely identify a person |
| NUMERIC_ID (stnum etc.) | ✅ New | Primary key — most important after names |
| Dutch BSN | ✅ New | National primary key |
| URL / social profile | ✅ New | LinkedIn URLs uniquely identify a person |
| LOCATION (address) | ✅ New | Consistency cost-free; no downside |
| ORG (organisation) | ✅ New | Same reasoning |
| DATE_TIME | ❌ Excluded | Dates are not person identifiers; hashing `September 2025` is meaningless |
| NRP (nationality/belief) | ❌ Excluded | Not an identifier |

**New hashing method — `HashEncoder.encode_value(entity_type, value)`:**
- Input: entity type label + full string value
- Output: 4 uppercase alphanumeric characters derived from
  `HMAC-SHA256(secret, entity_type + ":" + value)[:4].upper()`
- Format: `[EMAIL_A2B3]`, `[STNUM_C4D1]`, `[PHONE_E9F2]`
- Same value + same type + same secret → same output across sessions
- Different secrets → different outputs (pseudonymization is secret-keyed)
- Label is shorter than the NER entity type name (EMAIL not EMAIL_ADDRESS)
  to keep placeholder length reasonable

**Label shortening for hashed placeholders:**

| NER entity type | Hashed label |
|---|---|
| EMAIL_ADDRESS | EMAIL |
| PHONE_NUMBER | PHONE |
| NUMERIC_ID | ID |
| NL_BSN | BSN |
| URL | URL |
| LOCATION | LOC |
| ORG | ORG |

**Column-based mode:** when hashing is on, `extract_column_replacements()`
uses `encode_value(column_label, str(value))` instead of the sequential
counter. `542348` in a `stnum` column → `[STNUM_C4D1]` (deterministic).

**Hashing off:** all existing sequential behaviour is completely unchanged.

### What to build

**`HashEncoder`**
- Add `encode_value(entity_type: str, value: str) -> str` method
- Returns the 4-char HMAC-derived hash for non-name values
- Reuses the existing secret already held by the encoder instance

**`FileProcessor._build_replacements()`**
- When encoder is set: for non-PERSON entities, call
  `encoder.encode_value(entity_type, original_text)` to get the hash segment;
  construct `[LABEL_XXXX]` placeholder using the shortened label
- DATE_TIME and NRP entities: skip hashing, use sequential placeholder as now

**`DocumentProcessor.extract_column_replacements()`**
- Add optional `encoder: HashEncoder | None = None` parameter
- When encoder provided: use `encoder.encode_value(label, value_str)`
  instead of the sequential counter
- Column label (e.g. `STNUM`) is used as the entity type for hashing

**`FileProcessor._process_xlsx()`**
- Pass encoder to `extract_column_replacements()` when hashing is enabled

**`CHANGELOG.md`**
- Visible output change: email/phone/etc. placeholder format changes from
  `[EMAIL_ADDRESS_1]` to `[EMAIL_A2B3]` when hashing is on.
  Note clearly in the release that this only affects hashing mode.

### ✅ Complete when
- Hashing on + email detected by NER → `[EMAIL_A2B3]` — deterministic with secret
- Hashing on + stnum column → `[STNUM_C4D1]` — same number, same placeholder
- Same value in two different files with same secret → identical placeholder
- Hashing off → all sequential behaviour unchanged; no regressions
- DATE_TIME entities use sequential format even when hashing is on
- `HashEncoder.encode_value()` tested: consistent across calls, secret-dependent
- `_build_replacements()` tested: non-PERSON entities hash when encoder provided
- Column-based with hashing tested: deterministic output confirmed
- All 155 existing tests still pass

---

## Step 9 🔄 — Acceptance Testing

**Codeberg issue:** #44 — in progress

**Goal:** A structured manual test run covering every feature added or changed
in v1.1.0. Performed after all build steps (1–8) are merged to main.
Any failures discovered here are fixed on a branch named
`fix/issue-N-step9-{short-description}` and merged before release.

Running the automated test suite (`pytest`) is a prerequisite but not
sufficient — these tests confirm behaviour the automated suite cannot reach:
visual output quality, UI interaction, cross-feature combinations, and real
documents with realistic content.

---

### Pre-test setup

- Fresh clone or `git pull main` — confirm you are on the latest main
- `pip install -r requirements.txt` — confirm all dependencies present
- Launch: `launch.bat` (Windows) — confirm browser opens automatically and
  app loads at `http://localhost:5000`
- Run `pytest` — all tests must pass before starting manual testing
- Prepare a test folder containing:
  - One DOCX with a name and email address
  - One PDF with a name and phone number
  - One Markdown file with a name
  - One `.xlsx` with a text cell containing a name, a numeric student
    number column (`stnum`), and a formula cell
  - One DOCX with no PII (for CHECKED_ verification)
  - A subfolder with one more DOCX

---

### 9a — Placeholder format (Step 1) ✅

Run Text Mode with a name and email in the input.
Used `tests/fixtures/sample_with_pii.md` content pasted into Text Mode.

| Check | Expected | Result |
|---|---|---|
| Name placeholder | `[PERSON_1]` — bracketed, not bare `PERSON_1` | ✅ Pass |
| Email placeholder | `[EMAIL_ADDRESS_1]` — bracketed | ✅ Pass |
| Key reference table (when enabled) | Shows bracketed placeholders | ✅ Pass |
| Date toggle (off by default, on when enabled) | DATE_TIME excluded/included correctly | ✅ Pass |
| Numeric ID toggle + euro exclusion | Only plain digit sequences matched; €12345 ignored | ✅ Pass |
| DOCX output | Bracketed placeholders in the output file | ✅ Pass (quick scan) |
| PDF output | Bracketed placeholders in the output file | ✅ Pass (quick scan) |

**Issue found:** URL entity is on by default and causes email addresses to be
detected twice (once as EMAIL_ADDRESS, once as URL). This produces garbled
output — surrounding text is consumed by the URL span, leaving truncated
placeholder sequences. See [Bug #1](#bug-1-url-detection-on-by-default) below.

---

### 9b — Branding and theme (Step 2) ✅

| Check | Expected | Result |
|---|---|---|
| Logo visible in nav | d-ranged logo appears top-left | ✅ Pass |
| Default theme | Dark green nav (T4 Dual Identity) | ✅ Pass |
| Click logo once | Theme switches to muted blue (T1 Neutral Professional) | ✅ Pass |
| Click logo again | Theme returns to T4 | ✅ Pass |
| Reload page | Last selected theme is restored (localStorage) | ✅ Pass |
| Both themes | No layout breaks, no illegible text in either theme | ✅ Pass |

---

### 9c — Excel NER anonymization (Step 4a) ✅

Using the fixtures folder processed as a batch (all files, NER only):

| Check | Expected | Result |
|---|---|---|
| Generic NER on, no column names | `ANON_` output; name replaced in string cell | ✅ Pass |
| Formula cell in output | Formula string unchanged | ✅ Pass |
| Numeric cells in output | Numbers unchanged | ✅ Pass |
| Cell formatting | Bold/colour formatting preserved | ✅ Pass |
| DOCX in same folder | Processed normally — Excel settings do not affect it | ✅ Pass |

---

### 9d — Excel column-based anonymization (Step 4b) ✅

Column names tested via fixtures folder (stnum column specified).

| Check | Expected | Result |
|---|---|---|
| NER off, column `stnum` | Integer values in stnum column replaced | ✅ Pass |
| Other columns | Untouched | ✅ Pass |
| NER on, column `stnum` | Both modes active simultaneously | ✅ Pass |
| NER off, no column names (both off) | File skipped in summary | Not explicitly tested |
| Column name not found in row 1 | Warning shown in completion summary | ⚠️ Shown, but styled as error — see [Bug #3](#bug-3-column-not-found-shown-with-error-styling) |
| Key reference enabled | Contains stnum → original value mapping | ✅ Pass |
| Advanced settings panel | Collapses/expands correctly; settings restored on reload | ✅ Pass |
| `.xlsx` selectable in single-file mode | File appears in browser file picker | ❌ Fail — see [Bug #2](#bug-2-xlsx-not-selectable-in-single-file-mode) |

---

### 9e — Key reference export (Step 5) ✅

| Check | Expected | Result |
|---|---|---|
| Folder mode, key reference on | Single consolidated `KEYREF_<folder>.csv` at folder root | ✅ Pass |
| CSV opens cleanly in Excel | Two columns: Placeholder, Original value | ✅ Pass |
| Text Mode export button | Clicking saves a file; in-UI table still visible | ✅ Pass |
| Single-file key reference | Unchanged from pre-5 behaviour | Not explicitly tested |

---

### 9f — Launcher and UX (Step 6) ⏭️ Partial

| Check | Expected | Result |
|---|---|---|
| `launch.bat` on Windows | Browser opens automatically after Flask starts | ✅ Pass |
| Flask not yet ready race | No 404 on open | Not tested |
| README macOS instructions | `bash launch.sh` shown as primary command | Not tested |
| macOS tkinter fallback | Graceful message and browse buttons disabled | ⏭️ Skipped — no Mac available; colleague will test |

macOS testing is non-blocking for this step — it will not delay the release.

---

### 9g — Anonymized subfolder output mode (Step 7) ✅

Tested via fixtures folder with subfolder output mode selected:

| Check | Expected | Result |
|---|---|---|
| `anonymized/` created at folder root | Yes | ✅ Pass |
| Structure mirrors original | Subfolder present inside `anonymized/` | ✅ Pass |
| Anonymized files | Original filename, no `ANON_` prefix | ✅ Pass |
| Clean files | Present in `anonymized/` as unmodified copies | ✅ Pass |
| Key reference (when on) | `KEYREF_folder.csv` at root of `anonymized/` | ✅ Pass |
| Original folder | Completely untouched — no ANON_/CHECKED_ files | ✅ Pass |
| UI toggle | Mode persists after reload | Not explicitly verified |
| Prefix mode still works | Switching back produces ANON_/CHECKED_ in place | ✅ Pass |

---

### 9h — Cross-feature combinations ✅ (with issues)

| Combination | Expected | Result |
|---|---|---|
| Hashing on + DOCX | Name encoded correctly; consistent across files | ✅ Pass |
| Hashing on + DOCX email | `[EMAIL_XXXX]` deterministic hash | ✅ Pass (but affected by Bug #1 — URL overlap) |
| Hashing on + Excel column-based stnum | `[STNUM_XXXX]` — same number, same placeholder every run | ✅ Pass |
| Hashing off → all sequential | `[PERSON_1]`, `[EMAIL_ADDRESS_1]` etc. unchanged | ✅ Pass |
| Hashing no-secret message | Blocked with clear message when secret field empty | ✅ Pass |
| Key reference + folder mode + subfolder output | KEYREF CSV inside `anonymized/`, covers all files | ✅ Pass |
| Mixed folder (DOCX + PDF + XLSX) — both Excel modes off | XLSX skipped | Not explicitly tested |
| Mixed folder column mode only | XLSX uses column replacement, DOCX/PDF use NER | Not explicitly tested |

---

### 9i — Regression: existing tests

```
pytest
```
All tests pass. Record count. Any failure blocks release.

*(To be confirmed before release — run on main after all Step 9 fixes are merged.)*

---

### Step 9 Findings

Three bugs identified during the test run. Each needs a dedicated fix branch
before Step 9 can be marked complete and v1.1.0 released.

---

#### Bug #1 — URL detection on by default

**Observed:** Email addresses in text mode and document mode produce garbled
output. Surrounding text is partially consumed by the URL entity span, leaving
truncated placeholder strings (e.g. `[EMAIL_ADDRESS_1]ne: [PHONE_NUMBER_1]IC_ID_2]`
instead of the expected `[EMAIL_ADDRESS_1] — [PHONE_NUMBER_1]`).

**Root cause:** `URL` is in the default `ENTITIES` list in `anonymizer.py`.
Presidio's URL recognizer also matches email addresses (they look like URLs
to a domain-based heuristic). When both URL and EMAIL_ADDRESS are active for
the same span, the overlapping entity detection produces unexpected results —
some surrounding text is consumed as part of the URL span, and double
replacements occur in edge cases where the two detectors disagree on span boundaries.

**Fix:** Make URL detection opt-in rather than opt-out.
- Remove `URL` from the default `ENTITIES` list in `anonymizer.py`
- Add an `anonymize_urls: bool` parameter to `_build_entity_list()` in
  `text_routes.py` and equivalent handling in `document_routes.py`/`FileProcessor`
- Add a "Detect URLs" toggle to the UI — default off; logically placed in the
  Advanced Settings panel in Document Mode and alongside Date/Numeric ID in Text Mode
- Persist via `UserSettings`

**Severity:** High — affects all text and document output when email addresses
are present.

---

#### Bug #2 — .xlsx not selectable in single-file mode

**Observed:** The file picker in single-file Document Mode does not show `.xlsx`
files. The file input's `accept` attribute does not include the Excel MIME type
or extension.

**Fix:** Add `.xlsx` and the OOXML MIME type to the `accept` attribute on the
file input in `document_mode.html`.

```html
accept=".docx,.pdf,.md,.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
```

**Severity:** Medium — single-file Excel processing is completely inaccessible
via the UI (folder mode works because it discovers files by extension).

---

#### Bug #3 — Column-not-found shown with error styling

**Observed:** When a specified column name is not found in any sheet's row 1
headers, the progress/completion summary flags it with error-level colour and
icon. This is a soft warning (expected and recoverable — the column name was
simply absent), not a processing failure.

**Fix:** Differentiate warning-level events from hard errors in the progress
display. Column-not-found should render with an amber warning indicator, not
a red error indicator. Requires a CSS class distinction and a corresponding
change to how the summary row is rendered in `document_mode.js` or the
relevant template section.

**Severity:** Low — functionality is correct; styling is misleading.

---

#### Deferred observations (not blocking release)

- **No overwrite warning on repeated folder run:** Re-running a folder quietly
  overwrites existing output files. Acceptable for now; low risk given that
  originals are never touched. Add to roadmap for a future release.
- **Option wrapping in Document Mode top bar:** When many options are active
  (key reference, check names, subfolder mode, etc.) the top settings bar
  wraps awkwardly on standard screen widths. Consider moving less common
  options into the Advanced Settings panel. Not blocking.
- **macOS test:** Deferred to a colleague. Non-blocking for v1.1.0 release.

---

### ✅ Complete when
- Bug #1 (URL default on) fixed and merged
- Bug #2 (.xlsx file picker) fixed and merged
- Bug #3 (column-not-found styling) fixed and merged
- `pytest` passes with no failures on main after fixes
- Any deferred items logged in `roadmap.md`

---

## Release — v1.1.0

Once all steps including Step 9 acceptance testing are complete:

1. Bump `__version__` in `app/__init__.py`
2. Update version badge in `README.md`
3. Add v1.1.0 entry to `CHANGELOG.md`
4. Commit: `Update version to v1.1.0`
5. Tag: `git tag v1.1.0 -m "Release v1.1.0"`
6. Push commits and tag: `git push && git push origin v1.1.0`
7. Codeberg → Releases → New Release → select tag → paste CHANGELOG entry → publish
