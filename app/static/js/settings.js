"use strict";

(function () {
    const input = document.getElementById("port-input");
    const saveBtn = document.getElementById("save-port-btn");
    const restartNotice = document.getElementById("port-restart-notice");
    const errorText = document.getElementById("port-error");

    if (!input || !saveBtn) return;

    async function savePort() {
        restartNotice.hidden = true;
        errorText.hidden = true;

        const port = parseInt(input.value, 10);
        if (Number.isNaN(port)) {
            errorText.textContent = "Enter a valid port number.";
            errorText.hidden = false;
            return;
        }

        try {
            const resp = await fetch("/settings/port", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ port: port }),
            });
            const data = await resp.json();
            if (!resp.ok || data.error) {
                errorText.textContent = data.error || "Could not save port.";
                errorText.hidden = false;
                return;
            }
            input.value = data.port;
            restartNotice.hidden = false;
        } catch (_) {
            errorText.textContent = "Could not reach the server.";
            errorText.hidden = false;
        }
    }

    saveBtn.addEventListener("click", savePort);
    input.addEventListener("keydown", function (e) {
        if (e.key === "Enter") { e.preventDefault(); savePort(); }
    });
})();

(function () {
    const strategySelect = document.getElementById("loading-strategy-select");
    const restartNotice = document.getElementById("loading-strategy-restart-notice");
    const errorText = document.getElementById("loading-strategy-error");
    const languageError = document.getElementById("language-error");
    const languageNotice = document.getElementById("language-notice");
    const languageList = document.getElementById("language-list");

    if (strategySelect) {
        strategySelect.addEventListener("change", async function () {
            restartNotice.hidden = true;
            errorText.hidden = true;
            try {
                const resp = await fetch("/settings/languages/loading-strategy", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ strategy: strategySelect.value }),
                });
                const data = await resp.json();
                if (!resp.ok || data.error) {
                    errorText.textContent = data.error || "Could not save loading strategy.";
                    errorText.hidden = false;
                    return;
                }
                restartNotice.hidden = false;
            } catch (_) {
                errorText.textContent = "Could not reach the server.";
                errorText.hidden = false;
            }
        });
    }

    function showLanguageError(message) {
        if (!languageError) return;
        languageError.textContent = message;
        languageError.hidden = false;
    }

    function showLanguageNotice(message) {
        if (!languageNotice) return;
        languageNotice.textContent = message;
        languageNotice.hidden = false;
    }

    function markRowInstalled(row) {
        const name = row.dataset.languageName;
        const status = row.querySelector(".language-status");
        if (status) status.textContent = "Installed";
        const toggle = row.querySelector(".language-enabled-toggle");
        if (toggle) toggle.disabled = false;
        const installBtn = row.querySelector(".language-install-btn");
        if (installBtn) {
            const removeBtn = document.createElement("button");
            removeBtn.className = "btn btn-secondary btn-sm language-remove-btn";
            removeBtn.textContent = "Remove";
            installBtn.replaceWith(removeBtn);
        }
        const progress = row.querySelector(".language-progress");
        if (progress) progress.hidden = true;
        showLanguageNotice(name + " installed. Restart d-tach to enable it.");
    }

    function markRowRemoved(row) {
        const name = row.dataset.languageName;
        const size = row.dataset.downloadSizeMb;
        const status = row.querySelector(".language-status");
        if (status) status.textContent = "Not installed (" + size + " MB)";
        const toggle = row.querySelector(".language-enabled-toggle");
        if (toggle) {
            toggle.checked = false;
            toggle.disabled = true;
        }
        const removeBtn = row.querySelector(".language-remove-btn");
        if (removeBtn) {
            const installBtn = document.createElement("button");
            installBtn.className = "btn btn-primary btn-sm language-install-btn";
            installBtn.textContent = "Install";
            installBtn.disabled = false;
            removeBtn.replaceWith(installBtn);
        }
        showLanguageNotice(name + " removed. Restart d-tach to apply.");
    }

    async function pollInstallStatus(code, row) {
        const progress = row.querySelector(".language-progress");
        const installBtn = row.querySelector(".language-install-btn");
        if (progress) {
            progress.hidden = false;
            progress.textContent = "Downloading…";
        }
        if (installBtn) installBtn.disabled = true;

        const poll = async () => {
            try {
                const resp = await fetch("/settings/languages/install-status?code=" + encodeURIComponent(code));
                const data = await resp.json();
                if (data.state === "downloading") {
                    setTimeout(poll, 1500);
                    return;
                }
                if (data.state === "error") {
                    if (progress) { progress.hidden = true; }
                    if (installBtn) installBtn.disabled = false;
                    showLanguageError(data.message || ("Failed to install " + code + "."));
                    return;
                }
                markRowInstalled(row);
            } catch (_) {
                if (progress) { progress.hidden = true; }
                if (installBtn) installBtn.disabled = false;
                showLanguageError("Could not reach the server.");
            }
        };
        poll();
    }

    if (languageList) {
        languageList.addEventListener("click", async function (e) {
            const installBtn = e.target.closest(".language-install-btn");
            const removeBtn = e.target.closest(".language-remove-btn");
            if (!installBtn && !removeBtn) return;

            const row = e.target.closest("[data-language-code]");
            const code = row.dataset.languageCode;
            if (languageError) languageError.hidden = true;
            if (languageNotice) languageNotice.hidden = true;

            if (installBtn) {
                try {
                    const resp = await fetch("/settings/languages/install", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ code: code }),
                    });
                    const data = await resp.json();
                    if (!resp.ok || data.error) {
                        showLanguageError(data.error || "Could not start install.");
                        return;
                    }
                    pollInstallStatus(code, row);
                } catch (_) {
                    showLanguageError("Could not reach the server.");
                }
                return;
            }

            removeBtn.disabled = true;
            try {
                const resp = await fetch("/settings/languages/remove", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ code: code }),
                });
                const data = await resp.json();
                if (!resp.ok || data.error) {
                    showLanguageError(data.error || "Could not remove language.");
                    removeBtn.disabled = false;
                    return;
                }
                markRowRemoved(row);
            } catch (_) {
                showLanguageError("Could not reach the server.");
                removeBtn.disabled = false;
            }
        });

        languageList.addEventListener("change", async function (e) {
            const toggle = e.target.closest(".language-enabled-toggle");
            if (!toggle) return;

            const row = toggle.closest("[data-language-code]");
            const code = row.dataset.languageCode;
            if (languageError) languageError.hidden = true;
            if (languageNotice) languageNotice.hidden = true;
            try {
                const resp = await fetch("/settings/languages/enabled", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ code: code, enabled: toggle.checked }),
                });
                const data = await resp.json();
                if (!resp.ok || data.error) {
                    showLanguageError(data.error || "Could not update language.");
                    toggle.checked = !toggle.checked;
                    return;
                }
                showLanguageNotice("Restart d-tach to apply language changes.");
            } catch (_) {
                showLanguageError("Could not reach the server.");
                toggle.checked = !toggle.checked;
            }
        });
    }
})();

