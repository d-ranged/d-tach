# d-tach — Video Tutorial Script

**Format:** Screen recording with voiceover. Short and punchy. No fluff.
**Target:** Colleagues who review student documents and need GDPR compliance without IT support.
**Tone:** Professional, direct, warm. One sentence per beat — pause, show, move on.

---

## Opening (0:00 – 0:15)

*Show: app running in browser, clean landing page.*

> "You've got a student document. It has a name, a student number, an email address.
> You need to share it for review — but GDPR says you can't send personal data.
> d-tach fixes that in under a minute, on your own machine, nothing sent anywhere."

---

## Beat 1 — Text Mode, the quick demo (0:15 – 1:00)

*Show: Text Mode open. Paste a short paragraph with a name and email.*

> "Paste your text here."

*Paste. Output appears immediately.*

> "Done. The name is gone. The email is gone. Replaced with consistent labels."

*Point to the key reference table.*

> "The key reference tells you exactly what was replaced and what it maps to.
> Export it as a CSV if you need a record."

*Point to the copy button.*

> "Copy the anonymized text. Paste it into your review tool. That's it."

---

## Beat 2 — Settings (1:00 – 1:30)

*Show: toggle Anonymize dates on. Result updates.*

> "Dates off by default — they're usually not sensitive. Toggle them on if you need to."

*Show: Enable hashing, type a secret.*

> "Hashing gives you consistent pseudonyms across documents.
> Same person, same secret, always the same code — across every file, every session."

*Show: the hash output — `[Cr-A2T5 HY23]` style.*

> "Reversible by the holder of the secret. Useful for tracking without exposing names."

---

## Beat 3 — Document Mode, single file (1:30 – 2:15)

*Show: switch to Document Mode tab.*

> "Got a Word document or PDF? Switch to Document Mode."

*Browse to a DOCX file.*

> "Browse to your file — or paste the path directly."

*Click Process File. Progress appears. Result shown.*

> "Anonymized file saved alongside the original. Prefixed ANON — nothing overwritten."

*Show the output DOCX opened.*

> "Open it. Names gone. Structure intact. Formatting preserved."

---

## Beat 4 — Folder Mode (2:15 – 2:50)

*Show: switch to Folder tab. Point to the Browse folder button.*

> "Whole folder? One click."

*Select the test folder. Progress bar fills. Log entries tick by.*

> "Every DOCX, PDF, Markdown, and Excel file — processed in one run.
> Clean files get CHECKED_. Files with PII get ANON_."

*Show: choose Subfolder mode radio button.*

> "Subfolder mode puts everything into an anonymized/ folder —
> originals untouched, output clean and separate, ready to hand over."

---

## Beat 5 — Excel (2:50 – 3:20)

*Show: Advanced Settings panel open. Excel section visible.*

> "Excel files work too. NER picks up names and emails in text cells."

*Show: column names field, type 'stnum'.*

> "Got a student number column? Tell it the column name.
> Every value in that column — replaced. Even if it's an integer."

---

## Beat 6 — The guarantee (3:20 – 3:40)

*Show: nothing in the network tab of dev tools — or simply state it.*

> "One thing worth saying clearly:
> d-tach makes no network calls. Nothing is uploaded. Nothing is logged.
> Your documents stay on your machine from start to finish."

---

## Closing — Install (3:40 – 4:00)

*Show: Codeberg release page briefly.*

> "Download from Codeberg — link in the description.
> Windows: double-click launch.bat. First run installs everything automatically.
> Browser opens, you're ready to go."

*Show: app open and ready.*

> "d-tach. GDPR-ready document review. Free and open source."

---

## Install steps (on-screen card at end)

```
1. Download the release zip from Codeberg
2. Unzip anywhere
3. Double-click launch.bat  (Windows)
        or  bash launch.sh  (Mac / Linux)
4. Browser opens at http://localhost:5000
5. Done — no account, no cloud, no data leaving your machine
```

---

*Script version: v1.1.0 — 2026-04-28*
