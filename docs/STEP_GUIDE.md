# STEP_GUIDE.md — d-tach Incremental Build Plan

This guide defines the build order for d-tach. Each step is a testable
milestone. Complete and verify each step before moving to the next.

If you hit a blocker on a tool or approach, consult `docs/PROJECT_GUIDE.md`
for documented alternatives before changing direction.

---

## Step 0 — Repository and Project Setup
*Do this manually before opening Claude Code*

**Goal:** A clean repo exists locally and on Codeberg with the correct folder
structure and all planning documents committed. No application code yet.

### Actions

1. Create a new repository on Codeberg named `d-tach`
   - Set visibility to **Private**
   - Do not initialise with a README
   - Note the remote URL

2. On your local machine:
   ```
   mkdir d-tach
   cd d-tach
   git init
   git remote add origin https://codeberg.org/YOUR_USERNAME/d-tach.git
   ```

3. Copy these files from this conversation into the project root:
   - `CLAUDE.md`
   - `.gitignore`
   - `.claude/settings.json`
   - `docs/PROJECT_GUIDE.md`
   - `docs/STEP_GUIDE.md` (this file)

4. Create the folder structure:
   ```
   mkdir -p app/routes app/services app/static/css app/static/js app/templates
   mkdir -p tests docs .claude
   touch app/__init__.py
   touch app/routes/__init__.py
   touch app/services/__init__.py
   touch app/static/css/.gitkeep
   touch app/static/js/.gitkeep
   touch app/templates/.gitkeep
   touch tests/.gitkeep
   ```

5. Create `README.md`:
   ```
   # d-tach
   A locally-run GDPR anonymization tool for text and documents.
   Built with Flask and Presidio. No data leaves your machine.
   Licensed under EUPL-1.2.
   ```

6. Create `run.py`:
   ```python
   from app import create_app

   app = create_app()

   if __name__ == "__main__":
       app.run(debug=True)
   ```

7. Create `requirements.txt`:
   ```
   flask>=3.0
   presidio-analyzer>=2.2
   presidio-anonymizer>=2.2
   spacy>=3.7
   pymupdf>=1.24
   python-docx>=1.1
   ```

8. Create `LICENSE` — paste the full EUPL-1.2 text from:
   https://eupl.eu/1.2/en/

9. First commit and push:
   ```
   git add .
   git commit -m "Initial project structure and documentation (issue #1)"
   git push -u origin main
   ```

### ✅ Step 0 is complete when
- Repo exists on Codeberg (private)
- Folder structure is in place
- All planning documents are committed
- `git log` shows the initial commit

---

## Step 1 — Python Environment and Dependencies
*Open Claude Code after Step 0 is complete*

**Codeberg issue to create first:**
`chore: set up Python environment and install dependencies`

**Goal:** Working Python environment with all dependencies installed and
spaCy language models downloaded.

### Actions

1. Create and activate virtual environment:
   ```
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Mac/Linux:
   source .venv/bin/activate
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Download spaCy models:
   ```
   python -m spacy download en_core_web_md
   python -m spacy download nl_core_news_md
   ```

4. Create minimal Flask app factory in `app/__init__.py` — returns a
   working app instance with no routes yet.

5. Verify Flask starts:
   ```
   flask run
   ```

### ✅ Step 1 is complete when
- `flask run` starts without errors
- Both spaCy models load without errors
- Browser visit to `http://localhost:5000` returns a basic 404
  (no routes yet — expected)

---

## Step 2 — Full Interface with Placeholders

**Codeberg issue to create first:**
`feature: build full HTML interface with placeholders`

**Goal:** Complete HTML interface visible and navigable. All panels and
controls present but nothing wired up. Buttons inactive, panels show
placeholder content. Gives a testable shell to build into.

### What to build

- `app/templates/base.html` — shared layout, navigation between modes
- `app/templates/text_mode.html` — two panels side by side: input left,
  output right. Copy button visible but inactive. Key Reference toggle
  visible but inactive. Hashing toggle with secret field (hidden until
  toggled) visible but inactive.
- `app/templates/document_mode.html` — folder selection input, progress
  area, results summary area, Key Reference toggle, file/folder name
  checking toggle, student number digit count input. All visible,
  none functional.
- `app/static/css/main.css` — clean, readable layout
- Persistent disclaimer visible at bottom of both pages
- Minimal Flask routes to serve the two pages

