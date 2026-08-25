"""
Database layer — SQLite schema, connection management, and query utilities.

All queries use parameterized statements (? placeholders) to prevent
SQL injection. Foreign keys are enforced on every connection.

STUDYFLIP — includes users, decks, cards, mock_exams, exam_questions tables.
Safe migration: adds new columns/tables without deleting existing data.
"""

import os
import sqlite3
from config import Config


# ═══════════════════════════════════════════════════════════════
#  SCHEMA — CREATE IF NOT EXISTS (safe to run multiple times)
# ═══════════════════════════════════════════════════════════════

SCHEMA = """
-- ── Users ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    email         TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    created_at    TEXT    DEFAULT (datetime('now'))
);

-- ── Decks ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS decks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    description TEXT    DEFAULT '',
    created_at  TEXT    DEFAULT (datetime('now'))
);

-- ── Cards ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cards (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    deck_id       INTEGER NOT NULL,
    question      TEXT    NOT NULL,
    answer        TEXT    NOT NULL,
    attempts      INTEGER DEFAULT 0,
    correct_count INTEGER DEFAULT 0,
    review_count  INTEGER DEFAULT 0,
    created_at    TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (deck_id) REFERENCES decks(id) ON DELETE CASCADE
);

-- ── Study Sessions ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS study_sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    deck_id         INTEGER NOT NULL,
    started_at      TEXT    DEFAULT (datetime('now')),
    completed_at    TEXT,
    cards_studied   INTEGER DEFAULT 0,
    correct_answers INTEGER DEFAULT 0,
    FOREIGN KEY (deck_id) REFERENCES decks(id) ON DELETE CASCADE
);

-- ── Mock Exams ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS mock_exams (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL DEFAULT 1,
    deck_id           INTEGER NOT NULL,
    score             REAL    DEFAULT 0,
    total_questions   INTEGER DEFAULT 0,
    correct_answers   INTEGER DEFAULT 0,
    incorrect_answers INTEGER DEFAULT 0,
    started_at        TEXT    DEFAULT (datetime('now')),
    completed_at      TEXT    DEFAULT NULL,
    time_taken        INTEGER DEFAULT 0,
    FOREIGN KEY (deck_id) REFERENCES decks(id) ON DELETE CASCADE
);

-- ── Exam Questions ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS exam_questions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id        INTEGER NOT NULL,
    card_id        INTEGER NOT NULL,
    question_text  TEXT    NOT NULL,
    option_a       TEXT    NOT NULL,
    option_b       TEXT    NOT NULL,
    option_c       TEXT    NOT NULL,
    option_d       TEXT    NOT NULL,
    correct_option TEXT    NOT NULL,
    question_order INTEGER DEFAULT 0,
    user_answer    TEXT    DEFAULT NULL,
    correct        INTEGER DEFAULT 0,
    self_mastered  INTEGER DEFAULT 0,
    FOREIGN KEY (exam_id) REFERENCES mock_exams(id) ON DELETE CASCADE
);

-- ── Indexes ─────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_cards_deck_id
    ON cards(deck_id);

CREATE INDEX IF NOT EXISTS idx_decks_user_id_NEW
    ON decks(user_id);

CREATE INDEX IF NOT EXISTS idx_mock_exams_user_id
    ON mock_exams(user_id);

CREATE INDEX IF NOT EXISTS idx_exam_questions_exam_id
    ON exam_questions(exam_id);

CREATE INDEX IF NOT EXISTS idx_study_sessions_deck_id
    ON study_sessions(deck_id);

CREATE INDEX IF NOT EXISTS idx_cards_review_count
    ON cards(deck_id, review_count DESC);
"""


# ═══════════════════════════════════════════════════════════════
#  CONNECTION
# ═══════════════════════════════════════════════════════════════

def get_db():
    """
    Return a new SQLite connection.

    Every connection:
    - Enables foreign key enforcement (PRAGMA foreign_keys = ON).
    - Uses sqlite3.Row as row_factory so results behave like dicts.
    """
    db_path = Config.DATABASE_PATH
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ═══════════════════════════════════════════════════════════════
#  INITIALIZATION + SAFE MIGRATION
# ═══════════════════════════════════════════════════════════════

