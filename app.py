"""
STUDYFLIP — Digital Flashcard + Mock Exam Preparation Platform
Application Entry Point

Run with:
    python app.py          (development)
    gunicorn app:app       (production)
"""

import functools
import os
from datetime import datetime, timezone
import uuid

from google.cloud import bigquery

from storage_service import (
    upload_file,
    download_file,
    delete_file,
    list_files,
)

from flask import (
    Flask, render_template, request, jsonify,
    session, redirect, url_for, send_file
)

from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from firestore_db import (
    init_db, query_db, execute_db, get_db,
    get_study_cards, get_smart_review_cards,
    record_response, calculate_priority,
    create_mock_exam, submit_mock_exam
)


# ── BigQuery configuration ─────────────────────────────────────
# Your BigQuery project is: digital-flashcard-app
# Environment variables still take priority when deployed elsewhere.
BIGQUERY_PROJECT = (
    os.getenv("GOOGLE_CLOUD_PROJECT")
    or os.getenv("GCP_PROJECT")
    or "digital-flashcard-app"
)
BIGQUERY_DATASET = os.getenv("BIGQUERY_DATASET", "studyflip_analytics")
BIGQUERY_VIEW = os.getenv("BIGQUERY_VIEW", "adaptive_recommendations")
BIGQUERY_LOCATION = os.getenv("BIGQUERY_LOCATION", "asia-south1")


