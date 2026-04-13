# d-tach

**d-tach** anonymizes names, contact details, and other personal data from text, Word documents, and PDFs before you share them for review or assessment.

Everything runs locally on your machine. No files or text are ever sent anywhere.

Licensed under [EUPL-1.2](LICENSE).

---

**Jump to:** [Download to Use](#download-to-use) · [Technical Setup](#technical-setup)

---

## Download to Use

_For educators, assessors, and colleagues who want to use the application without a technical background._

### What it does

Paste text or select a document and d-tach replaces personal details — names, email addresses, phone numbers, student numbers, and more — with neutral placeholders such as `PERSON_1` or `EMAIL_ADDRESS_1`. The original file is never touched; a new anonymized copy is saved alongside it.

You choose:
- **Text mode** — paste text directly and copy the anonymized result.
- **Document mode** — select a single file or an entire folder; anonymized copies are saved in the same location.

A key reference file can be generated so you can reverse the anonymization if needed.

### What it does not do

- It does not send your data anywhere. There is no internet connection, no account, and no telemetry.
- It is not 100% accurate. Always review the output before sharing. A disclaimer is shown in the application as a reminder.

### Prerequisites

You need **Python 3.11 or newer** installed on your machine.

- **Windows:** Download from [python.org/downloads](https://www.python.org/downloads/). During installation, tick **"Add Python to PATH"**.
- **macOS / Linux:** Python is often pre-installed. Open a terminal and run `python3 --version` to check.

### Setup (Windows)

Do this once, the first time you use d-tach.

1. Download the repository as a zip file from Codeberg and extract it to a folder of your choice.

2. Open the extracted folder. You should see files including `launch.bat`, `run.py`, and `requirements.txt`.

3. Open **Command Prompt** in that folder:
   - Hold **Shift** and right-click inside the folder.
   - Choose **"Open PowerShell window here"** or **"Open command window here"**.

4. Run the following commands one at a time, pressing Enter after each:

   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   python -m spacy download en_core_web_md
   python -m spacy download nl_core_news_md
   ```

   This takes a few minutes the first time. It only needs to be done once.

5. Once complete, close the command window.

### Setup (macOS / Linux)

Do this once, the first time you use d-tach.

1. Download the repository as a zip file and extract it to a folder of your choice.

2. Open a terminal and navigate to the extracted folder:
   ```bash
   cd /path/to/d-tach
   ```

3. Run the following commands one at a time:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python -m spacy download en_core_web_md
   python -m spacy download nl_core_news_md
   ```

   Make the launcher script executable (one time only):
   ```bash
   chmod +x launch.sh
   ```

### Starting the application

**Windows:** Double-click `launch.bat` in the d-tach folder.

**macOS / Linux:** Double-click `launch.sh`, or run `./launch.sh` from a terminal.

A browser window will open automatically at `http://localhost:5000`. Keep the terminal window open while you use the application — closing it will stop the server.

To stop the application, close the terminal window or press **Ctrl + C** inside it.

### Using the application

**Text mode**
1. Paste your text into the left panel.
2. Select the language (EN or NL).
3. Adjust settings as needed (hashing, date anonymization, student number detection).
4. Click **Anonymize**. The result appears on the right.
5. Click **Copy** to copy it to the clipboard.

**Document mode**
1. Click **Browse…** to select a file or folder, or type the path directly.
2. Adjust settings as needed.
3. Click **Process**. Anonymized copies are saved in the same folder as the originals with an `ANON_` prefix, or `CHECKED_` if no personal data was found.

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

Or double-click `launch.bat` (Windows) / `launch.sh` (macOS / Linux).

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
├── launch.bat           # Windows launcher
├── launch.sh            # macOS / Linux launcher
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
