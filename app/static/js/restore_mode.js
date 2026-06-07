"use strict";

const inputPathInput   = document.getElementById("input-path");
const keyrefPathInput  = document.getElementById("keyref-path");
const browseInputBtn   = document.getElementById("browse-input-btn");
const browseKeyrefBtn  = document.getElementById("browse-keyref-btn");
const browseInputNote  = document.getElementById("browse-input-note");
const browseKeyrefNote = document.getElementById("browse-keyref-note");
const restoreBtn       = document.getElementById("restore-btn");
const restoreResult    = document.getElementById("restore-result");

// ---------------------------------------------------------------------------
// tkinter availability check
// ---------------------------------------------------------------------------

(async function checkBrowseAvailable() {
    try {
        const resp = await fetch("/browse/status");
        const data = await resp.json();
        if (!data.available) disableBrowseButtons();
    } catch (_) { /* leave buttons visible */ }
})();

function disableBrowseButtons() {
    browseInputBtn.hidden  = true;
    browseInputNote.hidden = false;
    browseKeyrefBtn.hidden  = true;
    browseKeyrefNote.hidden = false;
}

// ---------------------------------------------------------------------------
// Browse buttons
// ---------------------------------------------------------------------------

browseInputBtn.addEventListener("click", async () => {
    browseInputBtn.disabled = true;
    try {
        const resp = await fetch("/browse/file");
        const data = await resp.json();
        if (data.tkinter_unavailable) { disableBrowseButtons(); }
        else if (data.path) { inputPathInput.value = data.path; }
    } catch (_) { /* silent */ } finally {
        browseInputBtn.disabled = false;
    }
});

browseKeyrefBtn.addEventListener("click", async () => {
    browseKeyrefBtn.disabled = true;
    try {
        const resp = await fetch("/browse/csv");
        const data = await resp.json();
        if (data.tkinter_unavailable) { disableBrowseButtons(); }
        else if (data.path) { keyrefPathInput.value = data.path; }
    } catch (_) { /* silent */ } finally {
        browseKeyrefBtn.disabled = false;
    }
});

// ---------------------------------------------------------------------------
// Restore
// ---------------------------------------------------------------------------

restoreBtn.addEventListener("click", runRestore);
inputPathInput.addEventListener("keydown", e => { if (e.key === "Enter") runRestore(); });

async function runRestore() {
    const inputPath  = inputPathInput.value.trim();
    const keyrefPath = keyrefPathInput.value.trim();

    if (!inputPath)  { setResult("Enter a path to the anonymized file.", true); return; }
    if (!keyrefPath) { setResult("Enter a path to the KEYREF CSV file.", true); return; }

    restoreBtn.disabled = true;
    setResult("Restoring…");

    try {
        const resp = await fetch("/restore/run", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ input_path: inputPath, keyref_path: keyrefPath }),
        });
        const data = await resp.json();
        if (data.error) {
            setResult(data.error, true);
        } else {
            const countLabel = data.replacements_made === 1
                ? "1 unique value restored"
                : `${data.replacements_made} unique value(s) restored`;
            const lines = [
                `✔ ${countLabel}.`,
                `Output: ${data.output_path}`,
            ];
            setResult(lines.join("\n"), false);
        }
    } catch (_) {
        setResult("Restore failed — please try again.", true);
    } finally {
        restoreBtn.disabled = false;
    }
}

function setResult(message, isError = false) {
    restoreResult.textContent = message;
    restoreResult.className = "summary-area" + (isError ? " area-error" : "");
}
