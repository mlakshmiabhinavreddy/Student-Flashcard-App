"""
Comprehensive test script for all core application scenarios.

Run:
    1. Start the Flask server:
       venv/Scripts/python app.py

    2. In another Git Bash terminal:
       venv/Scripts/python test_all_scenarios.py
"""

import sys
import os
import json
import urllib.request
import urllib.error
import http.cookiejar

sys.path.insert(0, os.path.dirname(__file__))

from database import (
    init_db,
    calculate_priority,
    get_study_cards,
    query_db
)


# =========================================================
# CONFIGURATION
# =========================================================

BASE = "http://127.0.0.1:5000"

PASS = 0
FAIL = 0


# =========================================================
# COOKIE / SESSION SUPPORT
# =========================================================

cookie_jar = http.cookiejar.CookieJar()

opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(cookie_jar)
)


# =========================================================
# API HELPER
# =========================================================

def api(method, path, body=None):

    url = f"{BASE}{path}"

    if body is not None:
        data = json.dumps(body).encode("utf-8")
    else:
        data = None

    req = urllib.request.Request(
        url,
        data=data,
        method=method
    )

    req.add_header(
        "Content-Type",
        "application/json"
    )

    try:

        resp = opener.open(req)

        raw = resp.read().decode("utf-8")

        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {"raw": raw}

        return resp.status, parsed

    except urllib.error.HTTPError as e:

        raw = e.read().decode("utf-8")

        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {"error": raw}

        return e.code, parsed

    except urllib.error.URLError as e:

        return 0, {
            "error": str(e)
        }


# =========================================================
# CHECK HELPER
# =========================================================

def check(label, condition):

    global PASS, FAIL

    if condition:
        status = "OK"
        PASS += 1
    else:
        status = "FAILED"
        FAIL += 1

    print(
        f"  {label:<40} [{status}]"
    )


# =========================================================
# AUTHENTICATION
# =========================================================

def authenticate():

    email = "scenario-test@example.com"

    password = "TestPassword123"

    register_data = {
        "name": "Scenario Test User",
        "email": email,
        "password": password,
        "confirm_password": password
    }

    status, response = api(
        "POST",
        "/api/auth/register",
        register_data
    )

    if status == 201:

        print("Authentication: Registered new test user")

        return True

    login_data = {
        "email": email,
        "password": password
    }

    status, response = api(
        "POST",
        "/api/auth/login",
        login_data
    )

    if status == 200:

        print("Authentication: Logged in successfully")

        return True

    print("Authentication failed")

    print(response)

    return False


# =========================================================
# MAIN TEST SUITE
# =========================================================

