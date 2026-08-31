"""
Firestore Database Layer for StudyFlip.
Replaces database.py with Google Cloud Firestore operations.
Maps tables to Firestore collections: users, decks, cards, study_sessions, mock_exams, exam_questions.

Includes automatic local SQLite fallback if GCP credentials are not present locally.
"""

import os
import time
import random
from datetime import datetime
from google.cloud import firestore
import google.auth.exceptions
import database

_client = None
_use_sqlite_fallback = False


def get_db():
    """Lazy-initialize and return the Firestore client.
    Falls back to SQLite if GCP credentials are missing.
    """

    global _client, _use_sqlite_fallback

    if _use_sqlite_fallback:
        return None

    if _client is None:
        try:
            # Get Google Cloud project ID
            project = (
                os.getenv("GOOGLE_CLOUD_PROJECT")
                or os.getenv("GCP_PROJECT")
            )

            # Your Firestore database ID
            database_id = os.getenv(
                "FIRESTORE_DATABASE_ID",
                "flashcard-db"
            )

            print(f"[INFO] Connecting to Firestore...")
            print(f"[INFO] Project: {project}")
            print(f"[INFO] Database: {database_id}")

            if project:
                _client = firestore.Client(
                    project=project,
                    database=database_id
                )
            else:
                _client = firestore.Client(
                    database=database_id
                )

            # Test the connection
            _client.collections()

            print(
                f"[INFO] Firestore connected successfully: "
                f"{project}/{database_id}"
            )

        except (
            google.auth.exceptions.DefaultCredentialsError,
            google.auth.exceptions.GoogleAuthError,
            Exception
        ) as e:
            print(f"[ERROR] Firestore connection failed: {e}")
            print("[INFO] Using local SQLite database mode.")

            _use_sqlite_fallback = True
            database.init_db()
            return None

    return _client


def generate_id():
    """Generate a unique integer ID for documents to maintain integer ID compatibility."""
    return int(time.time() * 1000) + random.randint(0, 999)


def init_db():
    """Initialize database (runs SQLite schema if fallback mode active)."""
    db = get_db()

    if db is None:
        return database.init_db()


# ═══════════════════════════════════════════════════════════════
# ADAPTIVE REVIEW PRIORITIZATION
# ═══════════════════════════════════════════════════════════════

def calculate_priority(attempts, correct_count, review_count):
    """
    Calculate review priority score for a single card.
    Formula: (review_count + 1) / (attempts + 2) [Laplace smoothed]
    """
    return database.calculate_priority(
        attempts,
        correct_count,
        review_count
    )


def record_response(card_id, knew_it):
    """
    Record a student's response to a card and update tracking fields.
    """

    db = get_db()

    if db is None:
        return database.record_response(card_id, knew_it)

    card_ref = db.collection("cards").document(str(card_id))
    doc = card_ref.get()

    if not doc.exists:
        return None

    card = doc.to_dict()

    attempts = card.get("attempts", 0) + 1

    if knew_it:
        correct_count = card.get("correct_count", 0) + 1
        review_count = card.get("review_count", 0)
    else:
        correct_count = card.get("correct_count", 0)
        review_count = card.get("review_count", 0) + 1

    updates = {
        "attempts": attempts,
        "correct_count": correct_count,
        "review_count": review_count
    }

    card_ref.update(updates)

    card.update(updates)

    return card


def get_study_cards(deck_id, user_id=None):
    """
    Return all cards in a deck, sorted by review priority (highest first).
    """

    db = get_db()

    if db is None:
        return database.get_study_cards(
            deck_id,
            user_id=user_id
        )

    if user_id is not None:
        deck_doc = (
            db.collection("decks")
            .document(str(deck_id))
            .get()
        )

        if (
            not deck_doc.exists
            or deck_doc.to_dict().get("user_id") != user_id
        ):
            return []

    cards_docs = (
        db.collection("cards")
        .where("deck_id", "==", int(deck_id))
        .get()
    )

    if not cards_docs:
        cards_docs = (
            db.collection("cards")
            .where("deck_id", "==", str(deck_id))
            .get()
        )

    cards = [doc.to_dict() for doc in cards_docs]

    for c in cards:
        c["priority"] = calculate_priority(
            c.get("attempts", 0),
            c.get("correct_count", 0),
            c.get("review_count", 0)
        )

    cards.sort(
        key=lambda c: c["priority"],
        reverse=True
    )

    return cards


