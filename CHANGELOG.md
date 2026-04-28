# Changelog

All notable changes to d-tach are documented here.
Version numbers follow [Semantic Versioning](https://semver.org/): MAJOR.MINOR.PATCH.

- **MAJOR** — significant overhaul or breaking change (rare for a tool like this)
- **MINOR** — new feature or capability added
- **PATCH** — bug fix or small correction

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