All interactive elements show a clear "under construction" state.

### ✅ Step 2 is complete when
- Both pages load without errors
- Layout matches the two-panel and folder-selection design in project goals
- No JavaScript console errors
- Disclaimer visible on both pages

---

## Step 3 — LanguageDetector and Anonymizer (Text Only)

**Codeberg issue to create first:**
`feature: implement LanguageDetector and Anonymizer service classes`

**Goal:** Core PII detection logic works in Python. Tested via pytest.
No UI wiring yet.

### What to build

- `app/services/language_detector.py` — `LanguageDetector` class accepts
  a string, returns a language code (`en` or `nl`)
- `app/services/anonymizer.py` — `Anonymizer` class accepts a string and
  language code, runs Presidio analysis and anonymization, returns
  anonymized string plus list of detected entities with their types
- `tests/test_anonymizer.py` — tests covering:
  - English name detected and replaced
  - Dutch name detected and replaced
  - Email detected and replaced
  - Phone number detected and replaced
  - Dutch BSN detected and replaced
  - Clean text returned unchanged

### ✅ Step 3 is complete when
- `pytest tests/test_anonymizer.py` passes fully
- English and Dutch names anonymized correctly
- Emails and phone numbers anonymized correctly

---

## Step 4 — HashEncoder Class

**Codeberg issue to create first:**
`feature: implement HashEncoder with salt-based consistent hashing`

**Goal:** Consistent hashing with user secret works correctly and produces
identical output for identical input and secret across sessions.

### What to build

- `app/services/hash_encoder.py` — `HashEncoder` class:
  - Accepts a secret (salt) on initialisation
  - `encode_first_name(name)` — returns first 2 chars + hyphen + 4-char hash
  - `encode_last_name(name)` — returns 4-char hash of full name
  - Same input + same secret always produces same output
- `tests/test_hash_encoder.py` — tests covering:
  - First name encoding preserves first 2 chars
  - First name hash is exactly 4 uppercase alphanumeric chars
  - Last name hash is exactly 4 uppercase alphanumeric chars
  - Same name + same secret → same output on repeated calls
  - Different secrets → different output for same name
  - First name appearing alone matches prefix of full name encoding

### ✅ Step 4 is complete when
- All hash encoder tests pass
- Consistency verified across multiple calls in same session

---

## Step 5 — UserSettings and PatternConfig

**Codeberg issue to create first:**
`feature: implement UserSettings persistence and PatternConfig`

**Goal:** User preferences are saved and restored between sessions.

### What to build

- `app/services/user_settings.py` — `UserSettings` class:
  - Persists hashing toggle state and secret to a local JSON file
  - Persists student number digit count setting
  - Persists file/folder name checking toggle state
  - Loads settings on initialisation; creates defaults if file absent
  - Note: `user_settings.json` is in `.gitignore` and must never be committed
- `app/services/pattern_config.py` — `PatternConfig` class:
  - Holds active pattern settings
  - Validates student number digit count is a positive integer
  - Provides the currency prefix exclusion rule for digit matching

### ✅ Step 5 is complete when
- Settings survive an app restart
- Hashing toggle and secret are restored correctly on relaunch
- PatternConfig correctly validates digit count input

---

## Step 6 — Wire Up Text Mode

**Codeberg issue to create first:**
`feature: wire text mode UI to Anonymizer and HashEncoder`

**Goal:** Text Mode works end to end in the browser.

### What to build

- Flask route in `text_routes.py` accepts POST with pasted text, calls
  `LanguageDetector`, `Anonymizer`, optionally `HashEncoder`, returns
  anonymized text and entity list as JSON
- JavaScript sends text on paste, receives response, populates output panel
- Copy button copies output to clipboard
- Hashing toggle opens secret field; secret validated before processing
- Key Reference output displayed when toggle enabled
- Settings saved via `UserSettings` when changed

### ✅ Step 6 is complete when
- English text with name and email anonymized correctly
- Dutch text with name anonymized correctly
- Hashing produces consistent Cr-A2T5 style output when enabled
- Copy button works
- Settings persist between sessions
- Nothing sent to external services (verify in browser network tab)

---

## Step 7 — FileProcessor: Single File (DOCX)

**Codeberg issue to create first:**
`feature: implement FileProcessor for single DOCX files`

**Goal:** A single DOCX file is anonymized correctly via the UI.

### What to build