def get_smart_review_cards(user_id, limit=25):
    """
    Return cards needing attention across ALL of a user's decks,
    sorted by Adaptive Review Prioritization.
    """

    db = get_db()

    if db is None:
        return database.get_smart_review_cards(
            user_id,
            limit=limit
        )

    decks = [
        doc.to_dict()
        for doc in (
            db.collection("decks")
            .where("user_id", "==", user_id)
            .get()
        )
    ]

    if not decks:
        return []

    deck_map = {
        d["id"]: d["name"]
        for d in decks
    }

    all_cards = []

    for deck in decks:
        c_docs = (
            db.collection("cards")
            .where("deck_id", "==", deck["id"])
            .get()
        )

        for cd in c_docs:
            c = cd.to_dict()
            c["deck_name"] = deck_map.get(
                c.get("deck_id"),
                ""
            )
            all_cards.append(c)

    for c in all_cards:
        c["priority"] = calculate_priority(
            c.get("attempts", 0),
            c.get("correct_count", 0),
            c.get("review_count", 0)
        )

    needing_attention = [
        c for c in all_cards
        if (
            c.get("attempts", 0) == 0
            or c.get("review_count", 0)
            > c.get("correct_count", 0)
        )
    ]

    target_cards = (
        needing_attention
        if needing_attention
        else all_cards
    )

    target_cards.sort(
        key=lambda c: c["priority"],
        reverse=True
    )

    return target_cards[:limit]


# ═══════════════════════════════════════════════════════════════
# MOCK EXAM — MCQ GENERATION
# ═══════════════════════════════════════════════════════════════

def generate_mcq_options(card, all_deck_cards):
    """
    Generate 4 MCQ options for a card deterministically.
    """
    return database.generate_mcq_options(
        card,
        all_deck_cards
    )


def create_mock_exam(user_id, deck_id, num_questions=20):
    """
    Create a new mock exam with auto-generated MCQ questions.
    """

    db = get_db()

    if db is None:
        return database.create_mock_exam(
            user_id,
            deck_id,
            num_questions=num_questions
        )

    deck_doc = (
        db.collection("decks")
        .document(str(deck_id))
        .get()
    )

    if not deck_doc.exists:
        return None

    deck = deck_doc.to_dict()

    if deck.get("user_id") != user_id:
        return None

    cards_docs = (
        db.collection("cards")
        .where("deck_id", "==", int(deck_id))
        .get()
    )

    all_cards = [
        d.to_dict()
        for d in cards_docs
    ]

    if not all_cards:
        return None

    num_questions = min(
        num_questions,
        len(all_cards)
    )

    for card in all_cards:
        card["priority"] = calculate_priority(
            card.get("attempts", 0),
            card.get("correct_count", 0),
            card.get("review_count", 0)
        )

    sorted_cards = sorted(
        all_cards,
        key=lambda c: c["priority"],
        reverse=True
    )

    selected_cards = sorted_cards[:num_questions]

    exam_id = generate_id()

    exam_doc = {
        "id": exam_id,
        "user_id": user_id,
        "deck_id": deck_id,
        "score": 0.0,
        "total_questions": num_questions,
        "correct_answers": 0,
        "incorrect_answers": 0,
        "started_at": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "completed_at": None,
        "time_taken": 0
    }

    db.collection("mock_exams").document(
        str(exam_id)
    ).set(exam_doc)

    questions = []

    for i, card in enumerate(selected_cards):

        mcq = generate_mcq_options(
            card,
            all_cards
        )

        q_id = generate_id()

        q_doc = {
            "id": q_id,
            "exam_id": exam_id,
            "card_id": card["id"],
            "question_text": card["question"],
            "option_a": mcq["option_a"],
            "option_b": mcq["option_b"],
            "option_c": mcq["option_c"],
            "option_d": mcq["option_d"],
            "correct_option": mcq["correct_option"],
            "question_order": i + 1,
            "user_answer": None,
            "correct": 0,
            "self_mastered": 0
        }

        db.collection("exam_questions").document(
            str(q_id)
        ).set(q_doc)

        questions.append(q_doc)

    return {
        "exam": exam_doc,
        "questions": questions,
        "deck": deck
    }


