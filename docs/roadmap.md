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

## Planned for v1.1.0

See `docs/step_1.1.0.md` for the full step-by-step build plan for this release.

- **change: standardise placeholder format to [PLACEHOLDER]** — See `step_1.1.0.md` Step 1.
- **feature: d-ranged branding and two-theme toggle** — See `step_1.1.0.md` Step 2.
- ~~**fix: PDF replacement text font size and readability**~~ — **Dropped.** Step 3 failed; reverted. See `step_1.1.0.md` Step 3 and ROADMAP section below.
- **feature: Excel file (.xlsx) anonymization** — See `step_1.1.0.md` Step 4.
- **feature: Key reference export improvements** — See `step_1.1.0.md` Step 5.
- **fix: Launcher UX and macOS tkinter fallback** — See `step_1.1.0.md` Step 6.
- **feature: anonymized subfolder output mode** — See `step_1.1.0.md` Step 7.

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

- **De-anonymization (reverse lookup)**
  Given a KEYREF CSV export and an anonymized file, replace all placeholders back
  with the original values, producing a de-anonymized document.

  - Supported file types: DOCX and plain text. **Not PDF** — redaction is structurally
    destructive and cannot be reversed.
  - User flow: upload the KEYREF CSV → upload the anonymized file → download the
    de-anonymized output.
  - Placeholder format must match the KEYREF (works correctly after Step 1 standardises
    the `[PLACEHOLDER]` format).
  - Implementation approach: simple find-and-replace on all `[PLACEHOLDER_N]` tokens
    using the CSV mapping; no NLP required.
  - Earliest version: v1.2.0 or later. Do not start until v1.1.0 is shipped.

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
  As the codebase has grown, each development session loads the full spaCy NLP models
  and Presidio engine, which are large and slow to initialise. Within a single session
  this is fine (models load once). But repeated context-window sessions (e.g. multi-step
  build plans over multiple days) pay the cold-start cost on each new conversation.
  Potential improvements: (1) document the startup cost prominently so AI-assisted
  development sessions front-load model-related work; (2) evaluate whether any of the
  service layer can be decoupled further so code changes can be tested without loading
  spaCy (mock-friendly seams); (3) investigate whether LFS fetch behaviour can be
  contained — LFS objects being pulled unexpectedly during branch switches added
  significant overhead in v1.1.0 development.

- **Multi-language architecture — language selectable at install, addable post-install**
  Currently d-tach supports EN and NL only, both baked in. A more extensible
  approach would let users select the active language(s) during first-run setup
  (spaCy model downloaded at that point rather than always both), and add further
  languages post-install via a CLI command or in-app settings panel.

  Key design questions to resolve before starting:
  - Is the install-time selection worth the complexity? Most users will want both
    EN and NL. A simpler alternative: ship EN + NL always, make adding a third
    language a documented manual step.
  - Language packages: each language requires a spaCy model download and
    potentially custom Presidio recognizer rules for local PII formats (e.g.
    German Personalausweis, French NIR). Scope carefully.
  - UI impact: the language selector currently has two fixed options. A dynamic
    list driven by installed models requires a model discovery utility.

  Suggested approach: build a `LanguageRegistry` class that scans installed spaCy
  models and exposes only languages that have both a model and a Presidio
  recognizer set. Adding a language = adding a model + a recognizer module +
  registering it.

  **Earliest version:** v1.2.0. Do not start until v1.1.0 is shipped.

- **Batch summary log**
  After a folder processing run, save a machine-readable summary log (JSON or CSV)
  to the processed folder listing each file's status, entity count, and output path.

- **Standalone packaged installer (PyInstaller)**
  Use PyInstaller to produce a single-folder distribution that includes the Python
  interpreter, all dependencies, and the spaCy models. Target audience: colleagues
  without Python experience who cannot or will not run the launcher scripts.
  Known challenges: spaCy model size, Flask static file paths under
  `sys._MEIPASS`, and `tkinter` bundling on macOS. Investigate once the app is
  stable post-public.
