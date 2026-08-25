"""
STUDYFLIP — Digital Flashcard + Mock Exam Preparation Platform
Application Entry Point

Run with:
    python app.py          (development)
    gunicorn app:app       (production)
"""

import functools
import os
from datetime import datetime

from flask import (
    Flask, render_template, request, jsonify,
    session, redirect, url_for
)
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from firestore_db import (
    init_db, query_db, execute_db,
    get_study_cards, get_smart_review_cards,
    record_response, calculate_priority,
    create_mock_exam, submit_mock_exam
)


def create_app():
    """Application factory."""
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )
    app.config.from_object(Config)

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
        """Record student response for a card."""
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
        updated_card = record_response(card_id, knew_it)
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
        total_cards = sum(d["card_count"] for d in decks)
        total_studied = sum(d["cards_studied"] for d in decks)
        total_correct = sum(d["correct_count"] for d in decks)
        total_attempts = sum(d["total_attempts"] for d in decks)

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
            acc = round((d["correct_count"] / d["total_attempts"]) * 100, 1) if d["total_attempts"] > 0 else 0
            prog = round((d["cards_studied"] / d["card_count"]) * 100, 1) if d["card_count"] > 0 else 0
            deck_list.append({
                "id": d["id"],
                "name": d["name"],
                "subject": d["subject"],
                "description": d["description"],
                "card_count": d["card_count"],
                "cards_studied": d["cards_studied"],
                "review_count": d["review_count"],
                "correct_count": d["correct_count"],
                "total_attempts": d["total_attempts"],
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

    return app


# ── Dev server ───────────────────────────────────────────────
app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(debug=Config.DEBUG, host="0.0.0.0", port=port)
