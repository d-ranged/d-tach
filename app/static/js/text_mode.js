"use strict";

// Detection settings, hashing, and known values are configured in Settings and
// read by the server on every run, so this page only carries the two choices
// that belong to a single run: which language to read the text as, and whether
// to show the key reference.
const inputEl              = document.getElementById("input-text");
const outputEl             = document.getElementById("output-text");
const copyBtn              = document.getElementById("copy-btn");
const keyrefToggle         = document.getElementById("keyref-toggle");
const keyrefSection        = document.getElementById("keyref-section");
const keyrefBody           = document.getElementById("keyref-body");
const exportKeyrefBtn      = document.getElementById("export-keyref-btn");
const langSelector         = document.getElementById("lang-selector");

const DEBOUNCE_MS = 600;
let lastKeyReference = [];
let debounceTimer = null;
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
    if (inputEl.value.trim()) runAnonymize();
});

// ---------------------------------------------------------------------------
// Anonymize
// ---------------------------------------------------------------------------

function scheduleAnonymize() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(runAnonymize, DEBOUNCE_MS);
}

async function runAnonymize() {
    const text = inputEl.value;
    if (!text.trim()) {
        resetOutput();
        return;
    }

    setOutputLoading();

    try {
        const response = await fetch("/text/anonymize", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                text,
                language: selectedLanguage,
                key_reference_enabled: keyrefToggle.checked,
            }),
        });

        const data = await response.json();

        if (data.error) {
            showError(data.error);
            return;
        }

        renderOutput(data);
    } catch {
        showError("Processing failed — please try again.");
    }
}

// ---------------------------------------------------------------------------
// Output rendering
// ---------------------------------------------------------------------------

function renderOutput(data) {
    outputEl.textContent = data.anonymized_text;
    copyBtn.disabled = false;

    if (keyrefToggle.checked && data.key_reference.length > 0) {
        lastKeyReference = data.key_reference;
        renderKeyReference(data.key_reference);
        keyrefSection.hidden = false;
        exportKeyrefBtn.disabled = false;
    } else {
        lastKeyReference = [];
        keyrefSection.hidden = true;
        exportKeyrefBtn.disabled = true;
    }
}

function renderKeyReference(entries) {
    keyrefBody.innerHTML = "";
    const fragment = document.createDocumentFragment();
    for (const entry of entries) {
        const row = document.createElement("tr");
        const tdPlaceholder = document.createElement("td");
        const tdOriginal    = document.createElement("td");
        const tdType        = document.createElement("td");
        tdPlaceholder.textContent = entry.placeholder;
        tdOriginal.textContent    = entry.original;
        tdType.textContent        = entry.type;
        row.append(tdPlaceholder, tdOriginal, tdType);
        fragment.appendChild(row);
    }
    keyrefBody.appendChild(fragment);
}

function resetOutput() {
    outputEl.innerHTML = '<span class="placeholder-text">Anonymized text will appear here.</span>';
    copyBtn.disabled = true;
    keyrefSection.hidden = true;
    exportKeyrefBtn.disabled = true;
    lastKeyReference = [];
}

function setOutputLoading() {
    outputEl.innerHTML = '<span class="placeholder-text">Processing&hellip;</span>';
    copyBtn.disabled = true;
    exportKeyrefBtn.disabled = true;
}

function showError(message) {
    const span = document.createElement("span");
    span.className = "error-text";
    span.textContent = message;
    outputEl.innerHTML = "";
    outputEl.appendChild(span);
    copyBtn.disabled = true;
}

// ---------------------------------------------------------------------------
// Copy button
// ---------------------------------------------------------------------------

copyBtn.addEventListener("click", () => {
    const text = outputEl.textContent;
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => {
        copyBtn.textContent = "Copied!";
        setTimeout(() => { copyBtn.textContent = "Copy to clipboard"; }, 1500);
    });
});

// ---------------------------------------------------------------------------
// Toggles
// ---------------------------------------------------------------------------

keyrefToggle.addEventListener("change", () => {
    if (!keyrefToggle.checked) keyrefSection.hidden = true;
    if (inputEl.value.trim()) runAnonymize();
});

inputEl.addEventListener("input", scheduleAnonymize);

// ---------------------------------------------------------------------------
// Key reference export
// ---------------------------------------------------------------------------

exportKeyrefBtn.addEventListener("click", () => {
    if (!lastKeyReference.length) return;

    const lines = ["Placeholder,Original,Type"];
    for (const entry of lastKeyReference) {
        lines.push(
            `${csvEscape(entry.placeholder)},${csvEscape(entry.original)},${csvEscape(entry.type)}`
        );
    }

    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "dtach_keyref.csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
});

function csvEscape(value) {
    const str = String(value);
    if (str.includes(",") || str.includes('"') || str.includes("\n")) {
        return '"' + str.replace(/"/g, '""') + '"';
    }
    return str;
}
