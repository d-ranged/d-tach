"use strict";

(function () {
    const input = document.getElementById("known-name-input");
    const addBtn = document.getElementById("add-known-name-btn");
    const tagsContainer = document.getElementById("known-names-tags");

    if (!input || !addBtn || !tagsContainer) return;

    const EMPTY_HTML = '<span class="muted">No known names yet — add names that are consistently missed by the anonymizer.</span>';

    function escapeHtml(str) {
        const div = document.createElement("div");
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

    function renderTags(values) {
        if (!values || values.length === 0) {
            tagsContainer.innerHTML = EMPTY_HTML;
            return;
        }
        tagsContainer.innerHTML = "";
        values.forEach(function (value) {
            const tag = document.createElement("span");
            tag.className = "known-name-tag";
            tag.innerHTML = escapeHtml(value) +
                ' <button class="known-name-remove" title="Remove ×">×</button>';
            tag.querySelector(".known-name-remove").addEventListener("click", function () {
                removeValue(value);
            });
            tagsContainer.appendChild(tag);
        });
    }

    async function loadValues() {
        try {
            const resp = await fetch("/settings/known-values");
            const data = await resp.json();
            renderTags(data.values || []);
        } catch (_) {
            tagsContainer.innerHTML = EMPTY_HTML;
        }
    }

    async function addValue(value) {
        if (!value.trim()) return;
        try {
            const resp = await fetch("/settings/known-values", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ value: value.trim() }),
            });
            const data = await resp.json();
            renderTags(data.values || []);
            input.value = "";
        } catch (_) { /* silent */ }
    }

    async function removeValue(value) {
        try {
            const resp = await fetch("/settings/known-values", {
                method: "DELETE",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ value: value }),
            });
            const data = await resp.json();
            renderTags(data.values || []);
        } catch (_) { /* silent */ }
    }

    addBtn.addEventListener("click", function () { addValue(input.value); });
    input.addEventListener("keydown", function (e) {
        if (e.key === "Enter") { e.preventDefault(); addValue(input.value); }
    });

    loadValues();
})();
