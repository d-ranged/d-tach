"use strict";

// ---- Elements ----
const hashingToggle          = document.getElementById("hashing-toggle");
const secretField            = document.getElementById("secret-field");
const secretInput            = document.getElementById("secret-input");
const keyrefToggle           = document.getElementById("keyref-toggle");
const namesToggle            = document.getElementById("names-toggle");
const datesToggle            = document.getElementById("dates-toggle");
const numericIdToggle        = document.getElementById("numeric-id-toggle");
const digitCountInput        = document.getElementById("digit-count");
const langSelector           = document.getElementById("lang-selector");
const urlsToggle             = document.getElementById("urls-toggle");
const locationsToggle        = document.getElementById("locations-toggle");
const excelNerToggle         = document.getElementById("excel-ner-toggle");
const excelColumnsInput      = document.getElementById("excel-columns");
const passThroughInput       = document.getElementById("pass-through-extensions");
const progressArea      = document.getElementById("progress-area");
const progressBarWrap   = document.getElementById("progress-bar-wrap");
const progressBar       = document.getElementById("progress-bar");
const progressLog       = document.getElementById("progress-log");
const summaryArea       = document.getElementById("summary-area");

// ---- File tab ----
const filePathInput     = document.getElementById("file-path");
const browseFileBtn     = document.getElementById("browse-file-btn");
const browseFileNote    = document.getElementById("browse-file-note");
const processFileBtn    = document.getElementById("process-file-btn");

// ---- Folder tab ----
const folderPathInput   = document.getElementById("folder-path");
const browseFolderBtn   = document.getElementById("browse-folder-btn");
const browseFolderNote  = document.getElementById("browse-folder-note");
const processFolderBtn  = document.getElementById("process-folder-btn");
const cancelBtn         = document.getElementById("cancel-btn");
const renameOnlyToggle      = document.getElementById("rename-only-toggle");
const folderContentOptions  = document.getElementById("folder-content-options");

// ---- Tabs ----
const tabFile           = document.getElementById("tab-file");
const tabFolder         = document.getElementById("tab-folder");
const panelFile         = document.getElementById("panel-file");
const panelFolder       = document.getElementById("panel-folder");

let selectedLanguage = INITIAL_LANGUAGE;
let activeEventSource = null;

function getOutputMode() {
    const checked = document.querySelector('input[name="output-mode"]:checked');
    return checked ? checked.value : "prefix";
}

// ---------------------------------------------------------------------------
// tkinter availability check (runs once on page load)
// ---------------------------------------------------------------------------

(async function checkBrowseAvailable() {
    try {
        const resp = await fetch("/browse/status");
        const data = await resp.json();
        if (!data.available) disableBrowseButtons();
    } catch {
        // Status check failed — leave buttons visible; will fail gracefully on click
    }
})();

function disableBrowseButtons() {
    browseFileBtn.hidden = true;
    browseFileNote.hidden = false;
    browseFolderBtn.hidden = true;
    browseFolderNote.hidden = false;
}

// ---------------------------------------------------------------------------
// Tab switching
// ---------------------------------------------------------------------------

[tabFile, tabFolder].forEach(tab => {
    tab.addEventListener("click", () => {
        tabFile.classList.toggle("active", tab === tabFile);
        tabFolder.classList.toggle("active", tab === tabFolder);
        panelFile.hidden = tab !== tabFile;
        panelFolder.hidden = tab !== tabFolder;
    });
});

// ---------------------------------------------------------------------------
// Browse buttons (native OS file/folder picker via Flask/tkinter)
// ---------------------------------------------------------------------------

browseFileBtn.addEventListener("click", async () => {
    browseFileBtn.disabled = true;
    try {
        const response = await fetch("/browse/file");
        const data = await response.json();
        if (data.tkinter_unavailable) {
            disableBrowseButtons();
        } else if (data.error) {
            setProgress("Could not open file browser: " + data.error, true);
        } else if (data.path) {
            filePathInput.value = data.path;
        }
    } catch {
        setProgress("Could not open file browser.", true);
    } finally {
        browseFileBtn.disabled = false;
    }
});

browseFolderBtn.addEventListener("click", async () => {
    browseFolderBtn.disabled = true;
    try {
        const response = await fetch("/browse/folder");
        const data = await response.json();
        if (data.tkinter_unavailable) {
            disableBrowseButtons();
        } else if (data.error) {
            setProgress("Could not open folder browser: " + data.error, true);
        } else if (data.path) {
            folderPathInput.value = data.path;
        }
    } catch {
        setProgress("Could not open folder browser.", true);
    } finally {
        browseFolderBtn.disabled = false;
    }
});

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
// Single file processing
// ---------------------------------------------------------------------------

