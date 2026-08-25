/**
 * STUDYFLIP — Study Mode
 *
 * Features:
 *  - 3D perspective flip card (click to flip, Enter/Space key support)
 *  - "Know It" / "Review Again" ONLY appear after the answer is revealed
 *  - Real-time progress bar & remaining cards counter
 *  - Adaptive review prioritization
 *  - Card shuffling
 *  - Full session completion screen
 */

const Study = (() => {
    "use strict";

    let deck = null;
    let cards = [];
    let currentIndex = 0;
    let isFlipped = false;

    // Session stats
    let sessionTotal = 0;
    let sessionKnowIt = 0;
    let sessionReviewAgain = 0;

    // ── HTML Escape ─────────────────────────────────────────
    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = String(text || "");
        return div.innerHTML;
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

    // ── Load study session ──────────────────────────────────
    async function load() {
        try {
            const endpoint = (typeof DECK_ID !== "undefined" && DECK_ID > 0)
                ? `/api/study/${DECK_ID}/cards`
                : `/api/smart-review/cards`;

            const res = await fetch(endpoint);
            if (res.status === 404) {
                renderNotFoundState();
                return;
            }
            if (!res.ok) throw new Error("Failed to load cards");

            const data = await res.json();
            deck = data.deck;
            cards = data.cards;

            if (cards.length === 0) {
                renderEmptyState();
                return;
            }

            sessionTotal = cards.length;
            currentIndex = 0;
            sessionKnowIt = 0;
            sessionReviewAgain = 0;
            isFlipped = false;

            document.getElementById("btn-shuffle").style.display = "inline-flex";
            renderCardView();
        } catch (err) {
            console.error("Study load error:", err);
            renderErrorState();
        }
    }

    // ── Empty State ─────────────────────────────────────────
    function renderEmptyState() {
        document.getElementById("btn-shuffle").style.display = "none";
        document.getElementById("study-container").innerHTML = `
            <div class="empty-state card-panel">
                <span class="empty-state-icon">🃏</span>
                <h3>No cards in this deck</h3>
                <p>Add some flashcards to <strong>${escapeHtml(deck ? deck.name : 'this deck')}</strong> before starting a study session.</p>
                <div style="display:flex; gap:1rem; justify-content:center; margin-top:1.5rem;">
                    <a href="/deck/${DECK_ID}" class="btn btn-primary">+ Add Cards</a>
                    <a href="/decks" class="btn btn-ghost">My Decks</a>
                </div>
            </div>
        `;
    }

    // ── Deck Not Found State ────────────────────────────────
    function renderNotFoundState() {
        document.getElementById("btn-shuffle").style.display = "none";
        document.getElementById("study-container").innerHTML = `
            <div class="empty-state card-panel">
                <span class="empty-state-icon">📚</span>
                <h3>Deck Not Found</h3>
                <p>This deck may have been deleted or does not exist.</p>
                <div style="display:flex; gap:1rem; justify-content:center; margin-top:1.5rem;">
                    <a href="/decks" class="btn btn-primary">Browse My Decks</a>
                    <a href="/dashboard" class="btn btn-ghost">Dashboard</a>
                </div>
            </div>
        `;
    }

    // ── Error State ─────────────────────────────────────────
    function renderErrorState() {
        document.getElementById("btn-shuffle").style.display = "none";
        document.getElementById("study-container").innerHTML = `
            <div class="empty-state card-panel">
                <span class="empty-state-icon">⚠️</span>
                <h3>Unable to load session</h3>
                <p>Could not connect to the study session service.</p>
                <a href="/decks" class="btn btn-primary">Back to Decks</a>
            </div>
        `;
    }

    // ── Render active Card ─────────────────────────────────────────
    function renderCardView() {
        const container = document.getElementById("study-container");
        const currentCard = cards[currentIndex];
        const progressPct = Math.round(((currentIndex) / sessionTotal) * 100);
        const remaining = sessionTotal - currentIndex;

        container.innerHTML = `
            <div class="study-layout">

                <!-- Progress header -->
                <div class="card-panel" style="width:100%;max-width:680px;margin-bottom:1.5rem;padding:1.25rem 1.5rem;">
                    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.75rem;margin-bottom:0.75rem;">
                        <div>
                            <h2 style="font-size:1.1rem;font-weight:700;margin:0;">${escapeHtml(deck.name)}</h2>
                            <span style="font-size:0.8rem;color:var(--color-text-muted);">Study Mode — Flashcard</span>
                        </div>
                        <div style="display:flex;gap:1.25rem;align-items:center;font-size:0.82rem;">
                            <span style="color:var(--color-success);">Known: <strong>${sessionKnowIt}</strong></span>
                            <span style="color:var(--color-warning);">Review: <strong>${sessionReviewAgain}</strong></span>
                            <span style="color:var(--color-text-muted);">Remaining: <strong>${remaining}</strong></span>
                        </div>
                    </div>
                    <div style="display:flex;align-items:center;gap:0.75rem;">
                        <div class="progress-bar-track" style="flex:1;height:8px;">
                            <div class="progress-bar-fill" style="width:${progressPct}%"></div>
                        </div>
                        <span style="font-size:0.75rem;color:var(--color-text-muted);white-space:nowrap;">Card ${currentIndex + 1} of ${sessionTotal}</span>
                    </div>
                </div>

                <!-- 3D Flip Card -->
                <div class="study-card-wrapper">
                    <div class="flip-card"
                         id="study-flip-card"
                         onclick="Study.toggleFlip()"
                         tabindex="0"
                         role="button"
                         aria-label="Flashcard. Click or press Space / Enter to flip.">
                        <div class="flip-card-inner">

                            <!-- FRONT FACE: Question -->
                            <div class="flip-card-front">
                                <span class="fc-label fc-label--question">
                                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                                    Question
                                </span>
                                <div class="fc-text">${escapeHtml(currentCard.question)}</div>
                                <span class="fc-prompt">
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>
                                    Click the card to reveal answer
                                </span>
                            </div>

                            <!-- BACK FACE: Answer -->
                            <div class="flip-card-back">
                                <span class="fc-label fc-label--answer">
                                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                                    Answer
                                </span>
                                <div class="fc-text">${escapeHtml(currentCard.answer)}</div>
                                <span class="fc-prompt">
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>
                                    Click the card to see question
                                </span>
                            </div>

                        </div>
                    </div>
                </div>

                <!-- Action buttons — hidden until card is flipped to answer -->
                <div class="study-action-row"
                     id="study-actions"
                     style="opacity:0;pointer-events:none;transform:translateY(14px);transition:opacity 0.35s ease,transform 0.35s ease;">
                    <button class="btn-review-again" onclick="Study.respond(false)" id="btn-review-again">
                        ↻ Review Again
                    </button>
                    <button class="btn-know-it" onclick="Study.respond(true)" id="btn-know-it">
                        ✓ Know It
                    </button>
                </div>

                <!-- Tip -->
                <p class="study-tip-bar" id="study-tip" style="opacity:0;transition:opacity 0.35s ease;">
                    💡 Use <strong>Know It</strong> if you're confident.
                    Use <span class="tip-orange">Review Again</span> to keep it in Smart Review.
                </p>

            </div>
        `;

        isFlipped = false;

        // Keyboard focus
        const cardEl = document.getElementById("study-flip-card");
        if (cardEl) {
            cardEl.addEventListener("keydown", (e) => {
                if (e.code === "Space" || e.code === "Enter") {
                    e.preventDefault();
                    toggleFlip();
                }
            });
            setTimeout(() => cardEl.focus(), 50);
        }
    }

    // ── Toggle Flip ──────────────────────────────────────────
    function toggleFlip() {
        const cardEl = document.getElementById("study-flip-card");
        const actionsEl = document.getElementById("study-actions");
        const tipEl = document.getElementById("study-tip");

        if (!cardEl) return;

        isFlipped = !isFlipped;
        cardEl.classList.toggle("flipped", isFlipped);

        cardEl.setAttribute(
            "aria-label",
            isFlipped
                ? "Flashcard showing answer. Click or press Space/Enter to flip back."
                : "Flashcard showing question. Click or press Space/Enter to reveal answer."
        );

        if (actionsEl) {
            if (isFlipped) {
                actionsEl.style.opacity = "1";
                actionsEl.style.pointerEvents = "all";
                actionsEl.style.transform = "translateY(0)";
            } else {
                actionsEl.style.opacity = "0";
                actionsEl.style.pointerEvents = "none";
                actionsEl.style.transform = "translateY(14px)";
            }
        }
        if (tipEl) {
            tipEl.style.opacity = isFlipped ? "1" : "0";
        }
    }

    // ── Record Response & Advance ──────────────────────────────
    async function respond(knewIt) {
        const currentCard = cards[currentIndex];

        if (knewIt) {
            sessionKnowIt++;
            showToast("✅ Great! Marked as known", "success");
        } else {
            sessionReviewAgain++;
            showToast("🔄 Added to review queue", "info");
        }

        try {
            await fetch(`/api/study/${currentCard.id}/respond`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ knew_it: knewIt })
            });
        } catch (e) {
            console.error("Failed to record response:", e);
        }

        currentIndex++;

        if (currentIndex < cards.length) {
            renderCardView();
        } else {
            renderCompletionScreen();
        }
    }

    // ── Shuffle Cards ─────────────────────────────────────────
    function shuffleCards() {
        if (cards.length === 0) return;
        const remainingCards = cards.slice(currentIndex);
        for (let i = remainingCards.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [remainingCards[i], remainingCards[j]] = [remainingCards[j], remainingCards[i]];
        }
        cards = cards.slice(0, currentIndex).concat(remainingCards);
        showToast("🔀 Cards shuffled!", "info");
        renderCardView();
    }

    // ── Completion Screen ─────────────────────────────────────
    function renderCompletionScreen() {
        document.getElementById("btn-shuffle").style.display = "none";

        const totalAnswered = sessionKnowIt + sessionReviewAgain;
        const accuracy = totalAnswered > 0 ? Math.round((sessionKnowIt / totalAnswered) * 100) : 0;

        document.getElementById("study-container").innerHTML = `
            <div class="completion-card">
                <div class="completion-icon">🎉</div>
                <h1 class="completion-title">Session Complete!</h1>
                <p class="completion-subtitle">Great job studying <strong>${escapeHtml(deck.name)}</strong>!</p>

                <div class="stats-grid completion-stats">
                    <div class="stat-card stat-card--accent">
                        <div class="stat-value">${sessionTotal}</div>
                        <div class="stat-label">Cards Studied</div>
                    </div>
                    <div class="stat-card stat-card--success">
                        <div class="stat-value" style="color:var(--color-success)">${sessionKnowIt}</div>
                        <div class="stat-label">Know It ✅</div>
                    </div>
                    <div class="stat-card stat-card--warning">
                        <div class="stat-value" style="color:var(--color-warning)">${sessionReviewAgain}</div>
                        <div class="stat-label">Review Again</div>
                    </div>
                    <div class="stat-card stat-card--accent">
                        <div class="stat-value">${accuracy}%</div>
                        <div class="stat-label">Accuracy</div>
                    </div>
                </div>

                <div class="completion-actions">
                    <button class="btn btn-success btn-lg" onclick="Study.load()">
                        🔄 Study Again
                    </button>
                    ${typeof DECK_ID !== 'undefined' && DECK_ID > 0 ? `<a href="/deck/${DECK_ID}" class="btn btn-ghost btn-lg">View Deck</a>` : ''}
                    <a href="/mock-exam" class="btn btn-primary btn-lg">
                        📝 Take Mock Exam
                    </a>
                    <a href="/dashboard" class="btn btn-ghost btn-lg">
                        📊 Dashboard
                    </a>
                </div>
            </div>
        `;
    }

    // ── Global Keyboard Navigation ──────────────────────────
    document.addEventListener("keydown", (e) => {
        // Only active during card study session
        if (currentIndex >= cards.length || !document.getElementById("study-flip-card")) return;

        if (e.code === "Space" || e.code === "Enter" || e.code === "ArrowUp" || e.code === "ArrowDown") {
            // Don't trigger if user is focused on a button (prevent double-fire)
            if (document.activeElement && document.activeElement.tagName === "BUTTON") return;
            e.preventDefault();
            toggleFlip();
        } else if (e.code === "ArrowRight") {
            // Know It — only if answer is visible
            if (isFlipped) {
                e.preventDefault();
                respond(true);
            }
        } else if (e.code === "ArrowLeft") {
            // Review Again — only if answer is visible
            if (isFlipped) {
                e.preventDefault();
                respond(false);
            }
        }
    });

    // ── Boot ────────────────────────────────────────────────
    document.addEventListener("DOMContentLoaded", load);

    return {
        load,
        toggleFlip,
        respond,
        shuffleCards
    };
})();
