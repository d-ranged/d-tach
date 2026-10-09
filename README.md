# d-tach

**d-tach** anonymizes names, contact details, and other personal data from text, Word documents, PDFs, and Markdown files before you share them for review or assessment.

Everything runs locally on your machine. No files or text are ever sent anywhere.

[![Version](https://img.shields.io/badge/version-1.3.0-blue)](https://codeberg.org/d-ranged/d-tach/releases)
&nbsp;
[![License: EUPL-1.2](https://img.shields.io/badge/license-EUPL--1.2-green)](LICENSE)

[⬇ Download Latest Release](https://codeberg.org/d-ranged/d-tach/releases)
&nbsp;
[▶ Watch the Tutorial](https://youtu.be/8uLj6M8AUug)

Developed on [Codeberg](https://codeberg.org/d-ranged/d-tach), mirrored to [GitHub](https://github.com/d-ranged/d-tach). Issues and pull requests on Codeberg.

---

**Jump to:** [Download to Use](#download-to-use) · [Technical Setup](#technical-setup)

---

## Download to Use

_For educators, assessors, and colleagues who want to use the application without a technical background._

### What it does

Paste text or select a document and d-tach replaces personal details — names, email addresses, phone numbers, student numbers, and more — with neutral placeholders such as `PERSON_1` or `EMAIL_ADDRESS_1`. The original file is never touched; a new anonymized copy is saved alongside it.

You choose:
- **Text mode** — paste text directly and copy the anonymized result.
- **Document mode** — select a single file or an entire folder; anonymized copies are saved in the same location with an `ANON_` prefix (or `CHECKED_` if no personal data was found). You can also rename file and folder names only, leaving every file's contents untouched.
- **AI mode** — let an AI assistant work with your documents without ever seeing a real name. See below.

A key reference file can be generated alongside the output so the anonymization can be reversed if needed.

You can also give d-tach a list of names it must always catch — typed in one at a time, or imported in bulk from a class list or roster spreadsheet. Detection is never perfect on its own, and this is how you close the gap for the people you know will appear.

### What it does not do

- It does not send your data anywhere. There is no internet connection, no account, and no telemetry.
- It is not 100% accurate. Always review the output before sharing. A disclaimer is shown in the application as a reminder.

### Install

Pick the download for your computer. Nothing else needs to be installed first.

| Computer | Download |
|---|---|
| Windows 10 or 11 | [d-tach-windows.zip](https://github.com/d-ranged/d-tach/releases/latest/download/d-tach-windows.zip) |
| Mac with Apple Silicon (M1 or newer) | [d-tach-macos-arm.zip](https://github.com/d-ranged/d-tach/releases/latest/download/d-tach-macos-arm.zip) |
| Linux, or a Mac with an Intel chip | [Run from source](#run-from-source), needs Python |

Not sure which Mac you have? Apple menu, **About This Mac**. "Chip: Apple M..." means Apple Silicon. "Processor: Intel" means Intel.

The same files are attached to the latest release on [Codeberg](https://codeberg.org/d-ranged/d-tach/releases). Older versions are on [GitHub](https://github.com/d-ranged/d-tach/releases).

d-tach is not signed with a paid developer certificate, so Windows and macOS warn you the first time you open it. The steps below show how to get past that. It happens once.

#### Windows

1. Download **d-tach-windows.zip**.
2. Right-click the zip, choose **Extract All**, and extract it to a folder you keep, for example `Documents`. Do not run d-tach from inside the zip.
3. Open the extracted **d-tach** folder and double-click **d-tach.exe**.
4. Windows shows **"Windows protected your PC"**. Click **More info**, then **Run anyway**.
5. Your browser opens d-tach. Continue with [First run](#first-run).

To start d-tach from the Start menu or the desktop, right-click **d-tach.exe**, choose **Show more options**, then **Send to**, **Desktop (create shortcut)** or **Pin to Start**.

#### Mac (Apple Silicon)

1. Download **d-tach-macos-arm.zip**. Safari unpacks it for you. Otherwise double-click the zip in Downloads.
2. Drag **d-tach** into your **Applications** folder. Do this before you open it: an app opened from Downloads runs from a temporary copy, and "start at login" then points to the wrong place.
3. Double-click **d-tach** in Applications. macOS says it cannot verify d-tach. Click **Done**, not Move to Trash.
4. Open **System Settings**, **Privacy & Security**, and scroll down to **Security**. Next to "d-tach was blocked", click **Open Anyway**. Enter your password, then click **Open Anyway** once more.
5. The d icon appears in the menu bar at the top of the screen and your browser opens d-tach. Continue with [First run](#first-run).

#### First run

1. d-tach asks which languages your documents are in. English is always included. Tick Dutch if you need it and click **Download and continue**. Each language is about 50 MB and downloads once.
2. d-tach asks whether to start automatically when you log in. Choose either, you can change it later.

The d icon in the system tray (Windows) or menu bar (Mac) is how you get back to d-tach after closing the browser tab. Click it for **Open d-tach**, or right-click it for **Quit**. Starting d-tach again while it is already running just opens the running one in your browser.

#### Updating

Quit d-tach from the tray icon, then replace the old **d-tach** folder (Windows) or app (Mac) with the new download. Your settings, AI mode token and languages are kept. They live apart from the app, in `%LOCALAPPDATA%\d-tach` on Windows and `~/Library/Application Support/d-tach` on a Mac.

### Run from source

For Linux, Intel Macs, or anyone who prefers to run the Python code directly. You need **Python 3.11 or newer**.

- **Windows:** Download from [python.org/downloads](https://www.python.org/downloads/). During installation, tick **"Add Python to PATH"**.
- **macOS / Linux:** Open Terminal and run `python3 --version` to check what you have.

**Windows**

1. Download the source zip of the latest release from [Codeberg](https://codeberg.org/d-ranged/d-tach/releases) and extract it to a folder of your choice.
2. Double-click **`launch.bat`**.

On first run, the launcher checks your Python version, then installs all required dependencies automatically. This takes a few minutes and only happens once. On all future runs it starts immediately.

> **Python not installed yet?** The launcher will display a clear error message with a download link and step-by-step instructions. Install Python, then double-click `launch.bat` again.

**macOS / Linux**

1. Download the source zip of the latest release from [Codeberg](https://codeberg.org/d-ranged/d-tach/releases) and extract it to a folder of your choice.
2. Open Terminal, navigate to the extracted folder, and run:
   ```bash
   bash launch.sh
   ```

On first run, the launcher checks your Python version, installs all dependencies automatically, and opens the app in your browser. Subsequent runs start immediately. From then on, [First run](#first-run) above applies too.

> **Python not installed or too old?** The launcher will display a clear error message. Install Python 3.11+ and run `bash launch.sh` again.

> **Optional:** Run `chmod +x launch.sh` once if you prefer to launch with `./launch.sh` or by double-clicking the file in future.

> **macOS — Browse buttons not working?** If the Browse buttons are disabled, tkinter is not installed. Run `brew install python-tk@3.x` (replace `3.x` with your Python version, e.g. `python-tk@3.11`) and restart the launcher.

> **Linux — no tray icon?** GNOME shows no tray icons without an extension such as AppIndicator. d-tach still runs; open `http://localhost:5555` in your browser.

### Using the application

**Text mode**
1. Paste your text into the left panel.
2. Select the language. English and Dutch are available; you choose which to download the first time you run d-tach, and can add or remove languages later in Settings.
3. Adjust settings as needed — hashing, date anonymization, student number detection.
4. Click **Anonymize**. The result appears on the right.
5. Click **Copy** to copy it to the clipboard.

**Document mode**
1. Click **Browse…** to select a file or folder, or type the path directly.
2. Adjust settings as needed.
3. Click **Process**. Anonymized copies are saved to the same folder as the originals.

To anonymize only the names of files and folders — leaving what is inside them exactly as it is — tick **Rename names only**. Nothing is copied and no new folder is created; the names change where they stand. This is useful when a download from another system has put real names into the folder names themselves.

**Settings**

**Port.** Change the port d-tach listens on (default `5555`) — useful if another
application already uses that port, or your institution's firewall blocks it.
Changing the port requires restarting d-tach (quit and reopen from the tray icon)
to take effect.

**Languages.** Install or remove language models, and switch each one on or off.
Models are downloaded only when you ask for them, so you are not carrying the
memory cost of a language you never use. A language you install is switched on
and ready straight away, and removing or switching one off applies at once, with
no restart. Text and Document mode only offer the languages that are installed
and switched on. With the Lazy loading strategy a language is loaded the first
time a document needs it instead of at startup.

**Known values.** The list of names and numbers d-tach must always anonymize,
whether or not the language model recognises them. Add them one at a time, or
click **Import from class list** to point at an `.xlsx` roster: d-tach reads the
header row, you say which column is a name and which is an ID number, and every
row is added in one go. If the roster gains rows later, **Re-sync** re-reads the
same file and adds only what is new. Imported entries can be cleared on their own
without touching anything you typed in yourself.

**AI mode.** Off by default. See below before turning it on.

### AI mode

Working with an AI assistant on sensitive documents normally means a manual round
trip: anonymize the file, paste the result into the conversation, get feedback back
that refers to `PERSON_1`, then match every placeholder to a real name by hand. AI
mode removes that last step. The assistant talks to d-tach directly, and d-tach
does the anonymizing and the restoring on your machine.

The trust boundary does not move: **anonymization still happens locally, before any
text reaches a cloud model.** What changes is who does the copying.

How it works in practice:

1. Put the real files in one folder, exactly as you downloaded them, and run
   Document mode's **Rename names only** over it once. From then on the folder and
   file names are safe to look at.
2. Turn on AI mode in Settings. d-tach generates a token, and shows a block of
   instructions written for the assistant — copy it into the assistant's system
   prompt or project instructions.
3. The assistant lists the folder itself, but never opens a file. For each one it
   wants to read, it asks d-tach, and gets back the anonymized text only.
4. When the assistant has produced something that needs the real names back — a
   report, a marked-up document, a summary — d-tach substitutes them in and writes
   the file straight to disk. The assistant never receives the restored text; it
   writes a file it cannot read.
5. If the assistant spots a real name that slipped through, it tells d-tach, and
   that name is caught for every file after it.

Points worth knowing before you turn it on:

- AI mode is off until you switch it on, and the local API does not respond at all
  while it is off.
- Every request needs the token from Settings. Keep it out of anything you share.
- Images and scanned PDF pages have no text to extract. d-tach says so rather than
  passing them through silently — those need your own eyes.
- The key reference file is yours. It is the only thing that maps an anonymized
  name back to a real one, and the assistant is never given it.

### Send clipboard text to d-tach with a keyboard shortcut (optional)

`GET /text?q=your+text` opens Text Mode with `your text` already in the input
box. Combined with an OS-level keyboard shortcut, this lets you select text
anywhere, press a hotkey, and have it appear in d-tach ready to anonymize —
without switching windows and pasting manually. These are personal automation
scripts you set up yourself; d-tach does not install or manage them.

**Windows** — PowerShell + a shortcut file, no background process required:

```powershell
# d-anonymize.ps1
$text    = Get-Clipboard
if (-not $text -or $text.Trim() -eq "") { exit }
$encoded = [System.Uri]::EscapeDataString($text)
Start-Process "http://localhost:5555/text?q=$encoded"
```

Create a `.lnk` shortcut pointing to
`powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File "path\to\d-anonymize.ps1"`,
then assign a shortcut key (e.g. `Ctrl+Alt+A`) via the shortcut's Properties
dialog. Place the shortcut on the Desktop or in the Start Menu folder for the
hotkey to work system-wide.

**macOS** — shell script + a Keyboard Shortcuts / Automator entry:

```bash
#!/bin/bash
# d-anonymize.sh
TEXT=$(pbpaste)
[ -z "$TEXT" ] && exit
ENCODED=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.stdin.read()))" <<< "$TEXT")
open "http://localhost:5555/text?q=$ENCODED"
```

Run `chmod +x d-anonymize.sh`, then assign a shortcut in System Preferences →
Keyboard → Shortcuts → App Shortcuts (or wrap it in an Automator Quick Action
for a right-click Services menu entry instead of a keyboard shortcut).

**Linux** — shell script + a desktop environment shortcut:

```bash
#!/bin/bash
# d-anonymize.sh
if command -v wl-paste &>/dev/null; then
    TEXT=$(wl-paste)
else
    TEXT=$(xclip -selection clipboard -o 2>/dev/null)
fi
[ -z "$TEXT" ] && exit
ENCODED=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.stdin.read()))" <<< "$TEXT")
xdg-open "http://localhost:5555/text?q=$ENCODED"
```

Assign the shortcut via GNOME Settings → Keyboard → Custom Shortcuts, or KDE
System Settings → Shortcuts → Custom Shortcuts.

> If you changed the port in Settings, replace `5555` in the script with your
> configured port.

---

## Technical Setup

_For developers and IT-literate users who want to clone the repository and run from source._

### Prerequisites

- Python 3.11+
- Git

### Installation

```bash
git clone https://codeberg.org/d-ranged/d-tach.git
cd d-tach
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
python -m spacy download en_core_web_md
python -m spacy download nl_core_news_md
```

### Running

```bash
python tray.py
```

This is the normal launch path — it starts the Flask server and shows a
system tray icon. `run.py` (debug mode) and `serve.py` (no tray, no debug)
remain available for development. All three read the port from
`UserSettings`, or from the `DTACH_PORT` environment variable if set:

```bash
DTACH_PORT=5001 python run.py
```

Or double-click `launch.bat` (Windows) / run `./launch.sh` (macOS / Linux). Both launchers handle first-time setup automatically.

The app is available at `http://localhost:5555` by default (configurable in Settings).

### Running tests

```bash
pytest
```

### Building the packaged app

The Windows and Mac downloads are built with PyInstaller from `packaging/d-tach.spec`. From the repo root, in the venv:

```bash
pip install -r packaging/requirements-build.txt
pyinstaller packaging/d-tach.spec --noconfirm
python packaging/smoke_test.py dist/d-tach/d-tach.exe
```

That builds for the machine you run it on: `dist/d-tach/` on Windows, `dist/d-tach.app` on macOS (smoke test `dist/d-tach.app/Contents/MacOS/d-tach`). PyInstaller cannot build for another platform. The smoke test starts the build on its own port and data folder, downloads English and anonymizes one line.

Releases are built by GitHub Actions (`.github/workflows/build.yml`) on the GitHub mirror. Pushing a `v*` tag to Codeberg reaches GitHub through the mirror, builds Windows and Apple Silicon Mac, and attaches both zips to a GitHub release for that tag. A tag with a dash, such as `v1.4.0-test.1`, makes a pre-release. The app icons are built from `app/static/d-logo.png` by `tools/build_icons.py`.

### Project structure

```
d-tach/
├── app/
│   ├── routes/          # Flask blueprints (text, document, browse, settings, restore, ai)
│   ├── services/        # Business logic (Anonymizer, FileProcessor, etc.)
│   ├── static/          # CSS and JavaScript
│   └── templates/       # HTML templates
├── tests/
├── docs/                # project_guide.md, original_steps.md, roadmap.md, step files
├── packaging/           # PyInstaller spec, app icons, smoke test for the packaged build
├── tools/               # Scripts that rebuild the word lists and the app icons
├── .github/workflows/   # Packaged builds on GitHub Actions
├── launch.bat           # Windows launcher (auto-setup on first run)
├── launch.sh            # macOS / Linux launcher (auto-setup on first run)
├── tray.py              # Normal launch path — Flask + system tray icon
├── run.py               # Development entry point (debug mode)
├── serve.py             # Development entry point (no debug, no tray)
└── requirements.txt
```

### Architecture notes

- **No logic in routes.** Routes receive a request, call a service method, and return a response.
- **Anonymizer** wraps Microsoft Presidio with English and Dutch spaCy models.
- **FileProcessor** handles a single file; **FolderProcessor** handles recursive batch runs.
- **UserSettings** persists preferences to `user_settings.json` in the per-user data folder (`%LOCALAPPDATA%\d-tach`, `~/Library/Application Support/d-tach` or `~/.local/share/d-tach`), with the downloaded language models and the log file. `DTACH_DATA_DIR` overrides the folder.
- **HashEncoder** provides optional consistent pseudonymization using a user-supplied secret as salt.

See `docs/project_guide.md` for full design decisions and `docs/original_steps.md` for the build plan.

---

## Authors

- **Craig Bradley** — creator and maintainer
- **Claude Sonnet 4.6** (Anthropic) — AI pair-programmer
