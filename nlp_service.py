"""
STUDYFLIP — NLP Service
Extracts main topics and subtopics from study material text using
Google Cloud Natural Language API.

Falls back gracefully to Gemini-based keyword extraction when the
Cloud NLP API is not available (e.g., in local dev without credentials).
"""

import os
import json

# ── Cloud NLP client (lazy, so app starts without credentials) ──────────────
_nlp_client = None


def _get_nlp_client():
    """Return a lazily-created Cloud Natural Language client, or None."""
    global _nlp_client
    if _nlp_client is not None:
        return _nlp_client

    try:
        from google.cloud import language_v2
        _nlp_client = language_v2.LanguageServiceClient()
        print("[NLP] Cloud Natural Language client ready.")
    except Exception as exc:
        print(f"[NLP] Cloud NLP unavailable ({type(exc).__name__}); "
              "will use Gemini fallback.")
        _nlp_client = False  # sentinel — don't retry

    return _nlp_client


# ── Text extraction helpers ──────────────────────────────────────────────────

def extract_text_from_bytes(file_bytes: bytes, filename: str) -> str:
    """
    Extract plain text from uploaded file bytes.

    Supports:
      .txt  — decoded as UTF-8 (with Latin-1 fallback)
      .pdf  — pdfplumber text extraction
      .docx — python-docx paragraph extraction
    """
    name_lower = filename.lower()

    if name_lower.endswith(".txt"):
        try:
            return file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return file_bytes.decode("latin-1", errors="replace")

    if name_lower.endswith(".pdf"):
        try:
            import pdfplumber
            import io
            pages = []
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text)
            return "\n".join(pages)
        except Exception as exc:
            print(f"[NLP] PDF extraction failed: {exc}")
            return ""

    if name_lower.endswith(".docx"):
        try:
            import docx
            import io
            doc = docx.Document(io.BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as exc:
            print(f"[NLP] DOCX extraction failed: {exc}")
            return ""

    # Fallback: try raw UTF-8 decode
    try:
        return file_bytes.decode("utf-8", errors="replace")
    except Exception:
        return ""


# ── NLP extraction ───────────────────────────────────────────────────────────

def _extract_via_cloud_nlp(text: str) -> dict:
    """
    Use Cloud Natural Language API to extract entities and categories.

    Returns:
        {
          "topics":    ["Python"],
          "subtopics": ["strings", "arrays", "functions"]
        }
    """
    from google.cloud import language_v2

    client = _get_nlp_client()
    document = language_v2.Document(
        content=text[:100_000],
        type_=language_v2.Document.Type.PLAIN_TEXT,
    )

    entity_response = client.analyze_entities(
        request={"document": document, "encoding_type": "UTF8"}
    )

    topics = []
    subtopics = []
    seen = set()

    for entity in entity_response.entities:
        name = entity.name.strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())

        if entity.salience >= 0.10:
            topics.append(name)
        elif entity.salience >= 0.01:
            subtopics.append(name)

    # Content classification
    if len(text) >= 20:
        try:
            cat_response = client.classify_text(
                request={"document": document}
            )
            for cat in cat_response.categories:
                if cat.confidence >= 0.5:
                    parts = [p for p in cat.name.split("/") if p]
                    if parts:
                        candidate = parts[-1].strip()
                        if candidate.lower() not in seen:
                            topics.insert(0, candidate)
                            seen.add(candidate.lower())
        except Exception as exc:
            print(f"[NLP] classify_text skipped: {exc}")

    return {"topics": topics[:5], "subtopics": subtopics[:12]}


def _extract_via_gemini(text: str) -> dict:
    """
    Fallback: use Gemini to extract topics when Cloud NLP is unavailable.
    """
    from google import genai
    from google.genai import types

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key or api_key.startswith("dummy"):
        return {"topics": [], "subtopics": []}

    client = genai.Client(api_key=api_key)

    prompt = f"""Analyze the following study material and extract:
1. Main topics (broad subjects, max 5)
2. Subtopics (specific concepts, terms, keywords, max 12)

Study material:
{text[:4000]}

Respond in strict JSON:
{{
  "topics": ["topic1", "topic2"],
  "subtopics": ["subtopic1", "subtopic2"]
}}"""

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "topics": {"type": "ARRAY", "items": {"type": "STRING"}},
                        "subtopics": {"type": "ARRAY", "items": {"type": "STRING"}},
                    },
                    "required": ["topics", "subtopics"],
                },
            ),
        )
        data = json.loads(response.text)
        return {
            "topics": data.get("topics", [])[:5],
            "subtopics": data.get("subtopics", [])[:12],
        }
    except Exception as exc:
        print(f"[NLP] Gemini fallback failed: {exc}")
        return {"topics": [], "subtopics": []}


# ── Public API ───────────────────────────────────────────────────────────────

def extract_topics(text: str) -> dict:
    """
    Extract topics and subtopics from study text.

    Tries Cloud Natural Language API first; falls back to Gemini.

    Args:
        text: Plain-text study material.

    Returns:
        {
          "topics":    ["Python"],
          "subtopics": ["strings", "arrays", "functions"]
        }
    """
    if not text or not text.strip():
        return {"topics": [], "subtopics": []}

    client = _get_nlp_client()
    if client:
        try:
            return _extract_via_cloud_nlp(text)
        except Exception as exc:
            print(f"[NLP] Cloud NLP failed, using Gemini fallback: {exc}")

    return _extract_via_gemini(text)
