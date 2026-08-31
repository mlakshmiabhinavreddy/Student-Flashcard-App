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
        const container = document.getElementById(
            "storage-files-container"
        );

        if (!container) return;

        try {
            const files = await api(
                "GET",
                "/api/storage/files"
            );

            if (!files.files || files.files.length === 0) {
                container.innerHTML = `
                    <div class="empty-state" style="padding:1.5rem;">
                        <span class="empty-state-icon">☁️</span>
                        <h3>No files yet</h3>
                        <p>Upload your first study material above.</p>
                    </div>
                `;
                return;
            }

            let html = `
                <div style="display:flex;flex-direction:column;gap:0.65rem;">
            `;

            for (const objectName of files.files) {
                const safeObjectName = encodeURIComponent(
                    objectName
                );

                const filename = objectName
                    .split("/")
                    .pop();

                html += `
                    <div
                        style="
                            display:flex;
                            justify-content:space-between;
                            align-items:center;
                            gap:1rem;
                            padding:0.85rem 1rem;
                            border:1px solid var(--border-color);
                            border-radius:0.75rem;
                        "
                    >
                        <div style="min-width:0;">
                            <span>📄</span>
                            <strong>
                                ${escapeHtml(filename)}
                            </strong>
                        </div>

                        <a
                            class="btn btn-ghost btn-sm"
                            href="/api/storage/download/${safeObjectName}"
                        >
                            ⬇️ Download
                        </a>
                    </div>
                `;
            }

            html += `</div>`;

            container.innerHTML = html;

        } catch (err) {
            console.error(
                "Load storage files error:",
                err
            );

            container.innerHTML = `
                <p class="text-muted">
                    Unable to load your files.
                </p>
            `;

            showToast(
                "Failed to load Cloud Storage files",
                "error"
            );
        }
    }


    async function handleStorageUpload(event) {
        event.preventDefault();

        const input = document.getElementById(
            "storage-file-input"
        );

        const button = document.getElementById(
            "storage-upload-btn"
        );

        const status = document.getElementById(
            "storage-upload-status"
        );

        if (!input || !input.files.length) {
            showToast(
                "Please choose a file first",
                "error"
            );
            return;
        }

        const file = input.files[0];

        const formData = new FormData();
        formData.append("file", file);

        button.disabled = true;
        button.textContent = "Uploading...";

        status.textContent =
            `Uploading ${file.name}...`;

        try {
            const response = await fetch(
                "/api/storage/upload",
                {
                    method: "POST",
                    body: formData,
                }
            );

            const data = await response.json();

            if (!response.ok) {
                throw data;
            }

            showToast(
                "File uploaded successfully",
                "success"
            );

            status.textContent =
                `${file.name} uploaded successfully.`;

            input.value = "";

            await loadStorageFiles();

        } catch (err) {
            console.error(
                "Storage upload error:",
                err
            );

            const message =
                err.error ||
                "File upload failed";

            showToast(message, "error");

            status.textContent = message;

        } finally {
            button.disabled = false;
            button.textContent = "☁️ Upload File";
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
    };
})();