- `app/services/document_processor.py` — `DocumentProcessor` class handles
  DOCX text extraction and content replacement using python-docx
- `app/services/file_processor.py` — `FileProcessor` class:
  - Accepts a single file path
  - Calls `DocumentProcessor` for content
  - Applies file name checking if enabled
  - Saves output with correct prefix to same folder as original
  - Saves `KEYREF_` file if Key Reference enabled
  - Returns result summary (anonymized / clean / error)
- Document Mode UI wired to process a single dropped file
- Progress shown for single file

### ✅ Step 7 is complete when
- A DOCX with names produces `ANON_` output with correct placeholders
- A DOCX with no PII produces `CHECKED_` copy
- Original file is not modified
- Key reference file generated when enabled
- File name anonymized when file/folder name checking is enabled

---

## Step 7.5 — Hotfix: Language Selection, Date Toggle, Pattern Config Parity

**Codeberg issue to create first:**
`fix: manual language selection, optional date anonymization, pattern config in both modes`

**Goal:** Correct three usability and accuracy problems identified during real-document
testing before continuing with PDF support. This step must be complete before Step 8.

### Background and reasoning

Three issues were found during testing on a real internship document:

**Issue 1 — Language detection is unreliable.**
`langdetect` is probabilistic. On short texts it can misidentify the language, and on
mixed-language documents (e.g. a Dutch report with English headings) it is inconsistent.
In testing, names were missed in a full sentence — the most likely cause is the wrong
spaCy model being selected because the language was detected incorrectly. The user always
knows what language their documents are in; they should choose it.

**Issue 2 — DATE_TIME anonymization is too aggressive.**
Presidio's `DATE_TIME` entity type catches all date formats including relative dates,
quarters, academic years, and any sequence that looks like a date. In internship and
student documents, dates are ubiquitous (submission dates, period headings, deadlines)
and are not personally identifying on their own. Anonymizing them makes output difficult
to read and is rarely what the user wants. Dates of birth are the one case where dates
ARE sensitive, but these are rare and will often be caught by context. DATE_TIME should
be off by default and opt-in.

**Issue 3 — Student number pattern config exists only in Document Mode.**
The digit-count input for student number detection was placed in Document Mode during
the Step 2 placeholder UI but was never added to Text Mode. Since student numbers
appear in plain pasted text too, both modes need the control. The control does not need
to be functional yet (that is Step 10) but it must be present in the UI now so it is
not forgotten.

### What to build

**1. Manual language selection — both modes**
- Add a language selector (EN / NL) to Text Mode settings bar and Document Mode
  settings panel.
- The selector replaces the automatic `LanguageDetector` call in both the
  `/text/anonymize` and `/document/process-file` routes.
- `LanguageDetector` can remain as a class for potential future use but is no
  longer called at runtime.
- `UserSettings` should persist the selected language and restore it on launch.

**2. DATE_TIME opt-in toggle — both modes**
- Add an "Anonymize dates" toggle to Text Mode settings bar and Document Mode
  settings panel. Off by default.
- When off, remove `DATE_TIME` from the entities list passed to Presidio.
- When on, include it as before.
- Persist the toggle state via `UserSettings`.
- Update `Anonymizer.anonymize()` to accept an optional `entities` override
  parameter, or filter the list at the route level before calling the anonymizer.

**3. Student number digit count in Text Mode**
- Add the digit count input and enable/disable toggle to the Text Mode settings
  bar (same control as already shown in Document Mode).
- Does not need to be wired to actual detection yet — that is Step 10.
- The visual control must be present and its value must persist via `UserSettings`.

### ✅ Step 7.5 is complete when
- Language selector appears in both modes; selected language is used for detection;
  selecting NL on a Dutch document with a name anonymizes it correctly
- "Anonymize dates" toggle appears in both modes, defaults to off; dates are not
  replaced when off; dates are replaced when on
- Student number digit count control is present in Text Mode
- All three settings persist between sessions
- Existing tests still pass

---

## Step 8 — FileProcessor: Single File (PDF)

**Codeberg issue to create first:**
`feature: implement FileProcessor for single PDF files`

**Goal:** A single PDF file is anonymized with in-place text replacement
via pymupdf.

### What to build

- PDF processing method in `DocumentProcessor` using pymupdf redaction API
- Text replaced in-place at original position where possible
- Same prefix and key reference behaviour as DOCX