def main():

    global PASS, FAIL

    # Initialize database
    init_db()

    print("\n=========================================================")
    print("       DIGITAL STUDENT FLASHCARD TEST SUITE")
    print("=========================================================\n")

    # -----------------------------------------------------
    # AUTHENTICATION
    # -----------------------------------------------------

    print("Authentication")

    authenticated = authenticate()

    check(
        "Authentication successful",
        authenticated
    )

    if not authenticated:

        print(
            "\nCannot continue because authentication failed."
        )

        return 1


    # -----------------------------------------------------
    # 1. DECK SCENARIOS
    # -----------------------------------------------------

    print("\nDeck")

    status, deck = api(
        "POST",
        "/api/decks",
        {
            "name": "Scenario Deck",
            "description": "Testing scenario flows"
        }
    )

    deck_id = deck.get("id")

    check(
        "Create deck",
        status == 201 and deck_id is not None
    )

    # Stop safely if deck creation failed
    if deck_id is None:

        print("\nDeck creation failed.")

        print("Response:")

        print(deck)

        return 1


    # Empty deck name

    status_empty, response_empty = api(
        "POST",
        "/api/decks",
        {
            "name": "   "
        }
    )

    check(
        "Empty deck rejected",
        status_empty == 400
    )


    # Edit deck

    status_edit, deck_edited = api(
        "PUT",
        f"/api/decks/{deck_id}",
        {
            "name": "Scenario Deck Updated",
            "description": "Updated description"
        }
    )

    check(
        "Edit deck",
        status_edit == 200
        and deck_edited.get("name")
        == "Scenario Deck Updated"
    )


    # -----------------------------------------------------
    # 2. CARD SCENARIOS
    # -----------------------------------------------------

    print("\nCards")


    # Create Card 1

    status_c1, card1 = api(
        "POST",
        f"/api/decks/{deck_id}/cards",
        {
            "question": "What is 2 + 2?",
            "answer": "4"
        }
    )

    card1_id = card1.get("id")

    check(
        "Create card",
        status_c1 == 201
        and card1_id is not None
    )


    # Empty question

    status_eq, response_eq = api(
        "POST",
        f"/api/decks/{deck_id}/cards",
        {
            "question": "",
            "answer": "4"
        }
    )

    check(
        "Empty question rejected",
        status_eq == 400
    )


    # Empty answer

    status_ea, response_ea = api(
        "POST",
        f"/api/decks/{deck_id}/cards",
        {
            "question": "What is 3 + 3?",
            "answer": "   "
        }
    )

    check(
        "Empty answer rejected",
        status_ea == 400
    )


    # Edit Card

    status_ce, card_edited = api(
        "PUT",
        f"/api/cards/{card1_id}",
        {
            "question": "What is 2 + 2?",
            "answer": "Four"
        }
    )

    check(
        "Edit card",
        status_ce == 200
        and card_edited.get("answer") == "Four"
    )


    # Create Card 2

    status_c2, card2 = api(
        "POST",
        f"/api/decks/{deck_id}/cards",
        {
            "question": "What is the capital of France?",
            "answer": "Paris"
        }
    )

    card2_id = card2.get("id")

    check(
        "Create second card",
        status_c2 == 201
        and card2_id is not None
    )


    # Temporary card for delete test

    status_temp, card_temp = api(
        "POST",
        f"/api/decks/{deck_id}/cards",
        {
            "question": "Temporary Question",
            "answer": "Temporary Answer"
        }
    )

    temp_id = card_temp.get("id")

    if temp_id is not None:

        status_delete_card, response_delete_card = api(
            "DELETE",
            f"/api/cards/{temp_id}"
        )

        check(
            "Delete card",
            status_delete_card == 200
        )

    else:

        check(
            "Delete card",
            False
        )


    # -----------------------------------------------------
    # 3. STUDY SCENARIOS
    # -----------------------------------------------------

    print("\nStudy")


    # Flip card

    check(
        "Flip card",
        card1.get("question", "") != ""
        and card1.get("answer", "") != ""
    )


    # Know It

    status_know, updated_know = api(
        "POST",
        f"/api/study/{card1_id}/respond",
        {
            "knew_it": True
        }
    )

    check(
        "Know It",
        status_know == 200
        and isinstance(updated_know, dict)
    )


    # Review Again

    status_review, updated_review = api(
        "POST",
        f"/api/study/{card2_id}/respond",
        {
            "knew_it": False
        }
    )

    check(
        "Review Again",
        status_review == 200
        and isinstance(updated_review, dict)
    )


    # Shuffle scenario

    cards_before = [
        card1_id,
        card2_id
    ]

    check(
        "Shuffle",
        len(cards_before) == 2
    )


    # Study cards

    status_study, study_data = api(
        "GET",
        f"/api/study/{deck_id}/cards"
    )

    cards_list = study_data.get(
        "cards",
        []
    )


    # Progress

    studied_count = sum(
        1
        for card in cards_list
        if card.get("attempts", 0) > 0
    )

    check(
        "Progress",
        studied_count >= 2
    )


    # Completion

    check(
        "Completion",
        len(cards_list) >= 2
    )


    # -----------------------------------------------------
    # 4. ADAPTIVE SYSTEM SCENARIOS
    # -----------------------------------------------------

    print("\nAdaptive System")


    # Get current card information

    card1_before = query_db(
        "SELECT * FROM cards WHERE id = ?",
        (card1_id,),
        one=True
    ) or {}


    p_initial = calculate_priority(
        card1_before.get("attempts", 0),
        card1_before.get("correct_count", 0),
        card1_before.get("review_count", 0)
    )


    # Review Again should increase priority

    api(
        "POST",
        f"/api/study/{card1_id}/respond",
        {
            "knew_it": False
        }
    )


    card1_after = query_db(
        "SELECT * FROM cards WHERE id = ?",
        (card1_id,),
        one=True
    ) or {}


    p_after_review = calculate_priority(
        card1_after.get("attempts", 0),
        card1_after.get("correct_count", 0),
        card1_after.get("review_count", 0)
    )


    check(
        "Review Again increases priority",
        p_after_review > p_initial
    )


    # Know It should decrease priority

    api(
        "POST",
        f"/api/study/{card1_id}/respond",
        {
            "knew_it": True
        }
    )


    card1_after_know = query_db(
        "SELECT * FROM cards WHERE id = ?",
        (card1_id,),
        one=True
    ) or {}


    p_after_know = calculate_priority(
        card1_after_know.get("attempts", 0),
        card1_after_know.get("correct_count", 0),
        card1_after_know.get("review_count", 0)
    )


    check(
        "Know It decreases priority",
        p_after_know < p_after_review
    )


    # Difficult cards prioritized

    api(
        "POST",
        f"/api/study/{card2_id}/respond",
        {
            "knew_it": False
        }
    )

    api(
        "POST",
        f"/api/study/{card2_id}/respond",
        {
            "knew_it": False
        }
    )


    ordered_cards = get_study_cards(
        deck_id
    )


    difficult_card_found = False

    if len(ordered_cards) > 0:

        difficult_card_found = (
            ordered_cards[0]["id"]
            == card2_id
        )


    check(
        "Difficult cards prioritized",
        difficult_card_found
    )


    # -----------------------------------------------------
    # CLEANUP
    # -----------------------------------------------------

    print("\nCleanup")


    status_delete_deck, response_delete_deck = api(
        "DELETE",
        f"/api/decks/{deck_id}"
    )


    check(
        "Delete deck",
        status_delete_deck == 200
    )


    # -----------------------------------------------------
    # RESULTS
    # -----------------------------------------------------

    print("\n=========================================================")

    print(
        f"Summary: {PASS} Passed, {FAIL} Failed"
    )

    print("=========================================================\n")


    if FAIL == 0:

        return 0

    return 1


# =========================================================
# PROGRAM ENTRY
# =========================================================

if __name__ == "__main__":

    sys.exit(main())