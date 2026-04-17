# Changelog

All notable changes to d-tach are documented here.
Version numbers follow [Semantic Versioning](https://semver.org/): MAJOR.MINOR.PATCH.

- **MAJOR** — significant overhaul or breaking change (rare for a tool like this)
- **MINOR** — new feature or capability added
- **PATCH** — bug fix or small correction

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
