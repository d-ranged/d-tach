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

## Step 10 — Custom Pattern: Student Numbers

**Codeberg issue to create first:**
`feature: implement configurable student number pattern detection`

**Goal:** User can configure digit count for student number detection.

### What to build

- Custom Presidio recognizer using `PatternConfig` digit count setting
- Applied in both Text Mode and Document Mode
- Currency prefix exclusion rule applied
- UI allows user to set digit count and enable/disable detection

### ✅ Step 10 is complete when
- A 7-digit student number (or configured count) is detected and anonymized
- A currency amount with same digit count is not flagged
- Setting persists between sessions

---

## Step 11 — Pre-Public Review
*Do this before making the repo public*

**Codeberg issue to create first:**
`chore: pre-public review and repo preparation`

### Checklist

- [ ] README.md complete with installation instructions and usage guide
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
1. Codeberg → Settings → Danger Zone → Make Public
2. Announce if relevant (colleagues, LinkedIn, Saxion community)

---

## Nice-to-Have Steps (Post-Public)

Lower priority — do not block Steps 0–12.

- **Step 13** — Visual highlighting of detected entities in Text Mode
- **Step 14** — Drag and drop individual file in Document Mode
- **Step 15** — Auto-clipboard on anonymization in Text Mode
- **Step 16** — Packaging for easier installation (setup script or similar)