processFileBtn.addEventListener("click", runProcessFile);
filePathInput.addEventListener("keydown", e => { if (e.key === "Enter") runProcessFile(); });

async function runProcessFile() {
    const filePath = filePathInput.value.trim();
    if (!filePath) { setProgress("Enter a file path to process."); return; }
    if (hashingToggle.checked && !secretInput.value.trim()) {
        setProgress("Enter a secret phrase to use hashing."); return;
    }

    setProgress("Processing\u2026");
    resetSummary();
    resetLog();
    processFileBtn.disabled = true;

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
                anonymize_locations: locationsToggle.checked,
                anonymize_urls: urlsToggle.checked,
                numeric_id_enabled: numericIdToggle.checked,
                digit_count: parseInt(digitCountInput.value, 10) || 7,
                excel_generic_enabled: excelNerToggle.checked,
                excel_column_names: excelColumnsInput.value.trim(),
                output_mode: getOutputMode(),
            }),
        });
        const data = await response.json();
        if (data.error) {
            setProgress(data.error, true);
        } else {
            setProgress("Done.");
            renderFileSummary(data);
        }
    } catch {
        setProgress("Processing failed \u2014 please try again.", true);
    } finally {
        processFileBtn.disabled = false;
    }
}

function renderFileSummary(data) {
    const lines = [];
    if (data.status === "anonymized") {
        lines.push(`\u2714 Anonymized \u2014 ${data.entities_found} unique value(s) replaced.`);
        lines.push(`Output: ${data.output_path}`);
        if (data.keyref_path) lines.push(`Key reference: ${data.keyref_path}`);
    } else if (data.status === "clean") {
        lines.push(`\u2714 No PII detected \u2014 file copied with CHECKED_ prefix.`);
        lines.push(`Output: ${data.output_path}`);
    } else if (data.status === "unreadable") {
        lines.push(`\u26A0 PDF unreadable \u2014 ${data.error_message}`);
        lines.push(`File copied as: ${data.output_path}`);
    } else if (data.status === "skipped") {
        lines.push(`\u26A0 Skipped: ${data.error_message}`);
    } else {
        lines.push(`\u2718 Error: ${data.error_message}`);
    }
    if (data.warnings && data.warnings.length > 0) {
        data.warnings.forEach(w => lines.push(`  \u2139 ${w}`));
    }
    setSummary(lines.join("\n"), data.status === "error" || data.status === "skipped");
}

// ---------------------------------------------------------------------------
// Folder processing (SSE)
// ---------------------------------------------------------------------------

processFolderBtn.addEventListener("click", runProcessFolder);
folderPathInput.addEventListener("keydown", e => { if (e.key === "Enter") runProcessFolder(); });
cancelBtn.addEventListener("click", cancelFolderProcessing);

renameOnlyToggle.addEventListener("change", () => {
    folderContentOptions.hidden = renameOnlyToggle.checked;
    processFolderBtn.textContent = renameOnlyToggle.checked ? "Rename Names Only" : "Process Folder";
});

function runProcessFolder() {
    const folderPath = folderPathInput.value.trim();
    if (!folderPath) { setProgress("Enter a folder path to process."); return; }
    if (hashingToggle.checked && !secretInput.value.trim()) {
        setProgress("Enter a secret phrase to use hashing."); return;
    }

    if (activeEventSource) activeEventSource.close();

    setProgress("Starting\u2026");
    resetSummary();
    resetLog();
    progressBarWrap.hidden = false;
    progressLog.hidden = false;
    setProgressBar(0);
    processFolderBtn.disabled = true;
    cancelBtn.hidden = false;

    const renameOnly = renameOnlyToggle.checked;
    const commonParams = {
        folder_path: folderPath,
        language: selectedLanguage,
        hashing_enabled: hashingToggle.checked,
        secret: secretInput.value,
        key_reference_enabled: keyrefToggle.checked,
        anonymize_dates: datesToggle.checked,
        anonymize_locations: locationsToggle.checked,
        anonymize_urls: urlsToggle.checked,
        numeric_id_enabled: numericIdToggle.checked,
        digit_count: parseInt(digitCountInput.value, 10) || 7,
    };

    const endpoint = renameOnly ? "/document/rename-folder" : "/document/process-folder";
    const params = renameOnly
        ? new URLSearchParams(commonParams)
        : new URLSearchParams({
            ...commonParams,
            check_file_names: namesToggle.checked,
            excel_generic_enabled: excelNerToggle.checked,
            excel_column_names: excelColumnsInput.value.trim(),
            output_mode: getOutputMode(),
            pass_through_extensions: passThroughInput.value.trim(),
        });

    activeEventSource = new EventSource(`${endpoint}?${params}`);

    activeEventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === "error") {
            setProgress(data.message, true);
            finishFolderProcessing();
            return;
        }

        if (data.type === "progress") {
            setProgress(`Processing file ${data.n} of ${data.total}: ${data.file_name}`);
            setProgressBar(data.n / data.total * 100);
            appendLogEntry(data);
        }

        if (data.type === "summary") {
            setProgress("Done.");
            setProgressBar(100);
            renderFolderSummary(data);
            finishFolderProcessing();
        }
    };

    activeEventSource.onerror = () => {
        setProgress("Connection lost \u2014 processing may have completed.", true);
        finishFolderProcessing();
    };
}

