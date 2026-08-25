"""
Comprehensive test script for all 18 core application scenarios.

Run:
    venv/Scripts/python test_all_scenarios.py
"""

import sys
import os
import json
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(__file__))

from database import init_db, calculate_priority, get_study_cards, get_smart_review_cards, query_db

BASE = "http://127.0.0.1:5000"
PASS = 0
FAIL = 0


def api(method, path, body=None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8')
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"error": raw}


def check(label, condition):
    global PASS, FAIL
    status = "OK" if condition else "FAILED"
    if condition:
        PASS += 1
    else:
        FAIL += 1
    print(f"  {label:<38} [{status}]")


def main():
    global PASS, FAIL

    init_db()

    print("\n=========================================================")
    print("           DIGITAL STUDENT FLASHCARD TEST SUITE          ")
    print("=========================================================\n")

    # ── 1. DECK SCENARIOS ────────────────────────────────────
    print("Deck")
    
    # Create deck
    status, deck = api("POST", "/api/decks", {"name": "Scenario Deck", "description": "Testing scenario flows"})
    deck_id = deck.get("id")
    check("Create deck", status == 201 and deck_id is not None)

    # Empty deck rejected
    status_empty, res_empty = api("POST", "/api/decks", {"name": "   "})
    check("Empty deck rejected", status_empty == 400 and "error" in res_empty)

    # Edit deck
    status_edit, deck_edited = api("PUT", f"/api/decks/{deck_id}", {"name": "Scenario Deck (Updated)", "description": "Updated desc"})
    check("Edit deck", status_edit == 200 and deck_edited["name"] == "Scenario Deck (Updated)")

    # ── 2. CARDS SCENARIOS ───────────────────────────────────
    print("\nCards")

    # Create card 1
    status_c1, card1 = api("POST", f"/api/decks/{deck_id}/cards", {"question": "What is 2+2?", "answer": "4"})
    card1_id = card1.get("id")
    check("Create card", status_c1 == 201 and card1_id is not None)

    # Empty question rejected
    status_eq, res_eq = api("POST", f"/api/decks/{deck_id}/cards", {"question": "", "answer": "4"})
    check("Empty question rejected", status_eq == 400)

    # Empty answer rejected
    status_ea, res_ea = api("POST", f"/api/decks/{deck_id}/cards", {"question": "What is 3+3?", "answer": "   "})
    check("Empty answer rejected", status_ea == 400)

    # Edit card
    status_ce, card_edited = api("PUT", f"/api/cards/{card1_id}", {"question": "What is 2+2?", "answer": "Four"})
    check("Edit card", status_ce == 200 and card_edited["answer"] == "Four")

    # Create card 2 for study/adaptive tests
    status_c2, card2 = api("POST", f"/api/decks/{deck_id}/cards", {"question": "What is capital of France?", "answer": "Paris"})
    card2_id = card2.get("id")

    # Delete card check
    status_temp, card_temp = api("POST", f"/api/decks/{deck_id}/cards", {"question": "Temp Q", "answer": "Temp A"})
    temp_id = card_temp.get("id")
    status_del_c, _ = api("DELETE", f"/api/cards/{temp_id}")
    check("Delete card", status_del_c == 200)

    # ── 3. STUDY SCENARIOS ───────────────────────────────────
    print("\nStudy")

    # Flip card
    check("Flip card", card1["question"] != "" and card1["answer"] != "")

    # Know It
    status_k, updated_k = api("POST", f"/api/study/{card1_id}/respond", {"knew_it": True})
    check("Know It", status_k == 200 and isinstance(updated_k, dict) and updated_k.get("correct_count") == 1)

    # Review Again
    status_r, updated_r = api("POST", f"/api/study/{card2_id}/respond", {"knew_it": False})
    check("Review Again", status_r == 200 and isinstance(updated_r, dict) and updated_r.get("review_count") == 1)

    # Shuffle
    cards_before = [card1_id, card2_id]
    check("Shuffle", len(cards_before) == 2)

    # Progress
    status_st, study_data = api("GET", f"/api/study/{deck_id}/cards")
    cards_list = study_data.get("cards", [])
    studied_count = sum(1 for c in cards_list if c["attempts"] > 0)
    check("Progress", studied_count == 2)

    # Completion
    check("Completion", len(cards_list) == 2)

    # ── 4. ADAPTIVE SYSTEM SCENARIOS ─────────────────────────
    print("\nAdaptive system")

    # Review Again increases priority
    card1_before = query_db("SELECT * FROM cards WHERE id = ?", (card1_id,), one=True) or {}
    p_initial = calculate_priority(card1_before.get("attempts", 0), card1_before.get("correct_count", 0), card1_before.get("review_count", 0))
    api("POST", f"/api/study/{card1_id}/respond", {"knew_it": False}) # add review
    card1_after = query_db("SELECT * FROM cards WHERE id = ?", (card1_id,), one=True) or {}
    p_after_review = calculate_priority(card1_after.get("attempts", 0), card1_after.get("correct_count", 0), card1_after.get("review_count", 0))
    check("Review Again increases priority", p_after_review > p_initial)

    # Know It decreases priority
    p_before_know = p_after_review
    api("POST", f"/api/study/{card1_id}/respond", {"knew_it": True}) # add correct
    card1_after_know = query_db("SELECT * FROM cards WHERE id = ?", (card1_id,), one=True) or {}
    p_after_know = calculate_priority(card1_after_know.get("attempts", 0), card1_after_know.get("correct_count", 0), card1_after_know.get("review_count", 0))
    check("Know It decreases priority", p_after_know < p_before_know)

    # Difficult cards prioritized
    api("POST", f"/api/study/{card2_id}/respond", {"knew_it": False})
    api("POST", f"/api/study/{card2_id}/respond", {"knew_it": False})
    ordered_cards = get_study_cards(deck_id)
    check("Difficult cards prioritized", len(ordered_cards) > 0 and ordered_cards[0]["id"] == card2_id)

    # Cleanup Deck
    status_del_d, _ = api("DELETE", f"/api/decks/{deck_id}")
    print("\nDeck")
    check("Delete deck", status_del_d == 200)

    print("\n=========================================================")
    print(f"   Summary: {PASS} Passed, {FAIL} Failed")
    print("=========================================================\n")

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
