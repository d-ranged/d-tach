"use strict";

const filePathInput  = document.getElementById("file-path");
const processBtn     = document.getElementById("process-btn");
const hashingToggle  = document.getElementById("hashing-toggle");
const secretField    = document.getElementById("secret-field");
const secretInput    = document.getElementById("secret-input");
const keyrefToggle   = document.getElementById("keyref-toggle");
const namesToggle    = document.getElementById("names-toggle");
const datesToggle    = document.getElementById("dates-toggle");
const langSelector   = document.getElementById("lang-selector");
const progressArea   = document.getElementById("progress-area");
const summaryArea    = document.getElementById("summary-area");

let selectedLanguage = INITIAL_LANGUAGE;

// ---------------------------------------------------------------------------
// Language selector
// ---------------------------------------------------------------------------

langSelector.addEventListener("click", (e) => {
    const btn = e.target.closest(".lang-btn");
    if (!btn) return;
    selectedLanguage = btn.dataset.lang;
    langSelector.querySelectorAll(".lang-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
});

// ---------------------------------------------------------------------------
// Process button
// ---------------------------------------------------------------------------

processBtn.addEventListener("click", runProcess);

filePathInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") runProcess();
});

async function runProcess() {
    const filePath = filePathInput.value.trim();
    if (!filePath) {
        setProgress("Enter a file path to process.");
        return;
    }

    if (hashingToggle.checked && !secretInput.value.trim()) {
        setProgress("Enter a secret phrase to use hashing.");
        return;
    }

    setProgress("Processing\u2026");
    setSummary("");
    processBtn.disabled = true;

    try {
        const response = await fetch("/document/process-file", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                file_path: filePath,
                language: selectedLanguage,
                hashing_enabled: hashingToggle.checked,
                secret: secretInput.value,
                key_reference_enabled: keyrefToggle.checked,
                check_file_names: namesToggle.checked,
                anonymize_dates: datesToggle.checked,
            }),
        });

        const data = await response.json();

        if (data.error) {
            setProgress(data.error, true);
        } else {
            setProgress("Done.");
            renderResult(data);
        }
    } catch {
        setProgress("Processing failed \u2014 please try again.", true);
    } finally {
        processBtn.disabled = false;
    }
}

// ---------------------------------------------------------------------------
// Result rendering
// ---------------------------------------------------------------------------

function renderResult(data) {
    const lines = [];

    if (data.status === "anonymized") {
        lines.push(`\u2714 Anonymized \u2014 ${data.entities_found} unique value(s) replaced.`);
        lines.push(`Output: ${data.output_path}`);
        if (data.keyref_path) {
            lines.push(`Key reference: ${data.keyref_path}`);
        }
    } else if (data.status === "clean") {
        lines.push(`\u2714 No PII detected \u2014 file copied with CHECKED_ prefix.`);
        lines.push(`Output: ${data.output_path}`);
    } else if (data.status === "skipped") {
        lines.push(`\u26A0 Skipped: ${data.error_message}`);
    } else {
        lines.push(`\u2718 Error: ${data.error_message}`);
    }

    setSummary(lines.join("\n"), data.status === "error" || data.status === "skipped");
}

function setProgress(message, isError = false) {
    progressArea.textContent = message;
    progressArea.className = "progress-area" + (isError ? " area-error" : "");
}

function setSummary(message, isError = false) {
    if (!message) {
        summaryArea.innerHTML = '<span class="muted">Results will appear here after processing.</span>';
        return;
    }
    summaryArea.textContent = message;
    summaryArea.className = "summary-area" + (isError ? " area-error" : "");
}

// ---------------------------------------------------------------------------
// Hashing toggle
// ---------------------------------------------------------------------------

hashingToggle.addEventListener("change", () => {
    secretField.hidden = !hashingToggle.checked;
    if (!hashingToggle.checked) secretInput.value = "";
});
