# CLAUDE.md — d-tach Project Context

This file is the primary reference for Claude when working on this project.
Read this before writing or modifying any code.

---

## What This Project Is

d-tach is a locally-run Flask web application that anonymizes personal data
from text and documents (PDF and DOCX) before they are shared externally for
review. It is built for educational and professional contexts where GDPR
compliance matters — specifically for reviewing student and internship documents
using AI-assisted tools.

The name d-tach reflects the core purpose: detaching identity from content.

**Core principle:** Nothing leaves the user's machine until it has been
anonymized. The application has no network calls, no telemetry, and no
external dependencies at runtime beyond locally installed libraries.

---

## Git usage

Issues are created manually via the Codeberg GUI. Claude references issue numbers in commits and branch names.

Workflow per step:
1. User creates the issue on Codeberg GUI and provides the issue number
2. Claude creates a branch: `chore/issue-N-short-description` or `feature/issue-N-short-description`
3. Claude commits regularly, each message referencing the issue: `Description of change (issue #N)`
4. When step is complete, Claude confirms what to do: user creates the PR via Codeberg GUI with description `Closes #N`
5. User tests, confirms working, merges via GUI, then deletes the feature branch

**Exception — documentation-only changes:** Updates to `docs/STEP_GUIDE.md`,
`docs/PROJECT_GUIDE.md`, or `CLAUDE.md` that contain no code changes may be
committed directly to `main` without a feature branch.

## Project Documentation

Before coding any feature, consult these files in order:

- `docs/PROJECT_GUIDE.md` — full goals, MoSCoW requirements, PII categories,
  tool decisions
- `docs/STEP_GUIDE.md` — incremental build plan; always know which step you
  are on before writing code
- `CLAUDE.md` — this file; coding conventions and permissions

---

## Language and Framework

- **Python 3.11+** — primary language
- **Flask** — web framework, local server only
- **Presidio Analyzer + Anonymizer** — PII detection and replacement engine
- **spaCy** — NLP models underlying Presidio (English and Dutch required)
- **pymupdf (fitz)** — PDF reading and in-place text redaction
- **python-docx** — DOCX reading and writing
- **HTML / CSS / Vanilla JavaScript** — frontend, served by Flask

---

## Code Style and Architecture

### OOP Principles

All business logic must be encapsulated in classes. Flask routes must be
thin — they receive a request, call a class method, and return a response.
No logic in routes beyond that.

Core classes (do not merge these responsibilities):

```
Anonymizer            — wraps Presidio engine; detects and replaces PII in text
DocumentProcessor     — handles PDF and DOCX file operations; calls Anonymizer
KeyReferenceStore     — manages placeholder-to-original mapping
LanguageDetector      — detects document language; selects correct spaCy model
HashEncoder           — handles consistent hashing with user secret as salt;
                        encodes first and last names separately
PatternConfig         — holds user-configured custom pattern settings
                        (digit count, toggles for file/folder name checking)
FileProcessor         — handles single file processing including renaming logic
FolderProcessor       — handles recursive folder processing; calls FileProcessor;
                        renames folders last after all file content is complete
UserSettings          — persists user preferences (hashing toggle, secret,
                        pattern config) to local storage; restores on launch
```

New classes follow the same pattern: single responsibility, clear name,
docstring on the class and every public method.

### General Rules

- Use type hints on all function and method signatures
- Docstrings on every class and every public method (one-line minimum)
- No magic numbers or hardcoded strings — use constants or config
- No logic in `__init__.py` files
- Separate concerns: detection logic never touches file I/O; file I/O never
  touches detection logic
- Keep methods short — if a method does more than one thing, split it
- Prefer explicit over clever

### Naming Conventions

- Classes: `PascalCase`
- Functions and methods: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Files: `snake_case.py`
- HTML templates: `snake_case.html`
- CSS and JS files: `snake_case.css` / `snake_case.js`

### Error Handling

- Never silently swallow exceptions
- Log errors with enough context to diagnose (file name, operation, exception)
- Return meaningful error messages to the frontend
- Do not expose stack traces to the UI
- A corrupt or unreadable file must be logged and skipped — it must not
  stop processing of remaining files

---

## Hashing Rules

These rules are fixed and must not be varied in implementation:

- Hashing is optional. Off by default.
- The hashing toggle and secret input appear together in the UI. Ticking
  the toggle opens the secret input field immediately alongside it.
- The user must enter a secret before hashing can proceed. If the toggle
  is enabled but no secret is entered, processing is blocked with a clear
  message.
- The secret is used as a cryptographic salt. It does not need to meet
  password complexity requirements — it is a convenience feature.
- First name rule: preserve first 2 characters exactly, hash the remainder
  to exactly 4 uppercase alphanumeric characters.
  Example: Craig → Cr-A2T5
- Last name rule: hash the full name to exactly 4 uppercase alphanumeric
  characters.
  Example: Bradley → HY23