### ⚠️ Decision point
If pymupdf redaction does not preserve layout acceptably, the fallback is
to output an anonymized DOCX or plain text file alongside the original PDF
with a clear note in the UI. Record the decision taken in `docs/PROJECT_GUIDE.md`
under Open Questions.

### ✅ Step 8 is complete when
- A PDF with names produces `ANON_` PDF with placeholders
- Layout is acceptably preserved
- Original PDF is not modified

---

## Step 9 — FolderProcessor: Folder and Subfolder Batch

**Codeberg issue to create first:**
`feature: implement FolderProcessor for recursive batch processing`

**Goal:** Folder selection processes all supported files recursively,
preserving subfolder hierarchy, with progress shown and resilient handling
of corrupt files.

### What to build

- `app/services/folder_processor.py` — `FolderProcessor` class:
  - Accepts a folder path
  - Recursively finds all PDF and DOCX files
  - Calls `FileProcessor` for each file, completing one before starting next
  - Catches and logs errors for corrupt/unreadable files without stopping batch
  - Renames folder names after all file content is complete, deepest first
  - Returns full summary of results
- Document Mode UI shows file N of M progress during processing
- Completion summary displayed after batch finishes

### ✅ Step 9 is complete when
- A folder with subfolders processes all supported files
- Subfolder hierarchy is preserved with anonymized names where applicable
- A corrupt file is skipped with a logged error and processing continues
- Progress updates shown during batch
- Completion summary correct

---

## Step 10 — Custom Pattern: Numeric ID Detection

**Codeberg issue to create first:**
`feature: implement configurable numeric ID pattern detection`

**Goal:** User can configure digit count for numeric ID detection (student numbers,
employee numbers, or any fixed-length numeric identifier).

### What to build

- Custom Presidio recognizer using `PatternConfig` digit count setting
- Applied in both Text Mode and Document Mode
- Currency prefix exclusion rule applied
- UI allows user to set digit count and enable/disable detection
- Entity type named `NUMERIC_ID` (generic, not domain-specific)

### ✅ Step 10 is complete when
- A 7-digit numeric ID (or configured count) is detected and anonymized
- A currency amount with same digit count is not flagged
- Setting persists between sessions

---

## Step 10.5 — Usability and Accuracy Fixes

**Codeberg issue:** `d-craig/d-tach#23`

**Goal:** Fix four issues identified during real-document testing.

### Changes

#### 1. Native OS file/folder browser buttons
`app/routes/browse_routes.py` — new Blueprint with two endpoints:
- `GET /browse/file` — opens `tkinter.filedialog.askopenfilename` (DOCX/PDF filter)
  and returns `{"path": "..."}` or `{"error": "..."}`.
- `GET /browse/folder` — opens `tkinter.filedialog.askdirectory` and returns the same
  shape.

`app/__init__.py` — registers `browse_bp`.

`app/templates/document_mode.html` — adds **Browse…** buttons next to both path inputs.

`app/static/js/document_mode.js` — adds click handlers that `fetch()` the browse
endpoints and populate the path inputs.

**Note:** `tkinter` is blocking. This is acceptable for a single-user local app.
The dialog opens in front of the browser window via `root.wm_attributes("-topmost", True)`.

#### 2. Case-insensitive filename renaming
`app/services/file_processor.py` — `_anonymize_filename()` previously used
`str.replace()` which is case-sensitive. Real documents had filenames like
`nick_surname_1234567.docx` where the NER engine detected `Nick Surname` (title case)
in the document body. The case mismatch meant the filename was never rewritten.

Fix: replace `readable.replace(original, placeholder)` with
`re.sub(re.escape(original), placeholder, readable, flags=re.IGNORECASE)`.

#### 3. NUMERIC_ID rename (student_number → numeric_id)
The entity type `STUDENT_NUMBER` and all associated identifiers are renamed to
`NUMERIC_ID` throughout:
- `app/services/anonymizer.py` — `NUMERIC_ID_ENTITY`, `NumericIdRecognizer`,
  `build_numeric_id_recognizer`
- `app/services/pattern_config.py` — `numeric_id_enabled`, `build_numeric_id_regex()`
- `app/services/user_settings.py` — default key `numeric_id_enabled`; migration in
  `_merge_with_defaults` accepts the old `student_number_enabled` key
- Routes, templates, JS — all updated to match
- `tests/test_student_number.py` — deleted; replaced by `tests/test_numeric_id.py`