def _column_exists(conn, table, column):
    """Check if a column exists in a table."""
    cur = conn.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cur.fetchall()]
    return column in cols


def _table_exists(conn, table):
    """Check if a table exists."""
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return cur.fetchone() is not None


def migrate_db(conn):
    """
    Safely add new columns/tables to an existing database.
    Uses ALTER TABLE only when the column does not already exist.
    Never drops or modifies existing data.
    """
    # Add user_id to decks (existing rows get user_id=1)
    if _table_exists(conn, 'decks') and not _column_exists(conn, 'decks', 'user_id'):
        conn.execute("ALTER TABLE decks ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1")

    # Add subject to decks
    if _table_exists(conn, 'decks') and not _column_exists(conn, 'decks', 'subject'):
        conn.execute("ALTER TABLE decks ADD COLUMN subject TEXT DEFAULT ''")

    # Add MCQ option columns to cards
    if _table_exists(conn, 'cards'):
        for col in ['option_a', 'option_b', 'option_c', 'option_d', 'correct_option']:
            if not _column_exists(conn, 'cards', col):
                conn.execute(f"ALTER TABLE cards ADD COLUMN {col} TEXT DEFAULT NULL")

    # Add self_mastered to exam_questions (safe migration)
    if _table_exists(conn, 'exam_questions') and not _column_exists(conn, 'exam_questions', 'self_mastered'):
        conn.execute("ALTER TABLE exam_questions ADD COLUMN self_mastered INTEGER DEFAULT 0")

    conn.commit()


def init_db():
    """
    Run migration first (adds missing columns to existing tables),
    then run schema DDL to create new tables and indexes.
    Safe to call multiple times.
    """
    conn = get_db()
    try:
        # Step 1: Migrate existing tables (add columns if missing)
        migrate_db(conn)
        # Step 2: Create new tables and indexes that don't exist yet
        conn.executescript(SCHEMA)
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
#  QUERY HELPERS
# ═══════════════════════════════════════════════════════════════

