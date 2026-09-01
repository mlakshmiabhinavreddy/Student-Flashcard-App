"""
Database verification script.
Run: venv/Scripts/python test_database.py

Tests:
  1. Schema creation (tables + indexes)
  2. Insert into all three tables
  3. Foreign key enforcement
  4. Cascade delete
  5. Parameterized queries via query_db / execute_db
"""

import sys
import os

# Ensure imports work from project root
sys.path.insert(0, os.path.dirname(__file__))

from database import init_db, get_db, query_db, execute_db

PASS = 0
FAIL = 0


def check(label, condition):
    global PASS, FAIL
    status = "PASS" if condition else "FAIL"
    if condition:
        PASS += 1
    else:
        FAIL += 1
    print(f"  [{status}] {label}")


def main():
    global PASS, FAIL

    # ── 1. Initialize database ───────────────────────────────
    print("\n1. Schema creation")
    init_db()

    conn = get_db()

    # Verify tables exist
    tables = [r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()]
    check("decks table exists", "decks" in tables)
    check("cards table exists", "cards" in tables)
    check("study_sessions table exists", "study_sessions" in tables)

    # Verify indexes exist
    indexes = [r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
    ).fetchall()]
    check("idx_cards_deck_id exists", "idx_cards_deck_id" in indexes)
    check("idx_study_sessions_deck_id exists", "idx_study_sessions_deck_id" in indexes)
    check("idx_cards_review_count exists", "idx_cards_review_count" in indexes)

    # Verify column names
         # Verify column names
    deck_cols = [r[1] for r in conn.execute("PRAGMA table_info(decks)").fetchall()]
    print("ACTUAL DECK COLUMNS:", deck_cols)
    expected_deck_cols = [
    "id",
    "name",
    "description",
    "created_at",
    "user_id",
    "subject"
]

    check("decks columns correct", deck_cols == expected_deck_cols)

    card_cols = [r[1] for r in conn.execute("PRAGMA table_info(cards)").fetchall()]
    print("ACTUAL CARD COLUMNS:", card_cols)

    expected_card_cols = [
    "id",
    "deck_id",
    "question",
    "answer",
    "attempts",
    "correct_count",
    "review_count",
    "created_at",
    "option_a",
    "option_b",
    "option_c",
    "option_d",
    "correct_option"
]

    check("cards columns correct", card_cols == expected_card_cols)

    session_cols = [r[1] for r in conn.execute("PRAGMA table_info(study_sessions)").fetchall()]
    # Verify foreign keys are ON
    fk_status = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    check("foreign_keys pragma is ON", fk_status == 1)

    conn.close()

    # ── 2. Insert test data ──────────────────────────────────
    print("\n2. Insert test data (parameterized queries)")

    deck_id = execute_db(
        "INSERT INTO decks (name, description) VALUES (?, ?)",
        ("Biology 101", "Cell biology fundamentals")
    )
    check(f"deck inserted (id={deck_id})", deck_id is not None and deck_id > 0)

    card1_id = execute_db(
        "INSERT INTO cards (deck_id, question, answer) VALUES (?, ?, ?)",
        (deck_id, "What is the powerhouse of the cell?", "Mitochondria")
    )
    card2_id = execute_db(
        "INSERT INTO cards (deck_id, question, answer) VALUES (?, ?, ?)",
        (deck_id, "What is DNA?", "Deoxyribonucleic acid")
    )
    check(f"card 1 inserted (id={card1_id})", card1_id is not None)
    check(f"card 2 inserted (id={card2_id})", card2_id is not None)

    session_id = execute_db(
        "INSERT INTO study_sessions (deck_id, cards_studied, correct_answers) VALUES (?, ?, ?)",
        (deck_id, 2, 1)
    )
    check(f"study_session inserted (id={session_id})", session_id is not None)

    # ── 3. Query data back ───────────────────────────────────
    print("\n3. Query data (query_db helper)")

    deck = query_db("SELECT * FROM decks WHERE id = ?", (deck_id,), one=True)
    check("deck query returns dict", isinstance(deck, dict))
    check("deck name correct", deck["name"] == "Biology 101")
    check("deck created_at auto-set", deck["created_at"] is not None)

    cards = query_db("SELECT * FROM cards WHERE deck_id = ?", (deck_id,))
    check(f"cards query returns {len(cards)} cards", len(cards) == 2)
    check("card defaults: attempts=0", cards[0]["attempts"] == 0)
    check("card defaults: correct_count=0", cards[0]["correct_count"] == 0)
    check("card defaults: review_count=0", cards[0]["review_count"] == 0)

    session = query_db("SELECT * FROM study_sessions WHERE id = ?", (session_id,), one=True)
    check("session cards_studied=2", session["cards_studied"] == 2)
    check("session correct_answers=1", session["correct_answers"] == 1)
    check("session completed_at is NULL", session["completed_at"] is None)

    # ── 4. Update tracking fields ────────────────────────────
    print("\n4. Update tracking fields")

    execute_db(
        "UPDATE cards SET attempts = attempts + 1, correct_count = correct_count + 1 WHERE id = ?",
        (card1_id,)
    )
    updated_card = query_db("SELECT * FROM cards WHERE id = ?", (card1_id,), one=True)
    check("attempts incremented to 1", updated_card["attempts"] == 1)
    check("correct_count incremented to 1", updated_card["correct_count"] == 1)

    # ── 5. Foreign key enforcement ───────────────────────────
    print("\n5. Foreign key enforcement")

    try:
        execute_db(
            "INSERT INTO cards (deck_id, question, answer) VALUES (?, ?, ?)",
            (9999, "Orphan question", "No deck")
        )
        check("FK violation blocked", False)  # Should not reach here
    except Exception as e:
        check(f"FK violation blocked ({type(e).__name__})", "FOREIGN KEY" in str(e).upper())

    # ── 6. Cascade delete ────────────────────────────────────
    print("\n6. Cascade delete")

    cards_before = query_db("SELECT COUNT(*) as cnt FROM cards WHERE deck_id = ?", (deck_id,), one=True)
    sessions_before = query_db("SELECT COUNT(*) as cnt FROM study_sessions WHERE deck_id = ?", (deck_id,), one=True)
    check(f"cards exist before delete ({cards_before['cnt']})", cards_before["cnt"] > 0)
    check(f"sessions exist before delete ({sessions_before['cnt']})", sessions_before["cnt"] > 0)

    execute_db("DELETE FROM decks WHERE id = ?", (deck_id,))

    cards_after = query_db("SELECT COUNT(*) as cnt FROM cards WHERE deck_id = ?", (deck_id,), one=True)
    sessions_after = query_db("SELECT COUNT(*) as cnt FROM study_sessions WHERE deck_id = ?", (deck_id,), one=True)
    check("cards cascade-deleted", cards_after["cnt"] == 0)
    check("sessions cascade-deleted", sessions_after["cnt"] == 0)

    # ── Summary ──────────────────────────────────────────────
    print(f"\n{'='*50}")
    print(f"  Results:  {PASS} passed,  {FAIL} failed")
    print(f"{'='*50}\n")

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
