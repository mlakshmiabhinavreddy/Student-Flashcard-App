/**
 * STUDYFLIP — Study Mode
 *
 * Features:
 *  - 3D perspective flip card
 *  - Question / Answer flip
 *  - Know It / Review Again
 *  - Progress tracking
 *  - Adaptive review
 *  - Card shuffling
 *  - Completion screen
 *  - Automatic response-time tracking
 *  - UNIQUE STUDY SESSION ID
 *
 * IMPORTANT:
 * Every card answered during ONE study session receives
 * the same session_id.
 *
 * Example:
 *
 * Session A
 * Card 1 -> session_id = abc123
 * Card 2 -> session_id = abc123
 * Card 3 -> session_id = abc123
 * Card 4 -> session_id = abc123
 * Card 5 -> session_id = abc123
 *
 * This allows the backend / BigQuery to count
 * ONE complete study session instead of 5 card attempts.
 */

const Study = (() => {
    "use strict";

    // =========================================================
    // GLOBAL STATE
    // =========================================================

    let deck = null;
    let cards = [];

    let currentIndex = 0;

    let isFlipped = false;

    // Time when the current card was displayed
    let cardStartTime = null;

    // Prevent double-click / double submission
    let responseSubmitted = false;

    // Session statistics
    let sessionTotal = 0;
    let sessionKnowIt = 0;
    let sessionReviewAgain = 0;

    // =========================================================
    // IMPORTANT:
    // ONE ID FOR ONE COMPLETE STUDY SESSION
    // =========================================================

    let studySessionId = null;


    function createStudySessionId() {

        // Modern browsers
        if (
            typeof crypto !== "undefined" &&
            typeof crypto.randomUUID === "function"
        ) {
            return crypto.randomUUID();
        }

        // Fallback
        return (
            "study-" +
            Date.now() +
            "-" +
            Math.random()
                .toString(36)
                .substring(2, 11)
        );
    }


    // =========================================================
    // HTML ESCAPE
    // =========================================================

    function escapeHtml(text) {

        const div =
            document.createElement("div");

        div.textContent =
            String(text || "");

        return div.innerHTML;
    }


    // =========================================================
    // TOAST
    // =========================================================

    function showToast(
        message,
        type = "info"
    ) {

        const container =
            document.getElementById(
                "toast-container"
            );

        if (!container) {
            console.log(message);
            return;
        }

        const toast =
            document.createElement("div");

        toast.className =
            `toast toast--${type}`;

        toast.textContent =
            message;

        container.appendChild(toast);

        setTimeout(
            () => toast.remove(),
            3500
        );
    }


    // =========================================================
    // LOAD STUDY SESSION
    // =========================================================

    async function load() {

        try {

            const endpoint =
                (
                    typeof DECK_ID !== "undefined" &&
                    DECK_ID > 0
                )
                    ? `/api/study/${DECK_ID}/cards`
                    : `/api/smart-review/cards`;


            const res =
                await fetch(endpoint);


            if (res.status === 404) {

                renderNotFoundState();

                return;
            }


            if (!res.ok) {

                throw new Error(
                    "Failed to load cards"
                );
            }


            const data =
                await res.json();


            deck =
                data.deck;

            cards =
                data.cards || [];


            if (cards.length === 0) {

                renderEmptyState();

                return;
            }


            // =================================================
            // START A BRAND NEW COMPLETE STUDY SESSION
            // =================================================

            studySessionId =
                createStudySessionId();


            console.log(
                "========================================"
            );

            console.log(
                "[STUDY] NEW STUDY SESSION"
            );

            console.log(
                "[STUDY] Session ID:",
                studySessionId
            );

            console.log(
                "[STUDY] Total cards:",
                cards.length
            );

            console.log(
                "========================================"
            );


            sessionTotal =
                cards.length;

            currentIndex = 0;

            sessionKnowIt = 0;

            sessionReviewAgain = 0;

            isFlipped = false;

            cardStartTime = null;

            responseSubmitted = false;


            const shuffleButton =
                document.getElementById(
                    "btn-shuffle"
                );


            if (shuffleButton) {

                shuffleButton.style.display =
                    "inline-flex";
            }


            renderCardView();


        } catch (err) {

            console.error(
                "Study load error:",
                err
            );

            renderErrorState();
        }
    }


    // =========================================================
    // EMPTY STATE
    // =========================================================

    function renderEmptyState() {

        const shuffleButton =
            document.getElementById(
                "btn-shuffle"
            );


        if (shuffleButton) {

            shuffleButton.style.display =
                "none";
        }


        const container =
            document.getElementById(
                "study-container"
            );


        if (!container) {
            return;
        }


        container.innerHTML = `

            <div class="empty-state card-panel">

                <span class="empty-state-icon">
                    🃏
                </span>

                <h3>
                    No cards in this deck
                </h3>

                <p>
                    Add some flashcards to
                    <strong>
                        ${escapeHtml(
                            deck
                                ? deck.name
                                : "this deck"
                        )}
                    </strong>
                    before starting a study session.
                </p>

                <div
                    style="
                        display:flex;
                        gap:1rem;
                        justify-content:center;
                        margin-top:1.5rem;
                    "
                >

                    <a
                        href="/deck/${DECK_ID}"
                        class="btn btn-primary"
                    >
                        + Add Cards
                    </a>

                    <a
                        href="/decks"
                        class="btn btn-ghost"
                    >
                        My Decks
                    </a>

                </div>

            </div>
        `;
    }


    // =========================================================
    // DECK NOT FOUND
    // =========================================================

    function renderNotFoundState() {

        const shuffleButton =
            document.getElementById(
                "btn-shuffle"
            );


        if (shuffleButton) {

            shuffleButton.style.display =
                "none";
        }


        const container =
            document.getElementById(
                "study-container"
            );


        if (!container) {
            return;
        }


        container.innerHTML = `

            <div class="empty-state card-panel">

                <span class="empty-state-icon">
                    📚
                </span>

                <h3>
                    Deck Not Found
                </h3>

                <p>
                    This deck may have been deleted
                    or does not exist.
                </p>

                <div
                    style="
                        display:flex;
                        gap:1rem;
                        justify-content:center;
                        margin-top:1.5rem;
                    "
                >

                    <a
                        href="/decks"
                        class="btn btn-primary"
                    >
                        Browse My Decks
                    </a>

                    <a
                        href="/dashboard"
                        class="btn btn-ghost"
                    >
                        Dashboard
                    </a>

                </div>

            </div>
        `;
    }


    // =========================================================
    // ERROR STATE
    // =========================================================

    function renderErrorState() {

        const shuffleButton =
            document.getElementById(
                "btn-shuffle"
            );


        if (shuffleButton) {

            shuffleButton.style.display =
                "none";
        }


        const container =
            document.getElementById(
                "study-container"
            );


        if (!container) {
            return;
        }


        container.innerHTML = `

            <div class="empty-state card-panel">

                <span class="empty-state-icon">
                    ⚠️
                </span>

                <h3>
                    Unable to load session
                </h3>

                <p>
                    Could not connect to the
                    study session service.
                </p>

                <a
                    href="/decks"
                    class="btn btn-primary"
                >
                    Back to Decks
                </a>

            </div>
        `;
    }


    // =========================================================
    // RENDER CARD
    // =========================================================

    function renderCardView() {

        const container =
            document.getElementById(
                "study-container"
            );


        if (!container) {
            return;
        }


        const currentCard =
            cards[currentIndex];


        if (!currentCard) {
            renderCompletionScreen();
            return;
        }


        const progressPct =
            Math.round(
                (
                    currentIndex /
                    sessionTotal
                ) * 100
            );


        const remaining =
            sessionTotal -
            currentIndex;


        container.innerHTML = `

            <div class="study-layout">

                <!-- ============================= -->
                <!-- PROGRESS HEADER -->
                <!-- ============================= -->

                <div
                    class="card-panel"
                    style="
                        width:100%;
                        max-width:680px;
                        margin-bottom:1.5rem;
                        padding:1.25rem 1.5rem;
                    "
                >

                    <div
                        style="
                            display:flex;
                            justify-content:space-between;
                            align-items:center;
                            flex-wrap:wrap;
                            gap:0.75rem;
                            margin-bottom:0.75rem;
                        "
                    >

                        <div>

                            <h2
                                style="
                                    font-size:1.1rem;
                                    font-weight:700;
                                    margin:0;
                                "
                            >
                                ${escapeHtml(
                                    deck
                                        ? deck.name
                                        : "Study Deck"
                                )}
                            </h2>

                            <span
                                style="
                                    font-size:0.8rem;
                                    color:
                                        var(
                                            --color-text-muted
                                        );
                                "
                            >
                                Study Mode — Flashcard
                            </span>

                        </div>


                        <div
                            style="
                                display:flex;
                                gap:1.25rem;
                                align-items:center;
                                font-size:0.82rem;
                            "
                        >

                            <span
                                style="
                                    color:
                                        var(
                                            --color-success
                                        );
                                "
                            >
                                Known:
                                <strong>
                                    ${sessionKnowIt}
                                </strong>
                            </span>


                            <span
                                style="
                                    color:
                                        var(
                                            --color-warning
                                        );
                                "
                            >
                                Review:
                                <strong>
                                    ${sessionReviewAgain}
                                </strong>
                            </span>


                            <span
                                style="
                                    color:
                                        var(
                                            --color-text-muted
                                        );
                                "
                            >
                                Remaining:
                                <strong>
                                    ${remaining}
                                </strong>
                            </span>

                        </div>

                    </div>


                    <div
                        style="
                            display:flex;
                            align-items:center;
                            gap:0.75rem;
                        "
                    >

                        <div
                            class="progress-bar-track"
                            style="
                                flex:1;
                                height:8px;
                            "
                        >

                            <div
                                class="progress-bar-fill"
                                style="
                                    width:${progressPct}%;
                                "
                            ></div>

                        </div>


                        <span
                            style="
                                font-size:0.75rem;
                                color:
                                    var(
                                        --color-text-muted
                                    );
                                white-space:nowrap;
                            "
                        >
                            Card
                            ${currentIndex + 1}
                            of
                            ${sessionTotal}
                        </span>

                    </div>

                </div>


                <!-- ============================= -->
                <!-- FLASHCARD -->
                <!-- ============================= -->

                <div class="study-card-wrapper">

                    <div
                        class="flip-card"
                        id="study-flip-card"
                        onclick="Study.toggleFlip()"
                        tabindex="0"
                        role="button"
                        aria-label="
                            Flashcard.
                            Click or press Space / Enter
                            to flip.
                        "
                    >

                        <div class="flip-card-inner">


                            <!-- FRONT -->

                            <div
                                class="flip-card-front"
                            >

                                <span
                                    class="
                                        fc-label
                                        fc-label--question
                                    "
                                >

                                    ❓

                                    Question

                                </span>


                                <div class="fc-text">

                                    ${escapeHtml(
                                        currentCard.question
                                    )}

                                </div>


                                <span class="fc-prompt">

                                    🔄

                                    Click the card
                                    to reveal answer

                                </span>

                            </div>


                            <!-- BACK -->

                            <div
                                class="flip-card-back"
                            >

                                <span
                                    class="
                                        fc-label
                                        fc-label--answer
                                    "
                                >

                                    ✓

                                    Answer

                                </span>


                                <div class="fc-text">

                                    ${escapeHtml(
                                        currentCard.answer
                                    )}

                                </div>


                                <span class="fc-prompt">

                                    🔄

                                    Click the card
                                    to see question

                                </span>

                            </div>

                        </div>

                    </div>

                </div>


                <!-- ============================= -->
                <!-- RESPONSE BUTTONS -->
                <!-- ============================= -->

                <div
                    class="study-action-row"
                    id="study-actions"
                    style="
                        opacity:0;
                        pointer-events:none;
                        transform:translateY(14px);
                        transition:
                            opacity 0.35s ease,
                            transform 0.35s ease;
                    "
                >

                    <button
                        class="btn-review-again"
                        id="btn-review-again"
                        onclick="
                            Study.respond(false)
                        "
                    >
                        ↻ Review Again
                    </button>


                    <button
                        class="btn-know-it"
                        id="btn-know-it"
                        onclick="
                            Study.respond(true)
                        "
                    >
                        ✓ Know It
                    </button>

                </div>


                <!-- ============================= -->
                <!-- TIP -->
                <!-- ============================= -->

                <p
                    class="study-tip-bar"
                    id="study-tip"
                    style="
                        opacity:0;
                        transition:
                            opacity 0.35s ease;
                    "
                >

                    💡 Use
                    <strong>
                        Know It
                    </strong>
                    if you're confident.

                    Use
                    <span class="tip-orange">
                        Review Again
                    </span>
                    to keep it in Smart Review.

                </p>

            </div>
        `;


        // =====================================================
        // START TIMER
        // =====================================================

        isFlipped = false;

        responseSubmitted = false;

        cardStartTime =
            performance.now();


        // =====================================================
        // KEYBOARD FOCUS
        // =====================================================

        const cardEl =
            document.getElementById(
                "study-flip-card"
            );


        if (cardEl) {

            cardEl.addEventListener(
                "keydown",
                (e) => {

                    if (
                        e.code === "Space" ||
                        e.code === "Enter"
                    ) {

                        e.preventDefault();

                        toggleFlip();
                    }
                }
            );


            setTimeout(
                () => cardEl.focus(),
                50
            );
        }
    }


    // =========================================================
    // FLIP CARD
    // =========================================================

    function toggleFlip() {

        const cardEl =
            document.getElementById(
                "study-flip-card"
            );


        const actionsEl =
            document.getElementById(
                "study-actions"
            );


        const tipEl =
            document.getElementById(
                "study-tip"
            );


        if (!cardEl) {
            return;
        }


        isFlipped =
            !isFlipped;


        cardEl.classList.toggle(
            "flipped",
            isFlipped
        );


        cardEl.setAttribute(
            "aria-label",

            isFlipped
                ? "Flashcard showing answer. Click or press Space/Enter to flip back."
                : "Flashcard showing question. Click or press Space/Enter to reveal answer."
        );


        if (actionsEl) {

            if (isFlipped) {

                actionsEl.style.opacity =
                    "1";

                actionsEl.style.pointerEvents =
                    "all";

                actionsEl.style.transform =
                    "translateY(0)";

            } else {

                actionsEl.style.opacity =
                    "0";

                actionsEl.style.pointerEvents =
                    "none";

                actionsEl.style.transform =
                    "translateY(14px)";
            }
        }


        if (tipEl) {

            tipEl.style.opacity =
                isFlipped
                    ? "1"
                    : "0";
        }
    }


    // =========================================================
    // RECORD RESPONSE
    // =========================================================

    async function respond(knewIt) {

        const currentCard =
            cards[currentIndex];


        // Prevent duplicate response
        if (
            !currentCard ||
            responseSubmitted
        ) {
            return;
        }


        responseSubmitted =
            true;


        // =====================================================
        // CALCULATE RESPONSE TIME
        // =====================================================

        const responseTimeSeconds =
            cardStartTime !== null

                ? Math.max(
                    0,
                    Number(
                        (
                            (
                                performance.now() -
                                cardStartTime
                            ) / 1000
                        ).toFixed(2)
                    )
                )

                : 0;


        // =====================================================
        // UPDATE CURRENT SESSION STATISTICS
        // =====================================================

        if (knewIt) {

            sessionKnowIt++;


            showToast(
                "✅ Great! Marked as known",
                "success"
            );

        } else {

            sessionReviewAgain++;


            showToast(
                "🔄 Added to review queue",
                "info"
            );
        }


        // =====================================================
        // SEND RESPONSE TO FLASK
        // =====================================================

        try {

            const res =
                await fetch(
                    `/api/study/${currentCard.id}/respond`,
                    {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body: JSON.stringify({

                            // Card result
                            knew_it:
                                knewIt,

                            // IMPORTANT:
                            // Same ID for every card
                            // in this complete study.
                            session_id:
                                studySessionId,

                            // Time for this card
                            response_time:
                                responseTimeSeconds
                        })
                    }
                );


            if (!res.ok) {

                throw new Error(
                    `Study response API returned ${res.status}`
                );
            }


            console.log(
                "[STUDY] Response saved"
            );

            console.log(
                "Session ID:",
                studySessionId
            );

            console.log(
                "Card:",
                currentCard.id
            );

            console.log(
                "Result:",
                knewIt
                    ? "correct"
                    : "review again"
            );

            console.log(
                "Response time:",
                responseTimeSeconds,
                "seconds"
            );


        } catch (e) {

            console.error(
                "Failed to record response:",
                e
            );


            showToast(
                "⚠️ Response could not be saved",
                "error"
            );
        }


        // =====================================================
        // MOVE TO NEXT CARD
        // =====================================================

        currentIndex++;


        if (
            currentIndex <
            cards.length
        ) {

            renderCardView();

        } else {

            renderCompletionScreen();
        }
    }


    // =========================================================
    // SHUFFLE CARDS
    // =========================================================

    function shuffleCards() {

        if (
            cards.length === 0
        ) {
            return;
        }


        const remainingCards =
            cards.slice(
                currentIndex
            );


        for (
            let i =
                remainingCards.length - 1;
            i > 0;
            i--
        ) {

            const j =
                Math.floor(
                    Math.random() *
                    (i + 1)
                );


            [
                remainingCards[i],
                remainingCards[j]
            ] = [
                remainingCards[j],
                remainingCards[i]
            ];
        }


        cards =
            cards
                .slice(
                    0,
                    currentIndex
                )
                .concat(
                    remainingCards
                );


        showToast(
            "🔀 Cards shuffled!",
            "info"
        );


        renderCardView();
    }


    // =========================================================
    // COMPLETION SCREEN
    // =========================================================

    function renderCompletionScreen() {

        const shuffleButton =
            document.getElementById(
                "btn-shuffle"
            );


        if (shuffleButton) {

            shuffleButton.style.display =
                "none";
        }


        const totalAnswered =
            sessionKnowIt +
            sessionReviewAgain;


        const accuracy =
            totalAnswered > 0

                ? Math.round(
                    (
                        sessionKnowIt /
                        totalAnswered
                    ) * 100
                )

                : 0;


        const container =
            document.getElementById(
                "study-container"
            );


        if (!container) {
            return;
        }


        container.innerHTML = `

            <div class="completion-card">

                <div class="completion-icon">
                    🎉
                </div>


                <h1 class="completion-title">
                    Session Complete!
                </h1>


                <p class="completion-subtitle">

                    Great job studying

                    <strong>
                        ${escapeHtml(
                            deck
                                ? deck.name
                                : "this deck"
                        )}
                    </strong>!

                </p>


                <div
                    class="
                        stats-grid
                        completion-stats
                    "
                >

                    <!-- CARDS STUDIED -->

                    <div
                        class="
                            stat-card
                            stat-card--accent
                        "
                    >

                        <div
                            class="stat-value"
                        >
                            ${sessionTotal}
                        </div>

                        <div
                            class="stat-label"
                        >
                            Cards Studied
                        </div>

                    </div>


                    <!-- KNOW IT -->

                    <div
                        class="
                            stat-card
                            stat-card--success
                        "
                    >

                        <div
                            class="stat-value"
                            style="
                                color:
                                    var(
                                        --color-success
                                    );
                            "
                        >
                            ${sessionKnowIt}
                        </div>


                        <div
                            class="stat-label"
                        >
                            Know It ✅
                        </div>

                    </div>


                    <!-- REVIEW AGAIN -->

                    <div
                        class="
                            stat-card
                            stat-card--warning
                        "
                    >

                        <div
                            class="stat-value"
                            style="
                                color:
                                    var(
                                        --color-warning
                                    );
                            "
                        >
                            ${sessionReviewAgain}
                        </div>


                        <div
                            class="stat-label"
                        >
                            Review Again
                        </div>

                    </div>


                    <!-- ACCURACY -->

                    <div
                        class="
                            stat-card
                            stat-card--accent
                        "
                    >

                        <div
                            class="stat-value"
                        >
                            ${accuracy}%
                        </div>


                        <div
                            class="stat-label"
                        >
                            Accuracy
                        </div>

                    </div>

                </div>


                <!-- ACTIONS -->

                <div
                    class="completion-actions"
                >

                    <button
                        class="
                            btn
                            btn-success
                            btn-lg
                        "
                        onclick="Study.load()"
                    >
                        🔄 Study Again
                    </button>


                    ${
                        typeof DECK_ID !==
                            "undefined" &&
                        DECK_ID > 0

                            ? `
                                <a
                                    href="/deck/${DECK_ID}"
                                    class="
                                        btn
                                        btn-ghost
                                        btn-lg
                                    "
                                >
                                    View Deck
                                </a>
                            `

                            : ""
                    }


                    <a
                        href="/mock-exam"
                        class="
                            btn
                            btn-primary
                            btn-lg
                        "
                    >
                        📝 Take Mock Exam
                    </a>


                    <a
                        href="/dashboard"
                        class="
                            btn
                            btn-ghost
                            btn-lg
                        "
                    >
                        📊 Dashboard
                    </a>

                </div>

            </div>
        `;
    }


    // =========================================================
    // KEYBOARD NAVIGATION
    // =========================================================

    document.addEventListener(
        "keydown",
        (e) => {

            // No active card
            if (
                currentIndex >=
                    cards.length ||
                !document.getElementById(
                    "study-flip-card"
                )
            ) {
                return;
            }


            // Don't interfere with buttons
            if (
                document.activeElement &&
                document.activeElement.tagName ===
                    "BUTTON"
            ) {
                return;
            }


            // =================================================
            // FLIP
            // =================================================

            if (
                e.code === "Space" ||
                e.code === "Enter" ||
                e.code === "ArrowUp" ||
                e.code === "ArrowDown"
            ) {

                e.preventDefault();

                toggleFlip();

                return;
            }


            // =================================================
            // KNOW IT
            // =================================================

            if (
                e.code === "ArrowRight"
            ) {

                if (isFlipped) {

                    e.preventDefault();

                    respond(true);
                }

                return;
            }


            // =================================================
            // REVIEW AGAIN
            // =================================================

            if (
                e.code === "ArrowLeft"
            ) {

                if (isFlipped) {

                    e.preventDefault();

                    respond(false);
                }
            }
        }
    );


    // =========================================================
    // START WHEN PAGE LOADS
    // =========================================================

    document.addEventListener(
        "DOMContentLoaded",
        load
    );


    // =========================================================
    // PUBLIC API
    // =========================================================

    return {

        load,

        toggleFlip,

        respond,

        shuffleCards
    };

})();