def submit_mock_exam(
    exam_id,
    user_id,
    answers,
    time_taken
):
    """
    Submit answers for an exam and calculate score.
    """

    db = get_db()

    if db is None:
        return database.submit_mock_exam(
            exam_id,
            user_id,
            answers,
            time_taken
        )

    exam_ref = (
        db.collection("mock_exams")
        .document(str(exam_id))
    )

    exam_doc = exam_ref.get()

    if not exam_doc.exists:
        return None

    exam = exam_doc.to_dict()

    if (
        exam.get("user_id") != user_id
        or exam.get("completed_at")
    ):
        return None

    q_docs = (
        db.collection("exam_questions")
        .where("exam_id", "==", int(exam_id))
        .get()
    )

    questions = [
        d.to_dict()
        for d in q_docs
    ]

    questions.sort(
        key=lambda q: q.get("question_order", 0)
    )

    correct = 0
    incorrect = 0
    known_count = 0
    unattempted = 0

    for q in questions:

        q_ref = (
            db.collection("exam_questions")
            .document(str(q["id"]))
        )

        if q.get("self_mastered", 0):
            known_count += 1
            continue

        user_answer = answers.get(
            str(q["id"]),
            ""
        )

        if not user_answer:
            unattempted += 1

            q_ref.update({
                "user_answer": None,
                "correct": 0
            })

        else:
            is_correct = (
                1
                if user_answer.lower()
                == q["correct_option"].lower()
                else 0
            )

            if is_correct:
                correct += 1

            else:
                incorrect += 1

                card_ref = (
                    db.collection("cards")
                    .document(str(q["card_id"]))
                )

                c_doc = card_ref.get()

                if c_doc.exists:
                    c = c_doc.to_dict()

                    card_ref.update({
                        "attempts":
                            c.get("attempts", 0) + 1,
                        "review_count":
                            c.get("review_count", 0) + 1
                    })

            q_ref.update({
                "user_answer": user_answer,
                "correct": is_correct
            })

    total_questions = len(questions)

    attempted = correct + incorrect

    score = (
        round((correct / attempted) * 100, 1)
        if attempted > 0
        else 0
    )

    now_str = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    exam_updates = {
        "score": score,
        "correct_answers": correct,
        "incorrect_answers": incorrect,
        "completed_at": now_str,
        "time_taken": time_taken
    }

    exam_ref.update(exam_updates)

    return {
        "exam_id": exam_id,
        "score": score,
        "total": total_questions,
        "attempted": attempted,
        "correct": correct,
        "incorrect": incorrect,
        "known": known_count,
        "unattempted": unattempted,
        "time_taken": time_taken
    }


# ═══════════════════════════════════════════════════════════════
# FIRESTORE SQL-QUERY DISPATCHERS
# ═══════════════════════════════════════════════════════════════

