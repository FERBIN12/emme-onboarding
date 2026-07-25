"""Standalone smoke test for the Gemini extraction path -- compare output
quality against the local Ollama path (test_extraction.py) on the same
document.

Requires GEMINI_API_KEY in the environment.

Usage: python test_extraction_gemini.py path/to/sample.pdf
"""

import sys

from app.extraction_gemini import extract_from_document_gemini

if __name__ == "__main__":
    path = sys.argv[1]
    media_type = "application/pdf" if path.lower().endswith(".pdf") else "image/png"

    with open(path, "rb") as f:
        file_bytes = f.read()

    result = extract_from_document_gemini(file_bytes, media_type)
    print(result.model_dump_json(indent=2))
