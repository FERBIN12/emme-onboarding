"""Standalone smoke test for the extraction pipeline -- run this directly,
no server needed, to verify the Claude call + parsing works before wiring
it into the upload endpoint.

Usage: python test_extraction.py path/to/sample.pdf
"""

import sys

from app.extraction import extract_from_document

if __name__ == "__main__":
    path = sys.argv[1]
    media_type = "application/pdf" if path.lower().endswith(".pdf") else "image/png"

    with open(path, "rb") as f:
        file_bytes = f.read()

    result = extract_from_document(file_bytes, media_type)
    print(result.model_dump_json(indent=2))
