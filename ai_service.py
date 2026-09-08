import os
import json

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not configured")

client = genai.Client(api_key=GEMINI_API_KEY)


def generate_flashcards(text, number_of_cards=5):

    if not text or not text.strip():
        raise ValueError("Study material cannot be empty")

    if number_of_cards < 1 or number_of_cards > 20:
        raise ValueError(
            "number_of_cards must be between 1 and 20"
        )

    prompt = f"""
Create {number_of_cards} high-quality educational flashcards
from the following study material.

Study material:
{text}

Requirements:

- Generate exactly {number_of_cards} flashcards.
- Questions should test understanding.
- Answers must be accurate and concise.
- Difficulty must be exactly one of:
  easy
  medium
  hard
"""

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema={
                "type": "OBJECT",
                "properties": {
                    "cards": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "question": {
                                    "type": "STRING"
                                },
                                "answer": {
                                    "type": "STRING"
                                },
                                "difficulty": {
                                    "type": "STRING",
                                    "enum": [
                                        "easy",
                                        "medium",
                                        "hard"
                                    ]
                                }
                            },
                            "required": [
                                "question",
                                "answer",
                                "difficulty"
                            ]
                        }
                    }
                },
                "required": ["cards"]
            }
        )
    )

    data = json.loads(response.text)

    if "cards" not in data:
        raise ValueError(
            "AI response does not contain cards"
        )

    return data["cards"]