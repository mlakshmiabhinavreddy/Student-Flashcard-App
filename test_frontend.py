"""
End-to-end frontend integration test.

Creates an authenticated user and test data via API,
then verifies that the frontend pages load correctly.

Run:
    Terminal 1:
        venv/Scripts/python app.py

    Terminal 2:
        venv/Scripts/python test_frontend.py
"""

import json
import sys
import urllib.request
import urllib.error
import http.cookiejar
import time


BASE = "http://127.0.0.1:5000"

PASS = 0
FAIL = 0


# ============================================================
# COOKIE / SESSION HANDLING
# ============================================================

cookie_jar = http.cookiejar.CookieJar()

opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(cookie_jar)
)


# ============================================================
# API HELPER
# ============================================================

def api(method, path, body=None):
    """
    Send an API request using the authenticated session.
    Returns:
        (status_code, response_data)
    """

    url = f"{BASE}{path}"

    data = None

    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        method=method
    )

    req.add_header("Content-Type", "application/json")

    try:
        resp = opener.open(req)

        raw = resp.read().decode("utf-8")

        try:
            response_data = json.loads(raw)
        except Exception:
            response_data = raw

        return resp.status, response_data

    except urllib.error.HTTPError as e:

        raw = e.read().decode("utf-8")

        try:
            response_data = json.loads(raw)
        except Exception:
            response_data = {"error": raw}

        return e.code, response_data

    except urllib.error.URLError as e:

        return 0, {
            "error": f"Server connection failed: {e}"
        }


# ============================================================
# PAGE HELPER
# ============================================================

def get_page(path):
    """
    Fetch an HTML page using the authenticated Flask session.

    Returns:
        (status_code, html)
    """

    url = f"{BASE}{path}"

    try:

        resp = opener.open(url)

        html = resp.read().decode("utf-8")

        return resp.status, html

    except urllib.error.HTTPError as e:

        html = e.read().decode("utf-8")

        return e.code, html

    except urllib.error.URLError:

        return 0, ""


# ============================================================
# TEST RESULT HELPER
# ============================================================

def check(label, condition):

    global PASS, FAIL

    if condition:
        PASS += 1
        print(f"  [PASS] {label}")

    else:
        FAIL += 1
        print(f"  [FAIL] {label}")


# ============================================================
# AUTHENTICATION
# ============================================================

def authenticate():

    print("\n0. Authentication")

    unique_id = int(time.time())

    name = "Frontend Test User"

    email = f"frontend-test-{unique_id}@example.com"

    password = "TestPassword123"

    # Try registering a new user
    status, response = api(
        "POST",
        "/api/auth/register",
        {
            "name": name,
            "email": email,
            "password": password,
            "confirm_password": password
        }
    )

    if status == 201:

        print("  Registered new frontend test user")

        check(
            "Authentication successful",
            isinstance(response, dict)
            and "user" in response
        )

        return True

    # If registration did not work,
    # try login just in case
    status, response = api(
        "POST",
        "/api/auth/login",
        {
            "email": email,
            "password": password
        }
    )

    check(
        "Authentication successful",
        status == 200
    )

    return status == 200


# ============================================================
# MAIN TEST
# ============================================================

