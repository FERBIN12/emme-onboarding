"""Minimal FastAPI app exposing the extraction and chatbot endpoints that
are B's responsibility. Session/autosave/submit endpoints (A's
responsibility) should be added here too -- this file is meant to be
merged with that work, not replaced by it.
"""

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .chatbot import answer_question
from .extraction import ExtractionError, extract_from_document

app = FastAPI(title="Emme Onboarding API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for real deployment; fine for a hackathon demo
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/extract")
async def extract(file: UploadFile):
    """Upload an SBC/EOB (PDF or image); returns whatever fields could be
    extracted. Caller merges this into their session state and leaves
    anything null for manual entry."""
    if file.content_type not in ("application/pdf", "image/png", "image/jpeg"):
        raise HTTPException(400, f"Unsupported file type: {file.content_type}")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(400, "Uploaded file is empty")

    try:
        result = extract_from_document(file_bytes, file.content_type)
    except ExtractionError as e:
        # Extraction failed (corrupt file, unreadable doc, malformed model
        # output). This is not a server error -- the caller should fall
        # back to manual entry, per the "graceful fallback" requirement.
        raise HTTPException(422, f"Could not extract data from this document: {e}")

    return result.model_dump()


class ChatRequest(BaseModel):
    question: str


@app.post("/chat")
async def chat(req: ChatRequest):
    """Small plain-language Q&A widget, independent of the main form flow."""
    return {"answer": answer_question(req.question)}
