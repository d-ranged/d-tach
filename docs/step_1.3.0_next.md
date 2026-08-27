# step_1.3.0_next.md — d-tach v1.3.0 Build Plan

This document breaks the v1.3.0 planned work into ordered, testable steps.
Each step should map to one or more Codeberg issues created before starting.

Consult `roadmap.md` for background context.
Consult `project_guide.md` for architectural decisions and documented alternatives.

---

## Status at a Glance

| Step | Description | Status |
|---|---|---|
| 1 | System tray app + configurable port | ✅ Complete |
| 2 | Language management — on-demand download, first-launch selection | ✅ Complete (not human-tested) |
| 3 | Fix double-anonymization of already-anonymized text | ✅ Complete |
| 4 | Class list import — bulk-populate known values from a roster file | ✅ Complete |
| 5 | AI Mode — filename-only rename prerequisite + local API for AI-assisted anonymize/restore | ✅ Complete |
| 6 | Acceptance Testing — real-work run through the finished feature set | ✅ Complete |

Acceptance testing moved from position 3 to position 6 (24-8-2026). It is no longer a
self-administered feature checklist run against test data — it is a real piece of the
tester's own work, done end to end through the finished feature set. That only works once
every step is in, so it goes last. See Step 6.

Step 6 closed 25-8-2026. The real task was a MoMi retroactive-absence warning letter,
built end to end through AI Mode from two real source documents. No student name,
surname or student number reached the assistant's context at any point in the run — the
tester confirmed this independently. Three defects were found and fixed inside this step
rather than deferred (rows 10-12 below); see the defect log below for the full list of
twelve. One completeness criterion — a roster/known-values entry catching a name that NER
missed — was not separately exercised in this run, since the real task didn't produce
that case; noted here rather than silently checked off.

---

## Background

v1.3.0 is an infrastructure release. It does three tightly coupled things:

1. **Tray app** — d-tach becomes a persistent background process rather than something
   you launch and close each session
2. **Configurable port** — users can change the port d-tach listens on from within the
   Settings panel; needed before distribution to diverse environments
3. **Language management** — users choose which spaCy language models to download and
   load; directly motivated by the tray work, since persistent background processes make
   the RAM cost of always-loaded models concrete

These three are designed together. Building tray without language management would mean
a background process always holding full RAM for models the user may never need.

**What this unlocks for v1.4.0:** because languages are now downloaded on demand rather
than bundled, a PyInstaller package can ship without models. The package binary
(Python runtime + Flask + Presidio + app code, no models) is likely 80–150 MB —
small enough to publish on Codeberg without a storage quota increase. v1.4.0 is
therefore a packaging/installer release that becomes feasible only after v1.3.0 ships.

---

## <Completed> Step 1 — System Tray App + Configurable Port COMPLETED </completed>



**Codeberg issue created:**
`d-ranged/d-tach#60`

### Port decision

Default port changes from **5000 → 5555**.

5000 is Flask's default and conflicts if any other Flask project is open simultaneously.
5555 has no meaningful Windows conflicts. The port is also user-configurable (see below).

### System tray app

**Goal:** d-tach runs as a persistent background process on login. A system tray icon
gives the user a visible handle on it — no need to know what a Flask server is.

**Libraries:** `pystray` (tray icon) + `Pillow` (required by pystray for image handling).
Both are pure Python and pip-installable. Add to `requirements.txt`.

**Behaviour:**

- On launch, start the Flask server in a background thread
- Display a tray icon using the d-ranged logo
- Right-click menu (minimum):
  - **Open d-tach** — opens `http://localhost:{port}` in the default browser
  - **Quit** — stops the Flask server and exits the tray process
- Single-click on the icon: open the browser (same as "Open d-tach")
- If the port is already in use on launch: show a system notification
  ("d-tach could not start — port {port} is in use") and exit cleanly

**Startup registration:**

The tray app should offer to register itself as a Windows startup program
(write a registry entry under `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`).
This should be a one-time prompt on first launch, not automatic.
On macOS, the equivalent is a LaunchAgent plist.

**Entry point:**

New file `tray.py` at the project root. This becomes the file users run
(or the executable users double-click if we later build with PyInstaller).
`run.py` and `serve.py` remain for development use.

### Configurable port

**Goal:** Users can choose which port d-tach listens on. Needed because power users
may already have something on 5555, and institutions may have firewall constraints.

**Design:**

- Default: `5555`
- Configurable via `UserSettings` — persisted alongside other settings
- Exposed in a new **Settings** panel within the existing UI (not a launch-time flag)
- Changing the port shows: "Restart d-tach to apply the new port" — no hot reload
- The tray icon's "Open d-tach" action reads the current configured port from
  `UserSettings` so the browser link stays correct after a port change

**`run.py` and `serve.py`:**

Both should read port from `UserSettings` (or an environment variable fallback
`DTACH_PORT`) so that development runs also respect the configured port.

### What to build

| Component | Description |
|---|---|
| `tray.py` | New entry point; starts Flask in thread; manages tray icon lifecycle |
| `UserSettings` | Add `port: int = 5555` field; persist and restore |
| Settings UI — Port | Port input; "Restart to apply" notice on change |
| `requirements.txt` | Add `pystray` and `Pillow` |
| `launch.bat` / `launch.sh` | Update to launch `tray.py` instead of (or alongside) `run.py` |
| `serve.py` | Update to read port from `UserSettings` or `DTACH_PORT` env var |
| `README.md` | Update installation section to describe tray app as the normal launch path |
| `text_routes.py` | Accept `?q=` URL parameter to pre-fill text mode input (see below) |

### URL parameter — pre-fill text mode from external tools

**Goal:** `GET /text?q=some+text+here` opens text mode with the input pre-filled.
This enables OS-level keyboard shortcuts (and future browser extensions) to send
clipboard content directly into d-tach without manual paste.

**What to build:**

- In the `GET /text` route, read `request.args.get('q', '')` and pass it to the template
- In `text_mode.html`, set the textarea value from the template variable if present
- No authentication or length limit beyond what the browser URL supports — this is
  local-only, the same trust boundary as the rest of the app

**Cross-platform OS shortcut setup (document in README):**

These are personal automation scripts — not bundled with d-tach. Document the approach
in README so users know it is possible. The shortcut key combination does not matter;
suggested defaults are listed below.

**Windows** — PowerShell + native shortcut file, no keyboard listener:
```powershell
# d-anonymize.ps1
$text    = Get-Clipboard
if (-not $text -or $text.Trim() -eq "") { exit }
$encoded = [System.Uri]::EscapeDataString($text)
Start-Process "http://localhost:5555/text?q=$encoded"
```
Create a `.lnk` shortcut pointing to:
`powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File "path\to\d-anonymize.ps1"`
Assign shortcut key `Ctrl+Alt+A` via the shortcut's Properties dialog.
Place the shortcut on the Desktop or in the Start Menu folder for the hotkey to work
system-wide. No background process required.

**macOS** — shell script + System Preferences keyboard shortcut:
```bash
#!/bin/bash
# d-anonymize.sh
TEXT=$(pbpaste)
[ -z "$TEXT" ] && exit
ENCODED=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.stdin.read()))" <<< "$TEXT")
open "http://localhost:5555/text?q=$ENCODED"
```
`chmod +x d-anonymize.sh`, then assign a shortcut in:
System Preferences → Keyboard → Shortcuts → App Shortcuts (or use Automator Quick Action
for a right-click Services menu entry instead of a keyboard shortcut).

