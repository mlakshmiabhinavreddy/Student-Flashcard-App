/**
 * STUDYFLIP — Dashboard Module
 * Fetches user stats from GET /api/dashboard and renders
 * the full learning overview: stat cards + deck progress + weak areas + recent exams.
 */

const Dashboard = (() => {
    "use strict";

    function showToast(message, type = "info") {
        const container = document.getElementById("toast-container");
        const toast = document.createElement("div");
        toast.className = `toast toast--${type}`;
        toast.textContent = message;
        container.appendChild(toast);
        setTimeout(() => toast.remove(), 3500);
    }

    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = String(text || "");
        return div.innerHTML;
    }

    // ── Load dashboard data ─────────────────────────────────
    async function load() {
        try {
            const [dashRes, weakRes] = await Promise.all([
                fetch("/api/dashboard"),
                fetch("/api/weak-areas")
            ]);

            if (!dashRes.ok) throw new Error(`API error: ${dashRes.status}`);
            const data = await dashRes.json();
            const weak = weakRes.ok ? await weakRes.json() : { weak_cards: [], weak_subjects: [] };

            renderStats(data);
            renderBreakdown(data.decks);
            renderWeakAreas(weak);
            renderRecentExams(data.recent_exams || []);
        } catch (err) {
            console.error("Dashboard load error:", err);
            showToast("Failed to load dashboard data", "error");
        }
    }

    // ── Render the stat cards ────────────────────────────────
    function renderStats(data) {
        animateValue("stat-total-decks", data.total_decks);
        animateValue("stat-total-cards", data.total_cards);
        animateValue("stat-mastered", data.questions_mastered || 0);
        animateValue("stat-exams", data.total_exams || 0);

        const avgScore = document.getElementById("stat-avg-score");
        if (avgScore) {
            avgScore.textContent = data.avg_exam_score > 0 ? `${data.avg_exam_score}%` : "—";
        }

        const accuracy = document.getElementById("stat-accuracy");
        if (accuracy) {
            accuracy.textContent = data.overall_accuracy > 0 ? `${data.overall_accuracy}%` : "—";
        }

        // Smart Review Banner
        const smartReviewText = document.getElementById("smart-review-count-text");
        if (smartReviewText) {
            if (data.cards_needing_review > 0) {
                smartReviewText.textContent = `🔥 ${data.cards_needing_review} card${data.cards_needing_review !== 1 ? 's' : ''} need attention`;
                smartReviewText.style.color = "var(--color-warning)";
            } else if (data.total_cards > 0) {
                smartReviewText.textContent = "✨ All cards mastered! Review your queue to stay sharp.";
                smartReviewText.style.color = "var(--color-success)";
            } else {
                smartReviewText.textContent = "Create a deck and add cards to activate Smart Review.";
                smartReviewText.style.color = "var(--color-text-secondary)";
            }
        }
    }

    // Simple number count-up animation
    function animateValue(elementId, target) {
        const el = document.getElementById(elementId);
        if (!el) return;
        if (target === 0) { el.textContent = "0"; return; }

        let current = 0;
        const step = Math.max(1, Math.floor(target / 20));
        const interval = setInterval(() => {
            current += step;
            if (current >= target) {
                current = target;
                clearInterval(interval);
            }
            el.textContent = current;
        }, 30);
    }

    // ── Render per-deck breakdown ────────────────────────────
    function renderBreakdown(decks) {
        const section = document.getElementById("deck-breakdown-section");
        if (!section) return;

        if (decks.length === 0) {
            section.innerHTML = `
                <div class="empty-state card-panel">
                    <span class="empty-state-icon">📚</span>
                    <h3>No decks yet</h3>
                    <p>Create your first flashcard deck to start tracking progress.</p>
                    <a href="/decks" class="btn btn-primary">+ Create Deck</a>
                </div>
            `;
            return;
        }

        let html = `<div class="dashboard-decks">`;
        for (const deck of decks) {
            html += renderDeckRow(deck);
        }
        html += '</div>';
        section.innerHTML = html;
    }

    function renderDeckRow(deck) {
        const progress = deck.progress || 0;
        const accuracy = deck.accuracy || 0;

        let accColor = "var(--color-text-muted)";
        if (deck.total_attempts > 0) {
            if (accuracy >= 80) accColor = "var(--color-success)";
            else if (accuracy >= 50) accColor = "var(--color-warning)";
            else accColor = "var(--color-danger)";
        }
        const accDisplay = deck.total_attempts > 0 ? `${accuracy}%` : "—";

        return `
            <div class="dashboard-deck-card" style="margin-bottom:1rem;">
                <div class="dashboard-deck-main">
                    <div class="dashboard-deck-info">
                        <h3 class="dashboard-deck-name">${escapeHtml(deck.name)}</h3>
                        <p class="dashboard-deck-desc">
                            ${deck.subject ? `<span style="color:var(--color-accent); font-size:0.8rem; font-weight:600;">📌 ${escapeHtml(deck.subject)}</span>` : ""}
                            ${deck.description ? `<span class="text-muted">${escapeHtml(deck.description)}</span>` : ""}
                        </p>
                    </div>
                    <div class="dashboard-deck-stats">
                        <div class="dashboard-stat-item">
                            <span class="dashboard-stat-value">${deck.card_count}</span>
                            <span class="dashboard-stat-label">Cards</span>
                        </div>
                        <div class="dashboard-stat-item">
                            <span class="dashboard-stat-value">${deck.cards_studied}</span>
                            <span class="dashboard-stat-label">Studied</span>
                        </div>
                        <div class="dashboard-stat-item">
                            <span class="dashboard-stat-value" style="color:var(--color-warning)">${deck.review_count}</span>
                            <span class="dashboard-stat-label">Reviews</span>
                        </div>
                        <div class="dashboard-stat-item">
                            <span class="dashboard-stat-value" style="color:${accColor}">${accDisplay}</span>
                            <span class="dashboard-stat-label">Accuracy</span>
                        </div>
                    </div>
                </div>

                <div class="dashboard-deck-progress">
                    <div class="dashboard-progress-header">
                        <span class="dashboard-progress-label">${Math.round(progress)}% mastered</span>
                        <span class="dashboard-progress-pct">${deck.cards_studied}/${deck.card_count}</span>
                    </div>
                    <div class="progress-bar-track">
                        <div class="progress-bar-fill" style="width:${progress}%"></div>
                    </div>
                </div>

                <div class="dashboard-deck-actions">
                    <a href="/deck/${deck.id}" class="btn btn-ghost btn-sm">View Deck</a>
                    ${deck.card_count > 0
                        ? `<a href="/study/${deck.id}" class="btn btn-success btn-sm">▶ Continue Studying</a>`
                        : `<span class="btn btn-ghost btn-sm" style="opacity:0.4;cursor:default">▶ Continue Studying</span>`
                    }
                    ${deck.card_count >= 4
                        ? `<a href="/mock-exam" class="btn btn-primary btn-sm" onclick="sessionStorage.setItem('preselect_deck', '${deck.id}')">📝 Mock Exam</a>`
                        : ""
                    }
                </div>
            </div>
        `;
    }

    // ── Render weak areas ────────────────────────────────────
    function renderWeakAreas(data) {
        const container = document.getElementById("weak-areas-section");
        if (!container) return;

        const weakCards = data.weak_cards || [];
        const weakSubjects = data.weak_subjects || [];

        if (weakCards.length === 0 && weakSubjects.length === 0) {
            container.innerHTML = `
                <div style="text-align:center; padding:1rem;">
                    <span style="font-size:1.5rem;">🎯</span>
                    <p style="color:var(--color-text-muted); font-size:0.875rem; margin-top:0.5rem;">
                        No weak areas detected. Keep studying!
                    </p>
                </div>
            `;
            return;
        }

        let html = "";
        const items = [...weakSubjects.slice(0, 2), ...weakCards.slice(0, 3)];

        if (weakSubjects.length > 0) {
            weakSubjects.slice(0, 2).forEach(s => {
                html += `
                    <div class="weak-area-item">
                        <div class="weak-area-info">
                            <div class="weak-area-name">${escapeHtml(s.subject)}</div>
                            <div class="weak-area-subject">Exam Performance</div>
                        </div>
                        <span class="weak-area-badge">Avg ${s.avg_score}%</span>
                    </div>
                `;
            });
        }

        if (weakCards.length > 0) {
            weakCards.slice(0, 3).forEach(c => {
                html += `
                    <div class="weak-area-item">
                        <div class="weak-area-info">
                            <div class="weak-area-name">${escapeHtml(c.question.substring(0, 50))}${c.question.length > 50 ? "..." : ""}</div>
                            <div class="weak-area-subject">${escapeHtml(c.deck_name)}</div>
                        </div>
                        <span class="weak-area-badge">${c.accuracy}%</span>
                    </div>
                `;
            });
        }

        html += `
            <div style="margin-top:1rem; padding-top:0.75rem; border-top:var(--border-subtle);">
                <a href="/progress" class="btn btn-ghost btn-sm" style="width:100%;">View Full Analysis →</a>
            </div>
        `;

        container.innerHTML = html;
    }

    // ── Render recent exams ──────────────────────────────────
    function renderRecentExams(exams) {
        const container = document.getElementById("recent-exams-section");
        if (!container) return;

        if (exams.length === 0) {
            container.innerHTML = `
                <div style="text-align:center; padding:1rem;">
                    <span style="font-size:1.5rem;">📝</span>
                    <p style="color:var(--color-text-muted); font-size:0.875rem; margin-top:0.5rem;">
                        No exams taken yet. <a href="/mock-exam" style="color:var(--color-accent);">Take your first!</a>
                    </p>
                </div>
            `;
            return;
        }

        let html = "";
        exams.forEach(e => {
            let scoreColor = "var(--color-success)";
            if (e.score < 60) scoreColor = "var(--color-danger)";
            else if (e.score < 80) scoreColor = "var(--color-warning)";

            const secs = e.time_taken || 0;
            const timeStr = `${Math.floor(secs / 60)}m ${(secs % 60).toString().padStart(2, "0")}s`;
            const date = e.completed_at ? e.completed_at.slice(0, 10) : "";

            html += `
                <a href="/exam-result/${e.id}" class="recent-exam-item">
                    <div>
                        <div class="recent-exam-name">${escapeHtml(e.deck_name)}</div>
                        <div class="recent-exam-date">${date} · ${timeStr}</div>
                    </div>
                    <span class="recent-exam-score" style="color:${scoreColor}">${e.score}%</span>
                </a>
            `;
        });

        html += `<a href="/progress" class="btn btn-ghost btn-sm" style="width:100%; margin-top:0.5rem;">View All History →</a>`;
        container.innerHTML = html;
    }

    // ── Boot ────────────────────────────────────────────────
    document.addEventListener("DOMContentLoaded", load);

    return { load };
})();