function cancelFolderProcessing() {
    if (activeEventSource) {
        activeEventSource.close();
        activeEventSource = null;
    }
    setProgress("Cancelled.");
    finishFolderProcessing();
}

function finishFolderProcessing() {
    if (activeEventSource) { activeEventSource.close(); activeEventSource = null; }
    processFolderBtn.disabled = false;
    cancelBtn.hidden = true;
}

function appendLogEntry(data) {
    const line = document.createElement("div");
    line.className = "log-entry log-" + data.status;
    const icon = data.status === "anonymized"  ? "\u2714"
               : data.status === "clean"       ? "\u2714"
               : data.status === "copied"      ? "\u2714"
               : data.status === "unreadable"  ? "\u26A0"
               : data.status === "skipped"     ? "\u26A0"
               : "\u2718";
    const detail = data.status === "anonymized"
        ? ` \u2014 ${data.entities_found} value(s) replaced`
        : data.status === "copied"
        ? " \u2014 copied without scanning"
        : data.error_message ? ` \u2014 ${data.error_message}` : "";
    line.textContent = `${icon} ${data.file_name}${detail}`;
    progressLog.appendChild(line);
    if (data.warnings && data.warnings.length > 0) {
        data.warnings.forEach(w => {
            const wLine = document.createElement("div");
            wLine.className = "log-entry log-info";
            wLine.textContent = `  ℹ ${w}`;
            progressLog.appendChild(wLine);
        });
    }
    progressLog.scrollTop = progressLog.scrollHeight;
}

function renderFolderSummary(data) {
    if (data.total === 0) {
        setSummary("No supported files found in this folder.");
        return;
    }
    const lines = [
        `Processed ${data.total} file(s):`,
        `  \u2714 Anonymized: ${data.anonymized}`,
        `  \u2714 Clean (no PII): ${data.clean}`,
    ];
    if (data.copied)      lines.push(`  \u2714 Copied (pass-through): ${data.copied}`);
    if (data.unreadable) lines.push(`  \u26A0 Unreadable PDF: ${data.unreadable}`);
    if (data.skipped)    lines.push(`  \u26A0 Skipped: ${data.skipped}`);
    if (data.errors)     lines.push(`  \u2718 Errors: ${data.errors}`);
    if (data.keyref_csv_path) lines.push(`Key reference: ${data.keyref_csv_path}`);
    setSummary(lines.join("\n"), data.errors > 0);
}

// ---------------------------------------------------------------------------
// Progress bar
// ---------------------------------------------------------------------------

function setProgressBar(pct) {
    progressBar.style.width = `${Math.min(100, pct)}%`;
}

// ---------------------------------------------------------------------------
// Shared UI helpers
// ---------------------------------------------------------------------------

function setProgress(message, isError = false) {
    progressArea.textContent = message;
    progressArea.className = "progress-area" + (isError ? " area-error" : "");
}

function setSummary(message, isError = false) {
    summaryArea.textContent = message;
    summaryArea.className = "summary-area" + (isError ? " area-error" : "");
}

function resetSummary() {
    summaryArea.innerHTML = '<span class="muted">Results will appear here after processing.</span>';
    summaryArea.className = "summary-area";
}

function resetLog() {
    progressLog.innerHTML = "";
    progressLog.hidden = true;
    progressBarWrap.hidden = true;
    setProgressBar(0);
}

// ---------------------------------------------------------------------------
// Toggles
// ---------------------------------------------------------------------------

hashingToggle.addEventListener("change", () => {
    secretField.hidden = !hashingToggle.checked;
    if (!hashingToggle.checked) secretInput.value = "";
});
