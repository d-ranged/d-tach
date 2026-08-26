# Changelog

All notable changes to d-tach are documented here.
Version numbers follow [Semantic Versioning](https://semver.org/): MAJOR.MINOR.PATCH.

- **MAJOR** — significant overhaul or breaking change (rare for a tool like this)
- **MINOR** — new feature or capability added
- **PATCH** — bug fix or small correction

---

## [1.3.0] — 2026-08-26

### Added

- **System tray app** — d-tach now runs as a persistent background process with a tray icon (Open d-tach / Quit) instead of something launched and closed each session. Offers a one-time prompt to register as a Windows startup program.
- **Configurable port** — the listening port (default changed from 5000 to 5555, avoiding conflicts with other local Flask projects) is set in Settings rather than fixed at launch; changing it prompts for a restart.
- **On-demand language management** — spaCy language models are downloaded and loaded on demand rather than bundled with the app, chosen at first launch and changeable later in Settings. Keeps the persistent tray process from holding memory for models never used, and shrinks what a future packaged installer needs to ship.
- **Class list import** — bulk-populate known values from a roster file (e.g. student number and name columns) instead of adding names one at a time. Re-syncing the same file only adds new rows; a "Clear class list values" action removes only imported entries, leaving manually-added ones in place.
- **AI Mode** — a local, token-authenticated API (`/ai/extract`, `/ai/restore`, `/ai/flag-term`) that lets an AI assistant work through real documents without ever reading a file's contents directly. Extract returns anonymized text and a session-scoped placeholder map; restore substitutes real values back in, optionally writing straight to an output path so restored content never has to pass back through the assistant at all. Includes a "Rename names only" pass that anonymizes every file and folder name in a tree in place, so the tree is safe to enumerate before any content is read.
- **Settings is now the single writer** for everything a run reads — hashing, detection toggles, Excel handling, folder output mode, default language. Every mode reads from Settings; a run's per-request overrides apply to that run only and are never written back.

### Fixed

- **Double-anonymization of already-anonymized text** — re-running anonymization on text that already contained d-tach placeholders corrupted them into nested, malformed brackets. Already-anonymized spans are now recognized and left untouched.
- **Known values matching inside longer words** — a known value could match as a substring of an unrelated word, corrupting prose and creating a false replacement that restore would later reinsert mid-word. Matching is now whole-word only.
- **Overlapping detections producing malformed placeholders** — two detections covering overlapping spans were both replaced independently, producing a placeholder no restore pass could map back to a real value. Overlaps are now resolved to one detection per span before replacement.
- **Possessive names hashing inconsistently** — a trailing possessive (`'s`, including the typographic `'s`) was included in the detected name span, so the same person could hash to three different placeholders depending on how their name was written. The possessive is now trimmed from the span before hashing and left in place in the surrounding text.
- **Image-based PDFs written into anonymized output unreadable** — a PDF with no extractable text (e.g. a scanned page) was still copied into the output, indistinguishable from a properly anonymized file once the destination folder dropped identifying prefixes. Nothing is now written for a PDF that can't be read at all; a PDF with only some image-only pages is anonymized on its text pages, with the image-only ones named in a warning.
- **AI Mode reporting the wrong placeholder** — `/ai/extract`'s entity list reported sequential placeholders (`[PERSON_1]`) while the returned text carried hashed ones, so the entity list named tokens absent from the document and reused the same label for a different person in every file. The entity list now reports the placeholder actually written into the text.

---

## [1.2.0] — 2026-06-07

### Added

- **Restore tab** — new mode for reversing anonymization. Select any file containing d-tach placeholders (DOCX, XLSX, MD, TXT) and a KEYREF CSV; the tool replaces all placeholders with their original values and saves a `RESTORED_` copy. The primary use case is AI-output round-tripping: anonymize a document, send it to an AI tool, then restore the AI's response so real names and values appear in the final output. Placeholder tokens in the filename itself are also resolved in the output filename. The KEYREF Browse button opens a dialog filtered to CSV files.
- **Known values list** — add names that the NER model consistently misses (e.g. uncommon names from less-represented language backgrounds) via a collapsible "Known names" panel in both Text and Document modes. Entries are stored in `user_settings.json` and applied as high-confidence (0.99) case-insensitive recognizers before every run, across both modes and including filename anonymization when that option is enabled.

### Fixed

- **PDF unreadable detection** — image-based PDFs or PDFs with non-standard encoding previously produced a silent `CHECKED_` output, falsely implying the file had been inspected for PII. They now produce an `UNREADABLE_` copy with a clear amber warning in the UI. Folder runs continue processing remaining files and include an unreadable count in the summary.
- **Numeric ID / phone number overlap** — when Numeric ID detection was active with a digit count matching a common phone number length (10–11 digits), the same number was detected by both recognizers and produced corrupted placeholder output. The anonymizer now resolves overlapping spans by confidence, keeping only the stronger detection.

---

## [1.1.0] — 2026-04-28

### Added

- **Excel (.xlsx) anonymization** — NER-based detection on string cells (names, emails, phones) plus a column-based mode for numeric identifiers (e.g. integer student number columns) that NER cannot reach. Both modes are independent toggles; either or both can be active simultaneously. When both are off, Excel files are skipped entirely.
- **Advanced Settings panel** — collapsible section in Document Mode exposing Excel-specific controls (NER toggle, column names input) and the new URL detection toggle.
- **Key reference export improvements** — folder runs produce a single consolidated `KEYREF_<folder>.csv` at the folder root (or inside `anonymized/` in subfolder mode). Text Mode gains a one-click Export CSV button.
- **Anonymized subfolder output mode** — instead of placing `ANON_`/`CHECKED_` files alongside originals, all output goes into an `anonymized/` subfolder mirroring the original structure with original filenames preserved.
- **Consistent hashing for all entity types** — when hashing is enabled, emails, phone numbers, BSN, numeric IDs, and locations all receive a deterministic 4-character HMAC hash (`[EMAIL_A2B3]`, `[PHONE_C4D1]`) in addition to names. The same value + same secret always produces the same placeholder across files and sessions.
- **URL detection toggle** — URL detection is now opt-in (off by default). This removes an overlap between the URL and EMAIL_ADDRESS recognisers that previously caused garbled output when email addresses were present.

### Changed

- Placeholder format changed from bare identifiers (`PERSON_1`) to bracketed format (`[PERSON_1]`). This affects all output modes: text, DOCX, PDF, and key reference files. **Visible change** — any downstream tooling or workflows that match on placeholder strings must be updated.
- d-ranged branding applied: SA green / Dutch orange dual-identity theme (T4) is now the default; clicking the logo toggles to a neutral professional theme (T1). Theme preference persists in `localStorage`.
- Launcher scripts (`launch.bat`, `launch.sh`) open the browser automatically after Flask starts.
- macOS: graceful fallback when tkinter is not installed — Browse buttons are hidden with a clear inline message; the rest of the app is unaffected.

### Fixed

- `.xlsx` files were not selectable in the single-file Browse dialog — the tkinter file type filter now includes Excel files.
- Column-not-found warnings in the progress log were displayed with error styling (amber ⚠); they now use a muted grey ℹ indicator to distinguish informational notices from actual processing failures.

---

## [1.0.0] — 2026-04-13

First public release.

### Features

**Anonymization**
- PERSON, EMAIL_ADDRESS, PHONE_NUMBER, LOCATION, URL detection via Microsoft Presidio
- Optional DATE_TIME detection (off by default — dates are ubiquitous in academic documents)
- Configurable numeric ID detection: set exact digit count to match student numbers, employee IDs, or any fixed-length identifier; currency amounts are excluded
- Optional hash-based pseudonymization: names are replaced with a consistent short code derived from a user-supplied secret, allowing de-anonymization by the holder of the secret
- English and Dutch language support (spaCy `en_core_web_md` and `nl_core_news_md`)
- Dutch BSN recognition with elfproef (11-check) validation

**Text Mode**
- Paste text, anonymize, copy result to clipboard
- Key reference panel showing placeholder → original mapping
- Settings persist between sessions

**Document Mode**
- Single file processing: DOCX, PDF, and Markdown (`.md`)
- Folder processing: recursive, deepest-first, with live progress reporting
- Output prefixes: `ANON_` (PII found), `CHECKED_` (clean)
- Optional key reference file (`KEYREF_`) saved alongside the output
- Optional file and folder name anonymization
- Native OS file/folder picker (Browse… buttons)

**Privacy**
- No network calls, no telemetry, no external services
- All processing runs locally; nothing leaves the machine
- `user_settings.json` (which may contain the hashing secret) is gitignored and never committed

**Launcher**
- `launch.bat` (Windows) and `launch.sh` (macOS/Linux)
- First-run setup is automatic: virtual environment creation, dependency installation, and spaCy model downloads happen on the first double-click

---

_To report a bug or request a feature, open an issue on [Codeberg](https://codeberg.org/d-craig/d-tach/issues)._