- First name and last name are always hashed separately so that a first
  name appearing alone (e.g. in a folder name) still resolves to the same
  prefix and hash as when the full name appears.
- The same name + the same secret always produces the same output across
  sessions.
- When hashing is off, standard sequential placeholders are used instead:
  PERSON_1, PERSON_2 etc.
- The hashing toggle state and secret are persisted via UserSettings and
  restored automatically on next launch.
- Security note: this is a consistency and pseudonymization feature, not
  a cryptographic security system. Users should be aware that the same
  secret always produces the same output, which means the anonymization
  is reversible if the secret is known.

---

## Custom Pattern Rules

- Student number detection: user selects an exact digit count N via a
  number input in the UI.
- A match requires exactly N consecutive digits where the character
  immediately before is a non-digit (or start of string) and the character
  immediately after is a non-digit (or end of string).
- No match if the sequence is immediately preceded by a currency symbol
  (€, $, £).
- File name and folder name checking is a separate toggle.
- A single disclaimer is shown persistently at the bottom of the UI:
  "Pattern matching may produce false positives. Review the key reference
  file before sharing anonymized output."

---

## File and Folder Processing Rules

- File names are checked and renamed using the same hash logic as document
  content when file/folder name checking is enabled.
- Folder names are checked and renamed using the same hash logic.
- Folder renaming always happens after all file content within has been
  fully processed — never mid-process.
- Subfolder hierarchy is preserved in output — structure mirrors the
  original, only names change where PII is detected.
- Processing order: files first from deepest level upward, then folder
  names from deepest to shallowest.
- Output prefix rules:
  - PII detected and removed: `ANON_` prefix on file
  - No PII detected: `CHECKED_` prefix on file (content unchanged)
  - Key reference file (when enabled): `KEYREF_` prefix, saved alongside

---

## Progress and Resilience

- Single file processing must complete before the next file begins.
- A corrupt or unprocessable file is logged and skipped; processing
  continues with the next file.
- UI shows progress during folder processing: current file N of total M.
- A completion summary is shown after folder processing: files anonymized,
  files clean, files skipped with reason.

---

## Multilingual Support

The application supports English and Dutch. Both spaCy models must be
loaded at startup. LanguageDetector identifies the primary language of
input and routes to the correct model. Dutch-specific PII patterns (BSN,
Dutch phone formats) require custom Presidio recognizer rules.

---

## Project Structure

```
d-tach/
├── app/
│   ├── __init__.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── text_routes.py
│   │   └── document_routes.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── anonymizer.py
│   │   ├── document_processor.py
│   │   ├── file_processor.py
│   │   ├── folder_processor.py
│   │   ├── hash_encoder.py
│   │   ├── key_reference_store.py
│   │   ├── language_detector.py
│   │   ├── pattern_config.py
│   │   └── user_settings.py
│   ├── static/
│   │   ├── css/
│   │   │   └── main.css
│   │   └── js/
│   │       ├── text_mode.js
│   │       └── document_mode.js
│   └── templates/
│       ├── base.html
│       ├── text_mode.html
│       └── document_mode.html
├── tests/
│   ├── test_anonymizer.py
│   ├── test_hash_encoder.py
│   ├── test_document_processor.py
│   ├── test_file_processor.py
│   └── test_key_reference_store.py
├── docs/
│   ├── PROJECT_GUIDE.md
│   └── STEP_GUIDE.md
├── .claude/
│   └── settings.json
├── .gitignore
├── CLAUDE.md
├── LICENSE
├── README.md
├── requirements.txt
└── run.py
```

---

## Git Workflow

### Branch Naming

```
feature/issue-{number}-{short-description}
fix/issue-{number}-{short-description}
chore/issue-{number}-{short-description}
```

### Commit Messages

Every commit must reference its issue:

```
Short description of what changed (issue #N)
```

### Workflow Per Feature

1. Create an issue on Codeberg
2. Create a branch from `main`
3. Commit regularly with issue references
4. Open a merge request when complete and tested
5. Merge to `main` only when working

Never commit directly to `main`.

---

## What Claude Is Allowed To Do

- Read, create, and edit any file within the project directory
- Run `git` commands: `status`, `add`, `commit`, `checkout`, `branch`,
  `merge`, `log`, `diff`, `push`, `pull`, `fetch`, `remote`, `init`
- Run `pip install` for packages in or discussed against `requirements.txt`
- Run `curl` and `wget` for fetching documentation or packages
- Run `python` scripts within the project
- Run `pytest` for tests
- Run `flask run` to start the development server
- Run `python -m spacy download` for language models

## What Claude Must Not Do

- Make any network requests from application code at runtime
- Install packages not discussed without flagging first
- Modify `.claude/settings.json` without explicit instruction
- Commit directly to `main`
- Delete files without explicit instruction
- Access files outside the project directory
- Use `git push --force` under any circumstances
