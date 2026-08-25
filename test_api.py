"""
API endpoint test script.
Tests all 10 REST endpoints against the running Flask server.

Run:
    1. Start server:  venv/Scripts/python app.py
    2. Run tests:     venv/Scripts/python test_api.py
"""

import json
import urllib.request
import urllib.error
import sys

BASE = "http://127.0.0.1:5000"
PASS = 0
FAIL = 0


def api(method, path, body=None):
    """Make an API request and return (status_code, response_dict)."""
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")

    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


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

    # ── 1. DECK: Create ─────────────────────────────────────
    print("\n1. POST /api/decks — Create deck")

    status, data = api("POST", "/api/decks", {"name": "Biology 101", "description": "Cell biology"})
    check(f"status=201", status == 201)
    check("returns deck with id", "id" in data)
    check("name matches", data["name"] == "Biology 101")
    check("description matches", data["description"] == "Cell biology")
    check("created_at is set", data["created_at"] is not None)
    deck_id = data["id"]

    # Create a second deck for listing test
    api("POST", "/api/decks", {"name": "History", "description": "World War II"})

    # ── 1b. Validation: empty name ───────────────────────────
    print("\n1b. POST /api/decks — Validation")

    status, data = api("POST", "/api/decks", {"name": ""})
    check("empty name -> 400", status == 400)
    check("error message present", "error" in data)

    status, data = api("POST", "/api/decks", {"name": "   "})
    check("whitespace name -> 400", status == 400)

    # ── 2. DECK: List ────────────────────────────────────────
    print("\n2. GET /api/decks — List all decks")

    status, data = api("GET", "/api/decks")
    check("status=200", status == 200)
    check("returns list", isinstance(data, list))
    check("at least 2 decks", len(data) >= 2)
    check("card_count field present", "card_count" in data[0])

    # ── 3. DECK: Get one ─────────────────────────────────────
    print("\n3. GET /api/decks/<id> — Get single deck")

    status, data = api("GET", f"/api/decks/{deck_id}")
    check("status=200", status == 200)
    check("correct id", data["id"] == deck_id)
    check("has card_count", "card_count" in data)

    status, data = api("GET", "/api/decks/9999")
    check("nonexistent -> 404", status == 404)

    # ── 4. DECK: Update ──────────────────────────────────────
    print("\n4. PUT /api/decks/<id> — Update deck")

    status, data = api("PUT", f"/api/decks/{deck_id}", {"name": "Bio 201", "description": "Advanced"})
    check("status=200", status == 200)
    check("name updated", data["name"] == "Bio 201")
    check("description updated", data["description"] == "Advanced")

    status, data = api("PUT", f"/api/decks/{deck_id}", {"name": ""})
    check("empty name -> 400", status == 400)

    status, data = api("PUT", "/api/decks/9999", {"name": "Nope"})
    check("nonexistent -> 404", status == 404)

    # ── 5. CARD: Create ─────────────────────────────────────
    print("\n5. POST /api/decks/<id>/cards — Create card")

    status, data = api("POST", f"/api/decks/{deck_id}/cards", {
        "question": "What is the powerhouse of the cell?",
        "answer": "Mitochondria"
    })
    check("status=201", status == 201)
    check("has id", "id" in data)
    check("question matches", data["question"] == "What is the powerhouse of the cell?")
    check("answer matches", data["answer"] == "Mitochondria")
    check("deck_id matches", data["deck_id"] == deck_id)
    check("attempts=0", data["attempts"] == 0)
    check("correct_count=0", data["correct_count"] == 0)
    check("review_count=0", data["review_count"] == 0)
    card_id = data["id"]

    # Add a second card
    api("POST", f"/api/decks/{deck_id}/cards", {
        "question": "What is DNA?",
        "answer": "Deoxyribonucleic acid"
    })

    # ── 5b. Card validation ──────────────────────────────────
    print("\n5b. POST /api/decks/<id>/cards — Validation")

    status, data = api("POST", f"/api/decks/{deck_id}/cards", {"question": "", "answer": "test"})
    check("empty question -> 400", status == 400)

    status, data = api("POST", f"/api/decks/{deck_id}/cards", {"question": "test", "answer": ""})
    check("empty answer -> 400", status == 400)

    status, data = api("POST", "/api/decks/9999/cards", {"question": "Q", "answer": "A"})
    check("nonexistent deck -> 404", status == 404)

    # ── 6. CARD: List ────────────────────────────────────────
    print("\n6. GET /api/decks/<id>/cards — List cards in deck")

    status, data = api("GET", f"/api/decks/{deck_id}/cards")
    check("status=200", status == 200)
    check("returns list", isinstance(data, list))
    check("2 cards", len(data) == 2)

    status, data = api("GET", "/api/decks/9999/cards")
    check("nonexistent deck -> 404", status == 404)

    # ── 7. CARD: Get one ─────────────────────────────────────
    print("\n7. GET /api/cards/<id> — Get single card")

    status, data = api("GET", f"/api/cards/{card_id}")
    check("status=200", status == 200)
    check("correct id", data["id"] == card_id)

    status, data = api("GET", "/api/cards/9999")
    check("nonexistent -> 404", status == 404)

    # ── 8. CARD: Update ──────────────────────────────────────
    print("\n8. PUT /api/cards/<id> — Update card")

    status, data = api("PUT", f"/api/cards/{card_id}", {
        "question": "Updated question?",
        "answer": "Updated answer"
    })
    check("status=200", status == 200)
    check("question updated", data["question"] == "Updated question?")
    check("answer updated", data["answer"] == "Updated answer")

    status, data = api("PUT", f"/api/cards/{card_id}", {"question": "", "answer": "A"})
    check("empty question -> 400", status == 400)

    status, data = api("PUT", "/api/cards/9999", {"question": "Q", "answer": "A"})
    check("nonexistent -> 404", status == 404)

    # ── 9. CARD: Delete ──────────────────────────────────────
    print("\n9. DELETE /api/cards/<id> — Delete card")

    status, data = api("DELETE", f"/api/cards/{card_id}")
    check("status=200", status == 200)
    check("message present", "message" in data)

    status, data = api("GET", f"/api/cards/{card_id}")
    check("card gone -> 404", status == 404)

    status, data = api("DELETE", "/api/cards/9999")
    check("nonexistent -> 404", status == 404)

    # ── 10. DECK: Delete (cascade) ───────────────────────────
    print("\n10. DELETE /api/decks/<id> — Delete deck (cascade)")

    # Check cards exist before delete
    status, cards_before = api("GET", f"/api/decks/{deck_id}/cards")
    check(f"cards before delete: {len(cards_before)}", len(cards_before) >= 1)

    status, data = api("DELETE", f"/api/decks/{deck_id}")
    check("status=200", status == 200)

    status, data = api("GET", f"/api/decks/{deck_id}")
    check("deck gone -> 404", status == 404)

    status, data = api("DELETE", "/api/decks/9999")
    check("nonexistent -> 404", status == 404)

    # ── Summary ──────────────────────────────────────────────
    print(f"\n{'='*50}")
    print(f"  Results:  {PASS} passed,  {FAIL} failed")
    print(f"{'='*50}\n")

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
