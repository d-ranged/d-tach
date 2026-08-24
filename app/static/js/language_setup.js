"use strict";

(function () {
    const continueBtn = document.getElementById("setup-continue-btn");
    const errorText = document.getElementById("setup-error");
    const progressWrap = document.getElementById("setup-progress-wrap");
    const progressBar = document.getElementById("setup-progress-bar");
    const progressText = document.getElementById("setup-progress-text");

    if (!continueBtn) return;

    function selectedCodes() {
        const codes = [];
        document.querySelectorAll(".setup-language-checkbox").forEach(function (box) {
            if (box.checked) {
                codes.push(box.closest("[data-language-code]").dataset.languageCode);
            }
        });
        return codes;
    }

    function setRowStatus(code, text) {
        const row = document.querySelector('[data-language-code="' + code + '"]');
        if (!row) return;
        const status = row.querySelector(".setup-language-status");
        if (!status) return;
        status.textContent = text;
        status.hidden = false;
    }

    async function pollUntilDone(codes) {
        const total = codes.length;
        while (true) {
            let resp;
            try {
                resp = await fetch("/setup/status?codes=" + encodeURIComponent(codes.join(",")));
            } catch (_) {
                errorText.textContent = "Could not reach the server.";
                errorText.hidden = false;
                continueBtn.disabled = false;
                return false;
            }
            const statuses = await resp.json();

            let doneCount = 0;
            let hasError = false;
            codes.forEach(function (code) {
                const s = statuses[code] || { state: "idle" };
                if (s.state === "done") {
                    doneCount += 1;
                    setRowStatus(code, "Installed");
                } else if (s.state === "error") {
                    hasError = true;
                    setRowStatus(code, "Failed: " + (s.message || "install error"));
                } else if (s.state === "downloading") {
                    setRowStatus(code, "Downloading…");
                }
            });

            progressBar.style.width = Math.round((doneCount / total) * 100) + "%";
            progressText.textContent = doneCount + " of " + total + " installed";

            if (hasError) {
                errorText.textContent = "Some languages failed to install. You can retry or continue with the ones that succeeded.";
                errorText.hidden = false;
                continueBtn.disabled = false;
                return false;
            }

            if (doneCount === total) {
                return true;
            }

            await new Promise((resolve) => setTimeout(resolve, 1500));
        }
    }

    continueBtn.addEventListener("click", async function () {
        const codes = selectedCodes();
        if (codes.length === 0) {
            errorText.textContent = "Select at least one language.";
            errorText.hidden = false;
            return;
        }

        errorText.hidden = true;
        continueBtn.disabled = true;
        progressWrap.hidden = false;
        progressText.hidden = false;

        try {
            await fetch("/setup/install", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ codes: codes }),
            });
        } catch (_) {
            errorText.textContent = "Could not reach the server.";
            errorText.hidden = false;
            continueBtn.disabled = false;
            return;
        }

        const allDone = await pollUntilDone(codes);
        if (!allDone) return;

        try {
            const resp = await fetch("/setup/complete", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ codes: codes }),
            });
            const data = await resp.json();
            window.location.href = data.redirect || "/";
        } catch (_) {
            errorText.textContent = "Could not reach the server.";
            errorText.hidden = false;
            continueBtn.disabled = false;
        }
    });
})();