**Migration:** `PatternConfig.from_dict()` accepts either `numeric_id_enabled` (new) or
`student_number_enabled` (old), preferring the new key. Existing `user_settings.json`
files on disk migrate transparently on first load.

#### 4. Table row NER context fix
`app/services/document_processor.py` — `_extract_docx_text()` previously fed each
table cell paragraph to the NER model as an isolated short string. Single-word cells
("Nick") provided too little context for spaCy to classify them as `PERSON`.

Fix: join all cell text in a row into one string (`row_text`) before appending to the
NER input list. This mirrors the fix recommended in the post-public backlog and is
applied here since it is a one-line change with no side effects on the replacement path.

### ✅ Step 10.5 is complete when
- Browse buttons open native OS picker and populate the path fields
- A file named after a person detected in its content is correctly renamed
- `NUMERIC_ID` entity name appears in output; old `STUDENT_NUMBER` name gone
- Names in table cells are detected when they appear alongside other cell text
- All 103 tests pass

---

## Step 11 — Pre-Public Review and Launcher Scripts
*Do this before making the repo public*

**Codeberg issue to create first:**
`chore: pre-public review, README completion, and launcher scripts`

### Goal
Prepare the repo for public release and make the application accessible to
colleagues who do not have Python installed or are not comfortable with the command line.

### Part A — Launcher Scripts

Create two scripts in the project root that non-technical users can double-click:

**`launch.bat` (Windows)**
```bat
@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python run.py
pause
```

**`launch.sh` (macOS / Linux)**
```bash
#!/usr/bin/env bash
cd "$(dirname "$0")"
source .venv/bin/activate
python run.py
```

Both scripts assume the virtual environment already exists at `.venv/`. If it does not,
they should print a friendly message directing the user to the README setup section.

Add a check to `launch.bat`:
```bat
if not exist ".venv\Scripts\activate.bat" (
    echo Virtual environment not found. Please follow the setup instructions in README.md.
    pause
    exit /b 1
)
```

Similarly in `launch.sh`:
```bash
if [ ! -f ".venv/bin/activate" ]; then
    echo "Virtual environment not found. Please follow the setup instructions in README.md."
    exit 1
fi
```

### Part B — Non-Developer README

`README.md` must be rewritten (or completed) to address two audiences:

**For technical users (developers, IT-literate colleagues):**
- Prerequisites: Python 3.11+
- Clone / download the repo
- `python -m venv .venv && .venv/Scripts/activate`
- `pip install -r requirements.txt`
- `python -m spacy download en_core_web_md && python -m spacy download nl_core_news_md`
- `python run.py` (or double-click `launch.bat`)

**For non-technical users (educators, assessors):**
- "Download" section with a link to the zip download on Codeberg
- Step-by-step with screenshots where possible
- Explain what the application does in plain language
- Explain that it never sends data anywhere
- Explain that nothing is installed system-wide — it runs from a folder
- Point to the launcher scripts as the way to start the application

### Part C — Pre-Public Checklist

- [ ] `launch.bat` and `launch.sh` created and tested
- [ ] README.md complete with instructions for both audiences
- [ ] `requirements.txt` accurate and pinned to tested versions
- [ ] No real student or personal data anywhere in repo or git history
- [ ] EUPL-1.2 `LICENSE` file present
- [ ] `KEYREF_`, `ANON_`, `CHECKED_` files absent from git history
- [ ] `user_settings.json` absent from git history
- [ ] Codeberg repo description and topics set
- [ ] Open issues reviewed — resolved ones closed, open ones labelled
- [ ] Saxion IP policy confirmed as not a concern for public release
- [ ] Consider adding `CONTRIBUTING.md` if external contributions are welcome

---

## Step 12 — Make Repo Public

### Actions
1. Verify all items in `craig_check.md` are ticked.
2. Codeberg → Settings → Danger Zone → Make Public.
3. Create the first release on Codeberg: Releases → New Release → tag `v1.0.0` → publish.
4. Announce if relevant (colleagues, LinkedIn, Saxion community).

### Release process (for all future versions)

Each release follows this sequence:

1. Bump `__version__` in `app/__init__.py`.
2. Update the version badge in `README.md` (the `version-X.X.X-blue` string).
3. Add a new entry to `CHANGELOG.md` with the version number, date, and a summary of changes.
4. Commit: `Update version to vX.X.X (issue #N)`.
5. Tag: `git tag vX.X.X -m "Release vX.X.X"`.
6. Push commits and tag: `git push && git push origin vX.X.X`.
7. Codeberg → Releases → New Release → select the tag → paste the CHANGELOG entry as release notes → publish.