def execute_db(query, args=()):
    """Execute an INSERT, UPDATE, or DELETE and return inserted/affected ID."""

    db = get_db()

    if db is None:
        return database.execute_db(
            query,
            args
        )

    q = query.strip()

    if q.startswith("INSERT INTO users"):

        new_id = generate_id()

        doc = {
            "id": new_id,
            "name": args[0],
            "email": args[1],
            "password_hash": args[2],
            "created_at":
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
        }

        db.collection("users").document(
            str(new_id)
        ).set(doc)

        return new_id

    elif q.startswith("INSERT INTO decks"):

        new_id = generate_id()

        doc = {
            "id": new_id,
            "user_id": args[0],
            "name": args[1],
            "subject":
                args[2]
                if len(args) > 2
                else "",
            "description":
                args[3]
                if len(args) > 3
                else "",
            "created_at":
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
        }

        db.collection("decks").document(
            str(new_id)
        ).set(doc)

        return new_id

    elif q.startswith("UPDATE decks SET name"):

        deck_id = args[3]
        user_id = args[4]

        d_ref = (
            db.collection("decks")
            .document(str(deck_id))
        )

        d_ref.update({
            "name": args[0],
            "subject": args[1],
            "description": args[2]
        })

        return deck_id

    elif q.startswith("DELETE FROM decks"):

        deck_id = args[0]

        db.collection("decks").document(
            str(deck_id)
        ).delete()

        c_docs = (
            db.collection("cards")
            .where(
                "deck_id",
                "==",
                int(deck_id)
            )
            .get()
        )

        for cd in c_docs:
            cd.reference.delete()

        return deck_id

    elif q.startswith("INSERT INTO cards"):

        new_id = generate_id()

        doc = {
            "id": new_id,
            "deck_id": args[0],
            "question": args[1],
            "answer": args[2],
            "option_a":
                args[3]
                if len(args) > 3
                else None,
            "option_b":
                args[4]
                if len(args) > 4
                else None,
            "option_c":
                args[5]
                if len(args) > 5
                else None,
            "option_d":
                args[6]
                if len(args) > 6
                else None,
            "correct_option":
                args[7]
                if len(args) > 7
                else None,
            "attempts": 0,
            "correct_count": 0,
            "review_count": 0,
            "created_at":
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
        }

        db.collection("cards").document(
            str(new_id)
        ).set(doc)

        return new_id

    elif q.startswith("UPDATE cards SET question"):

        card_id = args[7]

        c_ref = (
            db.collection("cards")
            .document(str(card_id))
        )

        c_ref.update({
            "question": args[0],
            "answer": args[1],
            "option_a": args[2],
            "option_b": args[3],
            "option_c": args[4],
            "option_d": args[5],
            "correct_option": args[6]
        })

        return card_id

    elif q.startswith("DELETE FROM cards"):

        card_id = args[0]

        db.collection("cards").document(
            str(card_id)
        ).delete()

        return card_id

    elif "attempts = attempts + 1, correct_count = correct_count + 1" in q:

        card_id = args[0]

        c_ref = (
            db.collection("cards")
            .document(str(card_id))
        )

        doc = c_ref.get()

        if doc.exists:
            c = doc.to_dict()

            c_ref.update({
                "attempts":
                    c.get("attempts", 0) + 1,
                "correct_count":
                    c.get("correct_count", 0) + 1
            })

        return card_id

    elif "attempts = attempts + 1, review_count = review_count + 1" in q:

        card_id = args[0]

        c_ref = (
            db.collection("cards")
            .document(str(card_id))
        )

        doc = c_ref.get()

        if doc.exists:
            c = doc.to_dict()

            c_ref.update({
                "attempts":
                    c.get("attempts", 0) + 1,
                "review_count":
                    c.get("review_count", 0) + 1
            })

        return card_id

    elif "correct_count = correct_count + 1" in q:

        card_id = args[0]

        c_ref = (
            db.collection("cards")
            .document(str(card_id))
        )

        doc = c_ref.get()

        if doc.exists:
            c = doc.to_dict()

            c_ref.update({
                "correct_count":
                    c.get("correct_count", 0) + 1
            })

        return card_id

    elif q.startswith("INSERT INTO mock_exams"):

        new_id = generate_id()

        doc = {
            "id": new_id,
            "user_id": args[0],
            "deck_id": args[1],
            "total_questions": args[2],
            "score": 0.0,
            "correct_answers": 0,
            "incorrect_answers": 0,
            "started_at":
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            "completed_at": None,
            "time_taken": 0
        }

        db.collection("mock_exams").document(
            str(new_id)
        ).set(doc)

        return new_id

    elif q.startswith("UPDATE mock_exams"):

        exam_id = args[4]

        e_ref = (
            db.collection("mock_exams")
            .document(str(exam_id))
        )

        e_ref.update({
            "score": args[0],
            "correct_answers": args[1],
            "incorrect_answers": args[2],
            "completed_at":
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            "time_taken": args[3]
        })

        return exam_id

    elif q.startswith("INSERT INTO exam_questions"):

        new_id = generate_id()

        doc = {
            "id": new_id,
            "exam_id": args[0],
            "card_id": args[1],
            "question_text": args[2],
            "option_a": args[3],
            "option_b": args[4],
            "option_c": args[5],
            "option_d": args[6],
            "correct_option": args[7],
            "question_order": args[8],
            "user_answer": None,
            "correct": 0,
            "self_mastered": 0
        }

        db.collection("exam_questions").document(
            str(new_id)
        ).set(doc)

        return new_id

    elif q.startswith(
        "UPDATE exam_questions SET user_answer = ?, correct = ?"
    ):

        q_id = args[2]

        db.collection("exam_questions").document(
            str(q_id)
        ).update({
            "user_answer": args[0],
            "correct": args[1]
        })

        return q_id

    elif q.startswith(
        "UPDATE exam_questions SET user_answer = NULL"
    ):

        q_id = args[0]

        db.collection("exam_questions").document(
            str(q_id)
        ).update({
            "user_answer": None,
            "correct": 0
        })

        return q_id

    elif q.startswith(
        "UPDATE exam_questions SET self_mastered = 1"
    ):

        q_id = args[0]

        db.collection("exam_questions").document(
            str(q_id)
        ).update({
            "self_mastered": 1,
            "user_answer": None,
            "correct": 0
        })

        return q_id

    return None