(function () {
    const toggle = document.getElementById("ai-mode-toggle");
    const body = document.getElementById("ai-mode-body");
    const tokenDisplay = document.getElementById("ai-token-display");
    const tokenCopyBtn = document.getElementById("ai-token-copy-btn");
    const tokenRegenerateBtn = document.getElementById("ai-token-regenerate-btn");
    const instructionsArea = document.getElementById("ai-instructions");
    const instructionsCopyBtn = document.getElementById("ai-instructions-copy-btn");
    const timeoutInput = document.getElementById("ai-timeout-input");
    const tempDirInput = document.getElementById("ai-temp-dir-input");
    const tempDirBrowseBtn = document.getElementById("ai-temp-dir-browse-btn");
    const inlineLimitInput = document.getElementById("ai-inline-limit-input");
    const configSaveBtn = document.getElementById("ai-config-save-btn");
    const notice = document.getElementById("ai-mode-notice");
    const errorText = document.getElementById("ai-mode-error");

    if (!toggle) return;

    function showAiNotice(message) {
        if (!notice) return;
        notice.textContent = message;
        notice.hidden = false;
    }

    function showAiError(message) {
        if (!errorText) return;
        errorText.textContent = message;
        errorText.hidden = false;
    }

    function clearAiMessages() {
        if (notice) notice.hidden = true;
        if (errorText) errorText.hidden = true;
    }

    toggle.addEventListener("change", async function () {
        clearAiMessages();
        try {
            const resp = await fetch("/settings/ai-mode", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ enabled: toggle.checked }),
            });
            const data = await resp.json();
            if (!resp.ok || data.error) {
                showAiError(data.error || "Could not update AI Mode.");
                toggle.checked = !toggle.checked;
                return;
            }
            body.hidden = !data.enabled;
            if (tokenDisplay) tokenDisplay.value = data.token || "";
        } catch (_) {
            showAiError("Could not reach the server.");
            toggle.checked = !toggle.checked;
        }
    });

    if (tokenCopyBtn) {
        tokenCopyBtn.addEventListener("click", async function () {
            clearAiMessages();
            try {
                await navigator.clipboard.writeText(tokenDisplay.value);
                showAiNotice("Token copied.");
            } catch (_) {
                showAiError("Could not copy to clipboard.");
            }
        });
    }

    if (instructionsCopyBtn) {
        instructionsCopyBtn.addEventListener("click", async function () {
            clearAiMessages();
            try {
                await navigator.clipboard.writeText(instructionsArea.value);
                showAiNotice("Instructions copied.");
            } catch (_) {
                showAiError("Could not copy to clipboard.");
            }
        });
    }

    if (tokenRegenerateBtn) {
        tokenRegenerateBtn.addEventListener("click", async function () {
            clearAiMessages();
            try {
                const resp = await fetch("/settings/ai-mode/regenerate-token", { method: "POST" });
                const data = await resp.json();
                if (!resp.ok || data.error) {
                    showAiError(data.error || "Could not regenerate token.");
                    return;
                }
                tokenDisplay.value = data.token;
                showAiNotice("Token regenerated. Update any agent using the old token.");
            } catch (_) {
                showAiError("Could not reach the server.");
            }
        });
    }

    if (tempDirBrowseBtn) {
        tempDirBrowseBtn.addEventListener("click", async function () {
            tempDirBrowseBtn.disabled = true;
            try {
                const resp = await fetch("/browse/folder");
                const data = await resp.json();
                if (data.path) tempDirInput.value = data.path;
            } catch (_) {
                showAiError("Could not open folder browser.");
            } finally {
                tempDirBrowseBtn.disabled = false;
            }
        });
    }

    if (configSaveBtn) {
        configSaveBtn.addEventListener("click", async function () {
            clearAiMessages();
            try {
                const resp = await fetch("/settings/ai-mode/config", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        session_timeout_minutes: parseInt(timeoutInput.value, 10),
                        temp_dir: tempDirInput.value.trim(),
                        inline_text_max_chars: parseInt(inlineLimitInput.value, 10),
                    }),
                });
                const data = await resp.json();
                if (!resp.ok || data.error) {
                    showAiError(data.error || "Could not save AI Mode settings.");
                    return;
                }
                timeoutInput.value = data.ai_session_timeout_minutes;
                tempDirInput.value = data.ai_temp_dir;
                inlineLimitInput.value = data.ai_inline_text_max_chars;
                showAiNotice("Saved.");
            } catch (_) {
                showAiError("Could not reach the server.");
            }
        });
    }
})();

