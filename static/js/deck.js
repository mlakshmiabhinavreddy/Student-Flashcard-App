/**
 * Deck — Single deck view: card management UI.
 *
 * Handles: list cards, add card, edit card, delete card.
 * Uses DECK_ID injected from the Flask template.
 *
 * Communicates with:
 *   GET    /api/decks/<id>          (deck info)
 *   GET    /api/decks/<id>/cards    (list cards)
 *   POST   /api/decks/<id>/cards    (create card)
 *   GET    /api/cards/<id>          (single card)
 *   PUT    /api/cards/<id>          (update card)
 *   DELETE /api/cards/<id>          (delete card)
 */

const Deck = (() => {
    "use strict";

    let currentDeck = null;
    let deleteCardId = null;

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

    // ── Load deck + cards ───────────────────────────────────
    async function load() {
        try {
            currentDeck = await api("GET", `/api/decks/${DECK_ID}`);
            renderDeckHeader(currentDeck);

            const cards = await api("GET", `/api/decks/${DECK_ID}/cards`);
            renderCards(cards);
        } catch (err) {
            console.error("Deck load error:", err);
            document.getElementById("deck-header").innerHTML = `
                <div class="empty-state">
                    <span class="empty-state-icon">❌</span>
                    <h3>Deck not found</h3>
                    <p>This deck may have been deleted.</p>
                    <a href="/decks" class="btn btn-primary">Back to My Decks</a>
                </div>
            `;
        }
    }

    // ── Render deck header ──────────────────────────────────
    function renderDeckHeader(deck) {
        const desc = deck.description
            ? `<p>${escapeHtml(deck.description)}</p>`
            : '<p class="text-muted">No description</p>';
        const subjectBadge = deck.subject
            ? `<span style="display:inline-block;background:var(--color-accent-subtle);color:var(--color-accent);padding:2px 12px;border-radius:999px;font-size:0.8rem;font-weight:600;margin-bottom:0.75rem;">📌 ${escapeHtml(deck.subject)}</span>`
            : '';

        document.getElementById("deck-header").innerHTML = `
            <div class="deck-detail-header">
                <div class="deck-detail-info">
                    ${subjectBadge}
                    <h1>${escapeHtml(deck.name)}</h1>
                    ${desc}
                    <div class="deck-stats-row">
                        <span class="deck-stat"><strong>${deck.card_count}</strong> card${deck.card_count !== 1 ? 's' : ''}</span>
                    </div>
                </div>
                <div class="deck-detail-actions">
                    <button class="btn btn-primary" onclick="Deck.openAddCardModal()">+ Add Card</button>
                    <a href="/study/${deck.id}" class="btn btn-success ${deck.card_count === 0 ? 'btn-disabled' : ''}"
                       ${deck.card_count === 0 ? 'onclick="event.preventDefault(); Deck.toast(\'Add cards first\', \'error\')"' : ''}>
                        ▶ Study Deck
                    </a>
                    ${deck.card_count >= 4
                        ? `<a href="/mock-exam" class="btn btn-ghost">📝 Mock Exam</a>`
                        : ''
                    }
                </div>
            </div>
        `;
    }

    // ── Render card list ────────────────────────────────────
    function renderCards(cards) {
        const container = document.getElementById("cards-container");

        if (cards.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <span class="empty-state-icon">🃏</span>
                    <h3>No cards yet</h3>
                    <p>Add your first flashcard to this deck.</p>
                    <button class="btn btn-primary" onclick="Deck.openAddCardModal()">+ Add Card</button>
                </div>
            `;
            return;
        }

        let html = `
            <div class="card-list-header">
                <h2>${cards.length} Card${cards.length !== 1 ? 's' : ''}</h2>
                <button class="btn btn-primary btn-sm" onclick="Deck.openAddCardModal()">+ Add Card</button>
            </div>
            <div class="card-list">
        `;

        for (let i = 0; i < cards.length; i++) {
            const card = cards[i];
            html += renderCardItem(card, i);
        }

        html += '</div>';
        container.innerHTML = html;
    }

    function renderCardItem(card, index) {
        const statsHtml = card.attempts > 0
            ? `<div class="card-item-stats">
                    <span class="card-item-stat">Attempts: ${card.attempts}</span>
                    <span class="card-item-stat text-success">Correct: ${card.correct_count}</span>
                    <span class="card-item-stat text-warning">Review: ${card.review_count}</span>
               </div>`
            : '<div class="card-item-stats"><span class="card-item-stat">Not studied yet</span></div>';

        return `
            <div class="card-item" style="animation-delay: ${index * 50}ms">
                <div class="card-item-content">
                    <div class="card-question">Q: ${escapeHtml(card.question)}</div>
                    <div class="card-answer">A: ${escapeHtml(card.answer)}</div>
                    ${statsHtml}
                </div>
                <div class="card-item-actions">
                    <button class="btn btn-ghost btn-sm" title="Edit"
                            onclick="Deck.openEditCardModal(${card.id})">
                        ✏️ Edit
                    </button>
                    <button class="btn btn-ghost btn-sm" title="Delete"
                            onclick="Deck.openDeleteCardModal(${card.id}, '${escapeAttr(card.question)}')">
                        🗑️
                    </button>
                </div>
            </div>
        `;
    }

    // ── Add / Edit Card Modal ───────────────────────────────
    function openAddCardModal() {
        document.getElementById("card-modal-title").textContent = "Add Card";
        document.getElementById("card-form-submit").textContent = "Add Card";
        document.getElementById("card-form-id").value = "";
        document.getElementById("card-form-question").value = "";
        document.getElementById("card-form-answer").value = "";
        // Clear MCQ fields
        ["card-form-option-a","card-form-option-b","card-form-option-c","card-form-option-d"].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = "";
        });
        const correct = document.getElementById("card-form-correct");
        if (correct) correct.value = "";
        document.getElementById("card-modal-overlay").classList.add("active");
        document.getElementById("card-form-question").focus();
    }

    async function openEditCardModal(cardId) {
        try {
            const card = await api("GET", `/api/cards/${cardId}`);
            document.getElementById("card-modal-title").textContent = "Edit Card";
            document.getElementById("card-form-submit").textContent = "Save Changes";
            document.getElementById("card-form-id").value = card.id;
            document.getElementById("card-form-question").value = card.question;
            document.getElementById("card-form-answer").value = card.answer;
            // Populate MCQ fields if they exist
            const oaEl = document.getElementById("card-form-option-a");
            if (oaEl) oaEl.value = card.option_a || "";
            const obEl = document.getElementById("card-form-option-b");
            if (obEl) obEl.value = card.option_b || "";
            const ocEl = document.getElementById("card-form-option-c");
            if (ocEl) ocEl.value = card.option_c || "";
            const odEl = document.getElementById("card-form-option-d");
            if (odEl) odEl.value = card.option_d || "";
            const correctEl = document.getElementById("card-form-correct");
            if (correctEl) correctEl.value = card.correct_option || "";
            document.getElementById("card-modal-overlay").classList.add("active");
            document.getElementById("card-form-question").focus();
        } catch (err) {
            showToast("Failed to load card", "error");
        }
    }

    function closeCardModal() {
        document.getElementById("card-modal-overlay").classList.remove("active");
    }

    async function handleCardSubmit(e) {
        e.preventDefault();
        const id = document.getElementById("card-form-id").value;
        const question = document.getElementById("card-form-question").value.trim();
        const answer = document.getElementById("card-form-answer").value.trim();
        // MCQ optional fields
        const option_a = (document.getElementById("card-form-option-a")?.value || "").trim() || null;
        const option_b = (document.getElementById("card-form-option-b")?.value || "").trim() || null;
        const option_c = (document.getElementById("card-form-option-c")?.value || "").trim() || null;
        const option_d = (document.getElementById("card-form-option-d")?.value || "").trim() || null;
        const correct_option = (document.getElementById("card-form-correct")?.value || "").trim() || null;

        if (!question) { showToast("Question is required", "error"); return; }
        if (!answer)   { showToast("Answer is required", "error"); return; }

        const payload = { question, answer, option_a, option_b, option_c, option_d, correct_option };

        try {
            if (id) {
                await api("PUT", `/api/cards/${id}`, payload);
                showToast("Card updated", "success");
            } else {
                await api("POST", `/api/decks/${DECK_ID}/cards`, payload);
                showToast("Card added", "success");
            }
            closeCardModal();
            await load();
        } catch (err) {
            showToast(err.error || "Something went wrong", "error");
        }
    }

    // ── Delete Card Modal ───────────────────────────────────
    function openDeleteCardModal(cardId, question) {
        deleteCardId = cardId;
        document.getElementById("delete-card-question").textContent = question;
        document.getElementById("delete-card-modal-overlay").classList.add("active");
    }

    function closeDeleteCardModal() {
        deleteCardId = null;
        document.getElementById("delete-card-modal-overlay").classList.remove("active");
    }

    async function confirmDeleteCard() {
        if (!deleteCardId) return;

        try {
            await api("DELETE", `/api/cards/${deleteCardId}`);
            showToast("Card deleted", "success");
            closeDeleteCardModal();
            await load();
        } catch (err) {
            showToast(err.error || "Failed to delete card", "error");
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

    function toast(msg, type) {
        showToast(msg, type);
    }

    // ── Close modals on overlay click / Escape key ──────────
    document.addEventListener("DOMContentLoaded", () => {
        load();

        document.getElementById("card-modal-overlay").addEventListener("click", (e) => {
            if (e.target === e.currentTarget) closeCardModal();
        });
        document.getElementById("delete-card-modal-overlay").addEventListener("click", (e) => {
            if (e.target === e.currentTarget) closeDeleteCardModal();
        });

        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape") {
                closeCardModal();
                closeDeleteCardModal();
                FileMaterials.closeGenerateModal();
            }
        });
    });

    // ── Public API ──────────────────────────────────────────
    return {
        load,
        openAddCardModal,
        openEditCardModal,
        closeCardModal,
        handleCardSubmit,
        openDeleteCardModal,
        closeDeleteCardModal,
        confirmDeleteCard,
        toast,
    };
})();

/* ============================================================
   FileMaterials — Study file upload + NLP topic extraction
   ============================================================ */
const FileMaterials = (() => {
    "use strict";

    // State for the currently-selected file to generate from
    let _currentText     = "";
    let _currentFileName = "";

    // ── API helper ─────────────────────────────────────────
    function showToast(message, type = "info") {
        const container = document.getElementById("toast-container");
        const toast = document.createElement("div");
        toast.className = `toast toast--${type}`;
        toast.textContent = message;
        container.appendChild(toast);
        setTimeout(() => toast.remove(), 3500);
    }

    // ── Handle file selected via input ─────────────────────
    async function handleFileSelect(event) {
        const file = event.target.files[0];
        if (!file) return;

        // Reset input so the same file can be re-selected
        event.target.value = "";

        const allowed = [".txt", ".pdf", ".docx"];
        const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
        if (!allowed.includes(ext)) {
            showToast(`Unsupported file type. Use ${allowed.join(", ")}`, "error");
            return;
        }

        await uploadFile(file);
    }

    // ── Upload file and display NLP results ────────────────
    async function uploadFile(file) {
        // Show progress UI
        document.getElementById("upload-progress-wrap").style.display = "block";
        document.getElementById("upload-status-text").textContent = "Uploading & analysing…";
        _animateProgress();

        const label = document.getElementById("upload-btn-label");
        label.textContent = "⏳ Analysing…";

        try {
            const formData = new FormData();
            formData.append("file", file);

            const res = await fetch(`/api/decks/${DECK_ID}/files/upload`, {
                method: "POST",
                body: formData,
            });
            const data = await res.json();

            if (!res.ok) {
                throw new Error(data.error || "Upload failed");
            }

            document.getElementById("upload-status-text").textContent = "✅ Analysis complete!";
            document.getElementById("upload-progress-inner").style.width = "100%";

            // Add the result row to the table
            addFileRow(data);
            showToast(`"${data.file_name}" uploaded and analysed!`, "success");
        } catch (err) {
            document.getElementById("upload-status-text").textContent = `❌ ${err.message}`;
            showToast(err.message, "error");
        } finally {
            setTimeout(() => {
                document.getElementById("upload-progress-wrap").style.display = "none";
                label.textContent = "⬆ Upload File";
            }, 2000);
        }
    }

    // ── Animate the indeterminate progress bar ─────────────
    function _animateProgress() {
        const bar = document.getElementById("upload-progress-inner");
        bar.style.width = "0%";
        let width = 0;
        const interval = setInterval(() => {
            width = Math.min(width + Math.random() * 8, 88);
            bar.style.width = width + "%";
            if (width >= 88) clearInterval(interval);
        }, 200);
    }

    // ── Render rows into the materials table ───────────────
    let _tableBody = null;

    function _ensureTable() {
        if (_tableBody) return;

        const container = document.getElementById("materials-table-container");
        container.innerHTML = `
            <div class="materials-table-wrap">
                <table class="materials-table" id="materials-table">
                    <thead>
                        <tr>
                            <th>📄 File Name</th>
                            <th>🏷 Topics</th>
                            <th>🔖 Subtopics</th>
                            <th>⚡ Action</th>
                        </tr>
                    </thead>
                    <tbody id="materials-tbody"></tbody>
                </table>
            </div>`;
        _tableBody = document.getElementById("materials-tbody");
        document.getElementById("materials-empty").style.display = "none";
    }

    function addFileRow(data) {
        _ensureTable();

        const topicsHtml = (data.topics || []).length
            ? data.topics.map(t => `<span class="topic-badge">${escapeHtml(t)}</span>`).join(" ")
            : '<span class="text-muted">—</span>';

        const subtopicsHtml = (data.subtopics || []).length
            ? data.subtopics.map(s => `<span class="subtopic-pill">${escapeHtml(s)}</span>`).join(" ")
            : '<span class="text-muted">—</span>';

        const row = document.createElement("tr");
        row.className = "materials-row";
        row.innerHTML = `
            <td class="materials-filename">
                <span class="file-icon">${_fileIcon(data.file_name)}</span>
                ${escapeHtml(data.file_name)}
            </td>
            <td class="materials-topics">${topicsHtml}</td>
            <td class="materials-subtopics">${subtopicsHtml}</td>
            <td class="materials-action">
                <button class="btn btn-primary btn-sm generate-btn"
                        onclick="FileMaterials.openGenerateModal(
                            ${JSON.stringify(data.file_name)},
                            ${JSON.stringify(data.text || "")},
                            ${JSON.stringify(data.topics || [])},
                            ${JSON.stringify(data.subtopics || [])}
                        )">
                    ✨ Generate AI Flashcards
                </button>
            </td>`;
        _tableBody.insertBefore(row, _tableBody.firstChild);
    }

    function _fileIcon(name) {
        if (name.endsWith(".pdf"))  return "📕";
        if (name.endsWith(".docx")) return "📘";
        return "📄";
    }

    // ── Generate Dialog ────────────────────────────────────
    function openGenerateModal(fileName, text, topics, subtopics) {
        _currentFileName = fileName;
        _currentText     = text;

        document.getElementById("generate-modal-file-name").textContent = `📄 ${fileName}`;
        document.getElementById("generate-card-count").value = "10";
        document.getElementById("generate-count-display").textContent = "10";

        // Show topic preview chips
        const preview = document.getElementById("generate-modal-topics-preview");
        if (topics && topics.length) {
            preview.innerHTML = topics.map(t => `<span class="topic-badge">${escapeHtml(t)}</span>`).join(" ");
        } else {
            preview.innerHTML = "";
        }

        document.getElementById("generate-modal-error").style.display = "none";
        const btn = document.getElementById("generate-modal-submit");
        btn.disabled = false;
        btn.textContent = "✨ Generate Cards";

        document.getElementById("generate-modal-overlay").classList.add("active");
    }

    function closeGenerateModal() {
        document.getElementById("generate-modal-overlay").classList.remove("active");
    }

    async function submitGenerate() {
        const count = parseInt(document.getElementById("generate-card-count").value, 10);
        const errEl = document.getElementById("generate-modal-error");
        const btn   = document.getElementById("generate-modal-submit");

        if (!_currentText || !_currentText.trim()) {
            errEl.textContent = "No text extracted from this file. Cannot generate cards.";
            errEl.style.display = "block";
            return;
        }

        btn.disabled = true;
        btn.textContent = "⏳ Generating…";
        errEl.style.display = "none";

        try {
            // 1. Generate flashcards from the text via AI
            const genRes = await fetch("/api/ai/generate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: _currentText, number_of_cards: count }),
            });
            const genData = await genRes.json();
            if (!genRes.ok) throw new Error(genData.error || "Generation failed");

            const cards = genData.cards || [];
            if (!cards.length) throw new Error("No cards were generated");

            // 2. Bulk-add cards to the deck
            let added = 0;
            for (const card of cards) {
                try {
                    await fetch(`/api/decks/${DECK_ID}/cards`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ question: card.question, answer: card.answer }),
                    });
                    added++;
                } catch (_) { /* skip individual failures */ }
            }

            closeGenerateModal();
            showToast(`✅ ${added} flashcard${added !== 1 ? "s" : ""} added from "${_currentFileName}"!`, "success");

            // Reload the cards list
            await Deck.load();
        } catch (err) {
            errEl.textContent = err.message;
            errEl.style.display = "block";
            btn.disabled = false;
            btn.textContent = "✨ Generate Cards";
        }
    }

    // ── Utilities ──────────────────────────────────────────
    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = String(text);
        return div.innerHTML;
    }

    // ── Close modal on overlay click ───────────────────────
    document.addEventListener("DOMContentLoaded", () => {
        document.getElementById("generate-modal-overlay")
            .addEventListener("click", (e) => {
                if (e.target === e.currentTarget) closeGenerateModal();
            });
    });

    // ── Public ─────────────────────────────────────────────
    return {
        handleFileSelect,
        uploadFile,
        openGenerateModal,
        closeGenerateModal,
        submitGenerate,
    };
})();

