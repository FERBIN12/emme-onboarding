"""Standalone smoke test for the local-only Ollama extraction path (not
used in the primary flow -- see app/extraction.py's module docstring for
why Gemini is primary). Kept for reference / in case hardware changes.

Usage: python test_extraction_local_ollama.py path/to/sample.pdf
"""

import sys

from app.extraction_local_ollama import extract_from_document

if __name__ == "__main__":
    path = sys.argv[1]
    media_type = "application/pdf" if path.lower().endswith(".pdf") else "image/png"

    with open(path, "rb") as f:
        file_bytes = f.read()

    result = extract_from_document(file_bytes, media_type)
    print(result.model_dump_json(indent=2))
