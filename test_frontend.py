"""
End-to-end frontend integration test.
Creates data via API, then verifies HTML pages contain the correct content.

Run:
    1. Start server:  venv/Scripts/python app.py
    2. Run tests:     venv/Scripts/python test_frontend.py
"""

import json
import sys
import urllib.request
import urllib.error

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
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def get_page(path):
    return urllib.request.urlopen(f"{BASE}{path}").read().decode()


def check(label, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
    else:
        FAIL += 1
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}")


def main():
    global PASS, FAIL

    # ── Setup test data ──────────────────────────────────────
    print("\n0. Setup test data")
    _, deck = api("POST", "/api/decks", {"name": "Frontend Test Deck", "description": "Testing the UI"})
    deck_id = deck["id"]
    check(f"Created test deck id={deck_id}", deck_id is not None)

    _, card1 = api("POST", f"/api/decks/{deck_id}/cards", {"question": "What is HTML?", "answer": "HyperText Markup Language"})
    _, card2 = api("POST", f"/api/decks/{deck_id}/cards", {"question": "What is CSS?", "answer": "Cascading Style Sheets"})
    check(f"Created 2 test cards", card1["id"] is not None and card2["id"] is not None)

    # ── 1. Landing page ──────────────────────────────────────
    print("\n1. Landing page (/)")
    html = get_page("/")
    check("has title", "Digital Student Flashcard" in html)
    check("has hero heading", "Master Any Subject" in html)
    check("has CTA button", "Get Started" in html)
    check("has feature grid", "Create Decks" in html)
    check("has nav links", "Dashboard" in html and "My Decks" in html)
    check("loads Inter font", "fonts.googleapis.com" in html)
    check("loads style.css", "style.css" in html)

    # ── 2. Dashboard page ────────────────────────────────────
    print("\n2. Dashboard page (/dashboard)")
    html = get_page("/dashboard")
    check("has dashboard title", "Dashboard" in html)
    check("has stat cards", "stat-total-decks" in html)
    check("has deck breakdown section", "deck-breakdown" in html)
    check("loads dashboard.js", "dashboard.js" in html)
    check("active nav link", 'class="nav-link active"' in html)

    # ── 3. Decks page ────────────────────────────────────────
    print("\n3. Decks page (/decks)")
    html = get_page("/decks")
    check("has page title", "My Decks" in html)
    check("has create button", "btn-create-deck" in html or "New Deck" in html)
    check("has deck container", "decks-container" in html)
    check("has create modal", "deck-modal-overlay" in html)
    check("has delete modal", "delete-deck-modal-overlay" in html)
    check("has form fields", "deck-form-name" in html)
    check("loads decks.js", "decks.js" in html)

    # ── 4. Deck detail page ──────────────────────────────────
    print(f"\n4. Deck detail page (/deck/{deck_id})")
    html = get_page(f"/deck/{deck_id}")
    check("has back link", "Back to My Decks" in html)
    check("has deck-header container", "deck-header" in html)
    check("has cards-container", "cards-container" in html)
    check("has card modal", "card-modal-overlay" in html)
    check("has card delete modal", "delete-card-modal-overlay" in html)
    check("has card form fields", "card-form-question" in html)
    check("has DECK_ID injected", f"DECK_ID = {deck_id}" in html)
    check("loads deck.js", "deck.js" in html)

    # ── 5. API returns correct data ──────────────────────────
    print("\n5. API data verification")
    status, decks = api("GET", "/api/decks")
    test_deck = next((d for d in decks if d["id"] == deck_id), None)
    check("deck in API list", test_deck is not None)
    check("deck has card_count=2", test_deck["card_count"] == 2)

    status, cards = api("GET", f"/api/decks/{deck_id}/cards")
    check("2 cards returned", len(cards) == 2)

    # ── Cleanup ──────────────────────────────────────────────
    print("\n6. Cleanup")
    api("DELETE", f"/api/decks/{deck_id}")
    status, _ = api("GET", f"/api/decks/{deck_id}")
    check("test deck cleaned up", status == 404)

    # ── Summary ──────────────────────────────────────────────
    print(f"\n{'='*50}")
    print(f"  Results:  {PASS} passed,  {FAIL} failed")
    print(f"{'='*50}\n")

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