**Linux** — shell script + desktop environment shortcut:
```bash
#!/bin/bash
# d-anonymize.sh
# Wayland
if command -v wl-paste &>/dev/null; then
    TEXT=$(wl-paste)
else
    TEXT=$(xclip -selection clipboard -o 2>/dev/null)
fi
[ -z "$TEXT" ] && exit
ENCODED=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.stdin.read()))" <<< "$TEXT")
xdg-open "http://localhost:5555/text?q=$ENCODED"
```
Assign the shortcut via GNOME Settings → Keyboard → Custom Shortcuts,
or KDE System Settings → Shortcuts → Custom Shortcuts.

### Automated shortcut setup — first-run opt-in (design note)

The OS shortcut scripts above could be created automatically during first run of the
tray app, with user permission. This fits the existing first-run prompt pattern (startup
registration question) rather than the installer.

**Proposed prompt on first tray launch:**

> "Would you like to set up a keyboard shortcut to send clipboard text to d-tach?
> This creates a small script on your machine and registers Ctrl+Alt+A as a system shortcut."
> [Set up]  [Skip]  [Show me what it creates]

"Show me what it creates" must be available — transparency principle; user sees the exact
files and system change before agreeing.

**Platform feasibility:**

| Platform | Script creation | Shortcut registration |
|---|---|---|
| Windows | ✅ trivial | ✅ via COM / pywin32 — reliable |
| macOS | ✅ trivial | 🟡 keyboard shortcut plist is fragile; Automator `.workflow` in `~/Library/Services/` is more reliable but user still assigns the key manually |
| Linux | ✅ trivial | 🟠 GNOME via `gsettings`, KDE via config file; other DEs fall back to manual instructions |

**Fallback for all platforms:** if automated registration is not possible or the user
skips, show the manual setup steps from the README.

This feature can be added to the tray first-run flow in the same step as startup
registration — scope it together rather than as a separate issue.

---

### ✅ Complete when

- Running `tray.py` starts the server and shows a tray icon
- Tray icon right-click: "Open d-tach" opens the browser; "Quit" exits cleanly
- Port can be changed in the Settings panel; restart notice shown
- After restart, the new port is used and the tray icon opens the correct URL
- `launch.bat` launches the tray app
- `serve.py` and `run.py` still work independently for dev use
- `GET /text?q=hello` opens text mode with "hello" pre-filled in the input
- `GET /text` (no parameter) opens text mode with empty input — existing behaviour unchanged
- README documents the OS shortcut approach for Windows, macOS, and Linux
- All existing tests pass

---

## <completed>Step 2 — Language Management: Completed, un human tested</completed>

**Codeberg issue:**
`d-ranged/d-tach#62`

### Why this is in v1.3.0 and not later

When d-tach runs as a persistent background process, the spaCy models loaded at startup
remain in memory for the lifetime of the process. A spaCy large model is typically
400–700 MB. Loading models for languages the user never processes wastes that RAM all day.

Language management is co-designed with the tray app — they are not independent features.

**Secondary benefit:** with languages downloaded on demand rather than bundled, a future
PyInstaller package can ship without models, making the downloadable binary small enough
to publish on Codeberg's free tier. See v1.4.0 planning note at the bottom of this file.

### Three states to distinguish

| State | Meaning | Where it lives |
|---|---|---|
| Supported | d-tach has recognizer rules for this language | Built into the codebase |
| Installed | The spaCy model is downloaded on this machine | Disk (~200–700 MB per language) |
| Loaded | The model is in RAM for the current session | Memory (~200–700 MB per language) |

All three states must be independently visible and manageable from the Settings panel.

### Loading strategy

| Strategy | Behaviour | Best for |
|---|---|---|
| Eager | All enabled models loaded at startup (current behaviour) | 1–2 languages; consistent latency |
| Lazy | Model loaded on first document in that language | Background/tray mode; lower idle RAM |

Default: **Eager** (preserves current behaviour). On first run in tray mode with more than
one language installed, the UI suggests switching to Lazy — one-time prompt, dismissible,
not blocking.

### First-launch language selection

On first launch (no `UserSettings` found), show a language selection screen before the
main UI loads:

- List each supported language with a checkbox and approximate model download size
- English is pre-selected
- The label reads: **"Language of documents to process"** — explicit that this is the
  NLP analysis language, not the application interface language
- User confirms and selected models are downloaded before the app opens

This replaces the current always-download-both approach and gives the user deliberate
control from the start.

**Note — UI interface language:** The application interface is English-only. The language
selection above controls which language d-tach analyses documents in, not the interface
language. This is a known limitation. If d-tach is later distributed to non-English-speaking
communities, interface internationalisation (i18n) should be scoped as a separate feature.
See `roadmap.md` for the tracking item.

### Settings panel — Languages section

The Settings panel gains a Languages section:

- For each supported language: name, locale code, status badge (Installed / Not installed)
- For installed languages: a **Load on startup** checkbox
- **Install** button (not installed) or **Remove** button (installed)
- **Loading strategy** toggle: Eager / Lazy, with a one-line RAM implication beneath it

Installing a language triggers `python -m spacy download <model>` as a background
subprocess. Progress shown inline. Completion message:
"Dutch installed. Restart d-tach to enable it."

Removing a language removes the model from disk. Completion message:
"Dutch removed. Restart d-tach to apply."

Changing the enabled/disabled state of an already-installed language shows:
"Restart d-tach to apply language changes."

All restart notices follow the same pattern as port changes — informational only,
no blocking.

### `LanguageRegistry` (new class)

Central registry for all language support in the application. Responsibilities:

- Enumerate supported languages — those with both a spaCy model name and a Presidio
  recognizer set defined in the codebase
- Check whether a given language's model is installed on disk
- Report which models are currently loaded in the session
- Trigger model download (`python -m spacy download`) and track subprocess progress
- Trigger model removal (pip uninstall of the spaCy model package)

All language-state decisions go through `LanguageRegistry`. No other class inspects
spaCy model availability directly.

### `LanguageDetector` update

Currently assumes both EN and NL models are always loaded. After this change:

- Before routing to a model, check `LanguageRegistry` whether it is loaded
- If not loaded (eager mode): surface a clear error. UI message:
  "Dutch detected but Dutch model is not enabled.
  Enable it in Settings > Languages and restart d-tach."
- If not loaded (lazy mode): `LanguageDetector` triggers a load via `LanguageRegistry`,
  waits, then routes. One-time latency per language per session; transparent to the user.

### `UserSettings` additions

- `enabled_languages: list[str]` — e.g. `["en", "nl"]` — which installed models
  load on startup
- `loading_strategy: Literal["eager", "lazy"]` — default `"eager"`

### What to build

| Component | Description |
|---|---|
| `LanguageRegistry` | New class; manages supported/installed/loaded language states |
| `LanguageDetector` | Update to consult `LanguageRegistry`; handle missing models gracefully |
| `UserSettings` | Add `enabled_languages` and `loading_strategy` fields |
| Settings UI — Languages | Install/remove/enable controls per language; loading strategy toggle |
| First-launch setup | Language selection screen on first run; downloads selected models before opening |

### ✅ Complete when

- First launch shows language selection screen with download sizes; selected models
  downloaded before app opens
- Settings > Languages shows correct Installed / Not installed status per language
- Installing a language from Settings shows progress; completion message shown
- Removing a language removes it from disk after restart
- Load on startup checkbox persists; only enabled models loaded on next start
- Lazy loading: model not in RAM at startup; loads on first document in that language
- If document language detected but model not loaded: clear UI error message shown
- All existing tests pass

---

## <completed>Step 3 — Fix Double-Anonymization of Already-Anonymized Text</completed>

**Codeberg issue:**
`d-ranged/d-tach#64`

### Why this must be fixed here, not just logged

