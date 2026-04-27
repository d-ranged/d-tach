# d-tach — Project Guide

A locally-run tool for anonymizing personal data from text and documents
before sharing externally for review. Built with GDPR compliance as a core
principle, not an afterthought.

The name d-tach reflects the core purpose: detaching identity from content.

---

## Purpose

When reviewing student or internship documents, staff may wish to use
AI-assisted tools to support feedback and assessment. To do this responsibly,
any personally identifiable information must be removed before content leaves
the machine. d-tach automates that process — locally and transparently — so
that what is shared contains no personal data by definition. Once anonymized,
the content falls outside GDPR scope entirely.

---

## Licence

Published under the **EUPL-1.2 (European Union Public Licence)**.
Created and maintained by the European Commission, legally vetted across all
EU member state legal systems, and compatible with GPL and other major open
source licences.

Full licence text: https://eupl.eu/1.2/en/

---

## Repository

Hosted on **Codeberg** — an EU-based, GDPR-compliant, open source Git platform
run as a non-profit, hosted in Germany.

The repository is kept private during initial development and made public after
Step 9 of the build plan (pre-public review complete, first working increment
verified). See `docs/original_steps.md`.

---

## MoSCoW Requirements

### Must Have

**General**
- Runs entirely locally. No network requests at any point. No text, file
  content, or metadata is transmitted externally. Non-negotiable.
- Two clearly separate modes: Text Mode and Document Mode.
- Supports **English and Dutch** input. Language detection is automatic.
- Anonymization targets only GDPR-sensitive identifiers while preserving
  as much original content, structure, and formatting as possible.
- A single persistent disclaimer shown at the bottom of the UI:
  *"Pattern matching may produce false positives. Review the key reference
  file before sharing anonymized output."*

**Text Mode**
- User pastes text; anonymized result appears immediately alongside the
  original for direct comparison.
- A copy button copies the anonymized output with a single click.
- If Key Reference is enabled, a reference table appears mapping each
  placeholder back to the original value.

**Document Mode**
- User selects a folder. All PDF and DOCX files within it and its
  subfolders are processed.
- Subfolder hierarchy is preserved in output — structure mirrors the
  original, only names change where PII is detected.
- Output files saved to the same location as originals.
- Every processed file receives a prefix:
  - PII detected and removed: `ANON_` prefix
  - No PII detected: `CHECKED_` prefix (content unchanged, renamed to
    confirm it was processed)
- Processing is file by file, completing each before starting the next.
  A corrupt file is logged and skipped without stopping the batch.
- UI shows progress: current file N of total M.
- Completion summary shown after batch: anonymized / clean / skipped counts.
- If Key Reference is enabled, a `KEYREF_` file is saved alongside each
  anonymized output.

**Key Reference Feature**
- Optional toggle, off by default.
- When enabled, produces a reference record mapping each placeholder to
  the original value it replaced.
- Stored locally only, never transmitted.
- When disabled, anonymization is fully one-way.

**Hashing Feature**
- Optional toggle, off by default.
- The toggle and secret input field appear together — ticking the toggle
  opens the secret field immediately alongside it.
- A secret must be entered before hashing can proceed. Processing is
  blocked with a clear message if the toggle is on but no secret is entered.
- First name rule: first 2 characters preserved exactly, remainder hashed
  to exactly 4 uppercase alphanumeric characters.
  Example: Craig → Cr-A2T5
- Last name rule: full name hashed to exactly 4 uppercase alphanumeric
  characters.
  Example: Bradley → HY23
- First and last names always hashed separately so a first name appearing
  alone (e.g. in a folder name) resolves to the same output.
- Same name + same secret always produces the same output across sessions.
- When hashing is off, sequential placeholders are used: PERSON_1, PERSON_2.
- Hashing toggle state and secret are persisted and restored on next launch.
- The secret does not need to meet password complexity requirements. This
  is a convenience and consistency feature, not a cryptographic security
  system. The application should be kept in a secure location.

