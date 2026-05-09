# step_1.3.0.md — d-tach v1.3.0 Build Plan

This document breaks the v1.3.0 planned work into ordered, testable steps.
Each step should map to one or more Codeberg issues created before starting.

Consult `roadmap.md` for background context.
Consult `project_guide.md` for architectural decisions and documented alternatives.

---

## Status at a Glance

| Step | Description | Status |
|---|---|---|
| 1 | System tray app + configurable port | ⬜ Not started |
| 2 | Language management — on-demand download, first-launch selection | ⬜ Not started |
| 3 | Acceptance Testing — all features | ⬜ Not started |

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

## Step 1 — System Tray App + Configurable Port

**Codeberg issue to create first:**
`feature: system tray app and configurable port`

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

## Step 2 — Language Management

**Codeberg issue to create first:**
`feature: language management — on-demand model download and first-launch selection`

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

## Step 3 — Acceptance Testing

**Codeberg issue to create first:**
`test: acceptance testing — v1.3.0 tray, port, language management`

**Goal:** Manual test run covering all v1.3.0 features after Steps 1 and 2 are merged
to main.

### Pre-test setup

- `git pull main` — confirm on latest main
- `pip install -r requirements.txt`
- Run `pytest` — must pass before starting manual tests
- Start via `tray.py` — confirm tray icon appears

### Test cases

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

### ✅ Complete when

- All test cases above pass
- No regressions in any existing feature
- `pytest` passes with no failures on main

---

## PDF Anonymization Quality Research (Separate — Not d-tach)

The standalone PDF replace-text research project from `step_1.2.0.md` continues in
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

## Release — v1.3.0

Once all steps including acceptance testing are complete:

1. Bump `__version__` in `app/__init__.py`
2. Update version badge in `README.md`
3. Add v1.3.0 entry to `CHANGELOG.md`
4. Commit: `Update version to v1.3.0`
5. Tag: `git tag v1.3.0 -m "Release v1.3.0"`
6. Push commits and tag: `git push && git push origin v1.3.0`
7. Codeberg → Releases → New Release → select tag → paste CHANGELOG entry → publish
