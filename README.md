# d-tach

**d-tach** anonymizes names, contact details, and other personal data from text, Word documents, PDFs, and Markdown files before you share them for review or assessment.

Everything runs locally on your machine. No files or text are ever sent anywhere.

[![Version](https://img.shields.io/badge/version-1.0.0-blue)](https://codeberg.org/d-craig/d-tach/releases)
&nbsp;
[![License: EUPL-1.2](https://img.shields.io/badge/license-EUPL--1.2-green)](LICENSE)

[⬇ Download Latest Release](https://codeberg.org/d-craig/d-tach/releases)

---

**Jump to:** [Download to Use](#download-to-use) · [Technical Setup](#technical-setup)

---

## Download to Use

_For educators, assessors, and colleagues who want to use the application without a technical background._

### What it does

Paste text or select a document and d-tach replaces personal details — names, email addresses, phone numbers, student numbers, and more — with neutral placeholders such as `PERSON_1` or `EMAIL_ADDRESS_1`. The original file is never touched; a new anonymized copy is saved alongside it.

You choose:
- **Text mode** — paste text directly and copy the anonymized result.
- **Document mode** — select a single file or an entire folder; anonymized copies are saved in the same location with an `ANON_` prefix (or `CHECKED_` if no personal data was found).

A key reference file can be generated alongside the output so the anonymization can be reversed if needed.

### What it does not do

- It does not send your data anywhere. There is no internet connection, no account, and no telemetry.
- It is not 100% accurate. Always review the output before sharing. A disclaimer is shown in the application as a reminder.

### Prerequisites

You need **Python 3.11 or newer** installed on your machine. This is a one-time requirement.

- **Windows:** Download from [python.org/downloads](https://www.python.org/downloads/). During installation, tick **"Add Python to PATH"**.
- **macOS:** Python is often pre-installed. Open Terminal and run `python3 --version` to check.

### Installation and first run (Windows)

1. Click **[⬇ Download Latest Release](https://codeberg.org/d-craig/d-tach/releases)**, select the most recent release, and download the source zip. Extract it to a folder of your choice.
2. Double-click **`launch.bat`**.

On first run, the launcher installs all required dependencies automatically. This takes a few minutes and only happens once. On all future runs it starts immediately.

A browser window will open at `http://localhost:5000`. Keep the terminal window open while you use the application — closing it stops the server.

### Installation and first run (macOS / Linux)

1. Click **[⬇ Download Latest Release](https://codeberg.org/d-craig/d-tach/releases)**, select the most recent release, and download the source zip. Extract it to a folder of your choice.
2. Open Terminal, navigate to the extracted folder, and make the launcher executable (one time only):
   ```bash
   chmod +x launch.sh
   ./launch.sh
   ```

On first run, dependencies are installed automatically. Subsequent runs start immediately.

### Using the application

**Text mode**
1. Paste your text into the left panel.
2. Select the language (EN or NL).
3. Adjust settings as needed — hashing, date anonymization, student number detection.
4. Click **Anonymize**. The result appears on the right.
5. Click **Copy** to copy it to the clipboard.

**Document mode**
1. Click **Browse…** to select a file or folder, or type the path directly.
2. Adjust settings as needed.
3. Click **Process**. Anonymized copies are saved to the same folder as the originals.

---

## Technical Setup

_For developers and IT-literate users who want to clone the repository and run from source._

### Prerequisites

- Python 3.11+
- Git

### Installation

```bash
git clone https://codeberg.org/d-craig/d-tach.git
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
python run.py
```

Or double-click `launch.bat` (Windows) / run `./launch.sh` (macOS / Linux). Both launchers handle first-time setup automatically.

The app is available at `http://localhost:5000`.

### Running tests

```bash
pytest
```

### Project structure

```
d-tach/
├── app/
│   ├── routes/          # Flask blueprints (text, document, browse)
│   ├── services/        # Business logic (Anonymizer, FileProcessor, etc.)
│   ├── static/          # CSS and JavaScript
│   └── templates/       # HTML templates
├── tests/
├── docs/                # PROJECT_GUIDE.md, STEP_GUIDE.md
├── launch.bat           # Windows launcher (auto-setup on first run)
├── launch.sh            # macOS / Linux launcher (auto-setup on first run)
├── run.py               # Application entry point
└── requirements.txt
```

### Architecture notes

- **No logic in routes.** Routes receive a request, call a service method, and return a response.
- **Anonymizer** wraps Microsoft Presidio with English and Dutch spaCy models.
- **FileProcessor** handles a single file; **FolderProcessor** handles recursive batch runs.
- **UserSettings** persists preferences to a local `user_settings.json` (gitignored).
- **HashEncoder** provides optional consistent pseudonymization using a user-supplied secret as salt.

See `docs/PROJECT_GUIDE.md` for full design decisions and `docs/STEP_GUIDE.md` for the build plan.

---

## Authors

- **Craig Bradley** — creator and maintainer
- **Claude Sonnet 4.6** (Anthropic) — AI pair-programmer