AI Mode (Step 5) depends on round-tripping text through `anonymize()` and `restore_string()`
correctly within a session. If a placeholder ever gets wrapped a second time
(`[[PERSON_1]_1]` or a hashed placeholder re-tagged as a new PERSON), `restore_string()`'s
exact-match dictionary lookup silently fails to unwrap the outer layer — the AI-mode user
gets a final document with a literal bracket-soup placeholder still in it instead of a name.
This is worse in AI Mode than in Text/Document mode today, because AI Mode is specifically
sold on "no more manual re-matching" — a silent restore failure undermines that. Fix it
before Step 5 ships, not after.

### Root cause

`Anonymizer.anonymize()` (`app/services/anonymizer.py`) runs spaCy NER and the pattern
recognizers over whatever text it's given, with no awareness of d-tach's own placeholder
syntax. If the input text already contains a sequential placeholder (`[PERSON_1]`,
`[EMAIL_ADDRESS_1]`) or a hashed placeholder (`[Cr-A2T5 HY23]`, `[EMAIL_A2B3]`), nothing
stops NER or a pattern recognizer from matching that bracketed text again — most often
spaCy tagging a hashed placeholder's letters-and-digits as a new PERSON, since it looks
like a short proper-noun token.

### Fix

Add a placeholder-recognition guard in `anonymize()`, after the existing
`results = [r for r in results if r.entity_type in active_set]` filter
(`app/services/anonymizer.py` around line 200):

- Add a module-level regex `PLACEHOLDER_PATTERN` matching both placeholder shapes d-tach
  produces:
  - Sequential: `\[[A-Z_]+_\d+\]` (e.g. `[PERSON_1]`, `[NUMERIC_ID_3]`)
  - Hashed: `\[[A-Za-z]{0,2}-?[A-Z0-9]{4}(?:\s[A-Z0-9]{4})?\]` (e.g. `[Cr-A2T5 HY23]`,
    `[EMAIL_A2B3]`) — match against the actual `HashEncoder` output format, not just this
    approximation; confirm exact shape from `hash_encoder.py` before finalizing the regex.
- Filter `results` to drop any entity whose `text[r.start:r.end]` fully matches
  `PLACEHOLDER_PATTERN` — these spans are already-anonymized and must pass through
  untouched rather than being re-detected.
- This is a pure detection-time guard; it does not change placeholder format, hashing, or
  any existing output for text that has no pre-existing placeholders in it (the common
  case today), so it should not be visible as a behaviour change for Text/Document mode
  on first-time anonymization.

### What to build

| Component | Description |
|---|---|
| `app/services/anonymizer.py` | Add `PLACEHOLDER_PATTERN` regex; filter already-anonymized spans out of `results` before placeholder assignment |
| `tests/test_anonymizer.py` | New cases: re-running `anonymize()` on already-anonymized text (sequential and hashed forms) leaves it unchanged; mixed text (one real name + one existing placeholder) anonymizes only the real name |

### ✅ Complete when

- Running `anonymize()` twice on the same input is idempotent: second pass produces
  identical output to the first (no nested brackets)
- A hashed placeholder (`[Cr-A2T5 HY23]`) is never re-tagged as a new PERSON
- Mixed input (one new name + one existing placeholder) anonymizes only the new name and
  leaves the existing placeholder untouched
- All existing Text/Document/Restore mode tests still pass — no behaviour change for
  text with no pre-existing placeholders
- `pytest` passes with no failures

---

## <completed>Step 4 — Class List Import</completed>

**Codeberg issue to create first:**
`d-ranged/d-tach#66`

### Background

