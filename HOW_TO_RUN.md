# STUDYFLIP — How to Run (Windows / macOS / Linux)

Your original Flask project, re-skinned with the **StudyFlip Anywhere** interface
(cream background, terracotta accent, rounded cards, light sidebar / mobile tab bar).
Only the UI/CSS changed — all backend code, routes, API, DB logic and JS are your originals.

## ⚠️ IF YOU STILL SEE THE OLD DARK THEME
That is your browser showing a CACHED copy of the old stylesheet. Fix it in 2 seconds:
- **Windows/Linux:** press **Ctrl + Shift + R** (hard refresh)
- **Mac:** press **Cmd + Shift + R**
- Or open the site in a private/incognito window.
The templates already include a cache-busting tag (`style.css?v=studyflip2`),
so a normal hard refresh once is enough.

## Run (development)
```bash
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate        # macOS / Linux
pip install -r requirements.txt
python app.py
```
Open **http://localhost:5000** (hard-refresh once if it looks dark).

## Run (production)
```bash
gunicorn app:app
```

## Responsive / cross-platform
- Laptop/desktop: left sidebar rail.
- Phone/tablet (Android, iPhone, iPad): bottom tab bar + top app bar, touch-friendly.
Works in any modern browser on any OS, portrait or landscape.
