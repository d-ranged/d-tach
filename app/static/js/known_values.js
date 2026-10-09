"use strict";

(function () {
    const input = document.getElementById("known-name-input");
    const addBtn = document.getElementById("add-known-name-btn");
    const tagsContainer = document.getElementById("known-names-tags");

    if (!input || !addBtn || !tagsContainer) return;

    const EMPTY_HTML = '<span class="muted">No values added by hand yet &mdash; add names that are consistently missed by the anonymizer, or import a class list below.</span>';

    // A class list of 500 students expands to well over a thousand values.
    // Rendering a tag each locks the page up, so imported values are shown as a
    // count and reached through search instead.
    const MAX_SEARCH_RESULTS = 100;

    const ENTITY_LABELS = {
        PERSON: "Person name",
        NUMERIC_ID: "Numeric ID",
        EMAIL_ADDRESS: "Email",
    };
    const SOURCE_LABELS = {
        manual: "Manual",
        class_list: "Class list",
    };
    const RULE_LABELS = {
        short: "kept for the full name only",
        capital: "matched with a capital letter only",
    };

    // Reassigned below when the class list import UI is present on this page.
    let renderClassListState = function () {};

    let importedValues = [];

    function escapeHtml(str) {
        const div = document.createElement("div");
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

    function buildTag(entry) {
        const tag = document.createElement("span");
        tag.className = "known-name-tag";
        const typeLabel = ENTITY_LABELS[entry.entity_type] || entry.entity_type;
        const ruleLabel = RULE_LABELS[entry.rule];
        const sourceLabel = (SOURCE_LABELS[entry.source] || entry.source) +
            (ruleLabel ? ", " + ruleLabel : "");
        tag.innerHTML = escapeHtml(entry.value) +
            ' <span class="known-name-type" title="' + escapeHtml(sourceLabel) + '">' + escapeHtml(typeLabel) + '</span>' +
            ' <button class="known-name-remove" title="Remove">&times;</button>';
        tag.querySelector(".known-name-remove").addEventListener("click", function () {
            removeValue(entry.value);
        });
        return tag;
    }

    function renderTags(values) {
        const all = values || [];
        const manual = all.filter(function (entry) { return entry.source !== "class_list"; });
        importedValues = all.filter(function (entry) { return entry.source === "class_list"; });

        if (manual.length === 0) {
            tagsContainer.innerHTML = EMPTY_HTML;
        } else {
            tagsContainer.innerHTML = "";
            manual.forEach(function (entry) {
                tagsContainer.appendChild(buildTag(entry));
            });
        }

        renderImportedSummary();
        renderSearchResults();
    }

    // ------------------------------------------------------------------
    // Imported values: summary and search
    // ------------------------------------------------------------------

    const importedRow = document.getElementById("imported-values-row");
    const importedSummary = document.getElementById("imported-values-summary");
    const importedSearch = document.getElementById("imported-values-search");
    const importedResults = document.getElementById("imported-values-results");

    const legacyNote = document.getElementById("class-list-legacy-note");

    const hasImportedUi = importedRow && importedSummary && importedSearch && importedResults;

    function renderImportedSummary() {
        if (!hasImportedUi) return;
        if (importedValues.length === 0) {
            importedRow.hidden = true;
            importedSearch.value = "";
            if (legacyNote) legacyNote.hidden = true;
            return;
        }
        importedRow.hidden = false;
        importedSummary.textContent =
            importedValues.length.toLocaleString() + " values imported from the class list";
        if (legacyNote) {
            // A class list entry without a name_part was imported before v1.4.0.
            legacyNote.hidden = importedValues.some(function (entry) { return !!entry.name_part; });
        }
    }

    function renderSearchResults() {
        if (!hasImportedUi) return;
        const query = importedSearch.value.trim().toLowerCase();
        if (!query || importedValues.length === 0) {
            importedResults.hidden = true;
            importedResults.innerHTML = "";
            return;
        }

        const matches = importedValues.filter(function (entry) {
            return String(entry.value).toLowerCase().indexOf(query) !== -1;
        });

        importedResults.innerHTML = "";
        if (matches.length === 0) {
            importedResults.innerHTML = '<span class="muted">No imported value matches that.</span>';
            importedResults.hidden = false;
            return;
        }

        matches.slice(0, MAX_SEARCH_RESULTS).forEach(function (entry) {
            importedResults.appendChild(buildTag(entry));
        });
        if (matches.length > MAX_SEARCH_RESULTS) {
            const note = document.createElement("span");
            note.className = "muted";
            note.textContent =
                "Showing the first " + MAX_SEARCH_RESULTS + " of " +
                matches.length.toLocaleString() + " matches. Narrow the search to see the rest.";
            importedResults.appendChild(note);
        }
        importedResults.hidden = false;
    }

    if (hasImportedUi) {
        importedSearch.addEventListener("input", renderSearchResults);
    }

    // ------------------------------------------------------------------
    // Add and remove
    // ------------------------------------------------------------------

    async function loadValues() {
        try {
            const resp = await fetch("/settings/known-values");
            const data = await resp.json();
            renderTags(data.values || []);
            renderClassListState(data.class_list_path || "", data.class_list_column_mapping || {});
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

    // ------------------------------------------------------------------
    // Class list import
    // ------------------------------------------------------------------

    const pathInput = document.getElementById("class-list-path");
    const browseBtn = document.getElementById("class-list-browse-btn");
    const columnsContainer = document.getElementById("class-list-columns");
    const importBtn = document.getElementById("class-list-import-btn");
    const resyncBtn = document.getElementById("class-list-resync-btn");
    const clearBtn = document.getElementById("class-list-clear-btn");
    const statusEl = document.getElementById("class-list-status");
    const errorEl = document.getElementById("class-list-error");

    const hasClassListUi = pathInput && browseBtn && columnsContainer &&
        importBtn && resyncBtn && clearBtn && statusEl && errorEl;

    if (hasClassListUi) {
        let rememberedMapping = {};

        const showError = function (message) {
            errorEl.textContent = message;
            errorEl.hidden = false;
            statusEl.hidden = true;
        };

        const showStatus = function (message) {
            statusEl.textContent = message;
            statusEl.hidden = false;
            errorEl.hidden = true;
        };

        const clearMessages = function () {
            errorEl.hidden = true;
            statusEl.hidden = true;
        };

        // Guess a column type from its header. "voornamen" is the full given
        // names (Johanna Maria), not what people use, so it is Ignore.
        const guessColumnType = function (header) {
            const lower = header.toLowerCase();
            if (lower.includes("voornamen")) return "";
            if (lower.includes("email")) return "EMAIL_ADDRESS";
            if (lower.includes("number") || lower.includes("id") || lower.includes("nr")) return "NUMERIC_ID";
            if (["first", "voornaam", "roepnaam"].some(function (w) { return lower.includes(w); })) return "FIRST_NAME";
            if (["last", "surname", "achternaam", "family", "tussenvoegsel", "prefix"].some(function (w) { return lower.includes(w); })) return "SURNAME";
            if (lower.includes("name") || lower.includes("naam")) return "FULL_NAME";
            return "";
        };

        const renderColumnPickers = function (columns) {
            columnsContainer.innerHTML = "";
            columns.forEach(function (header) {
                const row = document.createElement("div");
                row.className = "class-list-column-row";
                row.dataset.header = header;

                const label = document.createElement("span");
                label.className = "class-list-column-label";
                label.textContent = header;

                const select = document.createElement("select");
                select.className = "class-list-column-select digit-input";
                [
                    ["", "Ignore"],
                    ["FIRST_NAME", "First name"],
                    ["SURNAME", "Surname"],
                    ["FULL_NAME", "Full name"],
                    ["NUMERIC_ID", "Numeric ID"],
                    ["EMAIL_ADDRESS", "Email"],
                ].forEach(function (pair) {
                    const opt = document.createElement("option");
                    opt.value = pair[0];
                    opt.textContent = pair[1];
                    select.appendChild(opt);
                });
                select.value = guessColumnType(header);

                row.appendChild(label);
                row.appendChild(select);
                columnsContainer.appendChild(row);
            });
            keepFirstGuessOnly("FIRST_NAME");
            keepFirstGuessOnly("FULL_NAME");
            columnsContainer.hidden = columns.length === 0;
            importBtn.hidden = columns.length === 0;
        };

        // The import takes one First name and one Full name column, so only the
        // first match is guessed and the rest stay on Ignore.
        const keepFirstGuessOnly = function (columnType) {
            let seen = false;
            columnsContainer.querySelectorAll(".class-list-column-select").forEach(function (select) {
                if (select.value !== columnType) return;
                if (seen) select.value = "";
                seen = true;
            });
        };

        const currentColumnMapping = function () {
            const mapping = {};
            columnsContainer.querySelectorAll(".class-list-column-row").forEach(function (row) {
                const value = row.querySelector(".class-list-column-select").value;
                if (value) mapping[row.dataset.header] = value;
            });
            return mapping;
        };

        renderClassListState = function (path, mapping) {
            pathInput.value = path || "";
            rememberedMapping = mapping || {};
            const hasRemembered = !!path && Object.keys(rememberedMapping).length > 0;
            resyncBtn.hidden = !hasRemembered;
            clearBtn.hidden = !hasRemembered;
            columnsContainer.hidden = true;
            columnsContainer.innerHTML = "";
            importBtn.hidden = true;
        };

        const loadColumns = async function (filePath) {
            clearMessages();
            if (!filePath.trim()) {
                showError("Enter or browse to a class list file first.");
                return;
            }
            try {
                const resp = await fetch("/settings/known-values/class-list/columns", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ file_path: filePath.trim() }),
                });
                const data = await resp.json();
                if (data.error) {
                    showError(data.error);
                    return;
                }
                renderColumnPickers(data.columns || []);
                if (!data.columns || data.columns.length === 0) {
                    showError("No column headers found in row 1 of that file.");
                }
            } catch (_) {
                showError("Could not read that file.");
            }
        };

        const runImport = async function (filePath, mapping) {
            clearMessages();
            if (!Object.keys(mapping).length) {
                showError("Choose a type for at least one column before importing.");
                return;
            }
            try {
                const resp = await fetch("/settings/known-values/class-list/import", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ file_path: filePath, column_mapping: mapping }),
                });
                const data = await resp.json();
                if (data.error) {
                    showError(data.error);
                    return;
                }
                await loadValues();
                showStatus(
                    "Added " + data.added + ", updated " + data.updated +
                    ", already present " + data.already_present + ". " +
                    data.full_name_only + " names kept for the full name only, " +
                    data.capital_only + " matched with a capital only. " +
                    data.total_known_values + " known values total."
                );
            } catch (_) {
                showError("Import failed.");
            }
        };

        const clearClassListValues = async function () {
            clearMessages();
            try {
                const resp = await fetch("/settings/known-values/class-list/clear", { method: "DELETE" });
                const data = await resp.json();
                renderTags(data.values || []);
                showStatus("Class list values removed.");
            } catch (_) {
                showError("Could not clear class list values.");
            }
        };

        browseBtn.addEventListener("click", async function () {
            try {
                const resp = await fetch("/browse/file");
                const data = await resp.json();
                if (data.tkinter_unavailable) {
                    showError("File browsing is unavailable on this system — paste the path instead.");
                    return;
                }
                if (data.error) {
                    showError(data.error);
                    return;
                }
                if (data.path) {
                    pathInput.value = data.path;
                    await loadColumns(data.path);
                }
            } catch (_) {
                showError("Could not open file browser.");
            }
        });

        pathInput.addEventListener("keydown", function (e) {
            if (e.key === "Enter") { e.preventDefault(); loadColumns(pathInput.value); }
        });

        importBtn.addEventListener("click", function () {
            runImport(pathInput.value.trim(), currentColumnMapping());
        });

        resyncBtn.addEventListener("click", function () {
            runImport(pathInput.value.trim(), rememberedMapping);
        });

        clearBtn.addEventListener("click", clearClassListValues);
    }

    loadValues();
})();
