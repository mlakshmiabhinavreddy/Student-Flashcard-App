"""
Adaptive Review Prioritization — verification script.

Tests:
  1. Formula correctness with known inputs
  2. Boundary conditions
  3. record_response() updates tracking fields
  4. get_study_cards() returns correct priority order
  5. Self-correction (mastered card → struggles again)

Run:
    venv/Scripts/python test_priority.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database import (
    init_db, query_db, execute_db,
    calculate_priority, record_response, get_study_cards
)

PASS = 0
FAIL = 0


def check(label, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
    else:
        FAIL += 1
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}")


def main():
    global PASS, FAIL
    init_db()

    # ═════════════════════════════════════════════════════════
    #  1. Formula correctness
    # ═════════════════════════════════════════════════════════
    print("\n1. calculate_priority() — formula verification")
    print("   Formula: priority = (review_count + 1) / (attempts + 2)")

    # New card: (attempts=0, correct=0, review=0)
    p = calculate_priority(0, 0, 0)
    check(f"New card (0,0,0) -> {p} == 0.5", p == 0.5)

    # All wrong: (attempts=5, correct=0, review=5)
    p = calculate_priority(5, 0, 5)
    expected = round(6 / 7, 4)
    check(f"All wrong (5,0,5) -> {p} == {expected}", p == expected)

    # All right: (attempts=5, correct=5, review=0)
    p = calculate_priority(5, 5, 0)
    expected = round(1 / 7, 4)
    check(f"All right (5,5,0) -> {p} == {expected}", p == expected)

    # Mixed: (attempts=4, correct=2, review=2)
    p = calculate_priority(4, 2, 2)
    check(f"Mixed (4,2,2) -> {p} == 0.5", p == 0.5)

    # Mostly OK: (attempts=10, correct=8, review=2)
    p = calculate_priority(10, 8, 2)
    check(f"Mostly OK (10,8,2) -> {p} == 0.25", p == 0.25)

    # Struggling: (attempts=10, correct=2, review=8)
    p = calculate_priority(10, 2, 8)
    check(f"Struggling (10,2,8) -> {p} == 0.75", p == 0.75)

    # ═════════════════════════════════════════════════════════
    #  2. Properties
    # ═════════════════════════════════════════════════════════
    print("\n2. Algorithm properties")

    # Always bounded [0, 1]
    check("Bounded: (0,0,0) in [0,1]",  0.0 <= calculate_priority(0, 0, 0) <= 1.0)
    check("Bounded: (100,0,100) in [0,1]", 0.0 <= calculate_priority(100, 0, 100) <= 1.0)
    check("Bounded: (100,100,0) in [0,1]", 0.0 <= calculate_priority(100, 100, 0) <= 1.0)

    # Monotonic: more review_count -> higher priority
    p_low  = calculate_priority(10, 8, 2)
    p_high = calculate_priority(10, 2, 8)
    check(f"More review -> higher priority ({p_high} > {p_low})", p_high > p_low)

    # Deterministic: same inputs -> same output
    a = calculate_priority(7, 3, 4)
    b = calculate_priority(7, 3, 4)
    check(f"Deterministic: same inputs -> same output ({a} == {b})", a == b)

    # Never quite 0 or 1 (Laplace smoothing prevents extremes)
    check("Never exactly 0", calculate_priority(1000, 1000, 0) > 0.0)
    check("Never exactly 1", calculate_priority(1000, 0, 1000) < 1.0)

    # ═════════════════════════════════════════════════════════
    #  3. record_response() — tracking fields
    # ═════════════════════════════════════════════════════════
    print("\n3. record_response() — updates tracking fields")

    # Create a test deck and card
    deck_id = execute_db(
        "INSERT INTO decks (name) VALUES (?)", ("Priority Test Deck",)
    )
    card_id = execute_db(
        "INSERT INTO cards (deck_id, question, answer) VALUES (?, ?, ?)",
        (deck_id, "Test Q", "Test A")
    )

    # Verify initial state
    card = query_db("SELECT * FROM cards WHERE id = ?", (card_id,), one=True)
    check("Initial attempts=0", card["attempts"] == 0)
    check("Initial correct_count=0", card["correct_count"] == 0)
    check("Initial review_count=0", card["review_count"] == 0)

    # Record "Know It"
    card = record_response(card_id, knew_it=True)
    check("After Know It: attempts=1", card["attempts"] == 1)
    check("After Know It: correct_count=1", card["correct_count"] == 1)
    check("After Know It: review_count=0", card["review_count"] == 0)

    # Record "Review Again"
    card = record_response(card_id, knew_it=False)
    check("After Review Again: attempts=2", card["attempts"] == 2)
    check("After Review Again: correct_count=1", card["correct_count"] == 1)
    check("After Review Again: review_count=1", card["review_count"] == 1)

    # Record another "Review Again"
    card = record_response(card_id, knew_it=False)
    check("After 2nd Review: attempts=3", card["attempts"] == 3)
    check("After 2nd Review: review_count=2", card["review_count"] == 2)

    # ═════════════════════════════════════════════════════════
    #  4. get_study_cards() — priority ordering
    # ═════════════════════════════════════════════════════════
    print("\n4. get_study_cards() — priority-sorted order")

    # Create cards with different histories
    easy_id = execute_db(
        "INSERT INTO cards (deck_id, question, answer, attempts, correct_count, review_count) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (deck_id, "Easy Q", "Easy A", 10, 9, 1)
    )
    hard_id = execute_db(
        "INSERT INTO cards (deck_id, question, answer, attempts, correct_count, review_count) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (deck_id, "Hard Q", "Hard A", 10, 2, 8)
    )
    new_id = execute_db(
        "INSERT INTO cards (deck_id, question, answer) VALUES (?, ?, ?)",
        (deck_id, "New Q", "New A")
    )

    cards = get_study_cards(deck_id)

    check(f"Returns all 4 cards", len(cards) == 4)
    check("Each card has 'priority' field", all("priority" in c for c in cards))

    # Verify order: hard card first, easy card last
    check(f"Hard card first (priority={cards[0]['priority']})", cards[0]["id"] == hard_id)
    check(f"Easy card last  (priority={cards[-1]['priority']})", cards[-1]["id"] == easy_id)

    # Print the full priority table
    print("\n   Priority table:")
    print(f"   {'Card':<20} {'Attempts':>8} {'Correct':>8} {'Review':>8} {'Priority':>9}")
    print(f"   {'-'*20} {'-'*8} {'-'*8} {'-'*8} {'-'*9}")
    for c in cards:
        print(f"   {c['question']:<20} {c['attempts']:>8} {c['correct_count']:>8} "
              f"{c['review_count']:>8} {c['priority']:>9.4f}")

    # ═════════════════════════════════════════════════════════
    #  5. Self-correction
    # ═════════════════════════════════════════════════════════
    print("\n5. Self-correction — mastered card struggles again")

    priority_before = calculate_priority(10, 9, 1)  # Easy card

    # Simulate the easy card getting 3 "Review Again" in a row
    for _ in range(3):
        record_response(easy_id, knew_it=False)

    easy_card = query_db("SELECT * FROM cards WHERE id = ?", (easy_id,), one=True)
    priority_after = calculate_priority(
        easy_card["attempts"], easy_card["correct_count"], easy_card["review_count"]
    )

    check(f"Priority rose: {priority_before} -> {priority_after}", priority_after > priority_before)

    # ── Cleanup ──────────────────────────────────────────────
    execute_db("DELETE FROM decks WHERE id = ?", (deck_id,))

    # ── Summary ──────────────────────────────────────────────
    print(f"\n{'='*50}")
    print(f"  Results:  {PASS} passed,  {FAIL} failed")
    print(f"{'='*50}\n")

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