// ---------------------------------------------------------------------------
// Saved-section helper
//
// Every section below saves as soon as a control changes, rather than behind a
// Save button. These are the values every mode reads, so leaving an edited but
// unsaved control on screen would misrepresent what the next run will do.
// ---------------------------------------------------------------------------

function makeSectionSaver(endpoint, noticeId, errorId) {
    const notice = document.getElementById(noticeId);
    const errorText = document.getElementById(errorId);

    return async function save(payload) {
        if (notice) notice.hidden = true;
        if (errorText) errorText.hidden = true;
        try {
            const resp = await fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await resp.json();
            if (!resp.ok || data.error) {
                if (errorText) {
                    errorText.textContent = data.error || "Could not save.";
                    errorText.hidden = false;
                }
                return null;
            }
            if (notice) {
                notice.textContent = "Saved.";
                notice.hidden = false;
            }
            return data;
        } catch (_) {
            if (errorText) {
                errorText.textContent = "Could not reach the server.";
                errorText.hidden = false;
            }
            return null;
        }
    };
}

// ---------------------------------------------------------------------------
// Default language
// ---------------------------------------------------------------------------

(function () {
    const select = document.getElementById("default-language-select");
    if (!select) return;
    const save = makeSectionSaver(
        "/settings/default-language", "language-notice", "language-error"
    );
    select.addEventListener("change", function () {
        save({ language: select.value });
    });
})();

