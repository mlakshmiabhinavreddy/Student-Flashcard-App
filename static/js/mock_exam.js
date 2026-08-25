/**
 * STUDYFLIP — Mock Exam Module
 *
 * Manages 3 screens:
 *   1. Exam Picker  — choose a deck
 *   2. Exam Config  — set questions/time
 *   3. Active Exam  — timed MCQ exam with submit + "I Know This"
 *
 * Question Status:
 *   UNATTEMPTED     — default state
 *   ANSWERED        — student selected an MCQ option (correct OR incorrect)
 *   KNOWN           — student clicked "I Know This" (self-mastered, not counted in score)
 */

const MockExam = (() => {
    "use strict";

    let selectedDeck = null;
    let examId = null;
    let questions = [];
    let currentIndex = 0;
    let answers = {};          // { question_id: "a" | "b" | "c" | "d" }
    let knownQuestions = {};   // { question_id: true } — I Know This
    let timerInterval = null;
    let secondsRemaining = 0;
    let startTimestamp = 0;
    let isSubmitting = false;

    // ── Pending know-this question (for confirmation modal) ───
    let pendingKnowThisId = null;

    // ── Utility ─────────────────────────────────────────────
    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = String(text || "");
        return div.innerHTML;
    }

    function showToast(message, type = "info") {
        const container = document.getElementById("toast-container");
        const toast = document.createElement("div");
        toast.className = `toast toast--${type}`;
        toast.textContent = message;
        container.appendChild(toast);
        setTimeout(() => toast.remove(), 3500);
    }

    // ── Screen transitions ───────────────────────────────────
    function showScreen(name) {
        ["exam-picker", "exam-config", "exam-active"].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.style.display = (id === name) ? "block" : "none";
        });
    }

    // ── Phase 1: Exam Picker ─────────────────────────────────
    async function loadPicker() {
        showScreen("exam-picker");
        const container = document.getElementById("picker-decks-container");

        try {
            const res = await fetch("/api/decks");
            if (!res.ok) throw new Error("Failed to load decks");
            const decks = await res.json();

            if (decks.length === 0) {
                container.innerHTML = `
                    <div class="empty-state card-panel">
                        <span class="empty-state-icon">📚</span>
                        <h3>No decks available</h3>
                        <p>Create a deck and add flashcards before taking a mock exam.</p>
                        <a href="/decks" class="btn btn-primary">+ Create a Deck</a>
                    </div>
                `;
                return;
            }

            // Filter decks with at least 4 cards (minimum for MCQ)
            const readyDecks = decks.filter(d => d.card_count >= 4);
            const notReadyDecks = decks.filter(d => d.card_count < 4);

            let html = `<div class="exam-picker-grid">`;
            for (const deck of readyDecks) {
                html += `
                    <div class="exam-deck-card" onclick="MockExam.selectDeck(${deck.id})">
                        <div class="exam-deck-name">${escapeHtml(deck.name)}</div>
                        <div class="exam-deck-subject">${deck.subject ? escapeHtml(deck.subject) : "General"}</div>
                        <div class="exam-deck-meta">
                            <span>🃏 ${deck.card_count} cards</span>
                        </div>
                        <button class="btn btn-primary btn-sm" style="width:100%">
                            📝 Select for Exam
                        </button>
                    </div>
                `;
            }
            html += `</div>`;

            if (notReadyDecks.length > 0) {
                html += `
                    <div style="margin-top:1.5rem;">
                        <p style="color:var(--color-text-muted); font-size:0.875rem;">
                            ⚠️ These decks need at least 4 cards to generate MCQ options:
                            ${notReadyDecks.map(d => `<strong>${escapeHtml(d.name)}</strong> (${d.card_count} card${d.card_count !== 1 ? 's' : ''})`).join(", ")}
                        </p>
                    </div>
                `;
            }

            container.innerHTML = html;
        } catch (err) {
            container.innerHTML = `
                <div class="empty-state card-panel">
                    <span class="empty-state-icon">⚠️</span>
                    <h3>Failed to load decks</h3>
                    <p>Please refresh the page and try again.</p>
                </div>
            `;
        }
    }

    function selectDeck(deckId) {
        fetch(`/api/decks/${deckId}`)
            .then(r => r.json())
            .then(deck => {
                selectedDeck = deck;
                showConfigScreen(deck);
            });
    }

    function showPicker() {
        selectedDeck = null;
        loadPicker();
    }

    // ── Phase 2: Config Screen ───────────────────────────────
    function showConfigScreen(deck) {
        document.getElementById("config-deck-name").textContent = deck.name;
        document.getElementById("config-deck-subject").textContent =
            deck.subject ? `Subject: ${deck.subject}` : "General";

        const numSel = document.getElementById("config-num-questions");
        const maxQ = Math.min(30, deck.card_count);
        Array.from(numSel.options).forEach(opt => {
            opt.disabled = parseInt(opt.value) > maxQ;
        });
        const defaultQ = maxQ >= 20 ? "20" : String(maxQ);
        numSel.value = defaultQ;

        showScreen("exam-config");
    }

    // ── Phase 3: Start Exam ──────────────────────────────────
    async function startExam() {
        if (!selectedDeck) return;

        const numQ = parseInt(document.getElementById("config-num-questions").value);
        const timeLimitMins = parseInt(document.getElementById("config-time-limit").value);

        const btn = document.getElementById("btn-start-exam");
        btn.textContent = "Creating exam...";
        btn.disabled = true;

        try {
            const res = await fetch("/api/mock-exam/start", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ deck_id: selectedDeck.id, num_questions: numQ })
            });

            if (!res.ok) {
                const err = await res.json();
                showToast(err.error || "Failed to create exam", "error");
                btn.textContent = "🚀 Start Exam";
                btn.disabled = false;
                return;
            }

            const data = await res.json();
            examId = data.exam.id;
            questions = data.questions;
            currentIndex = 0;
            answers = {};
            knownQuestions = {};
            secondsRemaining = timeLimitMins * 60;
            startTimestamp = Date.now();
            isSubmitting = false;

            showScreen("exam-active");
            renderQuestion();
            startTimer();

            btn.textContent = "🚀 Start Exam";
            btn.disabled = false;
        } catch (err) {
            showToast("Network error. Please try again.", "error");
            btn.textContent = "🚀 Start Exam";
            btn.disabled = false;
        }
    }

    // ── Timer ────────────────────────────────────────────────
    function startTimer() {
        updateTimerDisplay();
        timerInterval = setInterval(() => {
            secondsRemaining--;
            updateTimerDisplay();

            if (secondsRemaining <= 0) {
                clearInterval(timerInterval);
                document.getElementById("timeout-modal-overlay").classList.add("active");
                setTimeout(() => submitExam(), 2000);
            }
        }, 1000);
    }

    function updateTimerDisplay() {
        const mins = Math.floor(secondsRemaining / 60);
        const secs = secondsRemaining % 60;
        const display = document.getElementById("timer-display");
        const timer = document.getElementById("exam-timer");

        if (display) {
            display.textContent = `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
        }
        if (timer) {
            timer.classList.remove("timer--warning", "timer--danger");
            if (secondsRemaining <= 60) timer.classList.add("timer--danger");
            else if (secondsRemaining <= 300) timer.classList.add("timer--warning");
        }
    }

    // ── Get question status ──────────────────────────────────
    function getQuestionStatus(questionId) {
        if (knownQuestions[questionId]) return "known";
        if (answers[questionId]) return "answered";
        return "unattempted";
    }

    // ── Render question ──────────────────────────────────────
    function renderQuestion() {
        const q = questions[currentIndex];
        const total = questions.length;

        // Update header
        document.getElementById("exam-header-name").textContent =
            selectedDeck ? selectedDeck.name : "Mock Exam";
        document.getElementById("q-num").textContent = currentIndex + 1;
        document.getElementById("q-total").textContent = total;
        document.getElementById("exam-question-count").textContent =
            `Question ${currentIndex + 1} of ${total}`;

        // Progress bar
        const pct = Math.round(((currentIndex + 1) / total) * 100);
        const fill = document.getElementById("exam-progress-fill");
        if (fill) fill.style.width = pct + "%";

        // Question text
        document.getElementById("exam-question-text").textContent = q.question_text;

        // Options
        const optionsContainer = document.getElementById("exam-options");
        const opts = [
            { key: "a", text: q.option_a },
            { key: "b", text: q.option_b },
            { key: "c", text: q.option_c },
            { key: "d", text: q.option_d }
        ];

        const isKnown = !!knownQuestions[q.id];
        const selected = answers[q.id];

        // Render options — disabled if question is already marked known
        optionsContainer.innerHTML = opts.map(opt => `
            <button
                class="exam-option${selected === opt.key ? " selected" : ""}${isKnown ? " exam-option--known" : ""}"
                onclick="${isKnown ? '' : `MockExam.selectAnswer('${opt.key}')`}"
                id="opt-${opt.key}"
                aria-label="Option ${opt.key.toUpperCase()}: ${escapeHtml(opt.text)}"
                ${isKnown ? 'disabled title="You marked this as I Know This"' : ''}
            >
                <span class="exam-option-letter">${opt.key}</span>
                <span class="exam-option-text">${escapeHtml(opt.text)}</span>
            </button>
        `).join("");

        // "I Know This" button
        const knowThisBtn = document.getElementById("btn-know-this");
        if (knowThisBtn) {
            if (isKnown) {
                knowThisBtn.textContent = "💡 Known ✓";
                knowThisBtn.disabled = true;
                knowThisBtn.classList.add("known");
            } else if (selected) {
                // If already answered, don't allow "I Know This"
                knowThisBtn.textContent = "💡 I Know This";
                knowThisBtn.disabled = true;
                knowThisBtn.title = "You already selected an answer";
            } else {
                knowThisBtn.textContent = "💡 I Know This";
                knowThisBtn.disabled = false;
                knowThisBtn.classList.remove("known");
                knowThisBtn.title = "Mark this question as self-mastered (won't affect exam score)";
            }
        }

        // Navigation buttons
        const btnPrev = document.getElementById("btn-prev");
        const btnNext = document.getElementById("btn-next");
        const btnSubmit = document.getElementById("btn-submit");

        btnPrev.disabled = currentIndex === 0;

        if (currentIndex === total - 1) {
            btnNext.style.display = "none";
            btnSubmit.style.display = "inline-flex";
        } else {
            btnNext.style.display = "inline-flex";
            btnSubmit.style.display = "none";
        }

        // Update dots
        renderDots();
    }

    function renderDots() {
        const container = document.getElementById("exam-dots");
        if (!container) return;
        container.innerHTML = questions.map((q, i) => {
            const status = getQuestionStatus(q.id);
            let dotClass = "exam-dot";
            let dotTitle = `Question ${i + 1}`;
            let dotLabel = i + 1;

            if (i === currentIndex) dotClass += " current";
            if (status === "answered") { dotClass += " answered"; dotTitle += " ✓ Answered"; }
            if (status === "known") { dotClass += " known"; dotTitle += " 💡 Known"; }

            return `<div class="${dotClass}"
                         onclick="MockExam.goToQuestion(${i})"
                         title="${dotTitle}"
                         aria-label="${dotTitle}">
                        ${dotLabel}
                    </div>`;
        }).join("");
    }

    function selectAnswer(optKey) {
        const q = questions[currentIndex];
        // Cannot select answer if question is already self-mastered
        if (knownQuestions[q.id]) return;
        answers[q.id] = optKey;
        renderQuestion();
    }

    function prevQuestion() {
        if (currentIndex > 0) {
            currentIndex--;
            renderQuestion();
        }
    }

    function nextQuestion() {
        if (currentIndex < questions.length - 1) {
            currentIndex++;
            renderQuestion();
        }
    }

    function goToQuestion(index) {
        currentIndex = index;
        renderQuestion();
    }

    // ── I Know This Flow ─────────────────────────────────────
    function promptKnowThis() {
        const q = questions[currentIndex];
        // Can't use if already answered
        if (answers[q.id]) {
            showToast("You already selected an answer for this question.", "info");
            return;
        }
        if (knownQuestions[q.id]) {
            showToast("This question is already marked as known.", "info");
            return;
        }

        pendingKnowThisId = q.id;

        // Update modal question info
        const qText = document.getElementById("know-this-question-text");
        if (qText) qText.textContent = q.question_text;

        // Show confirmation modal
        document.getElementById("know-this-modal-overlay").classList.add("active");
    }

    async function confirmKnowThis() {
        if (!pendingKnowThisId || !examId) return;

        const questionId = pendingKnowThisId;
        pendingKnowThisId = null;

        // Close modal
        document.getElementById("know-this-modal-overlay").classList.remove("active");

        try {
            const res = await fetch(`/api/mock-exam/${examId}/know-this`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ question_id: questionId })
            });

            if (res.ok) {
                knownQuestions[questionId] = true;
                // Remove any previously selected answer for this question
                delete answers[questionId];

                showToast("💡 Marked as Self-Mastered! (Exam score unchanged)", "success");
                renderQuestion();
            } else {
                const err = await res.json();
                showToast(err.error || "Failed to mark as known", "error");
            }
        } catch (e) {
            showToast("Network error. Please try again.", "error");
        }
    }

    function cancelKnowThis() {
        pendingKnowThisId = null;
        document.getElementById("know-this-modal-overlay").classList.remove("active");
    }

    // ── Submit Flow ──────────────────────────────────────────
    function confirmSubmit() {
        const answered = Object.keys(answers).length;
        const known = Object.keys(knownQuestions).length;
        const total = questions.length;
        const unanswered = total - answered - known;

        const msg = document.getElementById("submit-confirm-msg");
        if (unanswered > 0) {
            msg.innerHTML = `You have <strong>${unanswered}</strong> unanswered question${unanswered !== 1 ? "s" : ""}${known > 0 ? ` and <strong>${known}</strong> marked as "I Know This"` : ""}. Are you sure you want to submit?`;
        } else {
            msg.textContent = `You have answered all ${answered} question${answered !== 1 ? "s" : ""}${known > 0 ? ` and marked ${known} as "I Know This"` : ""}. Ready to submit?`;
        }
        document.getElementById("submit-modal-overlay").classList.add("active");
    }

    function closeSubmitModal() {
        document.getElementById("submit-modal-overlay").classList.remove("active");
    }

    async function submitExam() {
        if (isSubmitting) return;
        isSubmitting = true;

        clearInterval(timerInterval);

        // Close modals
        const submitModal = document.getElementById("submit-modal-overlay");
        const timeoutModal = document.getElementById("timeout-modal-overlay");
        if (submitModal) submitModal.classList.remove("active");
        if (timeoutModal) timeoutModal.classList.remove("active");

        const timeTaken = Math.floor((Date.now() - startTimestamp) / 1000);

        // Build answers payload — only include questions that were actually answered
        // (not self-mastered ones — those were already sent to the server via know-this API)
        const answersPayload = {};
        for (const [qId, ans] of Object.entries(answers)) {
            answersPayload[String(qId)] = ans;
        }

        try {
            const res = await fetch(`/api/mock-exam/${examId}/submit`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ answers: answersPayload, time_taken: timeTaken })
            });

            if (res.ok) {
                window.location.href = `/exam-result/${examId}`;
            } else {
                showToast("Failed to submit exam. Please try again.", "error");
                isSubmitting = false;
            }
        } catch (err) {
            showToast("Network error during submit.", "error");
            isSubmitting = false;
        }
    }

    // ── Boot ─────────────────────────────────────────────────
    document.addEventListener("DOMContentLoaded", loadPicker);

    // Keyboard shortcuts during exam
    document.addEventListener("keydown", (e) => {
        const activeScreen = document.getElementById("exam-active");
        if (!activeScreen || activeScreen.style.display === "none") return;

        if (e.key === "ArrowRight") nextQuestion();
        else if (e.key === "ArrowLeft") prevQuestion();
        else if (e.key === "a" || e.key === "1") selectAnswer("a");
        else if (e.key === "b" || e.key === "2") selectAnswer("b");
        else if (e.key === "c" || e.key === "3") selectAnswer("c");
        else if (e.key === "d" || e.key === "4") selectAnswer("d");
    });

    // Warn before leaving during active exam
    window.addEventListener("beforeunload", (e) => {
        if (examId && !isSubmitting && secondsRemaining > 0) {
            e.preventDefault();
            e.returnValue = "Your exam is in progress. Are you sure you want to leave?";
        }
    });

    return {
        loadPicker,
        selectDeck,
        showPicker,
        startExam,
        selectAnswer,
        prevQuestion,
        nextQuestion,
        goToQuestion,
        confirmSubmit,
        closeSubmitModal,
        submitExam,
        promptKnowThis,
        confirmKnowThis,
        cancelKnowThis
    };
})();