def create_app():
    """Application factory."""
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )
    app.config.from_object(Config)

    # BigQuery client is created lazily so the Flask app can still start
    # when BigQuery credentials are not available.
    bigquery_client = None

    def get_bigquery_client():
        """Create the BigQuery client only when it is first needed."""
        nonlocal bigquery_client
        if bigquery_client is None:
            print(
                f"[BIGQUERY] Connecting to "
                f"{BIGQUERY_PROJECT}.{BIGQUERY_DATASET}.{BIGQUERY_VIEW}"
            )
            bigquery_client = bigquery.Client(project=BIGQUERY_PROJECT)
            print(f"[BIGQUERY] Client ready for project: {BIGQUERY_PROJECT}")
        return bigquery_client

    # Initialize the database on startup
    with app.app_context():
        init_db()

    # ── Security headers ─────────────────────────────────────
    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response

    # ── Error handlers ───────────────────────────────────────
    @app.errorhandler(404)
    def handle_404(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Resource not found"}), 404
        return render_template("index.html"), 404

    @app.errorhandler(500)
    def handle_500(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Internal server error"}), 500
        return render_template("index.html"), 500

    # ── Auth decorator ───────────────────────────────────────
    def login_required(f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            if "user_id" not in session:
                if request.path.startswith("/api/"):
                    return jsonify({"error": "Authentication required"}), 401
                return redirect(url_for("login_page"))
            return f(*args, **kwargs)
        return decorated

    def current_user():
        """Return the logged-in user dict, or None."""
        uid = session.get("user_id")
        if uid is None:
            return None
        return query_db("SELECT id, name, email, created_at FROM users WHERE id = ?", (uid,), one=True)

    # ═════════════════════════════════════════════════════════
    #  AUTH PAGE ROUTES
    # ═════════════════════════════════════════════════════════

    @app.route("/login")
    def login_page():
        if "user_id" in session:
            return redirect(url_for("dashboard"))
        return render_template("login.html")

    @app.route("/register")
    def register_page():
        if "user_id" in session:
            return redirect(url_for("dashboard"))
        return render_template("register.html")

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login_page"))

    # ═════════════════════════════════════════════════════════
    #  PAGE ROUTES (protected)
    # ═════════════════════════════════════════════════════════

    @app.route("/")
    def index():
        if "user_id" in session:
            return redirect(url_for("dashboard"))
        return redirect(url_for("login_page"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        user = current_user()
        return render_template("dashboard.html", user=user)

    @app.route("/decks")
    @login_required
    def decks_page():
        user = current_user()
        return render_template("decks.html", user=user)

    @app.route("/deck/<int:deck_id>")
    @login_required
    def deck_page(deck_id):
        user = current_user()
        # Ownership check
        deck = query_db(
            "SELECT * FROM decks WHERE id = ? AND user_id = ?",
            (deck_id, session["user_id"]), one=True
        )
        if not deck:
            return redirect(url_for("decks_page"))
        return render_template("deck.html", deck_id=deck_id, user=user)

    @app.route("/study/<int:deck_id>")
    @login_required
    def study_page(deck_id):
        user = current_user()
        deck = query_db(
            "SELECT * FROM decks WHERE id = ? AND user_id = ?",
            (deck_id, session["user_id"]), one=True
        )
        if not deck:
            return redirect(url_for("decks_page"))
        return render_template("study.html", deck_id=deck_id, is_smart_review=False, user=user)

    @app.route("/smart-review")
    @login_required
    def smart_review_page():
        user = current_user()
        return render_template("study.html", deck_id=0, is_smart_review=True, user=user)

    @app.route("/mock-exam")
    @login_required
    def mock_exam_page():
        user = current_user()
        return render_template("mock_exam.html", user=user)

    @app.route("/exam-result/<int:exam_id>")
    @login_required
    def exam_result_page(exam_id):
        user = current_user()
        exam = query_db(
            "SELECT * FROM mock_exams WHERE id = ? AND user_id = ?",
            (exam_id, session["user_id"]), one=True
        )
        if not exam:
            return redirect(url_for("mock_exam_page"))
        return render_template("exam_result.html", exam_id=exam_id, user=user)

    @app.route("/progress")
    @login_required
    def progress_page():
        user = current_user()
        return render_template("progress.html", user=user)

    # ═════════════════════════════════════════════════════════
    #  AUTH API
    # ═════════════════════════════════════════════════════════

    @app.route("/api/auth/register", methods=["POST"])
    def api_register():
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        name = (data.get("name") or "").strip()
        email = (data.get("email") or "").strip().lower()
        password = (data.get("password") or "").strip()
        confirm = (data.get("confirm_password") or "").strip()

        if not name:
            return jsonify({"error": "Name is required"}), 400
        if not email or "@" not in email:
            return jsonify({"error": "Valid email is required"}), 400
        if len(password) < 6:
            return jsonify({"error": "Password must be at least 6 characters"}), 400
        if password != confirm:
            return jsonify({"error": "Passwords do not match"}), 400

        # Check duplicate email
        existing = query_db("SELECT id FROM users WHERE email = ?", (email,), one=True)
        if existing:
            return jsonify({"error": "Email already registered"}), 409

        password_hash = generate_password_hash(password)
        user_id = execute_db(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, password_hash)
        )

        session.clear()
        session["user_id"] = user_id
        session["user_name"] = name
        session.permanent = True

        return jsonify({"message": "Account created", "user": {"id": user_id, "name": name, "email": email}}), 201

    @app.route("/api/auth/login", methods=["POST"])
    def api_login():
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        email = (data.get("email") or "").strip().lower()
        password = (data.get("password") or "").strip()

        if not email or not password:
            return jsonify({"error": "Email and password are required"}), 400

        user = query_db("SELECT * FROM users WHERE email = ?", (email,), one=True)
        if not user or not check_password_hash(user["password_hash"], password):
            return jsonify({"error": "Invalid email or password"}), 401

        session.clear()
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session.permanent = True

        return jsonify({
            "message": "Login successful",
            "user": {"id": user["id"], "name": user["name"], "email": user["email"]}
        }), 200

    @app.route("/api/auth/logout", methods=["POST"])
    def api_logout():
        session.clear()
        return jsonify({"message": "Logged out"}), 200

    # ═════════════════════════════════════════════════════════
    #  DECK API (user-scoped)
    # ═════════════════════════════════════════════════════════

    @app.route("/api/decks", methods=["GET"])
    @login_required
    def api_get_decks():
        """List user's decks, each with its card count."""
        user_id = session["user_id"]
        decks = query_db("""
            SELECT d.*,
                   COUNT(c.id) AS card_count
            FROM decks d
            LEFT JOIN cards c ON c.deck_id = d.id
            WHERE d.user_id = ?
            GROUP BY d.id
            ORDER BY d.created_at DESC
        """, (user_id,))
        return jsonify(decks), 200

    @app.route("/api/decks", methods=["POST"])
    @login_required
    def api_create_deck():
        """Create a new deck. Requires: name. Optional: subject, description."""
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Deck name is required"}), 400

        subject = (data.get("subject") or "").strip()
        description = (data.get("description") or "").strip()
        user_id = session["user_id"]

        deck_id = execute_db(
            "INSERT INTO decks (user_id, name, subject, description) VALUES (?, ?, ?, ?)",
            (user_id, name, subject, description)
        )

        deck = query_db("SELECT * FROM decks WHERE id = ?", (deck_id,), one=True)
        return jsonify(deck), 201

    @app.route("/api/decks/<int:deck_id>", methods=["GET"])
    @login_required
    def api_get_deck(deck_id):
        """Get a single deck by ID, with card count (ownership check)."""
        user_id = session["user_id"]
        deck = query_db("""
            SELECT d.*,
                   COUNT(c.id) AS card_count
            FROM decks d
            LEFT JOIN cards c ON c.deck_id = d.id
            WHERE d.id = ? AND d.user_id = ?
            GROUP BY d.id
        """, (deck_id, user_id), one=True)

        if not deck:
            return jsonify({"error": "Deck not found"}), 404

        return jsonify(deck), 200

    @app.route("/api/decks/<int:deck_id>", methods=["PUT"])
    @login_required
    def api_update_deck(deck_id):
        """Update a deck. Ownership check enforced."""
        user_id = session["user_id"]
        deck = query_db("SELECT * FROM decks WHERE id = ? AND user_id = ?", (deck_id, user_id), one=True)
        if not deck:
            return jsonify({"error": "Deck not found"}), 404

        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Deck name is required"}), 400

        subject = (data.get("subject") or "").strip()
        description = (data.get("description") or "").strip()

        execute_db(
            "UPDATE decks SET name = ?, subject = ?, description = ? WHERE id = ? AND user_id = ?",
            (name, subject, description, deck_id, user_id)
        )

        updated = query_db("SELECT * FROM decks WHERE id = ?", (deck_id,), one=True)
        return jsonify(updated), 200

    @app.route("/api/decks/<int:deck_id>", methods=["DELETE"])
    @login_required
    def api_delete_deck(deck_id):
        """Delete a deck and all its cards. Ownership check enforced."""
        user_id = session["user_id"]
        deck = query_db("SELECT * FROM decks WHERE id = ? AND user_id = ?", (deck_id, user_id), one=True)
        if not deck:
            return jsonify({"error": "Deck not found"}), 404

        execute_db("DELETE FROM decks WHERE id = ? AND user_id = ?", (deck_id, user_id))
        return jsonify({"message": "Deck deleted"}), 200

    # ═════════════════════════════════════════════════════════
    #  CARD API (user-scoped via deck ownership)
    # ═════════════════════════════════════════════════════════

    @app.route("/api/decks/<int:deck_id>/cards", methods=["GET"])
    @login_required
    def api_get_cards(deck_id):
        """List all cards in a user's deck."""
        user_id = session["user_id"]
        deck = query_db("SELECT * FROM decks WHERE id = ? AND user_id = ?", (deck_id, user_id), one=True)
        if not deck:
            return jsonify({"error": "Deck not found"}), 404

        cards = query_db(
            "SELECT * FROM cards WHERE deck_id = ? ORDER BY created_at DESC",
            (deck_id,)
        )
        return jsonify(cards), 200

    @app.route("/api/decks/<int:deck_id>/cards", methods=["POST"])
    @login_required
    def api_create_card(deck_id):
        """Add a card to a deck. Requires: question, answer. Optional: MCQ options."""
        user_id = session["user_id"]
        deck = query_db("SELECT * FROM decks WHERE id = ? AND user_id = ?", (deck_id, user_id), one=True)
        if not deck:
            return jsonify({"error": "Deck not found"}), 404

        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        question = (data.get("question") or "").strip()
        if not question:
            return jsonify({"error": "Question is required"}), 400

        answer = (data.get("answer") or "").strip()
        if not answer:
            return jsonify({"error": "Answer is required"}), 400

        option_a = (data.get("option_a") or "").strip() or None
        option_b = (data.get("option_b") or "").strip() or None
        option_c = (data.get("option_c") or "").strip() or None
        option_d = (data.get("option_d") or "").strip() or None
        correct_option = (data.get("correct_option") or "").strip() or None

        card_id = execute_db(
            """INSERT INTO cards
               (deck_id, question, answer, option_a, option_b, option_c, option_d, correct_option)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (deck_id, question, answer, option_a, option_b, option_c, option_d, correct_option)
        )

        card = query_db("SELECT * FROM cards WHERE id = ?", (card_id,), one=True)
        return jsonify(card), 201

    @app.route("/api/cards/<int:card_id>", methods=["GET"])
    @login_required
    def api_get_card(card_id):
        """Get a single card by ID (ownership check via deck)."""
        user_id = session["user_id"]
        card = query_db("""
            SELECT c.* FROM cards c
            JOIN decks d ON d.id = c.deck_id
            WHERE c.id = ? AND d.user_id = ?
        """, (card_id, user_id), one=True)
        if not card:
            return jsonify({"error": "Card not found"}), 404
        return jsonify(card), 200

    @app.route("/api/cards/<int:card_id>", methods=["PUT"])
    @login_required
    def api_update_card(card_id):
        """Update a card. Ownership check via deck."""
        user_id = session["user_id"]
        card = query_db("""
            SELECT c.* FROM cards c
            JOIN decks d ON d.id = c.deck_id
            WHERE c.id = ? AND d.user_id = ?
        """, (card_id, user_id), one=True)
        if not card:
            return jsonify({"error": "Card not found"}), 404

        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        question = (data.get("question") or "").strip()
        if not question:
            return jsonify({"error": "Question is required"}), 400

        answer = (data.get("answer") or "").strip()
        if not answer:
            return jsonify({"error": "Answer is required"}), 400

        option_a = (data.get("option_a") or "").strip() or None
        option_b = (data.get("option_b") or "").strip() or None
        option_c = (data.get("option_c") or "").strip() or None
        option_d = (data.get("option_d") or "").strip() or None
        correct_option = (data.get("correct_option") or "").strip() or None

        execute_db(
            """UPDATE cards
               SET question = ?, answer = ?, option_a = ?, option_b = ?,
                   option_c = ?, option_d = ?, correct_option = ?
               WHERE id = ?""",
            (question, answer, option_a, option_b, option_c, option_d, correct_option, card_id)
        )

        updated = query_db("SELECT * FROM cards WHERE id = ?", (card_id,), one=True)
        return jsonify(updated), 200

    @app.route("/api/cards/<int:card_id>", methods=["DELETE"])
    @login_required
    def api_delete_card(card_id):
        """Delete a card. Ownership check via deck."""
        user_id = session["user_id"]
        card = query_db("""
            SELECT c.* FROM cards c
            JOIN decks d ON d.id = c.deck_id
            WHERE c.id = ? AND d.user_id = ?
        """, (card_id, user_id), one=True)
        if not card:
            return jsonify({"error": "Card not found"}), 404

        execute_db("DELETE FROM cards WHERE id = ?", (card_id,))
        return jsonify({"message": "Card deleted"}), 200

    # ═════════════════════════════════════════════════════════
    #  STUDY API (user-scoped)
    # ═════════════════════════════════════════════════════════

    @app.route("/api/study/<int:deck_id>/cards", methods=["GET"])
    @login_required
    def api_study_cards(deck_id):
        """Get all cards for a deck, sorted by adaptive review priority."""
        user_id = session["user_id"]
        deck = query_db("SELECT * FROM decks WHERE id = ? AND user_id = ?", (deck_id, user_id), one=True)
        if not deck:
            return jsonify({"error": "Deck not found"}), 404

        cards = get_study_cards(deck_id, user_id=user_id)
        return jsonify({"deck": deck, "cards": cards}), 200

    @app.route("/api/study/<int:card_id>/respond", methods=["POST"])
    @login_required
    def api_study_respond(card_id):
        """Record student response and create an automatic analytics event."""
        user_id = session["user_id"]

        # Ownership check
        card = query_db("""
            SELECT c.* FROM cards c
            JOIN decks d ON d.id = c.deck_id
            WHERE c.id = ? AND d.user_id = ?
        """, (card_id, user_id), one=True)
        if not card:
            return jsonify({"error": "Card not found"}), 404

        data = request.get_json(silent=True) or {}
        knew_it = bool(data.get("knew_it", False))

        # Optional response time sent by the frontend, in seconds.
        response_time = data.get("response_time")
        try:
            response_time = float(response_time) if response_time is not None else 0.0
        except (TypeError, ValueError):
            response_time = 0.0

        # 1. Update the student's card progress.
        updated_card = record_response(card_id, knew_it)

        # 2. Automatically create a Firestore study event.
        #    This document is picked up by Eventarc/Cloud Run.
        db = get_db()
        if db is not None:
            event_id = str(uuid.uuid4())

            event_data = {
                "event_id": event_id,
                "user_id": str(user_id),
                "deck_id": str(card.get("deck_id")),
                "card_id": str(card_id),
                "event_type": "card_response",
                "correct": knew_it,
                "response_time": response_time,
                "timestamp": datetime.now(timezone.utc),
            }

            db.collection("study_events").document(event_id).set(event_data)
            print(f"[ANALYTICS] Study event created: {event_id}")
        else:
            # Local SQLite mode: the Firestore analytics pipeline is not active.
            print("[ANALYTICS] Firestore unavailable; study event was not created.")

        return jsonify(updated_card), 200

    @app.route("/api/smart-review/cards", methods=["GET"])
    @login_required
    def api_smart_review_cards():
        """Get prioritized cards needing review across all user's decks."""
        user_id = session["user_id"]
        cards = get_smart_review_cards(user_id)
        return jsonify({
            "deck": {
                "id": 0,
                "name": "🧠 Smart Review Queue",
                "description": "Prioritized cards needing attention across all your subjects"
            },
            "cards": cards
        }), 200

    # ═════════════════════════════════════════════════════════
    #  DASHBOARD API (user-scoped)
    # ═════════════════════════════════════════════════════════

    @app.route("/api/dashboard", methods=["GET"])
    @login_required
    def api_dashboard():
        """Return aggregate learning statistics for the user's dashboard."""
        user_id = session["user_id"]

        decks = query_db("""
            SELECT d.id, d.name, d.subject, d.description, d.created_at,
                   COUNT(c.id)                          AS card_count,
                   SUM(CASE WHEN c.attempts > 0 THEN 1 ELSE 0 END) AS cards_studied,
                   COALESCE(SUM(c.review_count), 0)     AS review_count,
                   COALESCE(SUM(c.correct_count), 0)    AS correct_count,
                   COALESCE(SUM(c.attempts), 0)         AS total_attempts
            FROM decks d
            LEFT JOIN cards c ON c.deck_id = d.id
            WHERE d.user_id = ?
            GROUP BY d.id
            ORDER BY d.created_at DESC
        """, (user_id,))

        needs_review_row = query_db("""
            SELECT COUNT(*) AS cnt FROM cards c
            JOIN decks d ON d.id = c.deck_id
            WHERE d.user_id = ? AND (c.attempts = 0 OR c.review_count > c.correct_count)
        """, (user_id,), one=True)
        cards_needing_review = needs_review_row["cnt"] if needs_review_row else 0

        # Mock exam stats
        exam_stats = query_db("""
            SELECT COUNT(*) AS total_exams,
                   COALESCE(AVG(score), 0) AS avg_score,
                   COALESCE(MAX(score), 0) AS best_score
            FROM mock_exams
            WHERE user_id = ? AND completed_at IS NOT NULL
        """, (user_id,), one=True)

        # Recent exams
        recent_exams = query_db("""
            SELECT me.*, d.name AS deck_name, d.subject
            FROM mock_exams me
            JOIN decks d ON d.id = me.deck_id
            WHERE me.user_id = ? AND me.completed_at IS NOT NULL
            ORDER BY me.completed_at DESC
            LIMIT 5
        """, (user_id,))

        # Aggregate totals
        total_decks = len(decks)
        total_cards = sum((d.get("card_count", 0) or 0) for d in decks)
        total_studied = sum((d.get("cards_studied", 0) or 0) for d in decks)
        total_correct = sum((d.get("correct_count", 0) or 0) for d in decks)
        total_attempts = sum((d.get("total_attempts", 0) or 0) for d in decks)

        # Cards mastered = correct_count > review_count AND attempts > 0
        mastered_row = query_db("""
            SELECT COUNT(*) AS cnt FROM cards c
            JOIN decks d ON d.id = c.deck_id
            WHERE d.user_id = ? AND c.attempts > 0
              AND c.correct_count > c.review_count
        """, (user_id,), one=True)
        questions_mastered = mastered_row["cnt"] if mastered_row else 0

        overall_accuracy = round((total_correct / total_attempts) * 100, 1) if total_attempts > 0 else 0

        deck_list = []
        for d in decks:
            card_count = d.get("card_count", 0) or 0
            cards_studied = d.get("cards_studied", 0) or 0
            review_count = d.get("review_count", 0) or 0
            correct_count = d.get("correct_count", 0) or 0
            total_attempts = d.get("total_attempts", 0) or 0
            acc = round((correct_count / total_attempts) * 100, 1) if total_attempts > 0 else 0
            prog = round((cards_studied / card_count) * 100, 1) if card_count > 0 else 0
            deck_list.append({
                "id": d.get("id"),
                "name": d.get("name", ""),
                "subject": d.get("subject", ""),
                "description": d.get("description", ""),
                "card_count": card_count,
                "cards_studied": cards_studied,
                "review_count": review_count,
                "correct_count": correct_count,
                "total_attempts": total_attempts,
                "accuracy": acc,
                "progress": prog,
            })

        return jsonify({
            "total_decks": total_decks,
            "total_cards": total_cards,
            "cards_studied": total_studied,
            "cards_needing_review": cards_needing_review,
            "overall_accuracy": overall_accuracy,
            "questions_mastered": questions_mastered,
            "total_exams": exam_stats["total_exams"] if exam_stats else 0,
            "avg_exam_score": round(exam_stats["avg_score"], 1) if exam_stats else 0,
            "best_exam_score": round(exam_stats["best_score"], 1) if exam_stats else 0,
            "decks": deck_list,
            "recent_exams": recent_exams,
        }), 200

    # ═════════════════════════════════════════════════════════
    #  ADAPTIVE RECOMMENDATIONS API (BigQuery)
    # ═════════════════════════════════════════════════════════

    @app.route("/api/adaptive-recommendations", methods=["GET"])
    @login_required
    def api_adaptive_recommendations():
        """Return adaptive recommendations for the logged-in student.

        BigQuery supplies the recommendation source and raw study_events
        supply the actual response metrics.

        Important ID rule:
        - BigQuery deck_id is an analytics identifier.
        - SQLite deck.id is the application's real deck identifier.
        - The response exposes the real local deck_id when a local deck can
          be resolved, while analytics_deck_id preserves the BigQuery ID.
        """

        user_id = str(session["user_id"]).strip()

        print("=" * 70)
        print("[ADAPTIVE] Loading recommendations")
        print("[ADAPTIVE] Flask session user_id:", user_id)
        print(
            "[ADAPTIVE] BigQuery view:",
            f"{BIGQUERY_PROJECT}.{BIGQUERY_DATASET}.{BIGQUERY_VIEW}"
        )

        recommendation_query = f"""
            SELECT
                user_id,
                deck_id,
                recommendation
            FROM `{BIGQUERY_PROJECT}.{BIGQUERY_DATASET}.{BIGQUERY_VIEW}`
            WHERE TRIM(CAST(user_id AS STRING)) = @user_id
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter(
                    "user_id",
                    "STRING",
                    user_id
                )
            ]
        )

        def is_placeholder_deck_name(name, analytics_deck_id):
            """Return True for automatically generated placeholder names."""
            if not name:
                return True

            normalized = str(name).strip().lower()
            analytics_id = str(analytics_deck_id).strip().lower()

            placeholder_names = {
                f"study deck {analytics_id}",
                f"study deck - {analytics_id}",
                f"study deck: {analytics_id}",
            }

            return normalized in placeholder_names

        def get_user_decks():
            """Return all decks owned by the current user."""
            return query_db(
                """
                SELECT
                    d.id,
                    d.name,
                    d.subject,
                    d.description,
                    d.created_at,
                    COUNT(c.id) AS card_count
                FROM decks d
                LEFT JOIN cards c ON c.deck_id = d.id
                WHERE d.user_id = ?
                GROUP BY d.id
                ORDER BY d.created_at DESC
                """,
                (session["user_id"],)
            ) or []

        try:
            client = get_bigquery_client()

            # ------------------------------------------------------------
            # 1. Read all raw study events for this user.
            # ------------------------------------------------------------
            events_query = f"""
                SELECT
                    TRIM(CAST(deck_id AS STRING)) AS deck_id,
                    COUNT(*) AS total_attempts,
                    COUNTIF(correct = TRUE) AS correct_answers,
                    AVG(SAFE_CAST(response_time AS FLOAT64))
                        AS average_response_time,
                    ARRAY_AGG(
                        DISTINCT TRIM(CAST(card_id AS STRING))
                        IGNORE NULLS
                        LIMIT 100
                    ) AS card_ids
                FROM `{BIGQUERY_PROJECT}.{BIGQUERY_DATASET}.study_events`
                WHERE TRIM(CAST(user_id AS STRING)) = @user_id
                GROUP BY deck_id
            """

            event_rows = client.query(
                events_query,
                job_config=job_config,
                location=BIGQUERY_LOCATION
            ).result()

            metrics_by_deck = {}

            for row in event_rows:
                analytics_deck_id = str(
                    getattr(row, "deck_id", "") or ""
                ).strip()

                total_attempts = int(
                    getattr(row, "total_attempts", 0) or 0
                )

                correct_answers = int(
                    getattr(row, "correct_answers", 0) or 0
                )

                average_response_time = float(
                    getattr(row, "average_response_time", 0) or 0
                )

                accuracy_percent = (
                    round(
                        (correct_answers / total_attempts) * 100,
                        1
                    )
                    if total_attempts > 0
                    else 0.0
                )

                raw_card_ids = getattr(row, "card_ids", None) or []

                card_ids = [
                    str(card_id).strip()
                    for card_id in raw_card_ids
                    if card_id is not None
                    and str(card_id).strip()
                ]

                metrics_by_deck[analytics_deck_id] = {
                    "total_attempts": total_attempts,
                    "correct_answers": correct_answers,
                    "accuracy_percent": accuracy_percent,
                    "average_response_time": round(
                        average_response_time,
                        2
                    ),
                    "card_ids": card_ids,
                }

            print(
                "[ADAPTIVE] Raw BigQuery events:",
                len(metrics_by_deck),
                "deck(s)"
            )

            # ------------------------------------------------------------
            # 2. Read recommendation rows from the existing view.
            # ------------------------------------------------------------
            view_rows = client.query(
                recommendation_query,
                job_config=job_config,
                location=BIGQUERY_LOCATION
            ).result()

            recommendations = []

            # Cache the user's local decks once instead of querying the
            # database repeatedly for every recommendation.
            user_decks = get_user_decks()

            print(
                "[ADAPTIVE] Local decks:",
                [
                    {
                        "id": d.get("id"),
                        "name": d.get("name"),
                        "card_count": d.get("card_count", 0)
                    }
                    for d in user_decks
                ]
            )

            for row in view_rows:
                row_user_id = getattr(row, "user_id", None)

                analytics_deck_id = str(
                    getattr(row, "deck_id", "") or ""
                ).strip()

                metrics = metrics_by_deck.get(
                    analytics_deck_id,
                    {
                        "total_attempts": 0,
                        "correct_answers": 0,
                        "accuracy_percent": 0.0,
                        "average_response_time": 0.0,
                        "card_ids": [],
                    }
                )

                recommendation = str(
                    getattr(row, "recommendation", "") or ""
                ).strip()

                if not recommendation:
                    accuracy = metrics["accuracy_percent"]

                    if accuracy < 60:
                        recommendation = "Review this deck again"
                    elif accuracy < 80:
                        recommendation = "Practice this deck more"
                    else:
                        recommendation = (
                            "Good performance - continue to next level"
                        )

                local_deck = None

                # --------------------------------------------------------
                # 3. First try exact local deck ID.
                # --------------------------------------------------------
                try:
                    possible_local_id = int(analytics_deck_id)

                    local_deck = query_db(
                        """
                        SELECT
                            d.id,
                            d.name,
                            d.subject,
                            d.description
                        FROM decks d
                        WHERE d.id = ?
                          AND d.user_id = ?
                        LIMIT 1
                        """,
                        (
                            possible_local_id,
                            session["user_id"]
                        ),
                        one=True
                    )

                    if local_deck:
                        print(
                            "[ADAPTIVE] Exact ID mapping:",
                            analytics_deck_id,
                            "->",
                            local_deck.get("id"),
                            local_deck.get("name")
                        )

                except (TypeError, ValueError):
                    local_deck = None

                # --------------------------------------------------------
                # 4. If IDs differ, try mapping an analytics card ID to
                #    the local cards table.
                # --------------------------------------------------------
                if local_deck is None:
                    for analytics_card_id in metrics["card_ids"]:

                        candidates = []

                        # SQLite may receive the card ID as either text
                        # or integer depending on the database adapter.
                        candidates.append(analytics_card_id)

                        try:
                            candidates.append(int(analytics_card_id))
                        except (TypeError, ValueError):
                            pass

                        for candidate_card_id in candidates:
                            try:
                                local_deck = query_db(
                                    """
                                    SELECT
                                        d.id,
                                        d.name,
                                        d.subject,
                                        d.description
                                    FROM cards c
                                    JOIN decks d
                                        ON d.id = c.deck_id
                                    WHERE c.id = ?
                                      AND d.user_id = ?
                                    LIMIT 1
                                    """,
                                    (
                                        candidate_card_id,
                                        session["user_id"]
                                    ),
                                    one=True
                                )
                            except Exception as card_error:
                                print(
                                    "[ADAPTIVE] Card mapping failed for",
                                    analytics_card_id,
                                    ":",
                                    card_error
                                )
                                local_deck = None

                            if local_deck:
                                print(
                                    "[ADAPTIVE] Card mapping:",
                                    "analytics deck",
                                    analytics_deck_id,
                                    "-> local deck",
                                    local_deck.get("id"),
                                    local_deck.get("name")
                                )
                                break

                        if local_deck:
                            break

                # --------------------------------------------------------
                # 5. IMPORTANT FIX:
                #
                # If the exact/card mapping points to an automatically
                # generated "Study Deck <analytics-id>" placeholder,
                # prefer a real user-created deck instead.
                #
                # This handles the situation where:
                #
                #   BigQuery deck = 1787759954631
                #   local generated deck name =
                #       Study Deck 1787759954631
                #
                # while the real deck has a meaningful name such as:
                #   Python Fundamentals - Mock Exam 1
                # --------------------------------------------------------
                if local_deck is not None and is_placeholder_deck_name(
                    local_deck.get("name"),
                    analytics_deck_id
                ):
                    real_named_decks = [
                        deck
                        for deck in user_decks
                        if not is_placeholder_deck_name(
                            deck.get("name"),
                            analytics_deck_id
                        )
                    ]

                    if len(real_named_decks) == 1:
                        print(
                            "[ADAPTIVE] Replacing generated placeholder:",
                            local_deck.get("name"),
                            "->",
                            real_named_decks[0].get("name")
                        )
                        local_deck = real_named_decks[0]

                # --------------------------------------------------------
                # 6. If there is exactly one local deck, it is safe to use
                #    it when BigQuery and SQLite IDs were generated
                #    independently.
                # --------------------------------------------------------
                if local_deck is None and len(user_decks) == 1:
                    local_deck = user_decks[0]

                    print(
                        "[ADAPTIVE] Single-deck fallback:",
                        analytics_deck_id,
                        "->",
                        local_deck.get("id"),
                        local_deck.get("name")
                    )

                # --------------------------------------------------------
                # 7. If there are multiple local decks and the current
                #    mapping failed, prefer a real named deck over a
                #    generated placeholder only when there is exactly one
                #    such real deck.
                # --------------------------------------------------------
                if local_deck is None and len(user_decks) > 1:
                    real_named_decks = [
                        deck
                        for deck in user_decks
                        if not is_placeholder_deck_name(
                            deck.get("name"),
                            analytics_deck_id
                        )
                    ]

                    if len(real_named_decks) == 1:
                        local_deck = real_named_decks[0]

                        print(
                            "[ADAPTIVE] Real-name fallback:",
                            analytics_deck_id,
                            "->",
                            local_deck.get("id"),
                            local_deck.get("name")
                        )
                    else:
                        print(
                            "[ADAPTIVE] Could not safely map analytics "
                            f"deck {analytics_deck_id}; "
                            f"user has {len(user_decks)} local decks."
                        )

                # --------------------------------------------------------
                # 8. Build the URL and DISPLAY NAME from the real local
                #    deck. Never use the analytics ID as the Study URL.
                # --------------------------------------------------------
                local_deck_id = None
                deck_name = None
                study_url = None

                if local_deck:
                    local_deck_id = local_deck.get("id")
                    deck_name = (
                        local_deck.get("name")
                        or ""
                    ).strip()

                    if local_deck_id is not None:
                        try:
                            study_url = url_for(
                                "study_page",
                                deck_id=int(local_deck_id)
                            )
                        except (TypeError, ValueError):
                            study_url = None

                # If there is no safe mapping, keep the analytics ID as
                # analytics_deck_id only. Do not pretend it is a real
                # local deck ID.
                if not deck_name:
                    deck_name = (
                        f"Study Deck {analytics_deck_id}"
                        if analytics_deck_id
                        else "Recommended Deck"
                    )

                # Use the REAL local ID when resolved. This fixes the
                # previous response where deck_id and study_url referred
                # to different identifiers.
                response_deck_id = (
                    str(local_deck_id)
                    if local_deck_id is not None
                    else analytics_deck_id
                )

                recommendations.append({
                    "user_id": (
                        str(row_user_id)
                        if row_user_id is not None
                        else user_id
                    ),

                    # BigQuery/analytics identifier retained for debugging
                    # and traceability.
                    "analytics_deck_id": analytics_deck_id,

                    # Real StudyFlip deck identifier when resolved.
                    "deck_id": response_deck_id,

                    # Real local deck name.
                    "deck_name": deck_name,

                    # Real local StudyFlip URL.
                    "study_url": study_url,

                    "total_attempts": metrics["total_attempts"],
                    "correct_answers": metrics["correct_answers"],
                    "accuracy_percent": metrics["accuracy_percent"],
                    "average_response_time": metrics[
                        "average_response_time"
                    ],
                    "recommendation": recommendation,
                })

            # ------------------------------------------------------------
            # 9. Weakest deck first.
            # ------------------------------------------------------------
            recommendations.sort(
                key=lambda item: (
                    item["accuracy_percent"],
                    -item["total_attempts"]
                )
            )

            best_action = (
                recommendations[0]
                if recommendations
                else None
            )

            response = {
                "success": True,
                "user_id": user_id,
                "recommendations": recommendations,
                "best_recommendation": best_action,
                "count": len(recommendations),
            }

            print("[ADAPTIVE] Final response:")
            print(response)
            print("=" * 70)

            result = jsonify(response)
            result.headers["Cache-Control"] = (
                "no-store, no-cache, must-revalidate, max-age=0"
            )

            return result, 200

        except Exception as e:
            print(
                "[BIGQUERY] Adaptive recommendation query failed:",
                repr(e)
            )

            return jsonify({
                "success": False,
                "user_id": user_id,
                "recommendations": [],
                "best_recommendation": None,
                "count": 0,
                "error": "Unable to load adaptive recommendations"
            }), 503



    # ═════════════════════════════════════════════════════════
    #  MOCK EXAM API
    # ═════════════════════════════════════════════════════════

    @app.route("/api/mock-exam/start", methods=["POST"])
    @login_required
    def api_start_exam():
        """Create a new mock exam for a deck."""
        user_id = session["user_id"]
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        deck_id = data.get("deck_id")
        num_questions = int(data.get("num_questions", 20))

        if not deck_id:
            return jsonify({"error": "deck_id is required"}), 400
        if num_questions < 1 or num_questions > 50:
            return jsonify({"error": "num_questions must be between 1 and 50"}), 400

        result = create_mock_exam(user_id, deck_id, num_questions)
        if not result:
            return jsonify({"error": "Could not create exam. Deck not found or has no cards."}), 404

        return jsonify(result), 201

    @app.route("/api/mock-exam/<int:exam_id>", methods=["GET"])
    @login_required
    def api_get_exam(exam_id):
        """Get exam details and questions."""
        user_id = session["user_id"]
        exam = query_db(
            "SELECT * FROM mock_exams WHERE id = ? AND user_id = ?",
            (exam_id, user_id), one=True
        )
        if not exam:
            return jsonify({"error": "Exam not found"}), 404

        questions = query_db(
            "SELECT * FROM exam_questions WHERE exam_id = ? ORDER BY question_order",
            (exam_id,)
        )
        deck = query_db("SELECT * FROM decks WHERE id = ?", (exam["deck_id"],), one=True)

        return jsonify({"exam": exam, "questions": questions, "deck": deck}), 200

    @app.route("/api/mock-exam/<int:exam_id>/submit", methods=["POST"])
    @login_required
    def api_submit_exam(exam_id):
        """Submit exam answers."""
        user_id = session["user_id"]
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        answers = data.get("answers", {})
        time_taken = int(data.get("time_taken", 0))

        result = submit_mock_exam(exam_id, user_id, answers, time_taken)
        if result is None:
            return jsonify({"error": "Exam not found or already submitted"}), 404

        return jsonify(result), 200

    @app.route("/api/mock-exam/<int:exam_id>/know-this", methods=["POST"])
    @login_required
    def api_know_this(exam_id):
        """Mark an exam question as self-mastered ('I Know This').

        This updates the student's card mastery record but does NOT
        count as an exam attempt, correct, or incorrect answer.
        The exam score is unaffected.
        """
        user_id = session["user_id"]

        # Verify exam ownership
        exam = query_db(
            "SELECT * FROM mock_exams WHERE id = ? AND user_id = ?",
            (exam_id, user_id), one=True
        )
        if not exam:
            return jsonify({"error": "Exam not found"}), 404
        if exam["completed_at"]:
            return jsonify({"error": "Exam already submitted"}), 400

        data = request.get_json(silent=True) or {}
        question_id = data.get("question_id")
        if not question_id:
            return jsonify({"error": "question_id is required"}), 400

        # Verify the question belongs to this exam
        question = query_db(
            "SELECT * FROM exam_questions WHERE id = ? AND exam_id = ?",
            (question_id, exam_id), one=True
        )
        if not question:
            return jsonify({"error": "Question not found"}), 404

        # Mark the question as self-mastered
        execute_db(
            "UPDATE exam_questions SET self_mastered = 1, user_answer = NULL, correct = 0 WHERE id = ?",
            (question_id,)
        )

        # Update the underlying card's mastery (correct_count + 1, but prevent duplicates)
        # We increment correct_count only, not attempts, to signal mastery without exam pressure
        card_id = question["card_id"]
        execute_db(
            "UPDATE cards SET correct_count = correct_count + 1 WHERE id = ?",
            (card_id,)
        )

        return jsonify({"message": "Question marked as self-mastered", "question_id": question_id}), 200

    @app.route("/api/mock-exam/<int:exam_id>/result", methods=["GET"])
    @login_required
    def api_exam_result(exam_id):
        """Get detailed exam result with question review.

        Returns separate lists for:
        - wrong_questions: ANSWERED_INCORRECT (for Review Mistakes flip cards)
        - known_questions: SELF_MASTERED ('I Know This')
        - unattempted_questions: no answer, not self-mastered
        """
        user_id = session["user_id"]
        exam = query_db(
            "SELECT * FROM mock_exams WHERE id = ? AND user_id = ?",
            (exam_id, user_id), one=True
        )
        if not exam:
            return jsonify({"error": "Exam not found"}), 404

        questions = query_db(
            "SELECT * FROM exam_questions WHERE exam_id = ? ORDER BY question_order",
            (exam_id,)
        )
        deck = query_db("SELECT * FROM decks WHERE id = ?", (exam["deck_id"],), one=True)

        # Format time
        secs = exam.get("time_taken", 0) or 0
        minutes = secs // 60
        seconds = secs % 60
        time_str = f"{minutes}m {seconds:02d}s"

        # Categorize questions
        wrong_questions = []
        known_questions = []
        unattempted_questions = []

        for q in questions:
            if q.get("self_mastered"):
                known_questions.append(q)
            elif q.get("user_answer") and not q.get("correct"):
                wrong_questions.append(q)
            elif not q.get("user_answer") and not q.get("self_mastered"):
                unattempted_questions.append(q)

        # Recalculate accurate stats from question data
        attempted = sum(1 for q in questions if q.get("user_answer") and not q.get("self_mastered"))
        correct_count = sum(1 for q in questions if q.get("correct") and not q.get("self_mastered"))
        incorrect_count = len(wrong_questions)
        known_count = len(known_questions)
        unattempted_count = len(unattempted_questions)
        accuracy = round((correct_count / attempted) * 100, 1) if attempted > 0 else 0

        return jsonify({
            "exam": exam,
            "questions": questions,
            "deck": deck,
            "time_str": time_str,
            "wrong_questions": wrong_questions,
            "known_questions": known_questions,
            "unattempted_questions": unattempted_questions,
            "stats": {
                "total": len(questions),
                "attempted": attempted,
                "correct": correct_count,
                "incorrect": incorrect_count,
                "known": known_count,
                "unattempted": unattempted_count,
                "accuracy": accuracy
            }
        }), 200

    # ═════════════════════════════════════════════════════════
    #  PROGRESS & HISTORY API
    # ═════════════════════════════════════════════════════════

    @app.route("/api/progress", methods=["GET"])
    @login_required
    def api_progress():
        """Return comprehensive progress stats for the user."""
        user_id = session["user_id"]

        # Overall exam stats
        exam_stats = query_db("""
            SELECT COUNT(*) AS total_exams,
                   COALESCE(AVG(score), 0) AS avg_score,
                   COALESCE(MAX(score), 0) AS best_score,
                   COALESCE(SUM(correct_answers), 0) AS total_correct,
                   COALESCE(SUM(total_questions), 0) AS total_attempted,
                   COALESCE(SUM(time_taken), 0) AS total_time
            FROM mock_exams
            WHERE user_id = ? AND completed_at IS NOT NULL
        """, (user_id,), one=True)

        # Study stats
        study_stats = query_db("""
            SELECT COALESCE(SUM(c.attempts), 0) AS total_attempts,
                   COALESCE(SUM(c.correct_count), 0) AS total_correct,
                   COALESCE(SUM(c.review_count), 0) AS total_reviews,
                   COUNT(CASE WHEN c.attempts > 0 AND c.correct_count > c.review_count THEN 1 END) AS mastered
            FROM cards c
            JOIN decks d ON d.id = c.deck_id
            WHERE d.user_id = ?
        """, (user_id,), one=True)

        # Subject performance from exams
        subject_perf = query_db("""
            SELECT d.subject,
                   d.name AS deck_name,
                   COUNT(me.id) AS exam_count,
                   COALESCE(AVG(me.score), 0) AS avg_score,
                   COALESCE(MAX(me.score), 0) AS best_score
            FROM mock_exams me
            JOIN decks d ON d.id = me.deck_id
            WHERE me.user_id = ? AND me.completed_at IS NOT NULL
            GROUP BY d.id
            ORDER BY avg_score DESC
        """, (user_id,))

        # Study accuracy per deck
        deck_accuracy = query_db("""
            SELECT d.name, d.subject,
                   COALESCE(SUM(c.attempts), 0) AS attempts,
                   COALESCE(SUM(c.correct_count), 0) AS correct,
                   COALESCE(SUM(c.review_count), 0) AS reviews,
                   COUNT(c.id) AS total_cards
            FROM decks d
            LEFT JOIN cards c ON c.deck_id = d.id
            WHERE d.user_id = ?
            GROUP BY d.id
            HAVING attempts > 0
            ORDER BY correct * 1.0 / attempts ASC
        """, (user_id,))

        # Format subject perf
        subject_list = []
        for s in subject_perf:
            subject_list.append({
                "subject": s["subject"] or s["deck_name"],
                "deck_name": s["deck_name"],
                "exam_count": s["exam_count"],
                "avg_score": round(s["avg_score"], 1),
                "best_score": round(s["best_score"], 1),
            })

        # Deck accuracy list
        deck_acc_list = []
        for d in deck_accuracy:
            acc = round((d["correct"] / d["attempts"]) * 100, 1) if d["attempts"] > 0 else 0
            deck_acc_list.append({
                "name": d["name"],
                "subject": d["subject"],
                "accuracy": acc,
                "attempts": d["attempts"],
                "correct": d["correct"],
                "reviews": d["reviews"],
                "total_cards": d["total_cards"]
            })

        overall_study_acc = 0
        if study_stats and study_stats["total_attempts"] > 0:
            overall_study_acc = round(
                (study_stats["total_correct"] / study_stats["total_attempts"]) * 100, 1
            )

        total_time_secs = exam_stats["total_time"] if exam_stats else 0
        total_time_str = f"{total_time_secs // 60}m" if total_time_secs > 0 else "—"

        return jsonify({
            "total_exams": exam_stats["total_exams"] if exam_stats else 0,
            "avg_score": round(exam_stats["avg_score"], 1) if exam_stats else 0,
            "best_score": round(exam_stats["best_score"], 1) if exam_stats else 0,
            "total_questions_attempted": exam_stats["total_attempted"] if exam_stats else 0,
            "total_correct_in_exams": exam_stats["total_correct"] if exam_stats else 0,
            "overall_exam_accuracy": round(
                (exam_stats["total_correct"] / exam_stats["total_attempted"]) * 100, 1
            ) if exam_stats and exam_stats["total_attempted"] > 0 else 0,
            "total_study_attempts": study_stats["total_attempts"] if study_stats else 0,
            "cards_mastered": study_stats["mastered"] if study_stats else 0,
            "overall_study_accuracy": overall_study_acc,
            "total_study_time": total_time_str,
            "subject_performance": subject_list,
            "deck_accuracy": deck_acc_list,
        }), 200

    @app.route("/api/exam-history", methods=["GET"])
    @login_required
    def api_exam_history():
        """Return the user's exam history."""
        user_id = session["user_id"]
        exams = query_db("""
            SELECT me.*, d.name AS deck_name, d.subject
            FROM mock_exams me
            JOIN decks d ON d.id = me.deck_id
            WHERE me.user_id = ? AND me.completed_at IS NOT NULL
            ORDER BY me.completed_at DESC
        """, (user_id,))

        result = []
        for e in exams:
            secs = e.get("time_taken", 0) or 0
            acc = round((e["correct_answers"] / e["total_questions"]) * 100, 1) if e["total_questions"] > 0 else 0
            result.append({
                **e,
                "accuracy": acc,
                "time_str": f"{secs // 60}m {secs % 60:02d}s",
                "date_str": e["completed_at"][:10] if e["completed_at"] else ""
            })

        return jsonify(result), 200

    @app.route("/api/weak-areas", methods=["GET"])
    @login_required
    def api_weak_areas():
        """Return weak areas based on study performance (low accuracy cards/decks)."""
        user_id = session["user_id"]

        # Cards with high review rate (weak cards)
        weak_cards = query_db("""
            SELECT c.question, c.answer, c.attempts, c.correct_count, c.review_count,
                   d.name AS deck_name, d.subject, d.id AS deck_id
            FROM cards c
            JOIN decks d ON d.id = c.deck_id
            WHERE d.user_id = ? AND c.attempts > 0
            ORDER BY (c.review_count * 1.0 / c.attempts) DESC
            LIMIT 10
        """, (user_id,))

        # Subjects with low exam scores
        weak_subjects = query_db("""
            SELECT d.subject, d.name AS deck_name, d.id AS deck_id,
                   COUNT(me.id) AS exams,
                   COALESCE(AVG(me.score), 0) AS avg_score
            FROM mock_exams me
            JOIN decks d ON d.id = me.deck_id
            WHERE me.user_id = ? AND me.completed_at IS NOT NULL
            GROUP BY d.id
            HAVING avg_score < 75
            ORDER BY avg_score ASC
            LIMIT 5
        """, (user_id,))

        # Format weak cards
        weak_card_list = []
        for c in weak_cards:
            acc = round((c["correct_count"] / c["attempts"]) * 100, 1)
            if acc < 70:  # Only show truly weak cards
                weak_card_list.append({
                    "question": c["question"],
                    "deck_name": c["deck_name"],
                    "subject": c["subject"],
                    "deck_id": c["deck_id"],
                    "accuracy": acc,
                    "attempts": c["attempts"],
                    "review_count": c["review_count"],
                })

        weak_subject_list = []
        for s in weak_subjects:
            weak_subject_list.append({
                "subject": s["subject"] or s["deck_name"],
                "deck_name": s["deck_name"],
                "deck_id": s["deck_id"],
                "avg_score": round(s["avg_score"], 1),
                "exams": s["exams"],
            })

        return jsonify({
            "weak_cards": weak_card_list,
            "weak_subjects": weak_subject_list,
        }), 200
    
        # ═════════════════════════════════════════════════════════
    #  CLOUD STORAGE API
    # ═════════════════════════════════════════════════════════

    @app.route("/api/storage/upload", methods=["POST"])
    @login_required
    def api_storage_upload():
        """
        Upload a study material file to Cloud Storage.

        Files are isolated by user:
            users/<user_id>/files/<filename>
        """

        user_id = str(session["user_id"])

        if "file" not in request.files:
            return jsonify({
                "error": "No file provided"
            }), 400

        file = request.files["file"]

        if not file or not file.filename:
            return jsonify({
                "error": "No filename provided"
            }), 400

        # Prevent directory traversal and unsafe paths.
        original_filename = os.path.basename(
            file.filename
        ).strip()

        if not original_filename:
            return jsonify({
                "error": "Invalid filename"
            }), 400

        # Generate a unique name so repeated uploads
        # don't overwrite each other.
        extension = os.path.splitext(
            original_filename
        )[1].lower()

        unique_name = (
            f"{uuid.uuid4().hex}"
            f"{extension}"
        )

        object_name = (
            f"users/{user_id}/files/{unique_name}"
        )

        try:
            uploaded_name = upload_file(
                file,
                object_name,
                file.content_type
            )

            return jsonify({
                "message": "File uploaded successfully",
                "filename": original_filename,
                "object_name": uploaded_name,
                "bucket": "digital-flashcard-app-files-2026",
            }), 201

        except Exception as exc:
            print(
                f"[STORAGE] Upload failed: {exc}"
            )

            return jsonify({
                "error": "File upload failed"
            }), 500


    @app.route(
        "/api/storage/download/<path:object_name>",
        methods=["GET"]
    )
    @login_required
    def api_storage_download(object_name):
        """
        Download a user's own file from Cloud Storage.
        """

        user_id = str(session["user_id"])

        expected_prefix = (
            f"users/{user_id}/files/"
        )

        # Security: users may only download files
        # belonging to their own storage namespace.
        if not object_name.startswith(
            expected_prefix
        ):
            return jsonify({
                "error": "Access denied"
            }), 403

        try:
            file_data, content_type = download_file(
                object_name
            )

            filename = os.path.basename(
                object_name
            )

            from io import BytesIO

            return send_file(
                BytesIO(file_data),
                mimetype=content_type,
                as_attachment=True,
                download_name=filename
            )

        except FileNotFoundError:
            return jsonify({
                "error": "File not found"
            }), 404

        except Exception as exc:
            print(
                f"[STORAGE] Download failed: {exc}"
            )

            return jsonify({
                "error": "File download failed"
            }), 500


    @app.route(
        "/api/storage/files",
        methods=["GET"]
    )
    @login_required
    def api_storage_files():
        """
        List the current user's files.
        """

        user_id = str(session["user_id"])

        prefix = (
            f"users/{user_id}/files/"
        )

        try:
            files = list_files(prefix)

            return jsonify({
                "files": files
            }), 200

        except Exception as exc:
            print(
                f"[STORAGE] Listing failed: {exc}"
            )

            return jsonify({
                "error": "Could not list files"
            }), 500
        
    return app


# ── Dev server ───────────────────────────────────────────────
app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(debug=Config.DEBUG, host="0.0.0.0", port=port)