**File and Folder Name Checking**
- Toggle to enable checking and renaming of file and folder names.
- Same hash logic applied to names found in file and folder names.
- Folder renaming happens after all file content within is fully processed.
- Processing order: files deepest-first, then folders deepest-first.

**Custom Pattern Detection**
- Student number detection: user selects an exact digit count N.
- Match rule: exactly N consecutive digits with a non-digit (or string
  boundary) on each side and no currency symbol (€, $, £) immediately before.

---

### Should Have

- Drag and drop of an individual file as an alternative to folder selection.
  When a single file is dropped, its source folder is used as the output
  location.
- Anonymized output in Text Mode automatically placed in clipboard on
  generation so user can paste without clicking copy.

---

### Could Have

- Visual highlighting of detected PII in Text Mode output. Noted here as it
  may influence frontend library choices. Not required in initial development.
- Batch summary log saved to the processed folder after Document Mode run.

---

### Won't Have (initial release)

- Any cloud processing, storage, or synchronisation.
- Support for file formats other than PDF and DOCX.
- Direct API connection to external tools. Output is always a clean local
  file or text which the user shares manually.

---

## Detected PII Categories

| Category | Examples | Notes |
|---|---|---|
| Full names | Student, supervisor | English and Dutch; hashed separately |
| Email addresses | Personal, institutional | Pattern matching |
| Phone numbers | Mobile, landline | Including Dutch formats |
| Physical addresses | Home, company | |
| Organisation names | Internship company | Less reliable; may need review |
| Student numbers | Saxion-format IDs | Custom Presidio rule; user-configured digit count |
| URLs / social profiles | LinkedIn, portfolio | Configurable |
| Dates of birth | Where present | |
| National ID / BSN | Dutch citizen service number | Pattern matching |

> **On organisation names:** GDPR applies to natural persons, not companies.
> However a company name combined with a supervisor name may together identify
> an individual. Recommended approach: anonymize both and retain the mapping
> in the Key Reference file if local context needs to be preserved.

---

## Tooling

All choices below are confirmed for initial development. Alternatives are
noted for reference if a blocker is encountered during build.

| Tool | Role | Status | Reasoning |
|---|---|---|---|
| Python 3.11+ | Primary language | **Confirmed** | Strongest ecosystem for PII detection and document processing. |
| Flask | Web framework | **Confirmed** | Full frontend control. Supports folder selection, drag and drop, and text highlighting — features Streamlit cannot handle. |
| Microsoft Presidio | PII detection engine | **Confirmed** | Built on spaCy; structured multi-category detection; produces entity mapping for Key Reference. |
| spaCy | NLP models | **Confirmed** | `en_core_web_md` (English) and `nl_core_news_md` (Dutch). Both required. |
| pymupdf (fitz) | PDF processing | **Confirmed** | Read and write. Redaction API allows in-place text replacement preserving layout. pdfplumber is read-only and unsuitable. |
| python-docx | DOCX processing | **Confirmed** | Standard library for DOCX read/write. No viable alternative needed. |
| Vanilla JS | Frontend interaction | **Confirmed** | Clipboard API, drag and drop, folder input all natively available. No framework needed. |
| scrubadub | Alternative PII library | **Alternative** | Lighter than Presidio. Fallback if Presidio setup proves problematic. Does not natively produce entity mapping. |
| Mark.js | Text highlighting | **Noted for later** | JS library for UI highlighting. Relevant only if visual highlighting (Could Have) is implemented. |

### PDF Preservation Note

pymupdf redaction is the best available approach for in-place PDF anonymization.
If layout preservation proves unacceptable during Step 7, the documented
fallback is to output an anonymized DOCX or plain text version alongside the
original PDF with a clear note to the user. This decision must be recorded
here if the fallback is taken.

---

## Open Questions

- **PDF output quality:** To be assessed during Step 7. Fallback to DOCX
  output if pymupdf redaction does not preserve layout acceptably.
- **Organisation name detection reliability:** To be assessed during Step 3
  testing. May require a confidence indicator or manual review step.
- **Saxion institutional policy:** Worth confirming before making the
  repository public, particularly if shared with colleagues.

---

*Last updated: April 2026*
