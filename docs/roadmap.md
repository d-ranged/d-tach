# roadmap.md — d-tach Future Development

Issues and ideas for versions after v1.0.0. Items here do not need to be done
in sequence — pick up by priority or contributor interest.

When an item is selected for a release, move it into a versioned step file
(e.g. `step_1.2.0.md`) and create the corresponding Codeberg issues before
starting work.

**When completing any issue that ships a change to users:**
- Decide whether it is a PATCH (bug fix), MINOR (new feature), or MAJOR (overhaul).
- Follow the release process in `original_steps.md` Step 12.
- Add an entry to `CHANGELOG.md` before tagging.
- Update the version badge in `README.md`.

---

## ✅ Shipped in v1.1.0

All steps complete. See `docs/step_1.1.0.md` and `CHANGELOG.md` for detail.
Key additions: bracketed placeholders, d-ranged branding, Excel anonymization,
key reference export, subfolder output mode, consistent hashing for all entity
types, URL detection opt-in, macOS launcher fallback.

---

## Infrastructure: Codeberg storage quota

The free Codeberg plan has a limited LFS/release storage quota. When a packaged
release (PyInstaller) is created, the binary will likely exceed the default limit.
Before publishing a packaged release, apply for additional quota via the Codeberg
Community issue tracker: describe the project, its privacy-first purpose, and the
intended audience (colleagues without Python experience).

---

## Deferred — PDF in-place text replacement (Step 3 attempt, v1.1.0)

**Background:** Attempted in v1.1.0 Step 3 (branch `fix/issue-31-pdf-replacement-font-size`,
Codeberg issue #31). Closed as failed. The pre-Step-3 behaviour (hardcoded `fontsize=11`,
`add_redact_annot` with text arg) was visually superior to all improvements attempted.

**Root cause of the difficulty:** Placeholders like `[NUMERIC_ID_1]` are much longer than
the values they replace (a 6-digit student number). PyMuPDF's `add_redact_annot(rect, text)`
squishes text to fit the original bounding box, producing 4pt output. Blank-then-insert
(`add_redact_annot` with no text + `insert_text` after `apply_redactions()`) avoids
squishing but causes overflow into adjacent content when the placeholder is wider than the
original. Width-scaling with exact font metrics (`fitz.Font("helv").text_length()`) eliminates
overflow in theory but made readability worse on real documents.

**Most promising path forward:**
1. **Shorten placeholder labels** — `[ID_1]` instead of `[NUMERIC_ID_1]`, `[EMAIL_1]`
   instead of `[EMAIL_ADDRESS_1]` etc. Reducing label length narrows the gap between
   original and replacement width. This is a prerequisite for any further PDF work.
   See "Shorten entity type labels" below.
2. **Check pymupdf for a replace-text primitive** — future versions of pymupdf may add
   a first-class text replacement feature that handles reflow internally. Check the
   pymupdf changelog and GitHub releases periodically (every 3–6 months). The project
   is actively developed.
3. **Redact and annotate** — an alternative approach: redact (black out) the original
   text, and insert a visible annotation or stamp marking it as anonymized, rather than
   trying to insert readable replacement text in the same position.

**Periodic check:** Visit https://github.com/pymupdf/PyMuPDF/releases and search for
"replace", "text replacement", or "redact text" in the release notes. If a replace-text
API appears, re-evaluate.

---

## High priority

- **Known Values — user-managed list of names always anonymized**
  ➡️ **Planned for v1.2.0** — see `step_1.2.0.md` Step 2.

  Presidio's NER models are trained predominantly on English and Dutch text and
  consistently miss uncommon names from other language backgrounds. The user needs
  an escape hatch: a persistent list of strings that are always caught regardless
  of whether NER detects them.

  Each entry is stored in `user_settings.json` and converted at runtime to a
  high-confidence (0.99) case-insensitive regex recognizer with entity type PERSON,
  prepended before NER in `_build_ad_hoc_recognizers()`. Hashing applies using the
  PERSON rules when enabled. The list is shared across Text Mode and Document Mode
  and applies to filename anonymization when check_file_names is on.

  UI: collapsible "Known names" panel in the settings bar; text input + Add button;
  entries render as removable tags. Separate API routes handle add and remove with
  immediate persistence.