---

## Post-Public Issue Backlog

After the repo goes public, further development is tracked as Codeberg issues rather
than ordered steps. Issues do not need to be done in sequence — they can be picked up
by any contributor or by the maintainer in priority order.

Create all of these as Codeberg issues at the time of going public (Step 12) so the
community can see the roadmap and self-assign work.

**When completing any post-public issue that ships a change to users:**
- Decide whether it is a PATCH (bug fix), MINOR (new feature), or MAJOR (overhaul).
- Follow the release process in Step 12 above.
- Add an entry to `CHANGELOG.md` before tagging.
- Update the version badge in `README.md`.

---

### Planned for v1.1.0

The three items below were identified during the v1.0.0 fresh-machine test.
Implement all three on a single `feature/issue-N-v1-1-0` branch and release together.

- **fix: Browse button crashes on macOS when tkinter is not installed**
  On macOS, `tkinter` is not bundled with all Python distributions (e.g. Homebrew Python
  requires a separate `python-tk@3.x` package). Two changes required:
  1. **`launch.sh` setup check:** during first-run setup, after pip install, run
     `python3 -c "import tkinter" 2>/dev/null` and if it fails print a clear one-line
     warning: `"Note: tkinter not found — Browse buttons will be disabled. To enable,
     run: brew install python-tk@3.x"`. Setup should continue; this is a warning not a
     blocker.
  2. **Graceful fallback in the app:** wrap the `tkinter` import in `browse_routes.py`
     in a try/except; if it fails, the `/browse/file` and `/browse/folder` endpoints
     return a clear error, and the JS hides the Browse buttons and shows a small inline
     note so the user can still type the path manually. The app must not crash.
  tkinter cannot be installed via pip — it is a system package. Auto-installing it from
  the script is not feasible; the warning and graceful fallback are the correct fix.

- **fix: PDF replacement text uses wrong font size**
  PyMuPDF's `apply_redactions()` inserts replacement text at a default font size that
  often differs from the original, making redacted PDFs look inconsistent. Fix: before
  calling `add_redact_annot()`, read the font size of the original text span from the
  page's text dict (`page.get_text("dict")`). Pass that size to `add_redact_annot()`
  via the `fontsize` parameter so the replacement text matches the surrounding content.

- **change: Standardise placeholder format to `[PLACEHOLDER]` across all output**
  Currently replacements appear as bare identifiers: `PERSON_1`, `EMAIL_ADDRESS_1`.
  Change the format to `[PERSON_1]`, `[EMAIL_ADDRESS_1]` throughout — text mode,
  DOCX, PDF, Markdown, and Excel output, and the key reference file. Brackets are the
  recognised redaction convention, look intentional in a document, and make replacements
  immediately distinguishable from surrounding text. This is a visible output change;
  update the CHANGELOG entry and mention it clearly in the v1.1.0 release notes.
  Also update any test assertions that match the bare placeholder format.

- **fix: README macOS instructions — add `bash launch.sh` as simpler alternative**
  The current README requires `chmod +x launch.sh && ./launch.sh` for first run, which
  involves an unfamiliar terminal command. Non-technical macOS users can instead run
  `bash launch.sh` directly without needing `chmod`. Update the macOS installation
  section to show `bash launch.sh` as the primary instruction, with `chmod +x` noted
  as an optional step for users who want to double-click the script in future.

- **fix: Launcher scripts do not open the browser automatically**
  After setup completes, `launch.bat` and `launch.sh` start the Flask server but leave
  the user staring at a terminal URL. Non-technical users may not know to copy it into
  a browser. Fix: after starting the server process, call `start http://localhost:5000`
  (Windows `.bat`) or `open http://localhost:5000` (macOS `.sh`) /
  `xdg-open http://localhost:5000` (Linux `.sh`). Add a short sleep (1–2 s) before
  opening to allow Flask to finish binding the port. This is a PATCH-level fix but is
  bundled with the two features below into a MINOR release.

