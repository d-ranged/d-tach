# Contributing to d-tach

Thank you for your interest in contributing. This document explains how to
report bugs, suggest features, and submit code changes.

---

## The non-negotiable rule: nothing goes online at runtime

d-tach is a privacy-first tool. Its core guarantee is that **no personal data
ever leaves the user's machine during operation**.

This means:

- No HTTP calls from application code at runtime, ever.
- No telemetry, analytics, error reporting, or usage tracking.
- No calls to external APIs, language models, or cloud services.
- No "phone home" behaviour of any kind.

Any pull request that adds a runtime network call will be closed without merge,
regardless of how useful the feature might otherwise be. If you want to propose
a feature that would require network access, open an issue first to discuss an
offline-compatible alternative.

---

## Reporting bugs

Open an issue on [Codeberg](https://codeberg.org/d-craig/d-tach/issues) and include:

- What you expected to happen.
- What actually happened (include the exact error message if there is one).
- Steps to reproduce, as minimal as possible.
- Your operating system, Python version (`python --version`), and how you
  installed the application (launcher script or manual setup).

If the issue involves a specific document type or language, note that too.
Do **not** attach documents containing real personal data — create a minimal
example with fake names instead.

---

## Suggesting features

Open an issue before writing any code. This prevents duplicate work and ensures
the feature fits the project's direction. The issue should explain:

- What problem the feature solves.
- Who it helps (which type of user, which workflow).
- Any alternative approaches you considered.

Small, well-scoped features are much more likely to be merged than large ones.

---

## Submitting code

### Setup

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

### Branch naming

```
feature/issue-{number}-{short-description}
fix/issue-{number}-{short-description}
chore/issue-{number}-{short-description}
```

Always branch from `main`.

### Making changes

- One pull request per issue. Keep changes focused.
- Do not bundle unrelated fixes into one PR.
- Reference the issue in every commit message: `Description of change (issue #N)`.

### Before opening a pull request

1. Run the full test suite and confirm it passes:
   ```bash
   pytest
   ```
2. If you added a new feature, add tests for it.
3. If you fixed a bug, add a test that would have caught it.

### Pull request requirements

Your PR description must include:

- **What** was changed, in plain language.
- **Why** the change was necessary (link to the issue).
- **How** you tested it (what you ran, what you checked).
- `Closes #N` so the issue closes automatically on merge.

Example PR body:
```
Fixes a crash when processing a DOCX file containing only a table with no
paragraph content. The anonymizer received an empty string and raised a
ValueError.

Added a guard in `_process_docx` to return a clean result immediately when
extracted text is empty. Added a test case with a table-only fixture.

Closes #42
```

PRs that say only "fixed the bug" or "added the feature" will be sent back
for a more complete description.

### Code conventions

These match the conventions in `CLAUDE.md`:

- **Type hints** on every function and method signature.
- **Docstrings** on every class and every public method (one-line minimum).
- **No logic in Flask routes** — routes call service methods and return responses.
- **No silent exception swallowing** — log with enough context to diagnose and re-raise or return a meaningful error.
- **No magic numbers or hardcoded strings** — use constants.
- **No runtime network calls** — see the rule at the top of this document.
- **Short methods** — if a method does more than one thing, split it.
- Class names: `PascalCase`. Functions and methods: `snake_case`. Constants: `UPPER_SNAKE_CASE`.

### Review process

All pull requests require approval from **d-craig** (maintainer) before merge.
The `main` branch is protected — no direct pushes are accepted.

Reviews typically check:
- Does the code follow the conventions above?
- Are there tests covering the new behaviour?
- Does the PR description explain the change clearly?
- Does anything in this change risk sending data over the network?

If the review requests changes, push additional commits to the same branch —
do not close and reopen the PR.

---

## Setting up branch protection on Codeberg (maintainers)

To protect `main` so that only pull requests (approved by the maintainer) can be merged:

1. Go to the repository on Codeberg.
2. **Settings → Branches → Add rule**.
3. Fill in the form as follows:

   | Field | Value |
   |---|---|
   | Protected branch name pattern | `main` |
   | Push | **Whitelist restricted push** → add `d-craig` |
   | Required approvals | `1` |
   | Restrict approvals to whitelisted users | ✅ tick → add `d-craig` |
   | Dismiss stale approvals | ✅ tick |
   | Block merge on rejected reviews | ✅ tick |
   | Pull request merge | **Enable merge whitelist** → add `d-craig` |

4. Save the rule.

**Why whitelist restricted push rather than disable push entirely?**
Disabling push completely would also block pushing version tags for releases.
Whitelisting the maintainer preserves that workflow while preventing contributors
from pushing directly to `main`.

**Note — enabling Releases on Codeberg:**
Releases is not enabled by default. Go to **Settings → Units** and tick the
**Releases** checkbox. A Releases tab will then appear on the repository page,
where you can create releases from existing tags.

---

## Trusted contributors

At the time of the v1.0.0 release, d-craig is the sole maintainer. As the
community grows, trusted contributors may be added to the review rotation.
This will be announced in the repository and documented here.

---

## Code of conduct

Be constructive and respectful. Feedback on code is not feedback on people.
Issues and pull requests that are hostile, dismissive, or off-topic will be closed.