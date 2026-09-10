/**
 * Decks — Deck management UI.
 *
 * Handles: list, create, edit, delete decks.
 * Communicates with:
 *   GET    /api/decks
 *   POST   /api/decks
 *   PUT    /api/decks/<id>
 *   DELETE /api/decks/<id>
 */

const Decks = (() => {
    "use strict";

    let deleteTargetId = null;
    let _allDecks = [];
    
    // Generator state
    let _currentText = "";
    let _currentFileName = "";

    // ── API helpers ─────────────────────────────────────────
    async function api(method, path, body) {
        const opts = {
            method,
            headers: { "Content-Type": "application/json" },
        };
        if (body) opts.body = JSON.stringify(body);

        const res = await fetch(path, opts);
        const data = await res.json();
        if (!res.ok) throw data;
        return data;
    }

    // ── Toast ───────────────────────────────────────────────
    function showToast(message, type = "info") {
        const container = document.getElementById("toast-container");
        const toast = document.createElement("div");
        toast.className = `toast toast--${type}`;
        toast.textContent = message;
        container.appendChild(toast);
        setTimeout(() => toast.remove(), 3500);
    }

    // ── Load decks ──────────────────────────────────────────
    async function loadDecks() {
        const container = document.getElementById("decks-container");

        try {
            const decks = await api("GET", "/api/decks");
            _allDecks = decks;

            if (decks.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <span class="empty-state-icon">📚</span>
                        <h3>No decks yet</h3>
                        <p>Create your first flashcard deck to get started.</p>
                        <button class="btn btn-primary" onclick="Decks.openCreateModal()">+ New Deck</button>
                    </div>
                `;
                return;
            }

            let html = '<div class="deck-grid">';
            for (const deck of decks) {
                html += renderDeckCard(deck);
            }
            html += '</div>';
            container.innerHTML = html;

        } catch (err) {
            console.error("Load decks error:", err);
            showToast("Failed to load decks", "error");
        }
    }

    function renderDeckCard(deck) {
        const desc = deck.description
            ? escapeHtml(deck.description)
            : '<span class="text-muted">No description</span>';

        const date = new Date(deck.created_at + "Z").toLocaleDateString("en-US", {
            month: "short", day: "numeric", year: "numeric"
        });

        const subjectBadge = deck.subject
            ? `<span style="display:inline-block;background:var(--color-accent-subtle);color:var(--color-accent);padding:2px 10px;border-radius:999px;font-size:0.75rem;font-weight:600;margin-bottom:0.5rem;">${escapeHtml(deck.subject)}</span><br>`
            : '';

        return `
            <div class="deck-card" onclick="Decks.openDeck(${deck.id})" id="deck-${deck.id}">
                <div class="deck-actions">
                    <button class="btn btn-ghost btn-icon" title="Edit"
                            onclick="event.stopPropagation(); Decks.openEditModal(${deck.id}, '${escapeAttr(deck.name)}', '${escapeAttr(deck.subject || '')}', '${escapeAttr(deck.description)}')">
                        ✏️
                    </button>
                    <button class="btn btn-ghost btn-icon" title="Delete"
                            onclick="event.stopPropagation(); Decks.openDeleteModal(${deck.id}, '${escapeAttr(deck.name)}')">
                        🗑️
                    </button>
                </div>
                ${subjectBadge}
                <div class="deck-name">${escapeHtml(deck.name)}</div>
                <div class="deck-description">${desc}</div>
                <div class="deck-meta">
                    <span class="deck-card-count">${deck.card_count} card${deck.card_count !== 1 ? 's' : ''}</span>
                    <span class="deck-date">${date}</span>
                </div>
            </div>
        `;
    }

    // ── Navigate to deck ────────────────────────────────────
    function openDeck(deckId) {
        window.location.href = `/deck/${deckId}`;
    }

    // ── Create / Edit Modal ─────────────────────────────────
    function openCreateModal() {
        document.getElementById("deck-modal-title").textContent = "New Deck";
        document.getElementById("deck-form-submit").textContent = "Create Deck";
        document.getElementById("deck-form-id").value = "";
        document.getElementById("deck-form-name").value = "";
        document.getElementById("deck-form-subject").value = "";
        document.getElementById("deck-form-desc").value = "";
        document.getElementById("deck-modal-overlay").classList.add("active");
        document.getElementById("deck-form-name").focus();
    }

    function openEditModal(id, name, subject, description) {
        document.getElementById("deck-modal-title").textContent = "Edit Deck";
        document.getElementById("deck-form-submit").textContent = "Save Changes";
        document.getElementById("deck-form-id").value = id;
        document.getElementById("deck-form-name").value = name;
        document.getElementById("deck-form-subject").value = subject || "";
        document.getElementById("deck-form-desc").value = description;
        document.getElementById("deck-modal-overlay").classList.add("active");
        document.getElementById("deck-form-name").focus();
    }

    function closeModal() {
        document.getElementById("deck-modal-overlay").classList.remove("active");
    }

    async function handleSubmit(e) {
        e.preventDefault();
        const id = document.getElementById("deck-form-id").value;
        const name = document.getElementById("deck-form-name").value.trim();
        const subject = document.getElementById("deck-form-subject").value.trim();
        const description = document.getElementById("deck-form-desc").value.trim();

        if (!name) {
            showToast("Deck name is required", "error");
            return;
        }

        try {
            if (id) {
                await api("PUT", `/api/decks/${id}`, { name, subject, description });
                showToast("Deck updated successfully", "success");
            } else {
                await api("POST", "/api/decks", { name, subject, description });
                showToast("Deck created successfully", "success");
            }
            closeModal();
            await loadDecks();
        } catch (err) {
            showToast(err.error || "Something went wrong", "error");
        }
    }

    // ── Delete Modal ────────────────────────────────────────
    function openDeleteModal(id, name) {
        deleteTargetId = id;
        document.getElementById("delete-deck-name").textContent = name;
        document.getElementById("delete-deck-modal-overlay").classList.add("active");
    }

    function closeDeleteModal() {
        deleteTargetId = null;
        document.getElementById("delete-deck-modal-overlay").classList.remove("active");
    }

    async function confirmDelete() {
        if (!deleteTargetId) return;

        try {
            await api("DELETE", `/api/decks/${deleteTargetId}`);
            showToast("Deck deleted", "success");
            closeDeleteModal();
            await loadDecks();
        } catch (err) {
            showToast(err.error || "Failed to delete deck", "error");
        }
    }

        // ═════════════════════════════════════════════════════════
    //  CLOUD STORAGE
    // ═════════════════════════════════════════════════════════

    async function loadStorageFiles() {
        const container = document.getElementById("storage-files-container");
        if (!container) return;

        try {
            const files = await api("GET", "/api/storage/files");

            if (!files.files || files.files.length === 0) {
                container.innerHTML = `
                    <div class="materials-empty" id="materials-empty">
                        <span class="materials-empty-icon">📄</span>
                        <p>No files uploaded yet. Upload a <strong>.txt</strong>, <strong>.pdf</strong>, or <strong>.docx</strong> file to extract topics.</p>
                    </div>
                `;
                return;
            }

            // We build the materials table structure
            let html = `
                <div class="materials-table-wrap">
                    <table class="materials-table" id="materials-table">
                        <thead>
                            <tr>
                                <th>📄 File Name</th>
                                <th>⚡ Action</th>
                            </tr>
                        </thead>
                        <tbody id="materials-tbody">
            `;

            for (const objectName of files.files) {
                const safeObjectName = encodeURIComponent(objectName);
                const filename = objectName.split("/").pop();

                html += `
                    <tr class="materials-row">
                        <td class="materials-filename">
                            <span class="file-icon">${_fileIcon(filename)}</span>
                            ${escapeHtml(filename)}
                        </td>
                        <td class="materials-action">
                            <div style="display:flex;gap:0.5rem;justify-content:flex-end;">
                                <button class="btn btn-primary btn-sm generate-btn"
                                        data-filename="${escapeHtml(filename)}"
                                        data-objectname="${escapeHtml(objectName)}"
                                        onclick="Decks.openGenerateModal(this.dataset.filename, this.dataset.objectname)">
                                    <i data-lucide="sparkles"></i> Generate AI Flashcards
                                </button>
                                <a class="btn btn-ghost btn-sm" href="/api/storage/download/${safeObjectName}" title="Download">
                                    <i data-lucide="download"></i>
                                </a>
                            </div>
                        </td>
                    </tr>
                `;
            }

            html += `</tbody></table></div>`;
            container.innerHTML = html;

        } catch (err) {
            console.error("Load storage files error:", err);
            container.innerHTML = `<p class="text-muted">Unable to load your files.</p>`;
            showToast("Failed to load Cloud Storage files", "error");
        }
    }

    function _fileIcon(name) {
        if (name.endsWith(".pdf"))  return "📕";
        if (name.endsWith(".docx")) return "📘";
        return "📄";
    }

    function _ensureTable() {
        const container = document.getElementById("storage-files-container");
        let tbody = document.getElementById("materials-tbody");
        if (!tbody) {
            container.innerHTML = `
                <div class="materials-table-wrap">
                    <table class="materials-table" id="materials-table">
                        <thead>
                            <tr>
                                <th>📄 File Name</th>
                                <th>⚡ Action</th>
                            </tr>
                        </thead>
                        <tbody id="materials-tbody"></tbody>
                    </table>
                </div>`;
            tbody = document.getElementById("materials-tbody");
        }
        return tbody;
    }

    function addFileRow(data) {
        const tbody = _ensureTable();
        const safeObjectName = encodeURIComponent(data.object_name);

        const row = document.createElement("tr");
        row.className = "materials-row";
        
        row.innerHTML = `
            <td class="materials-filename">
                <span class="file-icon">${_fileIcon(data.filename)}</span>
                ${escapeHtml(data.filename)}
            </td>
            <td class="materials-action">
                <div style="display:flex;gap:0.5rem;justify-content:flex-end;">
                    <button class="btn btn-primary btn-sm generate-btn"
                            data-filename="${escapeHtml(data.filename)}"
                            data-objectname="${escapeHtml(data.object_name)}"
                            onclick="Decks.openGenerateModal(this.dataset.filename, this.dataset.objectname)">
                        <i data-lucide="sparkles"></i> Generate AI Flashcards
                    </button>
                    <a class="btn btn-ghost btn-sm" href="/api/storage/download/${safeObjectName}" title="Download">
                        <i data-lucide="download"></i>
                    </a>
                </div>
            </td>`;
        
        tbody.insertBefore(row, tbody.firstChild);
    }

    // ── Animate the indeterminate progress bar ─────────────
    function _animateProgress() {
        const bar = document.getElementById("upload-progress-inner");
        if(!bar) return;
        bar.style.width = "0%";
        let width = 0;
        const interval = setInterval(() => {
            width = Math.min(width + Math.random() * 8, 88);
            bar.style.width = width + "%";
            if (width >= 88) clearInterval(interval);
        }, 200);
    }

    async function handleStorageUpload(event) {
        event.preventDefault();

        const input = document.getElementById("storage-file-input");
        const button = document.getElementById("storage-upload-btn");
        const status = document.getElementById("storage-upload-status");
        const progressWrap = document.getElementById("upload-progress-wrap");

        if (!input || !input.files.length) {
            showToast("Please choose a file first", "error");
            return;
        }

        const file = input.files[0];
        const formData = new FormData();
        formData.append("file", file);

        button.disabled = true;
        button.textContent = "⏳ Analysing...";
        status.textContent = `Uploading & analysing ${file.name}...`;

        if(progressWrap) progressWrap.style.display = "block";
        _animateProgress();

        try {
            const response = await fetch("/api/storage/upload", {
                method: "POST",
                body: formData,
            });

            const data = await response.json();

            if (!response.ok) {
                throw data;
            }

            const bar = document.getElementById("upload-progress-inner");
            if(bar) bar.style.width = "100%";

            showToast("File uploaded & analysed successfully", "success");
            status.textContent = `✅ ${file.name} analysed successfully.`;
            input.value = "";

            addFileRow(data);

        } catch (err) {
            console.error("Storage upload error:", err);
            const message = err.error || "File upload failed";
            showToast(message, "error");
            status.textContent = `❌ ${message}`;
        } finally {
            button.disabled = false;
            button.textContent = "☁️ Upload File";
            setTimeout(() => {
                if(progressWrap) progressWrap.style.display = "none";
            }, 2000);
        }
    }

    // ── Generate AI Flashcards Modal ─────────────────────────
    async function openGenerateModal(fileName, objectName) {
        _currentFileName = fileName;

        document.getElementById("generate-modal-file-name").textContent = `📄 ${fileName}`;
        document.getElementById("generate-card-count").value = "10";
        document.getElementById("generate-count-display").textContent = "10";
        
        const preview = document.getElementById("generate-modal-topics-preview");
        preview.innerHTML = `<span class="text-muted">⏳ Analyzing document...</span>`;

        // Populate deck dropdown
        const select = document.getElementById("generate-target-deck");
        select.innerHTML = '<option value="">-- Select a deck --</option><option value="auto">✨ Create New Deck (Auto)</option>';
        _allDecks.forEach(deck => {
            const opt = document.createElement("option");
            opt.value = deck.id;
            opt.textContent = deck.name;
            select.appendChild(opt);
        });

        document.getElementById("generate-modal-error").style.display = "none";
        const btn = document.getElementById("generate-modal-submit");
        btn.disabled = true;
        btn.textContent = "⏳ Analyzing...";

        document.getElementById("generate-modal-overlay").classList.add("active");

        try {
            const response = await fetch("/api/storage/analyze", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ object_name: objectName })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "Analysis failed");

            _currentText = data.text;
            
            const allTopics = [...(data.topics || []), ...(data.subtopics || [])];
            if (allTopics.length) {
                preview.innerHTML = allTopics.map(t => `<span class="topic-badge">${escapeHtml(t)}</span>`).join(" ");
            } else {
                preview.innerHTML = `<span class="text-muted">No specific topics found. Flashcards will be generated from the text.</span>`;
            }

            btn.disabled = false;
            btn.textContent = "✨ Generate Cards";
        } catch (err) {
            preview.innerHTML = `<span style="color:var(--color-danger)">❌ ${escapeHtml(err.message)}</span>`;
            btn.disabled = false;
            btn.textContent = "✨ Generate Cards (Try Anyway)";
        }
    }

    function closeGenerateModal() {
        document.getElementById("generate-modal-overlay").classList.remove("active");
    }

    async function submitGenerate() {
        const count = parseInt(document.getElementById("generate-card-count").value, 10);
        let deckId = document.getElementById("generate-target-deck").value;
        const errEl = document.getElementById("generate-modal-error");
        const btn   = document.getElementById("generate-modal-submit");

        if (!deckId) {
            errEl.textContent = "Please select a deck to save the flashcards to.";
            errEl.style.display = "block";
            return;
        }

        if (!_currentText || !_currentText.trim()) {
            errEl.textContent = "No text extracted from this file. Cannot generate cards.";
            errEl.style.display = "block";
            return;
        }

        btn.disabled = true;
        btn.textContent = "⏳ Generating…";
        errEl.style.display = "none";

        try {
            // If Auto Create, make the deck first
            if (deckId === "auto") {
                const safeName = _currentFileName.split('.').slice(0, -1).join('.') || _currentFileName;
                const deckRes = await api("POST", "/api/decks", {
                    name: safeName,
                    subject: "Auto-generated",
                    description: "Created automatically from " + _currentFileName
                });
                // Assuming api returns the created deck or we fetch it. Wait, api just returns { message } in standard implementation, but looking at POST /api/decks in app.py it returns { message, id }. Let's assume it returns { id }.
                // If it doesn't return id, we might need to fetch decks and find the newest. Let's check app.py later if needed. For now, we will reload decks.
                // Wait, POST /api/decks usually returns {"message": "Deck created successfully", "id": new_id}.
                if (!deckRes.id) {
                     // fallback: reload decks and pick the last one
                     const decks = await api("GET", "/api/decks");
                     deckId = decks[decks.length - 1].id;
                } else {
                     deckId = deckRes.id;
                }
            }

            // 1. Generate flashcards
            const genRes = await fetch("/api/ai/generate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: _currentText, number_of_cards: count }),
            });
            const genData = await genRes.json();
            if (!genRes.ok) throw new Error(genData.error || "Generation failed");

            const cards = genData.cards || [];
            if (!cards.length) throw new Error("No cards were generated");

            // 2. Bulk-add to deck
            let added = 0;
            for (const card of cards) {
                try {
                    await fetch(`/api/decks/${deckId}/cards`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ question: card.question, answer: card.answer }),
                    });
                    added++;
                } catch (_) { /* skip individual failures */ }
            }

            closeGenerateModal();
            showToast(`✅ ${added} flashcard${added !== 1 ? "s" : ""} added from "${_currentFileName}"!`, "success");

            // Refresh decks view to update card counts
            await loadDecks();
        } catch (err) {
            errEl.textContent = err.message;
            errEl.style.display = "block";
            btn.disabled = false;
            btn.textContent = "✨ Generate Cards";
        }
    }

    // ── Utilities ───────────────────────────────────────────
    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    function escapeAttr(text) {
        return (text || "").replace(/\\/g, "\\\\").replace(/'/g, "\\'").replace(/"/g, '\\"');
    }

    // ── Close modals on overlay click ───────────────────────
        document.addEventListener("DOMContentLoaded", () => {
        loadDecks();
        loadStorageFiles();

        const storageUploadForm =
            document.getElementById(
                "storage-upload-form"
            );

        if (storageUploadForm) {
            storageUploadForm.addEventListener(
                "submit",
                handleStorageUpload
            );
        }

        // Click outside modal to close
        document.getElementById("deck-modal-overlay").addEventListener("click", (e) => {
            if (e.target === e.currentTarget) closeModal();
        });
        document.getElementById("delete-deck-modal-overlay").addEventListener("click", (e) => {
            if (e.target === e.currentTarget) closeDeleteModal();
        });

        // Escape key to close
        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape") {
                closeModal();
                closeDeleteModal();
                closeGenerateModal();
            }
        });
    });

    // ── Public API ──────────────────────────────────────────
        return {
        loadDecks,
        openDeck,
        openCreateModal,
        openEditModal,
        closeModal,
        handleSubmit,
        openDeleteModal,
        closeDeleteModal,
        confirmDelete,
        loadStorageFiles,
        handleStorageUpload,
        openGenerateModal,
        closeGenerateModal,
        submitGenerate,
    };
})();