- **feature: Excel file (.xlsx) anonymization**
  Add `.xlsx` to the list of supported file types in `FileProcessor` and
  `FolderProcessor`. Use `openpyxl` to read cell values, run them through `Anonymizer`,
  and write replacements back to a copy of the file. Preserve cell formatting and
  formulas — only replace string cell values that contain detected PII. Add
  `openpyxl>=3.1` to `requirements.txt`. Implement a `load_xlsx` /
  `save_xlsx_with_replacements` / `save_xlsx_copy` pattern in `DocumentProcessor`
  matching the existing DOCX and PDF methods.

- **feature: Key reference export — folder mode and improved single-file export**
  The key reference is currently shown on screen (Text Mode) and saved per-document
  (Document Mode). Expand this in two directions:
  - **Folder mode:** When the key reference toggle is enabled and a folder is processed,
    save a single consolidated `KEYREF_<folder-name>.txt` (or `.csv`) at the root of
    the selected folder, listing all placeholder → original mappings across all files
    in the run. Design the format so it is readable by non-technical users — consider
    a simple two-column CSV: `Placeholder, Original value`.
  - **Text Mode and single-file mode:** Add an explicit **Export** button alongside the
    on-screen key reference table so the user can save it as a file with one click. The
    in-UI table remains; the button is additive.
  This replaces the "Key Reference export" entry in the High priority section below.

---

### Infrastructure: Codeberg storage quota

The free Codeberg plan has a limited LFS/release storage quota. When a packaged release
(PyInstaller — see lower priority items below) is created, the binary will likely exceed
the default limit. Before publishing a packaged release, apply for additional quota via
the Codeberg Community issue tracker: describe the project, its privacy-first purpose,
and the intended audience (colleagues without Python experience).

---

### High priority (do first after public)

- **Improve NER detection accuracy — names in tables and less common names**
  During real-document testing, names in the first-page table of an internship
  document were inconsistently detected: the student name in the table was found
  but a supervisor name in an adjacent row was missed. Names later in the document
  were found normally. Two likely causes: (1) the medium spaCy models (`_md`) have
  lower recall than the large models (`_lg`) for less common names; (2) table cell
  text is fed to the NER model in short isolated chunks, which reduces context and
  hurts detection. Suggested investigation: test with `en_core_web_lg` /
  `nl_core_news_lg`; consider concatenating table row text before analysis to give
  the model more context. Create a small anonymized test corpus of representative
  document structures to make accuracy improvements measurable and repeatable.

- **Key Reference export** *(see full spec in "Planned for v1.1.0" above)*
  Expanded scope: Text Mode export button + consolidated folder-level key reference file.
  Original single-file export behaviour remains; folder mode and explicit export button
  are additive.

- **Accuracy review and model upgrade path**
  Evaluate whether `en_core_web_lg` and `nl_core_news_lg` (the large spaCy models)
  meaningfully improve name detection over the medium models. Document the trade-off
  (download size vs. accuracy) and offer the larger models as an opt-in in the
  installation guide.

- **Organisation name detection review**
  As noted in `PROJECT_GUIDE.md`, organisation names are less reliably detected and
  may or may not be sensitive under GDPR depending on context. Assess detection quality
  after real-world use and consider adding a confidence indicator or a review step.

### Medium priority

- **Visual highlighting of detected entities in Text Mode**
  Highlight detected PII in the output panel so the user can visually verify what was
  replaced. `Mark.js` is the documented candidate library (see `PROJECT_GUIDE.md`).

- **Drag and drop individual file in Document Mode**
  Allow a single file to be dropped onto the Document Mode panel as an alternative to
  typing the path. When dropped, populate the file path field automatically.
  Note: the browser security model means the server still needs the absolute path;
  investigate the File System Access API as the mechanism.

- **Auto-clipboard on anonymization in Text Mode**
  Place the anonymized output in the clipboard automatically when processing completes,
  so the user can paste without clicking the copy button.

### Lower priority

- **Batch summary log**
  After a folder processing run, save a machine-readable summary log (JSON or CSV)
  to the processed folder listing each file's status, entity count, and output path.

- **Standalone packaged installer (PyInstaller)**
  Use PyInstaller to produce a single-folder distribution that includes the Python
  interpreter, all dependencies, and the spaCy models. Target audience: colleagues
  without Python experience who cannot or will not run the launcher scripts.
  The launcher scripts in Step 11 are a stepping stone; PyInstaller is the full
  zero-install solution. Known challenges: spaCy model size, Flask static file
  paths under PyInstaller's `sys._MEIPASS`, and `tkinter` bundling on macOS.
  Investigate once the app is stable post-public.
