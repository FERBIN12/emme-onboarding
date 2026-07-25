"""Cloud fallback / A-B comparison path: same extraction contract as
extraction.py, but calling Gemini instead of local Ollama.

    extract_from_document_gemini(file_bytes, media_type) -> IntakeData

Kept as a separate module (not merged into extraction.py) so the team can
A/B test local vs. cloud quality on the same sample documents and pick
whichever demos better, without the two implementations tangled together.

Requires GEMINI_API_KEY in the environment. Get a free key at
https://aistudio.google.com/apikey
"""

import json
import os

from google import genai
from google.genai import types

from .extraction import _SCHEMA_HINT  # reuse the same prompt for a fair comparison
from .schema import IntakeData

_MODEL = "gemini-flash-latest"

_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def extract_from_document_gemini(file_bytes: bytes, media_type: str) -> IntakeData:
    """media_type: e.g. "application/pdf", "image/png", "image/jpeg".

    Unlike the local Ollama path, Gemini accepts PDFs directly -- no need
    to rasterize pages first.
    """

    response = _client.models.generate_content(
        model=_MODEL,
        contents=[
            types.Part.from_bytes(data=file_bytes, mime_type=media_type),
            _SCHEMA_HINT,
        ],
        config=types.GenerateContentConfig(temperature=0),
    )

    raw_text = response.text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    start, end = raw_text.find("{"), raw_text.rfind("}")
    raw_text = raw_text[start : end + 1]

    data = json.loads(raw_text)
    return IntakeData.model_validate(data)