def query_db(query, args=(), one=False):
    """Execute a SELECT query against Firestore collections."""

    db = get_db()

    if db is None:
        return database.query_db(
            query,
            args,
            one=one
        )

    q = query.strip()
    results = []

    if q.startswith(
        "SELECT"
    ) and "FROM users WHERE id =" in q:

        uid = args[0]

        doc = (
            db.collection("users")
            .document(str(uid))
            .get()
        )

        if doc.exists:
            results.append(doc.to_dict())

    elif q.startswith(
        "SELECT"
    ) and "FROM users WHERE email =" in q:

        email = args[0]

        docs = (
            db.collection("users")
            .where("email", "==", email)
            .get()
        )

        results = [
            d.to_dict()
            for d in docs
        ]

    elif q.startswith(
        "SELECT * FROM decks WHERE id = ? AND user_id = ?"
    ):

        deck_id, user_id = args[0], args[1]

        doc = (
            db.collection("decks")
            .document(str(deck_id))
            .get()
        )

        if doc.exists:
            d = doc.to_dict()

            if d.get("user_id") == user_id:
                results.append(d)

    elif q.startswith(
        "SELECT * FROM decks WHERE id = ?"
    ):

        deck_id = args[0]

        doc = (
            db.collection("decks")
            .document(str(deck_id))
            .get()
        )

        if doc.exists:
            results.append(doc.to_dict())

    elif (
        "FROM decks d" in q
        and "COUNT(c.id)" in q
        and "WHERE d.user_id = ?" in q
        and "WHERE d.id = ?" not in q
    ):

        user_id = args[0]

        d_docs = (
            db.collection("decks")
            .where("user_id", "==", user_id)
            .get()
        )

        decks = [
            d.to_dict()
            for d in d_docs
        ]

        all_cards_docs = (
            db.collection("cards")
            .get()
        )

        cards_by_deck = {}

        for cd in all_cards_docs:

            c = cd.to_dict()
            did = c.get("deck_id")

            cards_by_deck[did] = (
                cards_by_deck.get(did, 0) + 1
            )

        for d in decks:
            d["card_count"] = cards_by_deck.get(
                d["id"],
                0
            )

        decks.sort(
            key=lambda x: x.get(
                "created_at",
                ""
            ),
            reverse=True
        )

        results = decks

    elif (
        "FROM decks d" in q
        and "COUNT(c.id)" in q
        and "WHERE d.id = ?" in q
    ):

        deck_id, user_id = args[0], args[1]

        doc = (
            db.collection("decks")
            .document(str(deck_id))
            .get()
        )

        if doc.exists:

            d = doc.to_dict()

            if d.get("user_id") == user_id:

                c_docs = (
                    db.collection("cards")
                    .where(
                        "deck_id",
                        "==",
                        int(deck_id)
                    )
                    .get()
                )

                d["card_count"] = len(c_docs)

                results.append(d)

    elif q.startswith(
        "SELECT * FROM cards WHERE deck_id = ?"
    ):

        deck_id = args[0]

        c_docs = (
            db.collection("cards")
            .where(
                "deck_id",
                "==",
                int(deck_id)
            )
            .get()
        )

        cards = [
            d.to_dict()
            for d in c_docs
        ]

        if "ORDER BY created_at DESC" in q:
            cards.sort(
                key=lambda c: c.get(
                    "created_at",
                    ""
                ),
                reverse=True
            )

        elif "ORDER BY id" in q:
            cards.sort(
                key=lambda c: c.get(
                    "id",
                    0
                )
            )

        results = cards

    elif q.startswith(
        "SELECT * FROM cards WHERE id = ?"
    ):

        card_id = args[0]

        doc = (
            db.collection("cards")
            .document(str(card_id))
            .get()
        )

        if doc.exists:
            results.append(
                doc.to_dict()
            )

    elif (
        "FROM cards c" in q
        and "JOIN decks d" in q
        and "WHERE c.id = ? AND d.user_id = ?" in q
    ):

        card_id, user_id = args[0], args[1]

        doc = (
            db.collection("cards")
            .document(str(card_id))
            .get()
        )

        if doc.exists:

            c = doc.to_dict()

            deck_doc = (
                db.collection("decks")
                .document(str(c.get("deck_id")))
                .get()
            )

            if (
                deck_doc.exists
                and deck_doc.to_dict().get(
                    "user_id"
                ) == user_id
            ):
                results.append(c)

    elif q.startswith(
        "SELECT * FROM mock_exams WHERE id = ? AND user_id = ?"
    ):

        exam_id, user_id = args[0], args[1]

        doc = (
            db.collection("mock_exams")
            .document(str(exam_id))
            .get()
        )

        if doc.exists:

            e = doc.to_dict()

            if e.get("user_id") == user_id:
                results.append(e)

    elif q.startswith(
        "SELECT * FROM mock_exams WHERE id = ?"
    ):

        exam_id = args[0]

        doc = (
            db.collection("mock_exams")
            .document(str(exam_id))
            .get()
        )

        if doc.exists:
            results.append(
                doc.to_dict()
            )

    elif q.startswith(
        "SELECT * FROM exam_questions WHERE exam_id = ?"
    ):

        exam_id = args[0]

        q_docs = (
            db.collection("exam_questions")
            .where(
                "exam_id",
                "==",
                int(exam_id)
            )
            .get()
        )

        qs = [
            d.to_dict()
            for d in q_docs
        ]

        qs.sort(
            key=lambda x: x.get(
                "question_order",
                0
            )
        )

        results = qs

    elif q.startswith(
        "SELECT * FROM exam_questions WHERE id = ? AND exam_id = ?"
    ):

        q_id, exam_id = args[0], args[1]

        doc = (
            db.collection("exam_questions")
            .document(str(q_id))
            .get()
        )

        if doc.exists:

            q_dict = doc.to_dict()

            if q_dict.get("exam_id") == exam_id:
                results.append(q_dict)

    elif (
        "SUM(CASE WHEN c.attempts > 0 THEN 1 ELSE 0 END) AS cards_studied"
        in q
    ):

        user_id = args[0]

        d_docs = (
            db.collection("decks")
            .where("user_id", "==", user_id)
            .get()
        )

        decks = [
            d.to_dict()
            for d in d_docs
        ]

        all_cards_docs = (
            db.collection("cards")
            .get()
        )

        all_cards = [
            cd.to_dict()
            for cd in all_cards_docs
        ]

        deck_stats = {}

        for d in decks:

            did = d["id"]

            deck_cards = [
                c
                for c in all_cards
                if c.get("deck_id") == did
            ]

            card_count = len(deck_cards)

            cards_studied = sum(
                1
                for c in deck_cards
                if c.get("attempts", 0) > 0
            )

            review_count = sum(
                c.get("review_count", 0)
                for c in deck_cards
            )

            correct_count = sum(
                c.get("correct_count", 0)
                for c in deck_cards
            )

            total_attempts = sum(
                c.get("attempts", 0)
                for c in deck_cards
            )

            deck_stats[did] = {
                "id": d["id"],
                "name": d["name"],
                "subject": d.get("subject", ""),
                "description": d.get(
                    "description",
                    ""
                ),
                "created_at": d.get(
                    "created_at",
                    ""
                ),
                "card_count": card_count,
                "cards_studied": cards_studied,
                "review_count": review_count,
                "correct_count": correct_count,
                "total_attempts": total_attempts
            }

        decks_list = list(
            deck_stats.values()
        )

        decks_list.sort(
            key=lambda x: x.get(
                "created_at",
                ""
            ),
            reverse=True
        )

        results = decks_list

    elif (
        "c.attempts = 0 OR c.review_count > c.correct_count"
        in q
    ):

        user_id = args[0]

        d_docs = (
            db.collection("decks")
            .where("user_id", "==", user_id)
            .get()
        )

        user_deck_ids = {
            d.to_dict()["id"]
            for d in d_docs
        }

        all_cards_docs = (
            db.collection("cards")
            .get()
        )

        count = 0

        for cd in all_cards_docs:

            c = cd.to_dict()

            if c.get("deck_id") in user_deck_ids:

                if (
                    c.get("attempts", 0) == 0
                    or c.get("review_count", 0)
                    > c.get("correct_count", 0)
                ):
                    count += 1

        results = [
            {"cnt": count}
        ]

    elif (
        "AVG(score)" in q
        and "mock_exams" in q
        and "GROUP BY" not in q
    ):

        user_id = args[0]

        e_docs = (
            db.collection("mock_exams")
            .where("user_id", "==", user_id)
            .get()
        )

        completed = [
            e.to_dict()
            for e in e_docs
            if e.to_dict().get(
                "completed_at"
            )
        ]

        if completed:

            total_exams = len(completed)

            avg_score = (
                sum(
                    e.get("score", 0)
                    for e in completed
                )
                / total_exams
            )

            best_score = max(
                e.get("score", 0)
                for e in completed
            )

            total_correct = sum(
                e.get("correct_answers", 0)
                for e in completed
            )

            total_attempted = sum(
                e.get("total_questions", 0)
                for e in completed
            )

            total_time = sum(
                e.get("time_taken", 0)
                for e in completed
            )

        else:

            total_exams = 0
            avg_score = 0.0
            best_score = 0.0
            total_correct = 0
            total_attempted = 0
            total_time = 0

        results = [{
            "total_exams": total_exams,
            "avg_score": avg_score,
            "best_score": best_score,
            "total_correct": total_correct,
            "total_attempted": total_attempted,
            "total_time": total_time
        }]

    elif (
        "FROM mock_exams me" in q
        and "JOIN decks d" in q
        and "ORDER BY me.completed_at DESC" in q
    ):

        user_id = args[0]

        e_docs = (
            db.collection("mock_exams")
            .where("user_id", "==", user_id)
            .get()
        )

        completed = [
            e.to_dict()
            for e in e_docs
            if e.to_dict().get(
                "completed_at"
            )
        ]

        completed.sort(
            key=lambda x: x.get(
                "completed_at",
                ""
            ),
            reverse=True
        )

        d_docs = (
            db.collection("decks")
            .get()
        )

        deck_map = {
            d.to_dict()["id"]:
                d.to_dict()
            for d in d_docs
        }

        items = []

        for e in completed:

            d = deck_map.get(
                e.get("deck_id"),
                {}
            )

            item = dict(e)

            item["deck_name"] = d.get(
                "name",
                ""
            )

            item["subject"] = d.get(
                "subject",
                ""
            )

            items.append(item)

        if "LIMIT 5" in q:
            items = items[:5]

        results = items

    elif (
        "c.correct_count > c.review_count" in q
        and "c.attempts > 0" in q
        and "COUNT(*) AS cnt" in q
    ):

        user_id = args[0]

        d_docs = (
            db.collection("decks")
            .where("user_id", "==", user_id)
            .get()
        )

        user_deck_ids = {
            d.to_dict()["id"]
            for d in d_docs
        }

        all_cards_docs = (
            db.collection("cards")
            .get()
        )

        count = 0

        for cd in all_cards_docs:

            c = cd.to_dict()

            if (
                c.get("deck_id")
                in user_deck_ids
                and c.get("attempts", 0) > 0
            ):

                if (
                    c.get("correct_count", 0)
                    > c.get("review_count", 0)
                ):
                    count += 1

        results = [
            {"cnt": count}
        ]

    elif (
        "SUM(c.attempts)" in q
        and "FROM cards c" in q
    ):

        user_id = args[0]

        d_docs = (
            db.collection("decks")
            .where("user_id", "==", user_id)
            .get()
        )

        user_deck_ids = {
            d.to_dict()["id"]
            for d in d_docs
        }

        all_cards_docs = (
            db.collection("cards")
            .get()
        )

        user_cards = [
            cd.to_dict()
            for cd in all_cards_docs
            if cd.to_dict().get(
                "deck_id"
            ) in user_deck_ids
        ]

        total_attempts = sum(
            c.get("attempts", 0)
            for c in user_cards
        )

        total_correct = sum(
            c.get("correct_count", 0)
            for c in user_cards
        )

        total_reviews = sum(
            c.get("review_count", 0)
            for c in user_cards
        )

        mastered = sum(
            1
            for c in user_cards
            if (
                c.get("attempts", 0) > 0
                and c.get("correct_count", 0)
                > c.get("review_count", 0)
            )
        )

        results = [{
            "total_attempts": total_attempts,
            "total_correct": total_correct,
            "total_reviews": total_reviews,
            "mastered": mastered
        }]

    elif (
        "FROM mock_exams me" in q
        and "GROUP BY d.id" in q
        and "avg_score DESC" in q
    ):

        user_id = args[0]

        e_docs = (
            db.collection("mock_exams")
            .where("user_id", "==", user_id)
            .get()
        )

        completed = [
            e.to_dict()
            for e in e_docs
            if e.to_dict().get(
                "completed_at"
            )
        ]

        d_docs = (
            db.collection("decks")
            .get()
        )

        deck_map = {
            d.to_dict()["id"]:
                d.to_dict()
            for d in d_docs
        }

        subj_stats = {}

        for e in completed:

            did = e.get("deck_id")

            d = deck_map.get(
                did,
                {}
            )

            if did not in subj_stats:

                subj_stats[did] = {
                    "subject": d.get(
                        "subject",
                        ""
                    ),
                    "deck_name": d.get(
                        "name",
                        ""
                    ),
                    "scores": []
                }

            subj_stats[did]["scores"].append(
                e.get("score", 0)
            )

        perf_list = []

        for did, data in subj_stats.items():

            scores = data["scores"]

            perf_list.append({
                "subject": data["subject"],
                "deck_name": data["deck_name"],
                "exam_count": len(scores),
                "avg_score":
                    sum(scores) / len(scores)
                    if scores
                    else 0,
                "best_score":
                    max(scores)
                    if scores
                    else 0
            })

        perf_list.sort(
            key=lambda x: x["avg_score"],
            reverse=True
        )

        results = perf_list

    elif (
        "FROM decks d" in q
        and "HAVING attempts > 0" in q
    ):

        user_id = args[0]

        d_docs = (
            db.collection("decks")
            .where("user_id", "==", user_id)
            .get()
        )

        user_decks = [
            d.to_dict()
            for d in d_docs
        ]

        all_cards_docs = (
            db.collection("cards")
            .get()
        )

        all_cards = [
            cd.to_dict()
            for cd in all_cards_docs
        ]

        deck_acc = []

        for d in user_decks:

            did = d["id"]

            deck_cards = [
                c
                for c in all_cards
                if c.get("deck_id") == did
            ]

            attempts = sum(
                c.get("attempts", 0)
                for c in deck_cards
            )

            if attempts > 0:

                correct = sum(
                    c.get("correct_count", 0)
                    for c in deck_cards
                )

                reviews = sum(
                    c.get("review_count", 0)
                    for c in deck_cards
                )

                deck_acc.append({
                    "name": d["name"],
                    "subject": d.get(
                        "subject",
                        ""
                    ),
                    "attempts": attempts,
                    "correct": correct,
                    "reviews": reviews,
                    "total_cards":
                        len(deck_cards)
                })

        deck_acc.sort(
            key=lambda x:
                (
                    x["correct"] * 1.0
                    / x["attempts"]
                )
        )

        results = deck_acc

    elif (
        "c.review_count * 1.0 / c.attempts" in q
    ):

        user_id = args[0]

        d_docs = (
            db.collection("decks")
            .where("user_id", "==", user_id)
            .get()
        )

        user_decks = {
            d.to_dict()["id"]:
                d.to_dict()
            for d in d_docs
        }

        all_cards_docs = (
            db.collection("cards")
            .get()
        )

        all_cards = [
            cd.to_dict()
            for cd in all_cards_docs
        ]

        weak = []

        for c in all_cards:

            did = c.get("deck_id")

            if (
                did in user_decks
                and c.get("attempts", 0) > 0
            ):

                d = user_decks[did]

                ratio = (
                    c.get("review_count", 0)
                    * 1.0
                    / c.get("attempts", 1)
                )

                weak.append({
                    "question":
                        c.get(
                            "question",
                            ""
                        ),
                    "answer":
                        c.get(
                            "answer",
                            ""
                        ),
                    "attempts":
                        c.get(
                            "attempts",
                            0
                        ),
                    "correct_count":
                        c.get(
                            "correct_count",
                            0
                        ),
                    "review_count":
                        c.get(
                            "review_count",
                            0
                        ),
                    "deck_name":
                        d.get(
                            "name",
                            ""
                        ),
                    "subject":
                        d.get(
                            "subject",
                            ""
                        ),
                    "deck_id": did,
                    "_ratio": ratio
                })

        weak.sort(
            key=lambda x:
                x["_ratio"],
            reverse=True
        )

        results = weak[:10]

    elif "HAVING avg_score < 75" in q:

        user_id = args[0]

        e_docs = (
            db.collection("mock_exams")
            .where("user_id", "==", user_id)
            .get()
        )

        completed = [
            e.to_dict()
            for e in e_docs
            if e.to_dict().get(
                "completed_at"
            )
        ]

        d_docs = (
            db.collection("decks")
            .get()
        )

        deck_map = {
            d.to_dict()["id"]:
                d.to_dict()
            for d in d_docs
        }

        subj_stats = {}

        for e in completed:

            did = e.get("deck_id")

            d = deck_map.get(
                did,
                {}
            )

            if did not in subj_stats:

                subj_stats[did] = {
                    "subject":
                        d.get(
                            "subject",
                            ""
                        ),
                    "deck_name":
                        d.get(
                            "name",
                            ""
                        ),
                    "deck_id": did,
                    "scores": []
                }

            subj_stats[did]["scores"].append(
                e.get("score", 0)
            )

        weak_subs = []

        for did, data in subj_stats.items():

            scores = data["scores"]

            avg = (
                sum(scores) / len(scores)
                if scores
                else 0
            )

            if avg < 75:

                weak_subs.append({
                    "subject":
                        data["subject"],
                    "deck_name":
                        data["deck_name"],
                    "deck_id":
                        data["deck_id"],
                    "avg_score": avg,
                    "exams": len(scores)
                })

        weak_subs.sort(
            key=lambda x:
                x["avg_score"]
        )

        results = weak_subs[:5]

    if one:
        return (
            results[0]
            if results
            else None
        )

    return results