def query_db(query, args=(), one=False):
    """
    Execute a SELECT and return results as a list of dicts.

    Args:
        query (str): SQL SELECT with ? placeholders.
        args (tuple): Parameter values.
        one (bool):   If True, return a single dict (or None).

    Returns:
        list[dict] | dict | None
    """
    conn = get_db()
    try:
        cur = conn.execute(query, args)
        rows = [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

    if one:
        return rows[0] if rows else None
    return rows


def execute_db(query, args=()):
    """
    Execute an INSERT, UPDATE, or DELETE and return lastrowid.

    Args:
        query (str): SQL statement with ? placeholders.
        args (tuple): Parameter values.

    Returns:
        int: The rowid of the last inserted row.
    """
    conn = get_db()
    try:
        cur = conn.execute(query, args)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
#  ADAPTIVE REVIEW PRIORITIZATION
# ═══════════════════════════════════════════════════════════════

def calculate_priority(attempts, correct_count, review_count):
    """
    Calculate a review priority score for a single card.

    Returns a float between 0.0 and 1.0:
        1.0 = highest priority (needs the most review)
        0.0 = lowest priority  (well mastered)

    Formula: (review_count + 1) / (attempts + 2)  [Laplace smoothed]
    """
    priority = (review_count + 1) / (attempts + 2)
    return round(priority, 4)


def record_response(card_id, knew_it):
    """
    Record a student's response to a card and update tracking fields.

    Args:
        card_id (int):  The card that was studied.
        knew_it (bool): True if "Know It", False if "Review Again".

    Returns:
        dict: The updated card row.
    """
    if knew_it:
        execute_db(
            "UPDATE cards SET attempts = attempts + 1, "
            "correct_count = correct_count + 1 WHERE id = ?",
            (card_id,)
        )
    else:
        execute_db(
            "UPDATE cards SET attempts = attempts + 1, "
            "review_count = review_count + 1 WHERE id = ?",
            (card_id,)
        )

    return query_db("SELECT * FROM cards WHERE id = ?", (card_id,), one=True)


def get_study_cards(deck_id, user_id=None):
    """
    Return all cards in a deck, sorted by review priority (highest first).
    Optionally filters by user_id via deck ownership.
    """
    if user_id is not None:
        # Verify deck belongs to user
        deck = query_db(
            "SELECT * FROM decks WHERE id = ? AND user_id = ?", (deck_id, user_id), one=True
        )
        if not deck:
            return []

    cards = query_db(
        "SELECT * FROM cards WHERE deck_id = ? ORDER BY id",
        (deck_id,)
    )

    for card in cards:
        card["priority"] = calculate_priority(
            card["attempts"],
            card["correct_count"],
            card["review_count"]
        )

    cards.sort(key=lambda c: c["priority"], reverse=True)
    return cards


def get_smart_review_cards(user_id, limit=25):
    """
    Return cards needing attention across ALL of a user's decks,
    sorted by Adaptive Review Prioritization (highest first).
    """
    cards = query_db("""
        SELECT c.*, d.name AS deck_name
        FROM cards c
        JOIN decks d ON d.id = c.deck_id
        WHERE d.user_id = ?
    """, (user_id,))

    for card in cards:
        card["priority"] = calculate_priority(
            card["attempts"],
            card["correct_count"],
            card["review_count"]
        )

    needing_attention = [c for c in cards if c["attempts"] == 0 or c["review_count"] > c["correct_count"]]
    target_cards = needing_attention if needing_attention else cards

    target_cards.sort(key=lambda c: c["priority"], reverse=True)
    return target_cards[:limit]


# ═══════════════════════════════════════════════════════════════
#  MOCK EXAM — MCQ GENERATION
# ═══════════════════════════════════════════════════════════════

import random


def generate_mcq_options(card, all_deck_cards):
    """
    Generate 4 MCQ options for a card deterministically.

    Strategy:
    1. If card has option_a/b/c/d set, use those directly.
    2. Otherwise, use card.answer as correct, and pick 3 wrong answers
       from other cards' answers in the same deck.

    Returns:
        dict with keys: option_a, option_b, option_c, option_d, correct_option
    """
    # Use hand-crafted options if available
    if card.get("option_a") and card.get("option_b") and card.get("option_c") and card.get("option_d"):
        return {
            "option_a": card["option_a"],
            "option_b": card["option_b"],
            "option_c": card["option_c"],
            "option_d": card["option_d"],
            "correct_option": card.get("correct_option", "a")
        }

    # Auto-generate from other cards' answers
    other_answers = [
        c["answer"] for c in all_deck_cards
        if c["id"] != card["id"] and c["answer"] != card["answer"]
    ]

    # Deduplicate
    other_answers = list(dict.fromkeys(other_answers))

    # Seed random with card ID for determinism
    rng = random.Random(card["id"])
    rng.shuffle(other_answers)

    wrong_answers = other_answers[:3]

    # Pad if not enough wrong answers
    while len(wrong_answers) < 3:
        wrong_answers.append(f"None of the above (option {len(wrong_answers) + 1})")

    # Place correct answer at a deterministic position (based on card id)
    options = wrong_answers[:]
    correct_pos = card["id"] % 4  # 0=a, 1=b, 2=c, 3=d
    options.insert(correct_pos, card["answer"])
    options = options[:4]

    option_labels = ["a", "b", "c", "d"]
    correct_label = option_labels[correct_pos]

    return {
        "option_a": options[0],
        "option_b": options[1],
        "option_c": options[2],
        "option_d": options[3],
        "correct_option": correct_label
    }


def create_mock_exam(user_id, deck_id, num_questions=20):
    """
    Create a new mock exam with auto-generated MCQ questions.

    Returns:
        dict: The created exam with its questions.
    """
    # Get deck and verify ownership
    deck = query_db("SELECT * FROM decks WHERE id = ? AND user_id = ?", (deck_id, user_id), one=True)
    if not deck:
        return None

    # Get all cards in deck
    all_cards = query_db("SELECT * FROM cards WHERE deck_id = ?", (deck_id,))
    if not all_cards:
        return None

    # Limit to available cards
    num_questions = min(num_questions, len(all_cards))

    # Prioritize cards by review need (high priority first)
    for card in all_cards:
        card["priority"] = calculate_priority(card["attempts"], card["correct_count"], card["review_count"])

    sorted_cards = sorted(all_cards, key=lambda c: c["priority"], reverse=True)
    selected_cards = sorted_cards[:num_questions]

    # Create exam record
    exam_id = execute_db(
        "INSERT INTO mock_exams (user_id, deck_id, total_questions) VALUES (?, ?, ?)",
        (user_id, deck_id, num_questions)
    )

    # Create question records
    for i, card in enumerate(selected_cards):
        mcq = generate_mcq_options(card, all_cards)
        execute_db("""
            INSERT INTO exam_questions
                (exam_id, card_id, question_text, option_a, option_b, option_c, option_d,
                 correct_option, question_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            exam_id, card["id"], card["question"],
            mcq["option_a"], mcq["option_b"], mcq["option_c"], mcq["option_d"],
            mcq["correct_option"], i + 1
        ))

    exam = query_db("SELECT * FROM mock_exams WHERE id = ?", (exam_id,), one=True)
    questions = query_db(
        "SELECT * FROM exam_questions WHERE exam_id = ? ORDER BY question_order",
        (exam_id,)
    )
    return {"exam": exam, "questions": questions, "deck": deck}


def submit_mock_exam(exam_id, user_id, answers, time_taken):
    """
    Submit answers for an exam and calculate score.

    IMPORTANT: Questions marked self_mastered ("I Know This") are NOT counted
    as attempted, correct, or incorrect. Exam score = correct / attempted.

    Args:
        exam_id (int): The exam being submitted.
        user_id (int): Must match exam owner.
        answers (dict): {question_id: selected_option} e.g. {"3": "b"}
        time_taken (int): Seconds taken.

    Returns:
        dict: Result summary.
    """
    exam = query_db(
        "SELECT * FROM mock_exams WHERE id = ? AND user_id = ?",
        (exam_id, user_id), one=True
    )
    if not exam:
        return None

    # Already submitted?
    if exam["completed_at"]:
        return None

    questions = query_db(
        "SELECT * FROM exam_questions WHERE exam_id = ? ORDER BY question_order",
        (exam_id,)
    )

    correct = 0
    incorrect = 0
    known_count = 0
    unattempted = 0

    for q in questions:
        # Skip self-mastered questions — they are NOT exam attempts
        if q.get("self_mastered", 0):
            known_count += 1
            continue

        user_answer = answers.get(str(q["id"]), "")
        if not user_answer:
            # Unattempted (no answer selected, not self-mastered)
            unattempted += 1
            execute_db(
                "UPDATE exam_questions SET user_answer = NULL, correct = 0 WHERE id = ?",
                (q["id"],)
            )
        else:
            is_correct = 1 if user_answer.lower() == q["correct_option"].lower() else 0
            if is_correct:
                correct += 1
            else:
                incorrect += 1
                # Increase card review priority for wrong answers
                execute_db(
                    "UPDATE cards SET attempts = attempts + 1, review_count = review_count + 1 WHERE id = ?",
                    (q["card_id"],)
                )
            execute_db(
                "UPDATE exam_questions SET user_answer = ?, correct = ? WHERE id = ?",
                (user_answer, is_correct, q["id"])
            )

    total_questions = len(questions)
    attempted = correct + incorrect
    # Score is based on attempted questions only (not self-mastered or unattempted)
    score = round((correct / attempted) * 100, 1) if attempted > 0 else 0

    execute_db("""
        UPDATE mock_exams
        SET score = ?, correct_answers = ?, incorrect_answers = ?,
            completed_at = datetime('now'), time_taken = ?
        WHERE id = ?
    """, (score, correct, incorrect, time_taken, exam_id))

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
