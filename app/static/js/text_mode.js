"use strict";

const inputEl       = document.getElementById("input-text");
const outputEl      = document.getElementById("output-text");
const copyBtn       = document.getElementById("copy-btn");
const hashingToggle = document.getElementById("hashing-toggle");
const secretField   = document.getElementById("secret-field");
const secretInput   = document.getElementById("secret-input");
const keyrefToggle  = document.getElementById("keyref-toggle");
const keyrefSection = document.getElementById("keyref-section");
const keyrefBody    = document.getElementById("keyref-body");
const datesToggle   = document.getElementById("dates-toggle");
const langSelector  = document.getElementById("lang-selector");

const DEBOUNCE_MS = 600;
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

    if (hashingToggle.checked && !secretInput.value.trim()) {
        showError("Enter a secret phrase to use hashing.");
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
                hashing_enabled: hashingToggle.checked,
                secret: secretInput.value,
                key_reference_enabled: keyrefToggle.checked,
                anonymize_dates: datesToggle.checked,
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
        renderKeyReference(data.key_reference);
        keyrefSection.hidden = false;
    } else {
        keyrefSection.hidden = true;
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
}

function setOutputLoading() {
    outputEl.innerHTML = '<span class="placeholder-text">Processing&hellip;</span>';
    copyBtn.disabled = true;
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

hashingToggle.addEventListener("change", () => {
    secretField.hidden = !hashingToggle.checked;
    if (!hashingToggle.checked) secretInput.value = "";
    if (inputEl.value.trim()) runAnonymize();
});

secretInput.addEventListener("input", scheduleAnonymize);

datesToggle.addEventListener("change", () => {
    if (inputEl.value.trim()) runAnonymize();
});

keyrefToggle.addEventListener("change", () => {
    if (!keyrefToggle.checked) keyrefSection.hidden = true;
    if (inputEl.value.trim()) runAnonymize();
});

inputEl.addEventListener("input", scheduleAnonymize);