The "known values" list (`UserSettings.known_values`, shipped v1.2.0) lets a user add
specific names that should always be anonymized, regardless of NER confidence —
important for names the spaCy models miss. Today these are added one at a time by typing
each name into the Settings UI. For a class of 20–30 students this is slow and easy to
get wrong (a typo means that student's name is never reliably caught).

Most teaching staff already have a class list / attendance register as an Excel file
with columns like student number, first name, last name. d-tach already has Excel
reading via `openpyxl` (`document_processor.py`). This step lets the user point at that
file once, pick which columns matter, and bulk-populate known values from every row —
making every student in the class a guaranteed-caught known value on the very first
anonymization pass, not just after a miss is noticed.

This is scoped before AI Mode (Step 5) because AI Mode's safety story depends on
anonymization being as complete as possible *before* any text reaches a cloud model —
this closes a real, common gap (a full roster of names) ahead of that, the same way
Step 3 closes the round-trip-integrity gap ahead of it.

### Schema change — typed known values

Different columns need different entity types: a name column should anonymize as
`PERSON`; a student number column should anonymize as `NUMERIC_ID` (correct placeholder
label, and safe even if the existing digit-count Numeric ID setting doesn't match the ID
format on that particular roster). This requires `known_values` to carry a type per
entry instead of being a flat list of PERSON-only strings.

- `UserSettings.known_values` changes from `list[str]` to `list[dict]`, each entry
  `{"value": str, "entity_type": str, "source": "manual" | "class_list"}`.
- **Migration:** on load, any existing plain-string entries are wrapped as
  `{"value": v, "entity_type": "PERSON", "source": "manual"}`. Follows the same pattern
  already used in `PatternConfig.from_dict` for its old-key migration
  (`pattern_config.py`) — load old format, normalize to new, save in new format from
  then on.
- `build_known_value_recognizers` (`anonymizer.py`) reads `entity_type` per entry instead
  of hardcoding `PERSON`.
- The `source` tag lets a "Clear class list values" action remove only imported entries
  without touching manually-added ones.

### One remembered class list, not many

Support exactly one current class-list source, not a managed collection of multiple
lists — matches the existing single-flat-list simplicity of known_values and avoids
the UI complexity of tracking which list contributed which names.

- `UserSettings` additions: `class_list_path: str`, `class_list_column_mapping: dict[str, str]`
  (header name → entity type, e.g. `{"stNum": "NUMERIC_ID", "First Name": "PERSON", "Last Name": "PERSON"}`).
- Settings UI shows the remembered file path and column mapping (if any) with a
  **Re-sync** button — re-reads the same file with the same mapping and adds any new
  rows. Useful when a roster gains late enrollments without re-doing the column picker.
- Pointing at a *different* file overwrites the remembered path/mapping — explicitly
  one current list, not an accumulating set.

### Workflow

1. Settings → Known Values gains an **Import from class list** sub-panel with a file
   browse button (reuses the existing `/browse/file` backend).
2. On selecting an `.xlsx` file, the UI calls a new endpoint to read just the header row
   and returns the column names.
3. For each column, the UI offers a type dropdown: **Ignore** (default for
   unrecognized headers) / **Person name** / **Numeric ID** / **Email**. Header text is
   used to pre-guess a sensible default (e.g. a header containing "name" suggests
   Person name, "number" or "id" suggests Numeric ID) — the user confirms or overrides
   before importing, nothing is auto-applied silently.
4. **Import** reads every row, pulls cell values from the mapped columns, normalizes
   (trim whitespace, skip blanks), dedupes case-insensitively against existing
   `known_values` (regardless of source), and adds the new ones tagged
   `source: "class_list"`. Returns a count: added / already-present / total.
5. The file path and column mapping are saved so **Re-sync** can repeat the same import
   later without re-picking columns.

### New endpoints — `app/routes/settings_routes.py`

| Endpoint | Method | Request | Response |
|---|---|---|---|
| `/settings/known-values/class-list/columns` | POST | `{file_path}` | `{columns: [str, ...]}` — header row only, no row data read yet |
| `/settings/known-values/class-list/import` | POST | `{file_path, column_mapping: {header: entity_type}}` | `{added, already_present, total_known_values}` |
| `/settings/known-values/class-list/clear` | DELETE | — | Removes all `source: "class_list"` entries; manual entries untouched |

Reuses `openpyxl` loading already present via `document_processor.load_xlsx` — no new
Excel dependency.

### What to build

| Component | Description |
|---|---|
| `user_settings.py` | Migrate `known_values` to typed entries; add `class_list_path`, `class_list_column_mapping` |
| `anonymizer.py` | `build_known_value_recognizers` reads `entity_type` per entry |
| `app/routes/settings_routes.py` | New class-list columns/import/clear endpoints |
| Settings UI — Known Values | Import sub-panel: file browse, column type dropdowns, Import button, remembered path + Re-sync button, Clear class list values button |
| `static/js/known_values.js` | Extend to render typed entries and the new import sub-panel |

### ✅ Complete when

- Existing plain-string `known_values` from before this change load correctly as
  `PERSON`-typed entries after migration (no data loss on upgrade)
- Pointing at a real class-list `.xlsx` returns its header row for column mapping
- Importing with a mapping (e.g. stNum → Numeric ID, First/Last Name → Person name) adds
  one typed entry per unique value per row, skipping duplicates already in the list
- Imported `NUMERIC_ID` entries anonymize with `[NUMERIC_ID_N]`, not `[PERSON_N]`
- Re-sync against the same file with new rows added only adds the new rows, not
  duplicates of existing ones
- "Clear class list values" removes only `source: "class_list"` entries; manually-added
  names remain
- All existing known-values tests pass with the new schema; new tests cover migration,
  import, dedup, and clear
- `pytest` passes with no failures

---

## <completed>Step 5 — AI Mode</completed>

**Codeberg issue:**
`d-ranged/d-tach#68`

### Background

Today, getting an AI assistant to analyze a sensitive document means a manual round
trip: anonymize a file in Document Mode → paste the anonymized text/KEYREF into the
AI conversation → get feedback back referencing placeholders → manually re-match those
placeholders to real names using the KEYREF file. Re-pasting placeholder ↔ name mappings
back into output by hand is slow and risks mismatches, and anonymization sometimes misses
values embedded in images with no tight feedback loop to fix the miss going forward.

d-tach already does text extraction (PDF/DOCX/XLSX/MD) and already has a `restore_text`
placeholder-substitution primitive (`document_processor.py`) and a persisted "always
anonymize this" list (`UserSettings.known_values`, shipped v1.2.0). AI Mode exposes these
as a small local API so an AI agent (e.g. Claude Code) calls d-tach directly instead of a
human manually copying text back and forth — cutting out the re-matching step entirely
while keeping the same trust boundary: **anonymization always happens locally, before any
text reaches a cloud model.**

**Single-tree design — this is the point of AI Mode, not a detail of it.** Earlier
anonymization workflows (Document Mode's `anonymized/` mirror) create a second folder tree
that has to be kept in sync with the original and cross-referenced back against the source
system (e.g. BrightSpace) by hand — this round trip between two trees is exactly the
friction AI Mode exists to remove. AI Mode assumes **one** folder, containing the user's
real files exactly as downloaded, with **only the file and folder names** anonymized
in place. File *content* is never rewritten to disk — it stays real, and is anonymized
only in-flight, per file, when the AI agent requests it through the API below. This is why
the filename/folder-only rename (see Prerequisite, below) has to exist before AI Mode is
usable: without it, an agent enumerating the tree to decide what to read next would see
real names in the paths themselves, which defeats the entire point of anonymizing the
content.

This step does not depend on Steps 1–2 (tray, language management) and could be built
alongside them. It does depend on Steps 3 and 4 landing first: they close the
round-trip-integrity gap and the roster gap that AI Mode's safety story rests on.
Step 6 then tests all of it together on real work.

### Prerequisite — Filename/Folder-Only Anonymization

**Goal:** anonymize every file and folder *name* in a tree, in place, without touching any
file's content and without producing a second copy of the tree.

This reuses the exact hash-rename logic already shipped for `check_file_names` in Document
Mode (see `step_1.1.0_completed.md`) — the new part is exposing it as a standalone action
that skips content extraction/anonymization entirely, rather than always running alongside
a full Document Mode pass.

**UI:** a new option in Document Mode's folder picker (or its own entry point): **"Rename
names only — don't touch file content."** When selected:

- File and folder names are checked against NER + `known_values` (same detection as
  content mode) and renamed **in place** using the existing hash/sequential placeholder
  logic — no `anonymized/` output folder is created, no file is opened for content
  rewriting.
- Processing order matches the existing rule: files deepest-first, then folders
  deepest-first (so a folder isn't renamed out from under files still being processed).
- The KEYREF export (if enabled) still applies — it is the only artifact needed to map a
  renamed path back to the real one, and only the human user (not the AI agent) reads it.

**Typical use:** a user downloads a whole folder of real submissions as-is (e.g. from
BrightSpace, which itself embeds real names in exported folder names) into one working
folder, runs this rename-only pass once over that folder before ever pointing an AI agent
at it, and from then on the tree's paths are safe to enumerate.

### Workflow

1. The AI agent lists the (already name-anonymized) folder tree itself — normal directory
   listing is safe now, because Step-6's prerequisite means no real name appears in any
   path. The agent **never reads file content directly** (no local file-read call) for any
   file inside an AI-Mode-managed tree — content only ever comes back through step 2.
2. For each file the agent wants to read, it calls `POST /ai/extract` with that file's
   (anonymized) path. d-tach extracts text (reusing the existing
   `load_docx`/`load_pdf`/`load_xlsx`/`load_md` loaders) and anonymizes it (reusing
   `Anonymizer`), exactly as Document Mode does today — but returns the anonymized text
   directly in the response instead of writing an output file, and the source file on disk
   is never modified.
3. d-tach keeps the placeholder → original mapping server-side, keyed by a `session_id`
   returned in that response. The AI never receives real values from this call.
4. The AI works with the anonymized text (sends it to a cloud model, drafts notes,
   marksheet comments, etc.) — using only placeholders/hash keys to refer to the subject
   of the file, never a real name it doesn't have.
5. When the AI has produced final output that should contain real values again (e.g. a
   completed marksheet ready for the human to paste elsewhere), it calls `POST /ai/restore`
   with `{session_id, text, output_path}`. d-tach substitutes placeholders back to real
   values locally and **writes the restored result directly to `output_path` on disk** —
   the restored text is not included in the HTTP response, so it never enters the AI
   agent's own context. If `output_path` is omitted, `/ai/restore` behaves as before and
   returns the restored text inline — that mode is for a human-in-the-loop caller (e.g. a
   manual API call the user makes themselves), not for an AI agent working unattended.
6. If the AI notices a real name slip through unanonymized in extracted text, it calls
   `POST /ai/flag-term` with the missed value — this appends to the existing
   `UserSettings.known_values` list so it's caught on every future run, not just
   retroactively in the current session.

Images and image-only PDF pages have no text layer today (`pymupdf` doesn't OCR). Rather
than add OCR now, `/ai/extract` reports per-page/file "no extractable text" warnings so
the user knows exactly what needs manual review — never silently passing image bytes
through. OCR is deferred; see `roadmap.md`.

### New service: `app/services/ai_session.py`

- `AISessionStore` — in-memory dict, `session_id -> {created_at, replacements: dict[placeholder, original], source_path}`.
- Sessions expire after a configurable idle period (default 60 min) and are also cleared
  on server restart — intentionally not durable storage; it only needs to live as long as
  one AI conversation.
- Shared helper `compose_replacements(entities) -> dict[str, str]` — extract this out of
  `_build_replacements` in `file_processor.py` rather than duplicating it.

### `document_processor.py` — small addition

Add `restore_string(text: str, replacements: dict[str, str]) -> tuple[str, int]`, a
string-in/string-out version of the existing file-in/file-out `restore_text`. Have
`restore_text` call `restore_string` internally so there's one substitution
implementation, not two.

### New route: `app/routes/ai_routes.py`

| Endpoint | Method | Request | Response |
|---|---|---|---|
| `/ai/status` | GET | — | `{enabled: bool}` — lets the AI check AI mode is on before trying anything else |
| `/ai/extract` | POST | `{file_path, language, hashing_enabled, secret, ...same settings as /document/process-file}` | Inline: `{session_id, anonymized_text, entities, warnings}`. Large file: `{session_id, anonymized_text_path, entities, warnings}` |
| `/ai/restore` | POST | `{session_id, text}` **or** `{session_id, text_path}`, plus optional `{output_path}` | No `output_path`: inline `{restored_text, replacements_applied}` (large input: `{restored_text_path, replacements_applied}`). With `output_path`: writes restored text to that path and returns `{status: "written", output_path, replacements_applied}` only — no restored content in the response |
| `/ai/flag-term` | POST | `{value}` | `{status: "added", known_values: [...]}` |

All four require header `X-D-Tach-Token: <token>` (see Settings below). Reuses
`current_app.file_processor` / `current_app.anonymizer` — no new extraction or detection
logic, only new glue around existing pieces.

`/ai/extract` internally: load the file via the same per-extension branch as
`file_processor._process_docx/_process_pdf/_process_xlsx/_process_markdown`, but stop
short of writing an output file — return text + entities instead. Refactor those four
`_process_*` methods minimally so the "extract + detect + build replacements" portion is
callable without the "write output file" portion, then have both Document Mode and
`/ai/extract` call the shared portion.

### Large file handling — inline text vs. temp file

JSON-over-HTTP can carry many MB without trouble — the real constraint is the AI's
context window, not d-tach or Flask. A 100-page report inlined as JSON would dominate a
single turn's useful context on one file. d-tach enforces a size cutoff and switches to a
file handoff above it:

- **Setting:** `ai_inline_text_max_chars` (default **50,000** chars, ≈ 12–15k tokens).
  Configurable in the AI Mode settings panel.
- **Setting:** `ai_temp_dir` (default: OS temp dir + `d-tach-ai/`; user can point it
  elsewhere). Must exist and be writable; validated when AI Mode is enabled.
- **`/ai/extract`:** if anonymized text length ≤ threshold, return it inline
  (`anonymized_text`). If over, write it to `{ai_temp_dir}/{session_id}_extracted.txt`
  and return `anonymized_text_path` instead (`anonymized_text` omitted) — the AI reads
  the file directly.
- **`/ai/restore`:** accepts either inline `text` or a `text_path`. Response mirrors the
  same inline-vs-path rule on the way out, using the same threshold.
- Temp files are named with the `session_id` so they're traceable to a session and get
  cleaned up when that session expires (`AISessionStore` deletes its temp files on
  expiry, not just the in-memory entry).
- This threshold is a quality-of-context safeguard, not a security boundary — both paths
  go through the same anonymize/restore logic either way.

### Settings — AI Mode panel

New section in the existing Settings UI:

- **Enable AI Mode** toggle — default **off**. `/ai/*` routes return 404 (not 403, to
  avoid confirming the route exists) when disabled.
- **Local API token** — generated once (`secrets.token_urlsafe(32)`), shown with a
  "Regenerate" button, stored in `UserSettings`. Copy-to-clipboard button.
- **AI agent instructions** — a read-only, copy-to-clipboard text block: the generic
  operating instructions for any AI agent using this mode, written once and shipped with
  the product. This is a real deliverable, not placeholder wording — it is the entire
  onboarding path for AI Mode, because there is no other way for an agent to learn the
  rules. Write it use-case-neutral (no wording tied to any one use case or user) so
  it drops straight into a system prompt or a `CLAUDE.md` for any kind of work. Step 6's
  acceptance run pastes this exact block verbatim and appends test-only additions to it —
  if the block has to be edited to make that run work, the block is wrong and gets fixed
  here rather than worked around there. Substitute the live port and token into the text
  before display. Baseline content:
  > "AI Mode is enabled on d-tach (http://localhost:{port}). Before pointing me at a
  > folder, run Document Mode's 'Rename names only' pass on it once so every path is
  > already name-anonymized. From then on: normal directory listing of that folder is
  > safe, but never read a file's contents directly — always call `POST /ai/extract`
  > with the file path first and work only with the returned `anonymized_text`. Refer to
  > the subject of each file only by its placeholder/hash, never a name you weren't given.
  > When producing final output that needs real values restored, call `POST /ai/restore`
  > with an `output_path` so the restored text is written straight to disk — never ask
  > for it inline. Include header `X-D-Tach-Token: {token}` on every request."
- **Session timeout** — minutes, default 60.
- **Temp folder** — path picker, default OS temp dir + `d-tach-ai/`; validated writable
  on save.
- **Inline text limit** — characters, default 50,000; one-line note: "Larger extractions
  are written to the temp folder instead of returned directly, to avoid flooding the
  AI's context window."

`UserSettings` additions: `ai_mode_enabled: bool = False`, `ai_api_token: str` (generated
lazily on first enable), `ai_session_timeout_minutes: int = 60`,
`ai_inline_text_max_chars: int = 50000`, `ai_temp_dir: str` (default computed from OS
temp dir).

### Explicitly deferred (not part of this step)

- **OCR for images/scanned PDFs** — flagged, not solved. `/ai/extract` reports the gap;
  revisit as a roadmap item once flag-only behaviour has been used for a while.
- **d-tach writing arbitrary, un-anonymized files on the AI's behalf** — `/ai/restore`
  with `output_path` only ever writes the *restored* text of a session it already holds
  the mapping for; it does not become a general-purpose "AI writes any file" primitive.
  Still in scope for this step (see `output_path` above) — what's deferred is generalizing
  it beyond the restore use case.

### What to build

| Component | Description |
|---|---|
| Document Mode — rename-only toggle | New folder-picker option: rename file/folder names in place using existing hash logic, skip content extraction/anonymization entirely, no `anonymized/` output tree |
| `app/routes/ai_routes.py` | New — `/ai/status`, `/ai/extract`, `/ai/restore`, `/ai/flag-term` |
| `app/services/ai_session.py` | New — `AISessionStore`, session expiry, temp-file cleanup |
| `document_processor.py` | Add `restore_string`; refactor `restore_text` to call it; `restore_string` callers may pass `output_path` to write instead of returning text |
| `file_processor.py` | Extract shared "detect + build replacements" helper out of the `_process_*` methods for reuse by `/ai/extract` |
| `user_settings.py` | Add `ai_mode_enabled`, `ai_api_token`, `ai_session_timeout_minutes`, `ai_inline_text_max_chars`, `ai_temp_dir` |
| Settings UI — AI Mode | Enable toggle, token display/regenerate, instructions block, timeout, temp folder, inline limit |
| `app/__init__.py` | Register `ai_routes` blueprint |

### ✅ Complete when

- Document Mode's folder picker offers "Rename names only" — running it against a folder
  renames files/folders in place using existing hash logic, leaves every file's content
  byte-for-byte unchanged, and creates no `anonymized/` output tree
- AI Mode is off by default; `/ai/*` returns 404 when disabled
- Enabling AI Mode in Settings generates and displays a token; instructions block is
  copyable
- `POST /ai/extract` on a real PDF/DOCX/XLSX/MD file returns anonymized text + entity
  list + a `session_id`, without writing any file to disk
- `POST /ai/extract` on an image-only PDF page returns a `warnings` entry instead of
  silently passing image content through
- `POST /ai/extract` on a file producing anonymized text over `ai_inline_text_max_chars`
  writes to `ai_temp_dir` and returns `anonymized_text_path` instead of inlining it;
  under the threshold it inlines as before
- `POST /ai/restore` accepts both inline `text` and `text_path`, and applies the same
  inline/path rule to its response when no `output_path` is given
- `POST /ai/restore` with a `session_id` and placeholder-containing text returns the
  original values correctly substituted back
- `POST /ai/restore` with `output_path` set writes the restored text to that path and
  the HTTP response contains no restored content, only a status and the path
- `POST /ai/flag-term` adds a value to `UserSettings.known_values`, visible afterward in
  the Settings known-values list and applied on the next extraction
- Requests without the correct `X-D-Tach-Token` header are rejected
- Existing Text/Document/Restore modes have no behavioural change (refactor of shared
  helpers is non-breaking)
- New unit tests: `tests/test_ai_session.py`, `tests/test_ai_routes.py`, a
  `restore_string` test in `tests/test_document_processor.py`, and a rename-only test
  confirming file content is untouched
- All existing tests pass

---

## <completed>Step 6 — Acceptance Testing</completed>

**Codeberg issue to create first:**
`test: acceptance testing — v1.3.0 end-to-end on real data`

**Goal:** accept v1.3.0 by using it for a real piece of work, end to end, rather than by
running a checklist against material prepared for the test.

### Why a real-work run rather than a self-administered checklist

The original Step 3 was a feature checklist the developer ran against himself, on data he
already knew, immediately after building the features. That catches crashes and little
else. The failure modes that actually decide whether this release is safe — a name the
models miss, a placeholder that doesn't round-trip, a roster row imported wrong, a real
value reaching a cloud model — only surface on data neither the tool nor the assistant has
seen before.

A real-work run exercises every v1.3.0 feature at once and attaches a hard pass/fail signal
to the release:

> **If a real identifying value reaches the AI assistant's context at any point, v1.3.0
> does not ship.**

It is last on purpose. It tests Steps 1–5 as one system rather than one at a time, so all
five have to be merged before it can start.

### Choosing the work

The run needs a task with four properties. Anything meeting them will do:

- **A folder of real documents containing real personal data** — not synthetic test files,
  and not data the assistant has been shown before
- **A known roster** of the people appearing in that data, exportable as `.xlsx`, so the
  class list import has something real to bulk-load
- **A real output** that has to carry real values back out again — something the tester
  genuinely needs written to disk with names restored, so `/ai/restore` is under real load
  rather than being demonstrated
- **A tester who can independently verify** each restored output against the source of
  truth, because that verification is the actual test

🟡 The specifics of the run — which dataset, which task, which output format, the
per-subject process — are deliberately **not recorded in this repository.** They describe
real people's data and the tester's own working process, neither of which belongs in public
source. They live in a private working document alongside the data. This repo records what
must be tested and what counts as a pass; it does not record whose data was used to do it.

### Pre-test setup

1. **Start the app the way a user would.** Run `launch.bat` (Windows) or `launch.sh`
   (macOS/Linux) — not a dev entry point, and no manual dependency install. If the launcher
   can't get a working app onto the screen unaided, that is the first defect of the run and
   goes in the log before anything else happens. Confirm the tray icon appears and the
   configured port is the one in use.
2. **Import the roster.** Export the roster (identifier column, name columns) to `.xlsx`.
   Settings → Known Values → Import from class list; map the columns (identifier → Numeric
   ID, names → Person name); import. Check the returned added / already-present counts
   against the file's row count — a mismatch is a defect to log, not a rounding difference
   to shrug at. This is the step that turns every subject into a guaranteed catch rather
   than an NER coin-flip.
3. **Put the real files in one folder, unmodified.** Downloaded exactly as they come from
   the source system. Names will appear in file and folder names at this point — expected,
   and exactly what the next step exists for.
4. **Rename-only pass.** Run Document Mode's "Rename names only" over that folder once, with
   KEYREF export enabled. File contents stay real and untouched on disk; only paths change.
   The KEYREF is the tester's only route from a renamed folder back to a real subject, and is
   never shown to the assistant. Tick **"Expand archives first"** on the same pass if the
   folder holds any `.zip` or `.tar`: an archive that stays packed hides both its contents and
   its member names from the rename, so step 5's check would pass over a tree that still holds
   real names inside it.
5. **Verify the tree by hand.** List the working folder and read every path. No name, no
   identifier, no email address in any file or folder name. If one survives, add it to known
   values and re-run the pass before going further. This check is the gate, and the assistant
   cannot perform it — it would have to see the names to do so.
6. **Enable AI Mode.** Settings → AI Mode → enable; generate the token; note the port. Copy
   the AI agent instructions block.

### What the run has to exercise

Whatever the task is, the run only counts as an acceptance test if all of this happens
naturally in the course of it:

| Feature | What the run must do with it |
|---|---|
| Class list import | Bulk-load the roster; at least one subject anonymized by a known-values entry rather than by NER |
| Rename-only pass | One real folder tree, renamed in place, contents untouched, no second tree created |
| `/ai/extract` | Every single file read goes through it — the assistant never opens a file in the tree directly |
| `/ai/restore` with `output_path` | Every real-valued output written straight to disk; the assistant composes only in placeholders and never receives the restored text |
| `/ai/flag-term` | Any value the assistant suspects slipped through gets flagged mid-run and caught for every subject after it |
| Placeholder guard (Step 3) | Text that is already anonymized passes through extraction unchanged, under real load |
| Tray / port / languages | The app stays up as a background process for the whole run, no restarts except where a settings change legitimately requires one |

**Verification alternates direction, subject by subject.** Assistant-first: it produces its
output and a short list of items for the tester to check against the real source. Tester-first:
the tester states their own findings and the assistant checks them against the extracted text,
saying plainly where it agrees, where it disagrees, and where the extracted text can't settle
it. The second direction matters more than it looks — it is the only way to catch the
assistant simply agreeing with whatever it was told, which a one-directional run cannot tell
apart from genuine agreement.

### Assistant instructions for the run

The AI Mode settings panel's generic instructions block (Step 5) is the base, and ships with
the product. For an acceptance run, paste that block plus the additions below. Keep the two
visibly separate — anything that turns out to be needed permanently belongs in the shipped
block instead.

> **Acceptance test additions — this run only.**
>
> For every file you extract, before you use it: print the placeholder set you were given
> (`[PERSON_1]`, `[NUMERIC_ID_2]`, `[Cr-A2T5 HY23]`, and so on) and the first two lines of the
> anonymized text verbatim. I want to see what d-tach actually handed you, not a summary of it.
>
> If you think a real name, identifier, email address or other identifying value has survived
> into text you were given, do three things and then carry on: quote the exact span, say what
> makes you think it is real rather than a placeholder, and call `POST /ai/flag-term` with that
> value. Do not stop the run, do not ask me first, and do not refuse to process that file — a
> suspected leak is a finding to record, not a reason to halt. I would rather have a finished
> item and a flag than neither.
>
> Never write a real value into chat, into a file, or into any output. If you believe you have
> worked out a real value, refer to it by its placeholder and tell me how you came to know it —
> that inference path is itself a finding.
>
> At the end of the run, give me one section listing every concern: the file, the span you saw,
> why it looked real, and whether you flagged it. Include the ones you were unsure about and the
> ones I had already told you were false alarms — an over-cautious flag is useful signal about
> detection tuning, and I want the rate, not just the hits.

The tester's side: confirm or reject each flag as it comes in, and record which it was. A high
false-positive rate is a finding about the Step 3 placeholder guard being too loose in the other
direction. A real leak is a finding about detection, and about whether the roster import in
setup step 2 actually covered that subject.

### Defect log

Keep one running list during the run rather than writing it up afterwards — the details that
matter are gone by the end. Per entry: which step or feature, what happened, what was expected,
and whether it blocked the work or was worked around. This log is the release evidence.
Anything in it marked as a blocker is a v1.3.0 fix, not a v1.4.0 backlog item.

**Run in progress — issue #70.** Entries below record the defect and its outcome only. What
was tested, and on whose data, stays out of this repository.

| # | Step / feature | Defect | Blocker | Status |
|---|---|---|---|---|
| 1 | Pre-test 1 — launcher | Launcher completed setup but no app reached the screen; the tray process died before the server thread started | Yes | Fixed |
| 2 | Pre-test 1 — launcher | First run installed dependencies but did not go on to start the app; a second run was needed | No | Fixed |
| 3 | Pre-test 2 — known values | A known value matched inside longer ordinary words, corrupting prose and registering false replacements that `/ai/restore` would put back mid-word | Yes | Fixed |
| 4 | Pre-test 2 — known values | Known values were reachable only from the Text and Document panels, not from Settings as the setup steps describe | No | Fixed |
| 5 | Pre-test 2 — known values | A roster-scale import built one recognizer per value and rendered one tag per value, making both matching and the settings page scale badly | No | Fixed |
| 6 | Pre-test 4 — rename-only pass | Archives were left packed, so their member names never reached the rename and the step 5 gate could pass a tree that still held real names | Yes | Fixed |
| 7 | Pre-test 4 — rename-only pass | Two detections covering overlapping spans were both replaced, producing malformed placeholders that no restore pass could map back to a real value | Yes | Fixed |
| 8 | Pre-test 6 — settings | Hashing was configured per mode rather than in Settings, so the same subject could encode to different placeholders depending on which mode reached them | No | Fixed |
| 9 | Pre-test 6 — settings | Detection, Excel and folder-output settings lived on the mode pages and were written back by each run, so one run could silently change what a later run in another mode did | Yes | Fixed |
| 10 | Test run — folder anonymization | An image-based PDF that could not be read was still written into the `anonymized/` output, where subfolder mode dropped the UNREADABLE_ prefix and left it indistinguishable from anonymized output | Yes | Fixed |
| 11 | Test run — AI Mode | A possessive form put the apostrophe inside the detected name, so the same person hashed to a different placeholder in `Name's` than in `Name`, and to a third with a typographic apostrophe — breaking the one-subject-one-token guarantee across a folder | Yes | Fixed |
| 12 | Test run — AI Mode | `/ai/extract` reported sequential placeholders (`[PERSON_1]`) while writing hashed ones into the text, so the entity list named tokens absent from the document and reused the same token for a different person in every file | Yes | Fixed |

### ✅ Complete when

- A complete real task is done through AI Mode start to finish, without falling back to the
  old manual copy-into-an-anonymized-folder workflow for any item
- No real name, identifier or email address reached the assistant's context at any point —
  confirmed against both the assistant's end-of-run concerns list and the tester's own read of
  the chat transcript
- Every output written via `/ai/restore` with `output_path` contains the correct real values
  matched to the right subject — independently spot-checked for at least three subjects; any
  mismatch is a blocker, not a note
- Roster import earned its place: at least one case identified where a known-values entry, not
  NER, is what caught a name
- Placeholders round-tripped cleanly under real load — no nested brackets anywhere, no literal
  placeholder text left in any finished output (Step 3, proven on real data)
- Every `/ai/flag-term` call is resolved as either a real miss or a false positive, and the
  ratio is recorded
- Tray, port and language management held up for the duration of the run
- The defect log has no unresolved blockers
- `pytest` passes on main after any fixes made during the run

### Appendix — feature checklist

Run this as a quick sweep before the real-work run starts, and as the fallback acceptance route
if no suitable real task is available inside the release window. It covers per-feature cases a
real run doesn't naturally reach. Falling back to this alone is a legitimate outcome — it just
means the release notes shouldn't claim AI Mode has been proven on real data.

| Check | Expected |
|---|---|
| `tray.py` launch | Server starts; tray icon appears |
| Tray right-click > Open d-tach | Browser opens at configured port |
| Tray right-click > Quit | Server stops; process exits |
| Port change in Settings | Restart notice shown; new port used after restart |
| Tray icon URL after port change | Opens at new port |
| First launch (fresh UserSettings) | Language selection screen shown; download completes; app opens |
| Settings > Languages — install | Progress shown; completion message; model usable after restart |
| Settings > Languages — remove | Model gone from disk after restart |
| Load on startup toggle | Only enabled models loaded; disabled model not in RAM |
| Lazy loading | Only base model in RAM at startup; second language loads on first use |
| Language not loaded — document processed | Clear error message in UI |
| Regression — Restore tab | Restore still works correctly |
| Regression — Document Mode | Anonymization still works correctly |
| Regression — Text Mode | Text anonymization still works correctly |
| `pytest` | All tests pass |
| Re-anonymize already-anonymized text | Idempotent — output identical to the first pass, no nested brackets |
| Hashed placeholder re-run | `[Cr-A2T5 HY23]` never re-tagged as a new PERSON |
| Class list import | Header row read; column mapping applied; typed entries added; counts correct |
| Imported Numeric ID entry | Anonymizes as `[NUMERIC_ID_N]`, not `[PERSON_N]` |
| Class list re-sync | Only new rows added; no duplicates |
| Clear class list values | Only `source: class_list` entries removed; manual entries remain |
| Known values in Settings | Manage and import from Settings; the same list applies in Text, Document and AI mode |
| Roster-scale import | A class-list-sized import stays responsive; imported values reachable by search rather than listed in full |
| Known value inside a longer word | Never matched — a value like "An" leaves "Thank", "and" and "standard" alone |
| Rename-only pass | Paths anonymized in place; file contents byte-for-byte unchanged; no `anonymized/` tree created |
| Expand archives first | Every `.zip`/`.tar` under the folder extracted beside itself, nested archives included, before the rename runs |
| Expand archives — name collision | An existing folder of the same name is never overwritten; the extraction lands beside it |
| Expand archives — hostile member path | A member pointing outside its destination is refused, not written |
| Delete each archive once expanded | Off by default; when on, only archives that expanded cleanly are removed |
| `/ai/*` with AI Mode off | 404, not 403 |
| `/ai/*` with wrong or missing token | Rejected |
| `/ai/extract` over inline limit | Returns `anonymized_text_path`; `anonymized_text` omitted |
| `/ai/extract` on image-only PDF page | `warnings` entry returned; no silent pass-through |
| `/ai/restore` with `output_path` | File written; response carries status and path only, no restored content |
| `/ai/flag-term` | Value appears in Settings known values and applies on the next extraction |
| Overlapping detections in one span | A single placeholder is emitted, never a malformed one built from two overlapping replacements |
| Settings is the only writer | A Text or Document run leaves `user_settings.json` byte-for-byte unchanged |
| Settings > Detection | Dates, URLs, locations, numeric ID and file-name checking save immediately and apply in Text, Document and AI mode alike |
| Settings > Hashing | Secret set once; the same value encodes to the same placeholder in every mode and after a restart |
| Settings > Excel | Generic NER and column overrides save immediately and apply to a Document Mode run |
| Settings > Folder output | Output mode and pass-through extensions save immediately and apply to a Document Mode folder run |
| Settings > Default language | Each mode opens on the saved language; a per-run switch does not change the default |
| Mode-page detection summary | Text and Document mode describe what will be detected and link to Settings, with nothing editable in two places |
| Image-based PDF in a folder run | Reported as unreadable and written nowhere — the output folder does not contain it under any name |
| PDF with some image-only pages | Text pages redacted, file written, and the image-only pages named in a warning |
| Possessive names | `Name`, `Name's` and `Name’s` all encode to the same placeholder, with the apostrophe left in the text |
| AI Mode placeholders | Every placeholder in `/ai/extract`'s entity list appears verbatim in the anonymized text it returns |

---

## PDF Anonymization Quality Research (Separate — Not d-tach)

The standalone PDF replace-text research project from `step_1.2.0_completed.md` continues in
parallel outside the d-tach codebase. If that research produces a clearly better approach
to in-place PDF text replacement, the findings should be assessed against the current
d-tach PDF anonymization before v1.4.0 is planned. No action required within this release.

---

## v1.4.0 Planning Note — PyInstaller Packaging

Once v1.3.0 ships, the packaging picture changes:

- Languages are downloaded on demand — not bundled into the distribution
- The PyInstaller binary (Python runtime + Flask + Presidio + app code) is expected
  to be 80–150 MB, likely within Codeberg's free storage quota
- Target audience: users without Python experience who cannot run launcher scripts

Key questions to resolve before starting v1.4.0:
- Confirm binary size on a clean build and check against current Codeberg quota
- Decide whether to bundle one default model (larger binary, no internet required on
  first launch) or always download on first launch (smaller binary, internet required)
- Test Flask static file paths under `sys._MEIPASS` — known PyInstaller challenge
- Test on macOS: `tkinter` bundling and `launch.sh` behaviour

A full step breakdown will be written as `step_1.4.0.md` when v1.3.0 is released.

---

## v1.4.0 Planning Note — GitHub Mirror + Pages

**Investigate when v1.4.0 is picked up. Nothing to do during v1.3.0.**

Arrived here from the summer-holiday plan
(`general/planning/summerholiday/step-3-den-sync.md`, step 3.3), where it was
originally bundled with a question about moving the personal `d-workspace` repo
to GitHub. That move was **declined** — but the reasoning does not carry over to
d-tach, and mixing the two muddied both. The d-workspace repo holds family and
financial records, so a permanent copy on US infrastructure was not worth it.
d-tach is public code under EUPL-1.2, so none of that applies.

### The proposal

Keep **Codeberg as origin** and add **GitHub as a push mirror**. Codeberg stays
the place issues, PRs and releases live — no change to the workflow in
`CLAUDE.md`. GitHub becomes a read-only reflection.

Two things it would buy:

1. **Pages that works.** Codeberg Pages has been attempted several times and has
   not come together. GitHub Pages is the fallback that would actually publish.
   The `d-ranged/pages/` folder is currently empty pending this.
2. **Reach.** GitHub is where people look for open source. For a project about
   to go public, discoverability is a real argument — a privacy tool nobody
   finds helps nobody.

### The tension worth naming

d-ranged's stated principles include a European sensibility and privacy-first
software, and Codeberg was chosen deliberately for that (`d-ranged/CLAUDE.md`).
Mirroring to a Microsoft-owned US platform sits awkwardly against that, even for
public code. 🟠 The counter-argument is that a mirror is a *reflection*, not a
move — origin, issues, and identity all stay on Codeberg, and reach serves the
principles rather than trading them away. This is a values call, not a technical
one, and should be made consciously rather than by drift.

### Questions to resolve

- Does the mirror push automatically (Codeberg has a built-in push-mirror
  setting) or via CI? Built-in is preferable — no secrets to manage.
- Do GitHub Pages get built from the mirrored repo, or does the site live in its
  own separate GitHub repo? A mirrored repo is force-overwritten on each sync,
  which may fight with a Pages build branch.
- Where does the README point contributors — Codeberg only, or both? A clear
  "issues and PRs live on Codeberg" banner on the GitHub side avoids splitting
  the community across two platforms.
- 🟡 Does this also solve the **release binary hosting** problem from the
  PyInstaller note above? GitHub Releases has a far more generous asset quota
  than Codeberg's free tier. If so, this note and that one are the same decision
  and should be planned together — see also `secrets/codeberg_storage_request.md`.

### Related

- `d-ranged/pages/README.md` — the Pages folder, empty pending this decision
- v1.4.0 PyInstaller packaging note above — overlapping storage/quota question

---

## Release Runbook — v1.3.0

All six build steps and acceptance testing are done. What is left is mechanical —
merge the branch, bump the version, publish. Two sittings, in order. Per `CLAUDE.md`,
**Claude does not commit directly to `main` and does not merge PRs** — both sittings
below are Craig's own actions on Codeberg/git, with Claude preparing content and
giving exact commands to run. This is a standing project rule, not a default that a
future session can quietly relax.

### Sitting 1 — Merge issue #70 into `main`

**Who:** Craig, via the Codeberg GUI. **Tier:** none needed, no AI session required
for this sitting.

- `fix/issue-70-launcher-startup` is 10 commits ahead of `main`, `main` has nothing
  it doesn't (verified 25-8-2026 — reverify if time has passed and other branches
  merged since)
- Codeberg → Pull Requests → New → `fix/issue-70-launcher-startup` into `main` →
  `Closes #70`
- Review, merge, delete the branch

**Comes out of this sitting:** `main` contains everything in v1.3.0 Steps 1-6,
including all twelve defects fixed during acceptance testing.

### Sitting 2 — Cut the release

**Who:** Craig, in a fresh session, Claude assisting. **Tier:** Sonnet — this is
execution against a fully written spec, no judgement calls left. **Opening line to
paste into a new session:**

> Follow the Release Runbook for v1.3.0 in `docs/step_1.3.0_next.md` — Sitting 2.
> `main` already has issue #70 merged. Walk me through it.

**What Claude does in this sitting:**

1. `git checkout main && git pull` — confirm `main` now has issue #70 merged
2. Run `pytest` — confirm the full suite is still green on `main` (431+ tests at
   last count; note the number if it's changed)
3. Bump `__version__` in `app/__init__.py`: `"1.2.0"` → `"1.3.0"`
4. Update the version badge in `README.md`: `version-1.2.0-blue` → `version-1.3.0-blue`
5. While touching `README.md`: fix five links still pointing at
   `codeberg.org/d-craig/d-tach` (lines 7, 11, 52, 63, 227) — the repo has been
   `d-ranged/d-tach` since the branding change and these currently 404. Pre-existing,
   unrelated to v1.3.0, but cheap to fix in the same pass rather than leaving a
   release with dead download links.
6. Paste the CHANGELOG entry below into `CHANGELOG.md`, above the `[1.2.0]` entry,
   with today's date filled in

**What Craig does — the parts `CLAUDE.md` reserves for him:**

1. Review the diff, then commit directly to `main` himself:
   `Update version to v1.3.0` with `Co-authored by d-craig and Claude Code`
2. Tag: `git tag v1.3.0 -m "Release v1.3.0"`
3. Push: `git push && git push origin v1.3.0`
4. Codeberg → Releases → New Release → select the `v1.3.0` tag → paste the
   CHANGELOG entry as the release notes → publish

**Comes out of this sitting:** a tagged, pushed, published v1.3.0 release.

**Optional follow-up, not part of the release itself:** update the test clone at
`C:\tools\d-tach` — quit the tray app, `git pull`, delete `.venv`, rerun `launch.bat`.

### CHANGELOG entry — ready to paste


## [1.3.0] —  2026-8-26

### Added
-
- **-System tray app** — d-tach now runs as a persistent background process with a tray icon (Open d-tach / Quit) instead of something launched and closed each session. Offers a one-time prompt to register as a Windows startup program.
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