- **Numeric ID / phone number double-detection overlap**
  When the Numeric ID toggle is active with a digit count that matches a phone number
  length (e.g. 10 or 11 digits), the same number is detected as both NUMERIC_ID and
  PHONE_NUMBER and receives two separate placeholders. The anonymizer currently processes
  whichever entity appears first; the second detection fires on the already-replaced text
  and produces a spurious nested replacement. Fix approach: add an overlap-resolution step
  in Anonymizer that, for the same text span detected by two entity types, keeps the
  higher-confidence detection and discards the lower. Alternatively, expose a "suppress
  phone detection when Numeric ID is active" option for users who know their ID format
  closely resembles a phone number.

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

- **Key reference export — folder mode and improved single-file export**
  - **Folder mode:** consolidated `KEYREF_<folder-name>.csv` at the root of the
    processed folder, listing all placeholder → original mappings across all files.
    Two-column CSV readable by non-technical users in Excel.
  - **Text Mode / single-file mode:** add an explicit **Export** button alongside
    the on-screen key reference table so the user can save it with one click.
    The in-UI table remains; the button is additive.

- **Accuracy review and model upgrade path**
  Evaluate whether `en_core_web_lg` and `nl_core_news_lg` meaningfully improve
  name detection over the medium models. Document the trade-off (download size vs.
  accuracy) and offer the larger models as an opt-in in the installation guide.

- **Organisation name detection review**
  Organisation names are less reliably detected and may or may not be sensitive
  under GDPR depending on context. Assess detection quality after real-world use
  and consider adding a confidence indicator or a review step.

- **Shorten entity type labels in placeholder output**
  Currently placeholder labels use the full Presidio entity type name:
  `[EMAIL_ADDRESS_1]`, `[PHONE_NUMBER_1]`, `[NUMERIC_ID_1]`. In PDF output where
  space is constrained, shorter labels (`[EMAIL_1]`, `[PHONE_1]`, `[ID_1]`) reduce
  the length mismatch between original text and placeholder, improving readability
  of the anonymized document without relying purely on font scaling.
  Decision needed before implementing: shorten labels everywhere (text, DOCX, key
  reference, PDF) for consistency, or only in PDF output via a mapping layer.
  Shortening everywhere is simpler and makes the key reference more readable too;
  PDF-only shortening preserves existing output for other modes but adds complexity.
  Either way this is a visible output change — note it clearly in the release that
  ships it and update the CHANGELOG.

---

## Medium priority

- **De-anonymization / Restore**
  ➡️ **Planned for v1.2.0** — see `step_1.2.0.md`.

  Given a KEYREF CSV and any file containing d-tach placeholders, replace all
  placeholders with their original values. The primary use case is AI-output
  round-tripping: the user anonymizes a document, sends it to an AI tool, and the AI
  returns new content (a letter, feedback report, summary) referencing `[PERSON_1]`
  etc. Restore substitutes real values back into that AI-generated output — the
  original document is never the restore target.

  Supported file types: DOCX, plain text, markdown, Excel.

  **PDF is not supported and not planned.** AI tools return text and markdown, not
  PDFs. The restore use case does not arise for PDFs. The PDF anonymization quality
  research (font-fit) is a separate concern tracked below.

- **Visual highlighting of detected entities in Text Mode**
  Highlight detected PII in the output panel so the user can visually verify what
  was replaced. `Mark.js` is the documented candidate library (see `project_guide.md`).

- **Drag and drop individual file in Document Mode**
  Allow a single file to be dropped onto the Document Mode panel as an alternative
  to typing the path. When dropped, populate the file path field automatically.
  Note: the browser security model means the server still needs the absolute path;
  investigate the File System Access API as the mechanism.

