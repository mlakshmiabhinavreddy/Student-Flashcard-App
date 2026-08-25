/**
 * STUDYFLIP — Exam Result Module
 *
 * Loads and renders exam results with:
 * - Score ring, accurate stats (correct/incorrect/known/unattempted)
 * - Review Mistakes: reusable 3D flip card component (only ANSWERED_INCORRECT)
 * - Known Questions: self-mastered questions listed separately
 * - Accuracy based only on attempted questions (not "I Know This")
 */

(() => {
    "use strict";

    // ── State for Review Mistakes navigator ──────────────────
    let reviewMistakes = [];
    let reviewIndex = 0;
    let reviewFlipped = false;

    // ── Utilities ────────────────────────────────────────────
    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = String(text || "");
        return div.innerHTML;
    }

    function getScoreColor(score) {
        if (score >= 80) return "var(--color-success)";
        if (score >= 60) return "var(--color-warning)";
        return "var(--color-danger)";
    }

    function getScoreBadgeClass(score) {
        if (score >= 80) return "score-badge--high";
        if (score >= 60) return "score-badge--mid";
        return "score-badge--low";
    }

    function getScoreEmoji(score) {
        if (score >= 90) return "🎉";
        if (score >= 80) return "🏆";
        if (score >= 70) return "👍";
        if (score >= 60) return "📚";
        return "💪";
    }

    function getScoreMessage(score) {
        if (score >= 90) return "Outstanding! You're a master!";
        if (score >= 80) return "Excellent work! Keep it up!";
        if (score >= 70) return "Good job! Review the mistakes.";
        if (score >= 60) return "Not bad! Keep practicing.";
        return "Keep studying — you'll get there!";
    }

    // ── Load ─────────────────────────────────────────────────
    async function load() {
        const container = document.getElementById("result-container");
        try {
            const res = await fetch(`/api/mock-exam/${EXAM_ID}/result`);
            if (!res.ok) {
                container.innerHTML = `
                    <div class="empty-state card-panel">
                        <span class="empty-state-icon">⚠️</span>
                        <h3>Result not found</h3>
                        <p>This exam result could not be loaded.</p>
                        <a href="/mock-exam" class="btn btn-primary">Take Another Exam</a>
                    </div>
                `;
                return;
            }

            const data = await res.json();
            const exam = data.exam;
            const deck = data.deck;
            const timeStr = data.time_str;
            const stats = data.stats;
            const wrongQuestions = data.wrong_questions || [];
            const knownQuestions = data.known_questions || [];
            const unattemptedQuestions = data.unattempted_questions || [];

            // Use accurate stats from the API (excludes self_mastered from score)
            const score = exam.score;
            const correct = stats.correct;
            const incorrect = stats.incorrect;
            const known = stats.known;
            const unattempted = stats.unattempted;
            const attempted = stats.attempted;
            const accuracy = stats.accuracy;

            const scoreDeg = Math.round((accuracy / 100) * 360);
            const scoreColor = getScoreColor(accuracy);

            reviewMistakes = wrongQuestions;
            reviewIndex = 0;
            reviewFlipped = false;

            container.innerHTML = `
                <!-- Hero result card -->
                <div class="result-hero">
                    <div class="result-emoji">${getScoreEmoji(accuracy)}</div>
                    <h1 class="result-title">EXAM COMPLETE</h1>
                    <p class="result-subtitle">${escapeHtml(deck ? deck.name : "Mock Exam")} · ${timeStr}</p>

                    <!-- Score Ring — based on accuracy of attempted questions -->
                    <div class="score-ring" style="--score-deg:${scoreDeg}deg;">
                        <span class="score-ring-value" style="color:${scoreColor}">${accuracy}%</span>
                    </div>

                    <p style="font-size:1.25rem; font-weight:600; color:${scoreColor}; margin-bottom:0.5rem;">
                        ${getScoreMessage(accuracy)}
                    </p>
                    <p style="color:var(--color-text-secondary); font-size:0.95rem;">
                        ${correct} correct out of ${attempted} attempted
                        ${known > 0 ? ` · ${known} self-mastered` : ""}
                    </p>
                </div>

                <!-- Stats grid — 6-column detailed breakdown -->
                <div class="stats-grid stats-grid--6" style="margin-bottom:2rem; gap:0.75rem;">
                    <div class="stat-card stat-card--success">
                        <div class="stat-icon">✅</div>
                        <div class="stat-value" style="color:var(--color-success)">${correct}</div>
                        <div class="stat-label">Correct</div>
                    </div>
                    <div class="stat-card stat-card--danger">
                        <div class="stat-icon">❌</div>
                        <div class="stat-value" style="color:var(--color-danger)">${incorrect}</div>
                        <div class="stat-label">Incorrect</div>
                    </div>
                    <div class="stat-card stat-card--warning">
                        <div class="stat-icon">💡</div>
                        <div class="stat-value" style="color:var(--color-warning)">${known}</div>
                        <div class="stat-label">Self-Mastered</div>
                    </div>
                    <div class="stat-card" style="background:rgba(150,150,150,0.07);">
                        <div class="stat-icon">⬜</div>
                        <div class="stat-value" style="color:var(--color-text-muted)">${unattempted}</div>
                        <div class="stat-label">Unattempted</div>
                    </div>
                    <div class="stat-card stat-card--accent">
                        <div class="stat-icon">📊</div>
                        <div class="stat-value">${attempted}</div>
                        <div class="stat-label">Attempted</div>
                    </div>
                    <div class="stat-card stat-card--accent">
                        <div class="stat-icon">🎯</div>
                        <div class="stat-value">${accuracy}%</div>
                        <div class="stat-label">Accuracy</div>
                    </div>
                </div>

                ${known > 0 ? `
                    <div style="background:rgba(245,166,35,0.06); border:1px solid rgba(245,166,35,0.2); border-radius:var(--radius-md); padding:0.875rem 1.25rem; margin-bottom:1.5rem; font-size:0.85rem; color:var(--color-text-secondary);">
                        💡 <strong style="color:var(--color-warning);">Accuracy note:</strong>
                        Accuracy is calculated from <strong>${attempted} attempted</strong> questions only.
                        The ${known} "I Know This" question${known !== 1 ? "s are" : " is"} not counted as correct or incorrect.
                    </div>
                ` : ""}

                <!-- Action buttons -->
                <div class="result-actions" style="margin-bottom:2rem; flex-wrap:wrap;">
                    ${wrongQuestions.length > 0 ? `
                        <button class="btn btn-danger btn-lg" onclick="toggleSection('review-mistakes-section')">
                            🔍 Review Mistakes (${wrongQuestions.length})
                        </button>
                    ` : ""}
                    ${knownQuestions.length > 0 ? `
                        <button class="btn btn-lg" style="background:rgba(245,166,35,0.12); border:1px solid rgba(245,166,35,0.3); color:var(--color-warning);" onclick="toggleSection('known-section')">
                            💡 Known Questions (${knownQuestions.length})
                        </button>
                    ` : ""}
                    <a href="/mock-exam" class="btn btn-primary btn-lg">🔄 Try Again</a>
                    <a href="/study/${deck ? deck.id : ''}" class="btn btn-success btn-lg">🃏 Study This Deck</a>
                    <a href="/dashboard" class="btn btn-ghost btn-lg">📊 Dashboard</a>
                </div>

                <!-- ── Review Mistakes Section (3D Flip Cards) ── -->
                ${wrongQuestions.length > 0 ? renderReviewMistakesSection(wrongQuestions) : `
                    <div class="card-panel" style="text-align:center; padding:2rem;">
                        <span style="font-size:3rem;">🎯</span>
                        <h3 style="margin:1rem 0 0.5rem;">No Mistakes!</h3>
                        <p style="color:var(--color-text-secondary);">You answered every attempted question correctly. Amazing!</p>
                    </div>
                `}

                <!-- ── Known / Self-Mastered Section ── -->
                ${knownQuestions.length > 0 ? renderKnownSection(knownQuestions) : ""}

                <!-- ── Unattempted Section ── -->
                ${unattempted > 0 ? renderUnattemptedSection(unattemptedQuestions) : ""}
            `;

            // Attach flip logic after DOM is ready
            attachReviewFlipListeners();

        } catch (err) {
            console.error("Result load error:", err);
            container.innerHTML = `
                <div class="empty-state card-panel">
                    <span class="empty-state-icon">⚠️</span>
                    <h3>Failed to load results</h3>
                    <p>Please try refreshing the page.</p>
                </div>
            `;
        }
    }

    // ── Render Review Mistakes using 3D Flip Cards ────────────
    function renderReviewMistakesSection(wrongQuestions) {
        if (!wrongQuestions.length) return "";

        return `
            <div class="review-section" id="review-mistakes-section" style="display:none;">
                <div class="section-header" style="margin-top:0;">
                    <h2>🔍 Review Mistakes</h2>
                    <span style="color:var(--color-text-muted); font-size:0.875rem;">
                        ${wrongQuestions.length} question${wrongQuestions.length !== 1 ? "s" : ""} to review
                    </span>
                </div>

                <p style="font-size:0.875rem; color:var(--color-text-secondary); margin-bottom:1.5rem;">
                    Click the card to flip and see the correct answer. Only your incorrect answers are shown here.
                </p>

                <!-- Single flip card display (navigated via Prev/Next) -->
                <div id="review-card-display">
                    ${renderSingleReviewCard(wrongQuestions, 0)}
                </div>

                <!-- Navigation -->
                ${wrongQuestions.length > 1 ? `
                <div class="review-nav-row">
                    <button class="btn btn-ghost" id="btn-review-prev" onclick="reviewNav(-1)" disabled>← Previous</button>
                    <span class="review-counter" id="review-counter">1 / ${wrongQuestions.length}</span>
                    <button class="btn btn-ghost" id="btn-review-next" onclick="reviewNav(1)">Next →</button>
                </div>
                ` : ""}
            </div>
        `;
    }

    function renderSingleReviewCard(wrongQuestions, index) {
        const q = wrongQuestions[index];
        if (!q) return "";

        const correctKey = q.correct_option;
        const correctText = q[`option_${correctKey}`] || q.correct_option;
        const userText = q.user_answer ? q[`option_${q.user_answer}`] || q.user_answer : "(No answer selected)";

        return `
            <!-- Reusable 3D Flip Card — Review Mistake ${index + 1} -->
            <div class="review-flip-wrapper">
                <div class="flip-card review-flip-card"
                     id="review-flip-card"
                     onclick="toggleReviewFlip()"
                     tabindex="0"
                     role="button"
                     aria-label="Review mistake. Click to flip and see the correct answer.">
                    <div class="flip-card-inner" id="review-flip-inner">
                        <!-- Front: Question -->
                        <div class="flip-card-front card-panel">
                            <span class="card-face-tag card-face-tag--question">QUESTION</span>
                            <div class="card-text">${escapeHtml(q.question_text)}</div>
                            <div class="card-flip-prompt">↻ Click to reveal the correct answer</div>
                        </div>
                        <!-- Back: Answer -->
                        <div class="flip-card-back card-panel">
                            <span class="card-face-tag card-face-tag--answer">CORRECT ANSWER</span>
                            <div class="card-text">${escapeHtml(correctText)}</div>
                            <div class="card-flip-prompt">↻ Click to flip back</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Compare Panel: visible only when flipped -->
            <div class="review-compare-panel" id="review-compare-panel">
                <div class="review-compare-wrong">
                    <div class="review-compare-label">❌ Your Answer</div>
                    <div class="review-compare-text">${escapeHtml(userText)}</div>
                </div>
                <div class="review-compare-correct">
                    <div class="review-compare-label">✅ Correct Answer</div>
                    <div class="review-compare-text">${escapeHtml(correctText)}</div>
                </div>
            </div>
        `;
    }

    function attachReviewFlipListeners() {
        // Keyboard flip support for review card
        document.addEventListener("keydown", (e) => {
            const card = document.getElementById("review-flip-card");
            if (!card) return;
            if (document.activeElement === card && (e.code === "Space" || e.code === "Enter")) {
                e.preventDefault();
                toggleReviewFlip();
            }
        });
    }

    // ── Review Flip Toggle ───────────────────────────────────
    window.toggleReviewFlip = function() {
        const card = document.getElementById("review-flip-card");
        const panel = document.getElementById("review-compare-panel");
        if (!card) return;

        reviewFlipped = !reviewFlipped;
        card.classList.toggle("flipped", reviewFlipped);

        if (panel) {
            panel.classList.toggle("visible", reviewFlipped);
        }
    };

    // ── Review Navigation ────────────────────────────────────
    window.reviewNav = function(direction) {
        const total = reviewMistakes.length;
        reviewIndex = Math.max(0, Math.min(total - 1, reviewIndex + direction));
        reviewFlipped = false;

        const display = document.getElementById("review-card-display");
        if (display) {
            display.innerHTML = renderSingleReviewCard(reviewMistakes, reviewIndex);
        }

        const counter = document.getElementById("review-counter");
        if (counter) counter.textContent = `${reviewIndex + 1} / ${total}`;

        const btnPrev = document.getElementById("btn-review-prev");
        const btnNext = document.getElementById("btn-review-next");
        if (btnPrev) btnPrev.disabled = reviewIndex === 0;
        if (btnNext) btnNext.disabled = reviewIndex === total - 1;
    };

    // ── Toggle sections (Review Mistakes, Known Questions) ───
    window.toggleSection = function(id) {
        const el = document.getElementById(id);
        if (!el) return;
        const isHidden = el.style.display === "none" || !el.style.display;
        el.style.display = isHidden ? "block" : "none";
        if (isHidden) {
            el.scrollIntoView({ behavior: "smooth", block: "start" });
        }
    };

    // ── Render Known Questions Section ───────────────────────
    function renderKnownSection(knownQuestions) {
        const items = knownQuestions.map(q => `
            <div class="known-question-item">
                <span style="font-size:1.1rem; flex-shrink:0;">💡</span>
                <span class="known-question-text">${escapeHtml(q.question_text)}</span>
                <span class="badge badge--success" style="flex-shrink:0;">Self-Mastered</span>
            </div>
        `).join("");

        return `
            <div class="review-section" id="known-section" style="display:none; margin-top:2rem;">
                <div class="section-header" style="margin-top:0;">
                    <h2>💡 Self-Mastered Questions</h2>
                    <span style="color:var(--color-text-muted); font-size:0.875rem;">${knownQuestions.length} question${knownQuestions.length !== 1 ? "s" : ""}</span>
                </div>
                <p style="font-size:0.875rem; color:var(--color-text-secondary); margin-bottom:1rem;">
                    These questions were marked as "I Know This" — they were not counted in your exam score.
                </p>
                ${items}
            </div>
        `;
    }

    // ── Render Unattempted Section ───────────────────────────
    function renderUnattemptedSection(unattemptedQuestions) {
        const items = unattemptedQuestions.map(q => `
            <div class="unattempted-question-item">
                <span style="font-size:1rem; flex-shrink:0; color:var(--color-text-muted);">⬜</span>
                <span class="unattempted-question-text">${escapeHtml(q.question_text)}</span>
            </div>
        `).join("");

        return `
            <div style="margin-top:2rem;">
                <div class="section-header" style="margin-top:0;">
                    <h2 style="color:var(--color-text-secondary);">⬜ Unattempted Questions</h2>
                    <span style="color:var(--color-text-muted); font-size:0.875rem;">${unattemptedQuestions.length} question${unattemptedQuestions.length !== 1 ? "s" : ""}</span>
                </div>
                ${items}
            </div>
        `;
    }

    document.addEventListener("DOMContentLoaded", load);
})();