// ---------------------------------------------------------------------------
// Detection
// ---------------------------------------------------------------------------

(function () {
    const toggles = document.querySelectorAll(".detection-toggle");
    const numbers = document.querySelectorAll(".detection-number");
    if (!toggles.length && !numbers.length) return;

    const save = makeSectionSaver(
        "/settings/detection", "detection-notice", "detection-error"
    );

    toggles.forEach(function (el) {
        el.addEventListener("change", async function () {
            const result = await save({ [el.dataset.field]: el.checked });
            if (!result) el.checked = !el.checked;
        });
    });

    numbers.forEach(function (el) {
        const previous = { value: el.value };
        el.addEventListener("change", async function () {
            const parsed = parseInt(el.value, 10);
            if (Number.isNaN(parsed)) {
                el.value = previous.value;
                return;
            }
            const result = await save({ [el.dataset.field]: parsed });
            if (result) {
                previous.value = String(result[el.dataset.field]);
            }
            el.value = previous.value;
        });
    });
})();

// ---------------------------------------------------------------------------
// Excel
// ---------------------------------------------------------------------------

(function () {
    const controls = document.querySelectorAll(".excel-control");
    if (!controls.length) return;

    const save = makeSectionSaver("/settings/excel", "excel-notice", "excel-error");

    controls.forEach(function (el) {
        el.addEventListener("change", function () {
            const value = el.type === "checkbox" ? el.checked : el.value.trim();
            save({ [el.dataset.field]: value });
        });
    });
})();

// ---------------------------------------------------------------------------
// Folder output
// ---------------------------------------------------------------------------

(function () {
    const controls = document.querySelectorAll(".folder-output-control");
    if (!controls.length) return;

    const save = makeSectionSaver(
        "/settings/folder-output", "folder-output-notice", "folder-output-error"
    );

    controls.forEach(function (el) {
        el.addEventListener("change", function () {
            if (el.type === "radio") {
                if (el.checked) save({ output_mode: el.value });
                return;
            }
            save({ [el.dataset.field]: el.value.trim() });
        });
    });
})();

// ---------------------------------------------------------------------------
// Hashing
// ---------------------------------------------------------------------------

(function () {
    const toggle = document.getElementById("hashing-toggle");
    const body = document.getElementById("hashing-body");
    const secretInput = document.getElementById("hashing-secret-input");
    const revealBtn = document.getElementById("hashing-secret-reveal-btn");
    const saveBtn = document.getElementById("hashing-save-btn");
    const notice = document.getElementById("hashing-notice");
    if (!toggle || !body || !secretInput) return;

    const save = makeSectionSaver("/settings/hashing", "hashing-notice", "hashing-error");

    toggle.addEventListener("change", async function () {
        body.hidden = !toggle.checked;
        // Enabling with no secret yet is not an error — the field has only just
        // been revealed. Wait for Save rather than rejecting the click.
        if (toggle.checked && !secretInput.value.trim()) {
            if (notice) {
                notice.textContent = "Enter a secret phrase, then press Save.";
                notice.hidden = false;
            }
            secretInput.focus();
            return;
        }
        const result = await save({ enabled: toggle.checked, secret: secretInput.value });
        if (!result) {
            toggle.checked = !toggle.checked;
            body.hidden = !toggle.checked;
        }
    });

    if (saveBtn) {
        saveBtn.addEventListener("click", function () {
            save({ enabled: toggle.checked, secret: secretInput.value });
        });
    }

    if (revealBtn) {
        revealBtn.addEventListener("click", function () {
            const hidden = secretInput.type === "password";
            secretInput.type = hidden ? "text" : "password";
            revealBtn.textContent = hidden ? "Hide" : "Show";
        });
    }
})();
