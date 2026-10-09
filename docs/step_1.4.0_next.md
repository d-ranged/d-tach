# step_1.4.0_next.md — d-tach v1.4.0 Build Plan

This document breaks the v1.4.0 planned work into ordered, testable steps.
Each step should map to one or more Codeberg issues created before starting.

Consult `roadmap.md` for background context.
Consult `project_guide.md` for architectural decisions and documented alternatives.
Consult `step_1.3.0_next.md` for the acceptance-run defect log these items came out of.

**Do not start until v1.3.0 has shipped.**

---

## Status at a Glance

| Step | Description | Status |
|---|---|---|
| 0 | Fixes from the tutorial dry run (8-10-2026), plus the class list name columns | ⬜ Not started |
| 1 | `/ai/restore` accepts a KEYREF file, not just a live session | ⬜ Not started |
| 2 | OCR fallback for image-based PDFs. Moved to v1.5.0 on 9-10-2026, [#78](https://codeberg.org/d-ranged/d-tach/issues/78) | ➡️ Moved |
| 3 | Standalone packaged installer (PyInstaller) | ⬜ Not started |

Steps 1 and 2 came out of the v1.3.0 Step 6 acceptance run (25-8-2026). Step 3 was
already committed to v1.4.0 in `roadmap.md` and is carried here unchanged.

---

## Background

Two gaps surfaced during the v1.3.0 acceptance run, both while doing a real piece of
work rather than a feature checklist. Neither blocked the release; both cost the tester
time and one of them nearly produced a wrong output.

**Restore is trapped inside a session.** `/ai/restore` can only reverse placeholders
that the same `/ai/extract` call created. Compose a document from two source files and
only one of them can be restored. Come back to an anonymized file a week later and
nothing can be restored at all, even though Document Mode exported a perfectly good
KEYREF CSV at the time. Document Mode's `/restore` already takes that CSV — AI Mode
simply never learned to.

**An unreadable PDF stops the work dead.** v1.3.0 correctly refuses to write a PDF it
could not read, which is the right call (see Step 2's design note). But the file still
has to be dealt with, and the tester ends up doing by hand what the tool exists to do.
Scanned letters and signed declarations are exactly the documents that carry the most
sensitive content, so this is not an edge case.

## Step 0 — Fixes From the Tutorial Dry Run

**Codeberg issues:** [#72](https://codeberg.org/d-ranged/d-tach/issues/72) (0a), [#73](https://codeberg.org/d-ranged/d-tach/issues/73) (0b), [#74](https://codeberg.org/d-ranged/d-tach/issues/74) (0c), [#75](https://codeberg.org/d-ranged/d-tach/issues/75) (0d), [#76](https://codeberg.org/d-ranged/d-tach/issues/76) (0e)

Found 8-10-2026 while dry-running the usage-video demo kit through v1.3.0
(`d-ranged/tutorials/d-tach/demo/build_demo.py` in d-workspace rebuilds it). The video
runbook currently steers around each of these. All four reproduced again on main 9-10-2026.
The issues hold the full reproduction and the fix direction.

| # | Defect | Reproduce | Likely cause |
|---|---|---|---|
| 0a | Output files renamed twice: `progress_[[L-ISB7_3PIB]].pdf` | Document Mode, subfolder output, hashing on, Check file and folder names on | Filename pass re-wraps a name that is already a placeholder, as body text did before issue #64 |
| 0b | Folder KEYREF is ambiguous without hashing | Document Mode on a folder, hashing off, Key reference on | Sequential numbering restarts per file, so one KEYREF maps `[PERSON_2]` to two people. Restore from it is then wrong |
| 0c | A name at the end of a line swallows the next line's first word | `Joris van Dijk` at a line end, `Guide` starting the next line, became one PERSON | Entity span crosses a newline. Trim spans at the first line break |
| 0d | A lone first name is missed in one file and caught in another | Class list holds `Lotte Vermeulen`. NER catches `Lotte` alone in the DOCX, the PDF line `Lotte is on track.` stays in the clear | NER is inconsistent on lone first names. Known values work as designed, see below |

0d is not a known-values bug. Class lists deliberately leave out the first-name column,
because short first names (An, En, El) match far too much ordinary text. Lone first names
are left to NER, which misses some. Agreed fix, 9-10-2026: when a document contains a full
name that was replaced, also match that name's first word on its own, in the same document
only, under the same rules as 0e below, so a lone name is treated one way whatever its
source. The source is every full name replaced in the document, known values and NER
alike (option B, decided 9-10-2026 in #75). Build 0e's rule first and call it from 0d.

0e, added 9-10-2026, is the feature that makes the first-name column safe to import.
Name columns become First name, Surname and Full name, and each student gives all three,
built or split when a column is missing. A first name or surname on its own is never
matched at 2 letters or fewer. One that is also an ordinary word (Will, Mark) only matches
with a capital. Every other name matches case-insensitively, as today. Detail in #76,
rules corrected by Craig 9-10-2026. 0d covers a lone
first name after the full name, 0e one in a document where the full name never appears.

**Tutorial impact.** The usage video keeps Check file and folder names off because of 0a.
On v1.3.0 the AI-mode extract shows `Lotte is on track` in the clear because of 0d. 0e changes the class list
import in Part 1. Each changes the
runbook (`d-ranged/tutorials/d-tach/usage-runbook.md` in d-workspace). Re-check it before
recording on v1.4.0.

### ✅ Complete when

- The four reproductions above (0a to 0d) give clean output on the demo kit.
- The class list cases in #76 pass (0e).
- Each fix has a regression test.

---

## Step 1 — `/ai/restore` Accepts a KEYREF File

**Codeberg issue:** [#77](https://codeberg.org/d-ranged/d-tach/issues/77)

### Background

`POST /ai/restore` requires a `session_id` and reads its replacement map from that
session alone. Sessions expire (`ai_session_timeout_minutes`), so the map is gone
within the hour, and it only ever described one document.

Document Mode already solves the durable half of this: with **Key reference** enabled
a run writes a `KEYREF_*.csv` next to its output, and `POST /restore` takes a
`keyref_path` and restores a whole file from it. The data is already in the right
shape. AI Mode just cannot read it.

### What this unblocks

- Composing one output from several source documents — currently only one document's
  placeholders survive the restore, and the rest are written out as raw tokens.
- Restoring an anonymized document in a later session, when the KEYREF was kept.
- Recovering when a session expires mid-task, without re-extracting the source and
  hoping the tokens come back identical.

### Design

Add an optional `keyref_path` to `POST /ai/restore`:

| Body | Behaviour |
|---|---|
| `session_id` only | Unchanged — restores from the live session map |
| `session_id` + `keyref_path` | Both maps merged; the session wins on conflict |
| `keyref_path` only | Restores from the CSV alone; no session required |
| Neither | 400, as now |

**Session wins on conflict** because it was produced by the document actually in hand,
while a KEYREF may be older and may have been written under a different secret.

Reuse the existing CSV reader rather than writing a second one. `restore_routes.py`
already parses KEYREF files for `POST /restore`; lift that into a shared helper so
exactly one implementation exists — the same rule `compose_replacements` follows.

Keep `output_path` working exactly as it does now. The privacy property that makes AI
Mode usable is that restored text can be written straight to disk without ever passing
back through the caller, and that must survive this change untouched.

### What to build

| Component | Description |
|---|---|
| KEYREF reader | Lift CSV parsing out of `restore_routes.py` into a shared service function |
| `ai_routes.restore` | Accept `keyref_path`; merge maps; relax the `session_id` requirement |
| Error handling | 404 for a missing file, 400 for an unparseable one — match `/restore`'s wording |
| Agent instructions | Update the generated AI Mode instructions in Settings to mention it |
| Tests | Merge precedence, keyref-only restore, missing file, malformed CSV, `output_path` still writes |

### A note on the alternative

A persistent local placeholder history in Settings was considered and **rejected for
now**. It would remove the need to pass a KEYREF at all, but it creates a single file
that maps every placeholder d-tach has ever produced back to a real name. That file
undoes the entire tool if it leaks, and it accumulates silently rather than by a
deliberate act. The CSV-per-run model keeps that decision in the user's hands each
time. Revisit only if the manual step proves to be the thing stopping people using
restore at all.

### ✅ Complete when

- An output composed from two extracted documents restores every placeholder from both.
- A file anonymized in an earlier session restores from its KEYREF with no live session.
- `output_path` still writes restored text straight to disk and returns no content.

---

## Step 2 — OCR Fallback for Image-Based PDFs

**Moved to v1.5.0 on 9-10-2026.** It is a piece of work on its own, with more to sort out
than fits v1.4.0. The full design (quarantined output, AI Mode warning, engine choice,
bounding boxes for later redaction) now lives in
[#78](https://codeberg.org/d-ranged/d-tach/issues/78), open to contributors. Copy it into
`step_1.5.0_next.md` when that file is started.

---

## Step 3 — Standalone Packaged Installer (PyInstaller)

**Codeberg issue:** _create before starting_

Carried unchanged from `roadmap.md`. v1.3.0's on-demand language download makes this
feasible: the binary ships without models, at an estimated 80–150 MB, small enough for
Codeberg's free storage tier without a quota increase.

- **Target audience:** users without Python experience who cannot or will not run the
  launcher scripts.
- **Known challenges:** Flask static file paths under `sys._MEIPASS`, `tkinter`
  bundling on macOS, confirming actual binary size on a clean build.
- **Platforms:** Windows, macOS and Linux, decided 9-10-2026. Craig's laptop builds
  Windows only, so the other two need CI. Mac colleagues test the macOS build.
- **OCR:** moved to v1.5.0 (#78), so it does not affect this build. Whoever takes #78
  must check its engine against the packaged build.

See `roadmap.md` for the original planning note.

---

## Carried From the v1.3.0 Acceptance Run — Not Yet Scoped

Observations logged during Step 6 that are real but did not warrant fixing in a
patch release. Confirm each is still reproducible before scoping.

- **PDF extraction mangles typographic apostrophes.** `pymupdf` renders `’` as U+FFFD,
  so extracted text reads "Saxion�s" and "the IND�s". Output quality, not privacy.
- **Inconsistent detection of a repeated organisation name.** In one acceptance
  document an organisation was hashed in most positions but appeared in the clear in a
  possessive form. 🟠 May share a root cause with defect 11 (possessive spans); needs a
  reproduction before it can be called.
- **`expand_archives_enabled` is dead config.** Read nowhere. Remove it or wire it up.
- **Short and dictionary-word known values.** A roster containing a surname that is
  also a common word matches far too much. Flag these at import time rather than
  letting the user discover it in the output.
- **Case sensitivity should differ for body text and filenames.** One setting currently
  governs both, and the right answer is not the same for each.
- **Single-token PERSON detection against a surname-only roster.** When the imported
  roster holds surnames only, a lone detected token is more likely a surname than a
  first name, and the placeholder should reflect that.
- **Tutorial / help affordance.** There is no in-app explanation of what the modes are
  for. New users have to be told.

---

## Backlog — Explicitly Not v1.4.0

- Interface translation (i18n). Significant scope, touches every template string.
  Revisit when there are real non-English-speaking users asking for it.
- Batch summary log — machine-readable JSON/CSV run summary written to the processed
  folder.

Both are described in `roadmap.md`.
