/**
 * STUDYFLIP — Progress Page Module
 * Loads and renders progress stats, subject performance, weak areas, and exam history.
 */

(() => {
    "use strict";

    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = String(text || "");
        return div.innerHTML;
    }

    function getScoreBadgeClass(score) {
        if (score >= 80) return "score-badge--high";
        if (score >= 60) return "score-badge--mid";
        return "score-badge--low";
    }

    function getBarColor(score) {
        if (score >= 80) return "var(--color-success)";
        if (score >= 60) return "var(--color-warning)";
        return "var(--color-danger)";
    }

    function showToast(message, type = "info") {
        const container = document.getElementById("toast-container");
        const toast = document.createElement("div");
        toast.className = `toast toast--${type}`;
        toast.textContent = message;
        container.appendChild(toast);
        setTimeout(() => toast.remove(), 3500);
    }

    // ── Load and render all ──────────────────────────────────
    async function load() {
        try {
            const [progressRes, historyRes, weakRes] = await Promise.all([
                fetch("/api/progress"),
                fetch("/api/exam-history"),
                fetch("/api/weak-areas")
            ]);

            const progress = await progressRes.json();
            const history = await historyRes.json();
            const weak = await weakRes.json();

            renderStats(progress);
            renderSubjectPerformance(progress.subject_performance, progress.deck_accuracy);
            renderExamHistory(history);
            renderWeakAreas(weak);
        } catch (err) {
            console.error("Progress load error:", err);
            showToast("Failed to load progress data", "error");
        }
    }

    // ── Stats ────────────────────────────────────────────────
    function renderStats(p) {
        setText("p-total-exams", p.total_exams || 0);
        setText("p-avg-score", p.avg_score > 0 ? `${p.avg_score}%` : "—");
        setText("p-best-score", p.best_score > 0 ? `${p.best_score}%` : "—");
        setText("p-questions", p.total_questions_attempted || 0);
        setText("p-accuracy",
            p.overall_exam_accuracy > 0 ? `${p.overall_exam_accuracy}%`
            : (p.overall_study_accuracy > 0 ? `${p.overall_study_accuracy}%` : "—")
        );
        setText("p-mastered", p.cards_mastered || 0);
    }

    function setText(id, value) {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    }

    // ── Subject Performance ──────────────────────────────────
    function renderSubjectPerformance(subjects, deckAccuracy) {
        const container = document.getElementById("subject-performance-section");

        const hasExamData = subjects && subjects.length > 0;
        const hasStudyData = deckAccuracy && deckAccuracy.length > 0;

        if (!hasExamData && !hasStudyData) {
            container.innerHTML = `
                <div class="empty-state" style="padding:2rem; text-align:center;">
                    <span style="font-size:2rem;">📊</span>
                    <p style="color:var(--color-text-muted); margin-top:0.5rem;">
                        Complete some exams or study sessions to see subject performance.
                    </p>
                    <div style="display:flex; gap:1rem; justify-content:center; margin-top:1rem;">
                        <a href="/mock-exam" class="btn btn-primary btn-sm">Take Exam</a>
                        <a href="/decks" class="btn btn-ghost btn-sm">Study</a>
                    </div>
                </div>
            `;
            return;
        }

        let html = "";

        if (hasExamData) {
            html += `<p style="font-size:0.75rem; color:var(--color-text-muted); margin-bottom:1rem; text-transform:uppercase; letter-spacing:0.05em;">Exam Performance</p>`;
            html += subjects.map(s => {
                const score = s.avg_score;
                return `
                    <div class="subject-bar-item">
                        <div class="subject-bar-header">
                            <span class="subject-bar-name">${escapeHtml(s.subject)}</span>
                            <span class="subject-bar-score" style="color:${getBarColor(score)}">${score}%</span>
                        </div>
                        <div class="subject-bar-track">
                            <div class="subject-bar-fill" style="width:${score}%; background:${getBarColor(score)};"></div>
                        </div>
                        <div style="font-size:0.75rem; color:var(--color-text-muted); margin-top:4px;">
                            ${s.exam_count} exam${s.exam_count !== 1 ? "s" : ""} · Best: ${s.best_score}%
                        </div>
                    </div>
                `;
            }).join("");
        }

        if (hasStudyData) {
            html += `<p style="font-size:0.75rem; color:var(--color-text-muted); margin: 1rem 0; text-transform:uppercase; letter-spacing:0.05em;">Flashcard Study Accuracy</p>`;
            html += deckAccuracy.map(d => {
                const acc = d.accuracy;
                return `
                    <div class="subject-bar-item">
                        <div class="subject-bar-header">
                            <span class="subject-bar-name">${escapeHtml(d.name)}</span>
                            <span class="subject-bar-score" style="color:${getBarColor(acc)}">${acc}%</span>
                        </div>
                        <div class="subject-bar-track">
                            <div class="subject-bar-fill" style="width:${acc}%; background:${getBarColor(acc)};"></div>
                        </div>
                        <div style="font-size:0.75rem; color:var(--color-text-muted); margin-top:4px;">
                            ${d.attempts} attempts · ${d.correct} correct · ${d.reviews} reviews
                        </div>
                    </div>
                `;
            }).join("");
        }

        container.innerHTML = html;
    }

    // ── Exam History ─────────────────────────────────────────
    function renderExamHistory(exams) {
        const container = document.getElementById("exam-history-section");

        if (exams.length === 0) {
            container.innerHTML = `
                <div class="card-panel">
                    <div class="empty-state" style="padding:1.5rem; text-align:center;">
                        <span style="font-size:2rem;">📝</span>
                        <p style="color:var(--color-text-muted); margin-top:0.5rem;">No exams taken yet.</p>
                        <a href="/mock-exam" class="btn btn-primary btn-sm" style="margin-top:1rem;">Take Your First Exam</a>
                    </div>
                </div>
            `;
            return;
        }

        const rows = exams.map(e => {
            const badgeClass = getScoreBadgeClass(e.score);
            return `
                <tr>
                    <td>
                        <div style="font-weight:600; color:var(--color-text-primary)">${escapeHtml(e.deck_name)}</div>
                        <div style="font-size:0.75rem; color:var(--color-text-muted)">${e.subject ? escapeHtml(e.subject) : "General"}</div>
                    </td>
                    <td><span class="score-badge ${badgeClass}">${e.score}%</span></td>
                    <td>${e.accuracy}%</td>
                    <td>${e.date_str}</td>
                    <td>${e.time_str}</td>
                    <td>
                        <a href="/exam-result/${e.id}" class="btn btn-ghost btn-sm">View</a>
                    </td>
                </tr>
            `;
        }).join("");

        container.innerHTML = `
            <div class="card-panel" style="padding:0; overflow:hidden;">
                <table class="exam-history-table">
                    <thead>
                        <tr>
                            <th>Exam</th>
                            <th>Score</th>
                            <th>Accuracy</th>
                            <th>Date</th>
                            <th>Time</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        `;
    }

    // ── Weak Areas ───────────────────────────────────────────
    function renderWeakAreas(data) {
        const container = document.getElementById("weak-areas-progress-section");
        const weakCards = data.weak_cards || [];
        const weakSubjects = data.weak_subjects || [];

        if (weakCards.length === 0 && weakSubjects.length === 0) {
            container.innerHTML = `
                <div style="text-align:center; padding:1.5rem;">
                    <span style="font-size:2rem;">🎯</span>
                    <p style="color:var(--color-text-secondary); margin-top:0.5rem;">
                        No weak areas detected yet. Keep studying and taking exams!
                    </p>
                </div>
            `;
            return;
        }

        let html = "";

        if (weakSubjects.length > 0) {
            html += `<p style="font-size:0.75rem; color:var(--color-text-muted); margin-bottom:1rem; text-transform:uppercase; letter-spacing:0.05em;">Subjects Needing Attention</p>`;
            html += weakSubjects.map(s => `
                <div class="weak-area-item">
                    <div class="weak-area-info">
                        <div class="weak-area-name">${escapeHtml(s.subject)}</div>
                        <div class="weak-area-subject">${s.exams} exam${s.exams !== 1 ? "s" : ""} taken</div>
                    </div>
                    <span class="weak-area-badge">Avg ${s.avg_score}%</span>
                </div>
            `).join("");
        }

        if (weakCards.length > 0) {
            html += `<p style="font-size:0.75rem; color:var(--color-text-muted); margin: ${weakSubjects.length ? '1rem' : '0'} 0 1rem; text-transform:uppercase; letter-spacing:0.05em;">Cards to Review</p>`;
            html += weakCards.slice(0, 5).map(c => `
                <div class="weak-area-item">
                    <div class="weak-area-info">
                        <div class="weak-area-name">${escapeHtml(c.question.substring(0, 60))}${c.question.length > 60 ? "..." : ""}</div>
                        <div class="weak-area-subject">${escapeHtml(c.deck_name)} · ${c.attempts} attempts</div>
                    </div>
                    <span class="weak-area-badge">${c.accuracy}%</span>
                </div>
            `).join("");
        }

        html += `
            <div style="margin-top:1.5rem; padding-top:1rem; border-top:var(--border-subtle);">
                <p style="font-size:0.875rem; font-weight:600; color:var(--color-text-primary); margin-bottom:0.75rem;">Recommended Actions</p>
                <div style="display:flex; flex-direction:column; gap:0.5rem;">
                    <a href="/smart-review" class="btn btn-ghost btn-sm">🧠 Start Smart Review</a>
                    <a href="/mock-exam" class="btn btn-ghost btn-sm">📝 Retry Mock Exam</a>
                </div>
            </div>
        `;

        container.innerHTML = html;
    }

    document.addEventListener("DOMContentLoaded", load);
})();