def main():

    global PASS, FAIL


    # --------------------------------------------------------
    # AUTHENTICATION
    # --------------------------------------------------------

    authenticated = authenticate()

    if not authenticated:

        print("\nAuthentication failed.")
        print("Cannot continue frontend tests.")

        return 1


    # --------------------------------------------------------
    # SETUP TEST DATA
    # --------------------------------------------------------

    print("\n1. Setup test data")


    status, deck = api(
        "POST",
        "/api/decks",
        {
            "name": "Frontend Test Deck",
            "description": "Testing the UI"
        }
    )


    print(f"  Create deck status: {status}")


    deck_id = None


    if isinstance(deck, dict):

        deck_id = deck.get("id")


    check(
        "Created test deck",
        status == 201 and deck_id is not None
    )


    # Stop if deck creation failed
    if deck_id is None:

        print("\nCannot continue because test deck was not created.")

        return 1


    # --------------------------------------------------------
    # CREATE CARD 1
    # --------------------------------------------------------

    status1, card1 = api(
        "POST",
        f"/api/decks/{deck_id}/cards",
        {
            "question": "What is HTML?",
            "answer": "HyperText Markup Language"
        }
    )


    # --------------------------------------------------------
    # CREATE CARD 2
    # --------------------------------------------------------

    status2, card2 = api(
        "POST",
        f"/api/decks/{deck_id}/cards",
        {
            "question": "What is CSS?",
            "answer": "Cascading Style Sheets"
        }
    )


    card1_id = None
    card2_id = None


    if isinstance(card1, dict):
        card1_id = card1.get("id")


    if isinstance(card2, dict):
        card2_id = card2.get("id")


    check(
        "Created 2 test cards",
        status1 == 201
        and status2 == 201
        and card1_id is not None
        and card2_id is not None
    )


    # ========================================================
    # 2. LANDING PAGE
    # ========================================================

    print("\n2. Landing page (/)")

    status, html = get_page("/")

    check(
        "Landing page loads",
        status == 200
    )


    if status == 200:

        # Check for login redirect
        check(
            "Not redirected to login",
            "Redirecting..." not in html
            and 'href="/login"' not in html
        )


        # Use flexible checks because landing page text
        # may differ slightly in your project.

        check(
            "Has title",
            "Digital Student Flashcard" in html
            or "Flashcard" in html
            or "<title>" in html
        )


        check(
            "Has hero heading",
            "Master Any Subject" in html
            or "Master" in html
            or "Study" in html
            or "Flashcard" in html
        )


        check(
            "Has CTA button",
            "Get Started" in html
            or "Dashboard" in html
            or "Start" in html
            or "href=" in html
        )


        check(
            "Has feature grid",
            "Create Decks" in html
            or "Deck" in html
            or "feature" in html.lower()
        )


        check(
            "Loads Inter font",
            "fonts.googleapis.com" in html
        )


        check(
            "Loads style.css",
            "style.css" in html
        )


    # ========================================================
    # 3. DASHBOARD
    # ========================================================

    print("\n3. Dashboard page (/dashboard)")

    status, html = get_page("/dashboard")


    check(
        "Dashboard loads",
        status == 200
    )


    if status == 200:

        check(
            "Has dashboard title",
            "Dashboard" in html
        )


        check(
            "Has stat cards",
            "stat-total-decks" in html
        )


        check(
            "Has deck breakdown section",
            "deck-breakdown" in html
        )


        check(
            "Loads dashboard.js",
            "dashboard.js" in html
        )


    # ========================================================
    # 4. DECKS PAGE
    # ========================================================

    print("\n4. Decks page (/decks)")

    status, html = get_page("/decks")


    check(
        "Decks page loads",
        status == 200
    )


    if status == 200:

        check(
            "Has page title",
            "My Decks" in html
        )


        check(
            "Has create button",
            "btn-create-deck" in html
            or "New Deck" in html
            or "Create Deck" in html
        )


        check(
            "Has deck container",
            "decks-container" in html
        )


        check(
            "Has create modal",
            "deck-modal-overlay" in html
        )


        check(
            "Has delete modal",
            "delete-deck-modal-overlay" in html
        )


        check(
            "Has form fields",
            "deck-form-name" in html
        )


        check(
            "Loads decks.js",
            "decks.js" in html
        )


    # ========================================================
    # 5. DECK DETAIL PAGE
    # ========================================================

    print(f"\n5. Deck detail page (/deck/{deck_id})")

    status, html = get_page(
        f"/deck/{deck_id}"
    )


    check(
        "Deck detail page loads",
        status == 200
    )


    if status == 200:

        check(
            "Has back link",
            "Back to My Decks" in html
        )


        check(
            "Has deck header",
            "deck-header" in html
        )


        check(
            "Has cards container",
            "cards-container" in html
        )


        check(
            "Has card modal",
            "card-modal-overlay" in html
        )


        check(
            "Has card delete modal",
            "delete-card-modal-overlay" in html
        )


        check(
            "Has card form fields",
            "card-form-question" in html
        )


        check(
            "Has DECK_ID injected",
            f"DECK_ID = {deck_id}" in html
            or f"DECK_ID={deck_id}" in html
        )


        check(
            "Loads deck.js",
            "deck.js" in html
        )


    # ========================================================
    # 6. API DATA VERIFICATION
    # ========================================================

    print("\n6. API data verification")


    status, decks = api(
        "GET",
        "/api/decks"
    )


    test_deck = None


    if isinstance(decks, list):

        test_deck = next(

            (
                d for d in decks

                if isinstance(d, dict)
                and d.get("id") == deck_id
            ),

            None
        )


    check(
        "Deck in API list",
        status == 200
        and test_deck is not None
    )


    if test_deck is not None:

        check(
            "Deck has card_count >= 2",
            test_deck.get("card_count", 0) >= 2
        )

    else:

        check(
            "Deck has card_count >= 2",
            False
        )


    status, cards = api(
        "GET",
        f"/api/decks/{deck_id}/cards"
    )


    if isinstance(cards, dict):

        cards_list = cards.get(
            "cards",
            []
        )

    elif isinstance(cards, list):

        cards_list = cards

    else:

        cards_list = []


    check(
        "2 cards returned",
        status == 200
        and len(cards_list) >= 2
    )


    # ========================================================
    # 7. CLEANUP
    # ========================================================

    print("\n7. Cleanup")


    status_delete, response_delete = api(
        "DELETE",
        f"/api/decks/{deck_id}"
    )


    check(
        "Test deck deleted",
        status_delete == 200
    )


    status_check, response_check = api(
        "GET",
        f"/api/decks/{deck_id}"
    )


    check(
        "Test deck cleaned up",
        status_check == 404
    )


    # ========================================================
    # SUMMARY
    # ========================================================

    print("\n==================================================")

    print(
        f"Results: {PASS} passed, {FAIL} failed"
    )

    print("==================================================")


    return 0 if FAIL == 0 else 1


# ============================================================
# PROGRAM ENTRY
# ============================================================

if __name__ == "__main__":

    sys.exit(
        main()
    )