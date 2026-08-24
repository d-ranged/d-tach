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
