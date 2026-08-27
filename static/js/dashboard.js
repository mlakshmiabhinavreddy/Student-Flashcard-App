/**
 * STUDYFLIP — Dashboard Module
 *
 * Fetches:
 *   GET /api/dashboard
 *   GET /api/weak-areas
 *   GET /api/adaptive-recommendations
 *
 * Renders:
 *   - Dashboard statistics
 *   - Deck progress
 *   - Weak areas
 *   - Recent exams
 *   - Adaptive recommendations
 */

const Dashboard = (() => {
    "use strict";


    // =========================================================
    // TOAST
    // =========================================================

    function showToast(message, type = "info") {

        const container =
            document.getElementById("toast-container");

        if (!container) {
            console.log(`[${type}] ${message}`);
            return;
        }

        const toast =
            document.createElement("div");

        toast.className =
            `toast toast--${type}`;

        toast.textContent =
            message;

        container.appendChild(toast);

        setTimeout(() => {
            toast.remove();
        }, 3500);
    }


    // =========================================================
    // HTML ESCAPE
    // =========================================================

    function escapeHtml(text) {

        const div =
            document.createElement("div");

        div.textContent =
            String(text ?? "");

        return div.innerHTML;
    }


    // =========================================================
    // MAIN LOAD
    // =========================================================

    async function load() {

        console.log(
            "[DASHBOARD] Loading dashboard..."
        );

        try {

            const [
                dashRes,
                weakRes,
                adaptiveRes
            ] = await Promise.all([

                fetch(
                    "/api/dashboard",
                    {
                        cache: "no-store"
                    }
                ),

                fetch(
                    "/api/weak-areas",
                    {
                        cache: "no-store"
                    }
                ),

                fetch(
                    "/api/adaptive-recommendations",
                    {
                        cache: "no-store"
                    }
                )
            ]);


            // =================================================
            // DASHBOARD API
            // =================================================

            if (!dashRes.ok) {

                throw new Error(
                    `Dashboard API error: ${dashRes.status}`
                );
            }

            const data =
                await dashRes.json();

            console.log(
                "[DASHBOARD] API data:",
                data
            );

            console.log(
                "[DASHBOARD] Decks:",
                data.decks || []
            );


            // =================================================
            // WEAK AREAS API
            // =================================================

            let weak = {
                weak_cards: [],
                weak_subjects: []
            };

            if (weakRes.ok) {

                try {

                    weak =
                        await weakRes.json();

                } catch (error) {

                    console.error(
                        "[WEAK AREAS] JSON error:",
                        error
                    );
                }

            } else {

                console.error(
                    "[WEAK AREAS] HTTP error:",
                    weakRes.status
                );
            }


            // =================================================
            // ADAPTIVE RECOMMENDATIONS API
            // =================================================

            let adaptive = {

                success: false,

                user_id: null,

                recommendations: [],

                best_recommendation: null,

                count: 0
            };


            if (adaptiveRes.ok) {

                try {

                    adaptive =
                        await adaptiveRes.json();

                    console.log(
                        "[ADAPTIVE] Recommendations:",
                        adaptive
                    );

                } catch (error) {

                    console.error(
                        "[ADAPTIVE] JSON error:",
                        error
                    );
                }

            } else {

                console.error(
                    "[ADAPTIVE] HTTP error:",
                    adaptiveRes.status
                );
            }


            // =================================================
            // RENDER EVERYTHING
            // =================================================

            renderStats(data);

            renderBreakdown(
                Array.isArray(data.decks)
                    ? data.decks
                    : []
            );

            renderWeakAreas(
                weak
            );

            renderRecentExams(
                Array.isArray(data.recent_exams)
                    ? data.recent_exams
                    : []
            );

            renderAdaptiveRecommendations(
                adaptive,
                Array.isArray(data.decks)
                    ? data.decks
                    : []
            );


            console.log(
                "[DASHBOARD] Rendering completed."
            );


        } catch (error) {

            console.error(
                "[DASHBOARD] Load error:",
                error
            );

            showToast(
                "Failed to load dashboard data",
                "error"
            );
        }
    }


    // =========================================================
    // STATS
    // =========================================================

    function renderStats(data) {

        console.log(
            "[DASHBOARD] Rendering stats:",
            data
        );


        // -----------------------------------------------------
        // TOTAL DECKS
        // -----------------------------------------------------

        animateValue(
            "stat-total-decks",
            data.total_decks || 0
        );


        // -----------------------------------------------------
        // TOTAL CARDS
        // -----------------------------------------------------

        animateValue(
            "stat-total-cards",
            data.total_cards || 0
        );


        // -----------------------------------------------------
        // QUESTIONS MASTERED
        // -----------------------------------------------------

        animateValue(
            "stat-mastered",
            data.questions_mastered || 0
        );


        // -----------------------------------------------------
        // MOCK EXAMS
        // -----------------------------------------------------

        animateValue(
            "stat-exams",
            data.total_exams || 0
        );


        // -----------------------------------------------------
        // AVERAGE EXAM SCORE
        // -----------------------------------------------------

        const avgScore =
            document.getElementById(
                "stat-avg-score"
            );

        if (avgScore) {

            const value =
                Number(
                    data.avg_exam_score || 0
                );

            avgScore.textContent =
                value > 0
                    ? `${value}%`
                    : "—";
        }


        // -----------------------------------------------------
        // OVERALL ACCURACY
        // -----------------------------------------------------

        const accuracy =
            document.getElementById(
                "stat-accuracy"
            );

        if (accuracy) {

            const value =
                Number(
                    data.overall_accuracy || 0
                );

            accuracy.textContent =
                value > 0
                    ? `${value}%`
                    : "—";
        }


        // -----------------------------------------------------
        // SMART REVIEW MESSAGE
        // -----------------------------------------------------

        const smartReviewText =
            document.getElementById(
                "smart-review-count-text"
            );


        if (smartReviewText) {

            const needingReview =
                Number(
                    data.cards_needing_review || 0
                );

            const totalCards =
                Number(
                    data.total_cards || 0
                );


            if (needingReview > 0) {

                smartReviewText.textContent =
                    `🔥 ${needingReview} card` +
                    `${needingReview !== 1 ? "s" : ""}` +
                    ` need attention`;

                smartReviewText.style.color =
                    "var(--color-warning)";

            } else if (totalCards > 0) {

                smartReviewText.textContent =
                    "✨ All cards mastered! Review your queue to stay sharp.";

                smartReviewText.style.color =
                    "var(--color-success)";

            } else {

                smartReviewText.textContent =
                    "Create a deck and add cards to activate Smart Review.";

                smartReviewText.style.color =
                    "var(--color-text-secondary)";
            }
        }
    }


    // =========================================================
    // NUMBER ANIMATION
    // =========================================================

    function animateValue(
        elementId,
        target
    ) {

        const element =
            document.getElementById(
                elementId
            );

        if (!element) {
            return;
        }


        target =
            Number(target) || 0;


        if (target === 0) {

            element.textContent =
                "0";

            return;
        }


        let current = 0;


        const step =
            Math.max(
                1,
                Math.floor(
                    target / 20
                )
            );


        const interval =
            setInterval(() => {

                current += step;


                if (current >= target) {

                    current =
                        target;

                    clearInterval(
                        interval
                    );
                }


                element.textContent =
                    current;

            }, 30);
    }


    // =========================================================
    // DECK BREAKDOWN
    // =========================================================

    function renderBreakdown(decks) {

        console.log(
            "[DASHBOARD] Rendering decks:",
            decks
        );


        /*
         * IMPORTANT:
         *
         * Your dashboard.html contains:
         *
         * <div id="deck-breakdown-section">
         *
         * Therefore this MUST use the same ID.
         */

        const section =
            document.getElementById(
                "deck-breakdown-section"
            );


        if (!section) {

            console.error(
                "[DASHBOARD] ERROR: #deck-breakdown-section was not found."
            );

            return;
        }


        // -----------------------------------------------------
        // NO DECKS
        // -----------------------------------------------------

        if (
            !Array.isArray(decks) ||
            decks.length === 0
        ) {

            section.innerHTML = `

                <div
                    class="empty-state card-panel"
                >

                    <span
                        class="empty-state-icon"
                    >
                        📚
                    </span>


                    <h3>
                        No decks yet
                    </h3>


                    <p>
                        Create your first flashcard deck
                        to start tracking progress.
                    </p>


                    <a
                        href="/decks"
                        class="btn btn-primary"
                    >
                        + Create Deck
                    </a>

                </div>
            `;

            return;
        }


        let html =
            `<div class="dashboard-decks">`;


        decks.forEach(
            deck => {

                html +=
                    renderDeckRow(
                        deck
                    );
            }
        );


        html +=
            "</div>";


        section.innerHTML =
            html;
    }


    // =========================================================
    // INDIVIDUAL DECK
    // =========================================================

    function renderDeckRow(deck) {

        const deckId =
            String(
                deck.id ?? ""
            );


        const cardCount =
            Number(
                deck.card_count ??
                deck.cards ??
                0
            );


        const cardsStudied =
            Number(
                deck.cards_studied ??
                deck.mastered ??
                0
            );


        const reviewCount =
            Number(
                deck.review_count ??
                deck.reviews ??
                0
            );


        const totalAttempts =
            Number(
                deck.total_attempts ??
                0
            );


        const progress =
            Math.max(
                0,
                Math.min(
                    100,
                    Number(
                        deck.progress ?? 0
                    )
                )
            );


        const accuracy =
            Number(
                deck.accuracy ?? 0
            );


        // -----------------------------------------------------
        // ACCURACY COLOR
        // -----------------------------------------------------

        let accuracyColor =
            "var(--color-text-muted)";


        if (
            totalAttempts > 0
        ) {

            if (
                accuracy >= 80
            ) {

                accuracyColor =
                    "var(--color-success)";

            } else if (
                accuracy >= 50
            ) {

                accuracyColor =
                    "var(--color-warning)";

            } else {

                accuracyColor =
                    "var(--color-danger)";
            }
        }


        const accuracyDisplay =
            totalAttempts > 0
                ? `${accuracy.toFixed(1)}%`
                : "—";


        // -----------------------------------------------------
        // SUBJECT
        // -----------------------------------------------------

        const subjectHtml =
            deck.subject
                ? `
                    <span
                        style="
                            color:var(--color-accent);
                            font-size:0.8rem;
                            font-weight:600;
                        "
                    >
                        📌
                        ${escapeHtml(deck.subject)}
                    </span>
                `
                : "";


        // -----------------------------------------------------
        // DESCRIPTION
        // -----------------------------------------------------

        const descriptionHtml =
            deck.description
                ? `
                    <span class="text-muted">
                        ${escapeHtml(
                            deck.description
                        )}
                    </span>
                `
                : "";


        // -----------------------------------------------------
        // STUDY BUTTON
        // -----------------------------------------------------

        const studyButton =
            cardCount > 0
                ? `
                    <a
                        href="/study/${encodeURIComponent(deckId)}"
                        class="btn btn-success btn-sm"
                    >
                        ▶ Continue Studying
                    </a>
                `
                : `
                    <span
                        class="btn btn-ghost btn-sm"
                        style="
                            opacity:0.4;
                            cursor:default;
                        "
                    >
                        ▶ Continue Studying
                    </span>
                `;


        // -----------------------------------------------------
        // MOCK EXAM BUTTON
        // -----------------------------------------------------

        const examButton =
            cardCount >= 4
                ? `
                    <a
                        href="/mock-exam"
                        class="btn btn-primary btn-sm"
                        onclick="
                            sessionStorage.setItem(
                                'preselect_deck',
                                '${deckId.replace(
                                    /'/g,
                                    "\\'"
                                )}'
                            );
                        "
                    >
                        📝 Mock Exam
                    </a>
                `
                : "";


        // -----------------------------------------------------
        // FINAL HTML
        // -----------------------------------------------------

        return `

            <div
                class="dashboard-deck-card"
                style="
                    margin-bottom:1rem;
                "
            >

                <div
                    class="dashboard-deck-main"
                >

                    <div
                        class="dashboard-deck-info"
                    >

                        <h3
                            class="dashboard-deck-name"
                        >
                            ${escapeHtml(
                                deck.name ||
                                "Untitled Deck"
                            )}
                        </h3>


                        <p
                            class="dashboard-deck-desc"
                        >

                            ${subjectHtml}

                            ${descriptionHtml}

                        </p>

                    </div>


                    <div
                        class="dashboard-deck-stats"
                    >

                        <div
                            class="dashboard-stat-item"
                        >

                            <span
                                class="dashboard-stat-value"
                            >
                                ${cardCount}
                            </span>

                            <span
                                class="dashboard-stat-label"
                            >
                                Cards
                            </span>

                        </div>


                        <div
                            class="dashboard-stat-item"
                        >

                            <span
                                class="dashboard-stat-value"
                            >
                                ${cardsStudied}
                            </span>

                            <span
                                class="dashboard-stat-label"
                            >
                                Studied
                            </span>

                        </div>


                        <div
                            class="dashboard-stat-item"
                        >

                            <span
                                class="dashboard-stat-value"
                                style="
                                    color:
                                    var(--color-warning);
                                "
                            >
                                ${reviewCount}
                            </span>

                            <span
                                class="dashboard-stat-label"
                            >
                                Reviews
                            </span>

                        </div>


                        <div
                            class="dashboard-stat-item"
                        >

                            <span
                                class="dashboard-stat-value"
                                style="
                                    color:
                                    ${accuracyColor};
                                "
                            >
                                ${accuracyDisplay}
                            </span>

                            <span
                                class="dashboard-stat-label"
                            >
                                Accuracy
                            </span>

                        </div>

                    </div>

                </div>


                <div
                    class="dashboard-deck-progress"
                >

                    <div
                        class="dashboard-progress-header"
                    >

                        <span
                            class="dashboard-progress-label"
                        >
                            ${Math.round(progress)}% mastered
                        </span>


                        <span
                            class="dashboard-progress-pct"
                        >
                            ${cardsStudied}/${cardCount}
                        </span>

                    </div>


                    <div
                        class="progress-bar-track"
                    >

                        <div
                            class="progress-bar-fill"
                            style="
                                width:
                                ${progress}%;
                            "
                        ></div>

                    </div>

                </div>


                <div
                    class="dashboard-deck-actions"
                >

                    <a
                        href="/deck/${encodeURIComponent(
                            deckId
                        )}"
                        class="btn btn-ghost btn-sm"
                    >
                        View Deck
                    </a>


                    ${studyButton}


                    ${examButton}

                </div>

            </div>
        `;
    }


    // =========================================================
    // WEAK AREAS
    // =========================================================

    function renderWeakAreas(data) {

        const container =
            document.getElementById(
                "weak-areas-section"
            );


        if (!container) {
            return;
        }


        const weakCards =
            Array.isArray(
                data.weak_cards
            )
                ? data.weak_cards
                : [];


        const weakSubjects =
            Array.isArray(
                data.weak_subjects
            )
                ? data.weak_subjects
                : [];


        if (
            weakCards.length === 0 &&
            weakSubjects.length === 0
        ) {

            container.innerHTML = `

                <div
                    style="
                        text-align:center;
                        padding:1rem;
                    "
                >

                    <span
                        style="
                            font-size:1.5rem;
                        "
                    >
                        🎯
                    </span>


                    <p
                        style="
                            color:
                            var(--color-text-muted);
                            font-size:
                            0.875rem;
                            margin-top:
                            0.5rem;
                        "
                    >
                        No weak areas detected.
                        Keep studying!
                    </p>

                </div>
            `;

            return;
        }


        let html =
            "";


        // -----------------------------------------------------
        // WEAK SUBJECTS
        // -----------------------------------------------------

        weakSubjects
            .slice(0, 2)
            .forEach(
                subject => {

                    html += `

                        <div
                            class="weak-area-item"
                        >

                            <div
                                class="weak-area-info"
                            >

                                <div
                                    class="weak-area-name"
                                >
                                    ${escapeHtml(
                                        subject.subject
                                    )}
                                </div>


                                <div
                                    class="weak-area-subject"
                                >
                                    Exam Performance
                                </div>

                            </div>


                            <span
                                class="weak-area-badge"
                            >
                                Avg
                                ${Number(
                                    subject.avg_score || 0
                                ).toFixed(1)}%
                            </span>

                        </div>
                    `;
                }
            );


        // -----------------------------------------------------
        // WEAK CARDS
        // -----------------------------------------------------

        weakCards
            .slice(0, 5)
            .forEach(
                card => {

                    const question =
                        String(
                            card.question || ""
                        );


                    const shortQuestion =
                        question.length > 55
                            ? `${question.substring(
                                0,
                                55
                            )}...`
                            : question;


                    html += `

                        <div
                            class="weak-area-item"
                        >

                            <div
                                class="weak-area-info"
                            >

                                <div
                                    class="weak-area-name"
                                >
                                    ${escapeHtml(
                                        shortQuestion
                                    )}
                                </div>


                                <div
                                    class="weak-area-subject"
                                >
                                    ${escapeHtml(
                                        card.deck_name ||
                                        ""
                                    )}
                                </div>

                            </div>


                            <span
                                class="weak-area-badge"
                            >
                                ${Number(
                                    card.accuracy || 0
                                ).toFixed(1)}%
                            </span>

                        </div>
                    `;
                }
            );


        html += `

            <div
                style="
                    margin-top:1rem;
                    padding-top:0.75rem;
                    border-top:
                        var(--border-subtle);
                "
            >

                <a
                    href="/progress"
                    class="btn btn-ghost btn-sm"
                    style="
                        width:100%;
                    "
                >
                    View Full Analysis →
                </a>

            </div>
        `;


        container.innerHTML =
            html;
    }


    // =========================================================
    // RECENT EXAMS
    // =========================================================

    function renderRecentExams(exams) {

        const container =
            document.getElementById(
                "recent-exams-section"
            );


        if (!container) {
            return;
        }


        if (
            !Array.isArray(exams) ||
            exams.length === 0
        ) {

            container.innerHTML = `

                <div
                    style="
                        text-align:center;
                        padding:1rem;
                    "
                >

                    <span
                        style="
                            font-size:1.5rem;
                        "
                    >
                        📝
                    </span>


                    <p
                        style="
                            color:
                            var(--color-text-muted);
                            font-size:
                            0.875rem;
                            margin-top:
                            0.5rem;
                        "
                    >
                        No exams taken yet.

                        <a
                            href="/mock-exam"
                            style="
                                color:
                                var(--color-accent);
                            "
                        >
                            Take your first!
                        </a>

                    </p>

                </div>
            `;

            return;
        }


        let html =
            "";


        exams.forEach(
            exam => {

                const score =
                    Number(
                        exam.score || 0
                    );


                let scoreColor =
                    "var(--color-success)";


                if (
                    score < 60
                ) {

                    scoreColor =
                        "var(--color-danger)";

                } else if (
                    score < 80
                ) {

                    scoreColor =
                        "var(--color-warning)";
                }


                const seconds =
                    Number(
                        exam.time_taken || 0
                    );


                const minutes =
                    Math.floor(
                        seconds / 60
                    );


                const remainingSeconds =
                    String(
                        seconds % 60
                    ).padStart(
                        2,
                        "0"
                    );


                const timeString =
                    `${minutes}m ` +
                    `${remainingSeconds}s`;


                const date =
                    exam.completed_at
                        ? String(
                            exam.completed_at
                        ).slice(
                            0,
                            10
                        )
                        : "";


                html += `

                    <a
                        href="/exam-result/${encodeURIComponent(
                            exam.id
                        )}"
                        class="recent-exam-item"
                    >

                        <div>

                            <div
                                class="recent-exam-name"
                            >
                                ${escapeHtml(
                                    exam.deck_name ||
                                    "Mock Exam"
                                )}
                            </div>


                            <div
                                class="recent-exam-date"
                            >
                                ${escapeHtml(
                                    date
                                )}

                                ·

                                ${escapeHtml(
                                    timeString
                                )}
                            </div>

                        </div>


                        <span
                            class="recent-exam-score"
                            style="
                                color:
                                ${scoreColor};
                            "
                        >
                            ${score.toFixed(1)}%
                        </span>

                    </a>
                `;
            }
        );


        html += `

            <a
                href="/progress"
                class="btn btn-ghost btn-sm"
                style="
                    width:100%;
                    margin-top:0.5rem;
                "
            >
                View All History →
            </a>
        `;


        container.innerHTML =
            html;
    }


    // =========================================================
    // ADAPTIVE RECOMMENDATIONS
    // =========================================================

    function renderAdaptiveRecommendations(
        data,
        localDecks = []
    ) {

        console.log(
            "[ADAPTIVE] Rendering:",
            data
        );


        /*
         * Look for an existing recommendation
         * container first.
         */

        let container =
            document.getElementById(
                "adaptive-recommendations-section"
            );


        /*
         * Your current dashboard HTML does not
         * contain this ID, so create it.
         */

        if (!container) {

            container =
                document.createElement(
                    "div"
                );


            container.id =
                "adaptive-recommendations-section";


            /*
             * IMPORTANT:
             *
             * Put the adaptive recommendation
             * BEFORE Weak Areas.
             */

            const weakSection =
                document.getElementById(
                    "weak-areas-section"
                );


            if (
                weakSection &&
                weakSection.parentNode
            ) {

                weakSection.parentNode.insertBefore(
                    container,
                    weakSection
                );

            } else {

                const main =
                    document.querySelector(
                        "main"
                    ) ||
                    document.body;


                main.appendChild(
                    container
                );
            }
        }


        const recommendations =
            Array.isArray(
                data.recommendations
            )
                ? data.recommendations
                : [];


        // -----------------------------------------------------
        // NO RECOMMENDATION
        // -----------------------------------------------------

        if (
            !data.success ||
            recommendations.length === 0
        ) {

            container.innerHTML = `

                <div
                    class="card-panel"
                    style="
                        margin:1rem 0;
                        padding:1.5rem;
                        border-radius:16px;
                        border-left:
                            5px solid
                            var(--color-accent);
                    "
                >

                    <div
                        style="
                            display:flex;
                            align-items:center;
                            gap:0.75rem;
                        "
                    >

                        <span
                            style="
                                font-size:1.5rem;
                            "
                        >
                            🧠
                        </span>


                        <div>

                            <h3
                                style="
                                    margin:0;
                                "
                            >
                                Adaptive Study Recommendation
                            </h3>


                            <p
                                style="
                                    margin:
                                    0.35rem 0 0;
                                    color:
                                    var(--color-text-muted);
                                "
                            >
                                Complete a few more
                                study sessions to receive
                                personalized recommendations.
                            </p>

                        </div>

                    </div>

                </div>
            `;

            return;
        }


        /*
         * BigQuery recommendations are already
         * sorted by weakest accuracy.
         */

        const best =
            data.best_recommendation ||
            recommendations[0];


        const accuracy =
            Number(
                best.accuracy_percent || 0
            );


        // -----------------------------------------------------
        // ACCURACY COLOR
        // -----------------------------------------------------

        let accuracyColor =
            "var(--color-success)";


        if (
            accuracy < 60
        ) {

            accuracyColor =
                "var(--color-danger)";

        } else if (
            accuracy < 80
        ) {

            accuracyColor =
                "var(--color-warning)";
        }


        // =====================================================
        // MOST IMPORTANT PART
        // RESOLVE BIGQUERY DECK TO FIRESTORE DECK
        // =====================================================

        const analyticsDeckId =
            best.analytics_deck_id ??
            best.deck_id ??
            "";


        const analyticsId =
            String(
                analyticsDeckId
            );


        console.log(
            "[ADAPTIVE] BigQuery deck ID:",
            analyticsId
        );


        let resolvedDeck =
            null;


        // -----------------------------------------------------
        // METHOD 1
        // EXACT ID MATCH
        // -----------------------------------------------------

        resolvedDeck =
            localDecks.find(
                deck =>
                    String(
                        deck.id
                    ) === analyticsId
            ) ||
            null;


        // -----------------------------------------------------
        // METHOD 2
        // MATCH BY DECK NAME
        // -----------------------------------------------------

        if (
            !resolvedDeck &&
            best.deck_name
        ) {

            const recommendationName =
                String(
                    best.deck_name
                )
                    .trim()
                    .toLowerCase();


            resolvedDeck =
                localDecks.find(
                    deck =>
                        String(
                            deck.name || ""
                        )
                            .trim()
                            .toLowerCase() ===
                        recommendationName
                ) ||
                null;
        }


        // -----------------------------------------------------
        // METHOD 3
        // MATCH BY NAME FROM ANALYTICS
        // -----------------------------------------------------

        if (
            !resolvedDeck &&
            best.deck_name
        ) {

            const recommendationName =
                String(
                    best.deck_name
                )
                    .trim()
                    .toLowerCase();


            resolvedDeck =
                localDecks.find(
                    deck => {

                        const localName =
                            String(
                                deck.name || ""
                            )
                                .trim()
                                .toLowerCase();


                        return (
                            localName.includes(
                                recommendationName
                            ) ||
                            recommendationName.includes(
                                localName
                            )
                        );
                    }
                ) ||
                null;
        }


        // -----------------------------------------------------
        // METHOD 4
        // MATCH BY ATTEMPTS + ACCURACY
        // -----------------------------------------------------

        if (
            !resolvedDeck &&
            localDecks.length > 0
        ) {

            const targetAttempts =
                Number(
                    best.total_attempts || 0
                );


            const targetAccuracy =
                Number(
                    best.accuracy_percent || 0
                );


            const candidates =
                localDecks.filter(
                    deck => {

                        const attempts =
                            Number(
                                deck.total_attempts ||
                                0
                            );


                        const deckAccuracy =
                            Number(
                                deck.accuracy ||
                                0
                            );


                        const attemptsMatch =
                            targetAttempts > 0 &&
                            attempts ===
                            targetAttempts;


                        const accuracyMatch =
                            Math.abs(
                                deckAccuracy -
                                targetAccuracy
                            ) < 1;


                        return (
                            attemptsMatch &&
                            accuracyMatch
                        );
                    }
                );


            if (
                candidates.length === 1
            ) {

                resolvedDeck =
                    candidates[0];
            }
        }


        // -----------------------------------------------------
        // METHOD 5
        // ONE LOCAL DECK
        // -----------------------------------------------------

        if (
            !resolvedDeck &&
            localDecks.length === 1
        ) {

            resolvedDeck =
                localDecks[0];
        }


        console.log(
            "[ADAPTIVE] Resolved local deck:",
            resolvedDeck
        );


        // -----------------------------------------------------
        // FINAL DECK NAME
        // -----------------------------------------------------

        const deckName =
            resolvedDeck?.name ||
            best.deck_name ||
            "Recommended Deck";


        // -----------------------------------------------------
        // RECOMMENDATION TEXT
        // -----------------------------------------------------

        const recommendation =
            best.recommendation ||
            "Review this deck again";


        // =====================================================
        // STUDY URL
        // =====================================================

        let studyUrl =
            "";


        /*
         * CRITICAL:
         *
         * If we found the real Firestore deck,
         * ALWAYS use its ID.
         *
         * Do NOT use the BigQuery analytics ID.
         */

        if (
            resolvedDeck &&
            resolvedDeck.id
        ) {

            studyUrl =
                `/study/${encodeURIComponent(
                    resolvedDeck.id
                )}`;

        } else if (
            best.study_url
        ) {

            studyUrl =
                String(
                    best.study_url
                );
        }


        console.log(
            "[ADAPTIVE] Final study URL:",
            studyUrl
        );


        // -----------------------------------------------------
        // STUDY BUTTON
        // -----------------------------------------------------

        let studyButton =
            "";


        if (
            studyUrl
        ) {

            studyButton = `

                <a
                    href="${escapeHtml(
                        studyUrl
                    )}"
                    class="btn btn-success btn-sm"
                    style="
                        display:inline-flex;
                        align-items:center;
                        justify-content:center;
                        gap:0.4rem;
                        text-decoration:none;
                    "
                >
                    ▶ Study This Deck
                </a>
            `;
        }


        // =====================================================
        // RENDER CARD
        // =====================================================

        container.innerHTML = `

            <div
                class="card-panel"
                style="
                    margin:1rem 0;
                    padding:1.5rem;
                    border-radius:16px;
                    border-left:
                        5px solid
                        var(--color-accent);
                "
            >

                <!-- HEADER -->

                <div
                    style="
                        display:flex;
                        justify-content:space-between;
                        align-items:flex-start;
                        gap:1rem;
                        flex-wrap:wrap;
                    "
                >

                    <div>

                        <div
                            style="
                                font-size:0.8rem;
                                font-weight:700;
                                text-transform:uppercase;
                                letter-spacing:0.08em;
                                color:
                                var(--color-accent);
                            "
                        >
                            🧠 Adaptive Recommendation
                        </div>


                        <h3
                            style="
                                margin:
                                0.4rem 0;
                            "
                        >
                            ${escapeHtml(
                                deckName
                            )}
                        </h3>


                        <p
                            style="
                                margin:0;
                                color:
                                var(--color-text-secondary);
                            "
                        >
                            ${escapeHtml(
                                recommendation
                            )}
                        </p>

                    </div>


                    <!-- ACCURACY -->

                    <div
                        style="
                            text-align:center;
                            min-width:90px;
                        "
                    >

                        <div
                            style="
                                font-size:1.5rem;
                                font-weight:800;
                                color:
                                ${accuracyColor};
                            "
                        >
                            ${accuracy.toFixed(1)}%
                        </div>


                        <div
                            style="
                                font-size:0.75rem;
                                color:
                                var(--color-text-muted);
                            "
                        >
                            Accuracy
                        </div>

                    </div>

                </div>


                <!-- STATISTICS -->

                <div
                    style="
                        display:flex;
                        gap:1rem;
                        align-items:center;
                        margin-top:1.25rem;
                        padding-top:1rem;
                        border-top:
                            var(--border-subtle);
                        flex-wrap:wrap;
                    "
                >

                    <span
                        style="
                            color:
                            var(--color-text-muted);
                            font-size:
                            0.85rem;
                        "
                    >
                        ${Number(
                            best.correct_answers || 0
                        )}
                        correct /
                        ${Number(
                            best.total_attempts || 0
                        )}
                        attempts
                    </span>


                    <span
                        style="
                            color:
                            var(--color-text-muted);
                            font-size:
                            0.85rem;
                        "
                    >
                        Avg response:
                        ${Number(
                            best.average_response_time ||
                            0
                        ).toFixed(2)}s
                    </span>


                    ${studyButton}

                </div>

            </div>
        `;
    }


    // =========================================================
    // START
    // =========================================================

    document.addEventListener(
        "DOMContentLoaded",
        load
    );


    return {
        load
    };

})();