- **Auto-clipboard on anonymization in Text Mode**
  Place the anonymized output in the clipboard automatically when processing
  completes, so the user can paste without clicking the copy button.

- **Browser opens before Flask is ready**
  The launcher scripts open the browser after a fixed delay, which is not always
  long enough for Flask and the spaCy models to finish loading. Replace the fixed
  delay with a poll loop (`curl` on Windows bat, `curl` on shell) that waits until
  port 5000 responds before opening the browser. Already planned for Step 6a in
  `step_1.1.0.md`; log here in case it slips to a later version.

---

## Deferred from v1.1.0 Step 9 acceptance testing

These items were observed during the Step 9 test run but are not blocking release.
They can be picked up as small fixes in v1.1.1 or bundled into v1.2.0.

- **No overwrite warning on repeated folder run**
  When folder processing is run twice against the same folder, existing output files
  (ANON_*, CHECKED_*, or the `anonymized/` subfolder) are silently overwritten.
  The originals are never at risk, so this is low severity. A future improvement
  could detect existing output and prompt or warn before proceeding.

- **Settings bar wrapping in Document Mode**
  When many toggles are active simultaneously (key reference, check names, hashing,
  dates, Numeric ID) the top settings bar can wrap on standard screen widths,
  reducing readability. The URL toggle has been placed in Advanced Settings to reduce
  this, but further consolidation may be worthwhile — e.g. grouping detection options
  (dates, numeric ID) into a single collapsible area.

- **macOS acceptance test**
  The Step 9 macOS test (launch.sh, tkinter fallback, browser auto-open) was skipped
  because no Mac was available. A colleague has been asked to run through the test.
  Result to be added to the Step 9 test record before marking v1.1.0 as fully accepted.

---

## Lower priority

- **Processing architecture review — context efficiency**
  Each AI-assisted development session loads spaCy NLP models and Presidio, which are
  large and slow to initialise. Within a single session this is fine (models load once),
  but multi-session build plans pay the cold-start cost on each new conversation.
  The LFS branch-switching overhead from v1.1.0 is resolved — fixture files are now
  managed cleanly. Remaining improvements: (1) evaluate mock-friendly seams in the
  service layer so code changes can be tested without loading spaCy; (2) group all
  planned issues upfront so a full release can be executed in one session rather than
  reloading context per step (see CLAUDE.md workflow note).

- **UI interface language / internationalisation (i18n)**
  The application interface is currently English-only. The language selection in
  v1.3.0 controls NLP analysis language, not the interface language. If d-tach is
  later distributed to non-English-speaking communities, the interface should be
  translatable. Significant scope — i18n touches every string in every template.
  Better addressed once the app is stable and has real non-English users requesting it.

- **Multi-language architecture — language selectable at install, addable post-install**
  ➡️ **Incorporated into v1.3.0 planning** — see `step_1.3.0.md`, Language Management section.
  The connection to the v1.3.0 tray/background work is that persistent background
  processes make the RAM cost of always-loaded spaCy models concrete: a large model
  is 400–700 MB, and loading languages the user never uses wastes that RAM all day.
  Language management is therefore co-designed with the tray and Settings work.

- **Batch summary log**
  After a folder processing run, save a machine-readable summary log (JSON or CSV)
  to the processed folder listing each file's status, entity count, and output path.

- **Standalone packaged installer (PyInstaller)**
  ➡️ **Planned for v1.4.0** — see `step_1.3.0.md` for the planning note.

  v1.3.0 language management (on-demand model download) unlocks this: the binary
  ships without models, making it small enough (~80–150 MB) to publish on Codeberg's
  free storage tier without a quota increase. Do not start until v1.3.0 is shipped.

  Target audience: users without Python experience who cannot or will not run the
  launcher scripts.
  Known challenges: Flask static file paths under `sys._MEIPASS`, `tkinter` bundling
  on macOS, confirming actual binary size on a clean build.
