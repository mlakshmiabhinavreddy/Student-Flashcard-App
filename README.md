# Digital Student Flashcard

A lightweight web application for students to create subject-based flashcard decks, study with interactive flip cards, and track learning progress with adaptive review prioritization.

## Tech Stack

| Layer      | Technology              |
|------------|-------------------------|
| Frontend   | HTML, CSS, Vanilla JS   |
| Backend    | Python, Flask, REST API |
| Database   | SQLite                  |
| Production | Gunicorn, GCE, Ubuntu   |

## Project Structure

```
digital-student-flashcards/
├── app.py                    # Flask application entry point
├── database.py               # Database connection, schema, queries
├── config.py                 # Configuration (env vars)
├── requirements.txt          # Python dependencies
├── README.md
├── .gitignore
├── .env.example              # Environment variable template
│
├── database/
│   └── flashcards.db         # SQLite database (auto-created)
│
├── templates/
│   ├── index.html            # Landing page
│   ├── dashboard.html        # Learning statistics
│   ├── decks.html            # Deck listing & management
│   ├── deck.html             # Single deck — card management
│   └── study.html            # Study mode
│
├── static/
│   ├── css/
│   │   └── style.css         # Design system & styles
│   └── js/
│       ├── dashboard.js      # Dashboard UI
│       ├── decks.js          # Deck management UI
│       ├── deck.js           # Card management UI
│       └── study.js          # Study mode UI
│
└── tests/
    ├── test_decks.py          # Deck API tests
    ├── test_cards.py          # Card API tests
    └── test_study.py          # Study API tests
```

## Quick Start

```bash
# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy environment config
cp .env.example .env

# 4. Run development server
python app.py
```

Then open **http://localhost:5000** in your browser.

## Development Stages

This application is built incrementally:

1. ✅ Project architecture & scaffolding
2. ⬜ Deck management (CRUD)
3. ⬜ Card management (CRUD)
4. ⬜ Study mode (flip, Know It / Review Again)
5. ⬜ Adaptive Review Prioritization
6. ⬜ Dashboard & statistics
7. ⬜ Polish & production deployment
