"""
STUDYFLIP — NLP Service
Extracts main topics and subtopics from study material text.

Primary engine: Gemini (google-genai) — already in the stack.

NOTE: Google Cloud Natural Language API (google-cloud-language) is currently
incompatible with the protobuf version required by the rest of the stack
(<=2.15.1 requires protobuf<6.0, but the rest of the stack needs >=6.33.5).
This module will be updated to use Cloud NLP once a compatible release is
published.
"""

import os
import json


# ── Text extraction helpers ──────────────────────────────────────────────────

def extract_text_from_bytes(file_bytes: bytes, filename: str) -> str:
    """
    Extract plain text from uploaded file bytes.

    Supports:
      .txt  — decoded as UTF-8 (Latin-1 fallback)
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

    # Fallback: raw UTF-8
    try:
        return file_bytes.decode("utf-8", errors="replace")
    except Exception:
        return ""


# ── Topic extraction via Gemini ──────────────────────────────────────────────

def _extract_via_gemini(text: str) -> dict:
    """
    Use Gemini to extract main topics and subtopics from study material text.

    Returns:
        {
          "topics":    ["Python"],
          "subtopics": ["strings", "arrays", "functions"]
        }
    """
    from google import genai
    from google.genai import types

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key or api_key.startswith("dummy"):
        print("[NLP] GEMINI_API_KEY not set — returning empty topics.")
        return {"topics": [], "subtopics": []}

    client = genai.Client(api_key=api_key)

    prompt = f"""Analyze the following study material and extract:
1. Main topics (broad subjects, max 5)
2. Subtopics (specific concepts, terms, keywords, max 12)

Study material:
{text[:4000]}

Respond in strict JSON only:
{{
  "topics": ["topic1", "topic2"],
  "subtopics": ["subtopic1", "subtopic2", "..."]
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
                        "topics":    {"type": "ARRAY", "items": {"type": "STRING"}},
                        "subtopics": {"type": "ARRAY", "items": {"type": "STRING"}},
                    },
                    "required": ["topics", "subtopics"],
                },
            ),
        )
        data = json.loads(response.text)
        return {
            "topics":    data.get("topics", [])[:5],
            "subtopics": data.get("subtopics", [])[:12],
        }
    except Exception as exc:
        print(f"[NLP] Gemini topic extraction failed: {exc}")
        return {"topics": [], "subtopics": []}


# ── Public API ───────────────────────────────────────────────────────────────

def extract_topics(text: str) -> dict:
    """
    Extract topics and subtopics from plain-text study material.

    Uses Gemini as the NLP engine. Cloud Natural Language API will be
    re-enabled once a protobuf-compatible version is released.

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

    return _extract_via_gemini(text)
