# Backend for the manual-fill intake flow.
# Handles: session creation, autosave on every field change, a confirmation
# summary, and a final structured JSON export for cost-calculation logic.
#
# Local dev:  pip install flask flask-cors flask-sqlalchemy --break-system-packages
#             python server.py
#             -> uses a local sqlite file, intake.db
#
# Production: set DATABASE_URL to a Postgres connection string, e.g.
#             postgresql://user:pass@host:5432/dbname
#             (Render/Railway/Supabase all give you this string directly)

import os
import uuid
import copy
import datetime
from flask import Flask, request, jsonify, session as browser_session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

from app.adapter import prune_nulls, to_session_shape
from app.chatbot import answer_chat, answer_question
from app.extraction import ExtractionError, extract_from_document
from app.plan_view import FIELD_MAP, from_plan_json, to_plan_json

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "hackathon-dev-secret-change-me")

# Frontend (Vercel) and backend (Render) are different origins, so the
# session cookie needs SameSite=None + Secure, and CORS needs an explicit
# origin list rather than "*" -- credentialed requests can't use a
# wildcard origin.
app.config["SESSION_COOKIE_SAMESITE"] = "None"
app.config["SESSION_COOKIE_SECURE"] = True

CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")
CORS(app, supports_credentials=True, origins=CORS_ORIGINS)

db_url = os.environ.get("DATABASE_URL", "sqlite:///intake.db")
# Render/Heroku-style URLs start with postgres://, SQLAlchemy wants postgresql://
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


class Session(db.Model):
    __tablename__ = "sessions"
    token = db.Column(db.String(36), primary_key=True)
    data = db.Column(db.JSON, nullable=False, default=dict)
    status = db.Column(db.String(20), nullable=False, default="in_progress")  # in_progress | completed
    # Flat frontend field keys (see app/plan_view.py FIELD_MAP) that came
    # from document extraction rather than manual entry -- drives whether
    # /api/extraction reports "verified" or "needs_confirmation".
    extracted_keys = db.Column(db.JSON, nullable=False, default=list)
    source_documents = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "token": self.token,
            "data": self.data,
            "status": self.status,
            "createdAt": self.created_at.isoformat() + "Z",
            "updatedAt": self.updated_at.isoformat() + "Z",
        }


def deep_merge(base, updates):
    """Merge partial updates into existing data without clobbering sibling fields."""
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def get_or_create_browser_session() -> Session:
    """emme-onboarding.html (the deployed frontend) has no concept of a
    session token -- it just calls /api/documents, /api/extraction,
    /api/plan directly, one implicit session per browser. Track that
    via a signed cookie, auto-creating the DB row on first hit."""
    token = browser_session.get("session_token")
    session = Session.query.get(token) if token else None
    if not session:
        token = str(uuid.uuid4())
        session = Session(token=token, data={}, extracted_keys=[], source_documents=[])
        db.session.add(session)
        db.session.commit()
        browser_session["session_token"] = token
    return session


# ---- Session lifecycle -----------------------------------------------------

@app.route("/api/session", methods=["POST"])
def create_session():
    token = str(uuid.uuid4())
    session = Session(token=token, data={})
    db.session.add(session)
    db.session.commit()
    return jsonify(session.to_dict()), 201


@app.route("/api/session/<token>", methods=["GET"])
def get_session(token):
    session = Session.query.get(token)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    return jsonify(session.to_dict())


# ---- Autosave ---------------------------------------------------------------
# Frontend calls this on blur/change with just the fields that changed, e.g.
# PATCH /api/session/<token>  { "identity": { "zipCode": "02116" } }

@app.route("/api/session/<token>", methods=["PATCH"])
def autosave_session(token):
    session = Session.query.get(token)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    if session.status == "completed":
        return jsonify({"error": "Session already finalized"}), 409

    updates = request.get_json(force=True) or {}
    merged = deep_merge(copy.deepcopy(session.data or {}), updates)
    session.data = merged
    db.session.commit()
    return jsonify(session.to_dict())


# ---- Confirmation summary ----------------------------------------------------
# Drives the "here's what we know about your plan" screen. Returns the raw
# data plus a flat list of anything still missing, so the frontend can flag gaps.

REQUIRED_FIELDS = {
    "identity": ["name", "email", "zipCode"],
    "planDetails": ["carrier", "planName", "metalTier", "planType"],
    "costSharing": ["deductibleIndividual", "oopMax", "monthlyPremium"],
}


@app.route("/api/session/<token>/summary", methods=["GET"])
def session_summary(token):
    session = Session.query.get(token)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    data = session.data or {}
    missing = []
    for section, fields in REQUIRED_FIELDS.items():
        section_data = data.get(section, {})
        for field in fields:
            if not section_data.get(field):
                missing.append(f"{section}.{field}")

    return jsonify({
        "data": data,
        "missingFields": missing,
        "isComplete": len(missing) == 0,
    })


# ---- Document upload / extraction -------------------------------------------
# Frontend: POST /api/session/<token>/documents, multipart field "file".
# Runs Gemini extraction, merges whatever fields it found into the session
# (never overwriting fields the member already filled in), and returns the
# updated session so the frontend can route extracted-but-uncertain fields
# to the confirm screen and everything else to manual entry.

ALLOWED_CONTENT_TYPES = {"application/pdf", "image/png", "image/jpeg"}


@app.route("/api/session/<token>/documents", methods=["POST"])
def upload_document(token):
    session = Session.query.get(token)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    file = request.files.get("file")
    if not file or file.content_type not in ALLOWED_CONTENT_TYPES:
        return jsonify({"error": f"Unsupported or missing file (got {file.content_type if file else None})"}), 400

    file_bytes = file.read()
    if not file_bytes:
        return jsonify({"error": "Uploaded file is empty"}), 400

    try:
        extracted = extract_from_document(file_bytes, file.content_type)
    except ExtractionError as e:
        # Not a server error -- frontend falls back to manual entry for
        # whatever wasn't extracted, per the graceful-fallback requirement.
        return jsonify({"error": f"Could not extract data from this document: {e}"}), 422

    extracted_shape = prune_nulls(to_session_shape(extracted))
    merged = deep_merge(copy.deepcopy(session.data or {}), extracted_shape)
    session.data = merged
    db.session.commit()
    return jsonify(session.to_dict())


# ---- Frontend contract routes (emme-onboarding.html) -------------------------
# No token in the URL -- one implicit session per browser, tracked via a
# signed cookie. See frontend/BACKEND_CONTRACT.md for the exact plan.json
# shape these must produce/accept.

@app.route("/api/documents", methods=["POST"])
def frontend_upload_documents():
    session = get_or_create_browser_session()
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files uploaded"}), 400

    uploaded_names = []
    source_documents = list(session.source_documents or [])
    extracted_keys = set(session.extracted_keys or [])
    merged_data = copy.deepcopy(session.data or {})

    for file in files:
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            continue
        file_bytes = file.read()
        if not file_bytes:
            continue
        try:
            extracted = extract_from_document(file_bytes, file.content_type)
        except ExtractionError:
            continue  # this file didn't extract; others may still succeed

        doc_type = "SBC" if "sbc" in (file.filename or "").lower() else "EOB"
        doc_id = f"d{len(source_documents) + 1}"
        source_documents.append({"id": doc_id, "filename": file.filename, "doc_type": doc_type})
        uploaded_names.append(file.filename)

        nested = prune_nulls(to_session_shape(extracted))
        merged_data = deep_merge(merged_data, nested)

        # Track which flat keys this extraction touched, for confidence tagging.
        for flat_key, (section, nested_key) in FIELD_MAP.items():
            if (nested.get(section) or {}).get(nested_key) is not None:
                extracted_keys.add(flat_key)

    session.data = merged_data
    session.extracted_keys = list(extracted_keys)
    session.source_documents = source_documents
    db.session.commit()

    if not uploaded_names:
        return jsonify({"error": "No file could be read (unsupported type or unreadable document)"}), 422
    return jsonify({"ok": True, "uploaded": uploaded_names})


@app.route("/api/extraction", methods=["GET"])
def frontend_get_extraction():
    session = get_or_create_browser_session()
    plan = to_plan_json(
        session.token,
        session.data or {},
        set(session.extracted_keys or []),
        session.source_documents or [],
    )
    plan["updated_at"] = session.updated_at.isoformat() + "Z"
    return jsonify(plan)


@app.route("/api/plan", methods=["GET"])
def frontend_get_plan():
    session = Session.query.get(browser_session.get("session_token")) if browser_session.get("session_token") else None
    if not session or not session.data:
        return jsonify(None)
    plan = to_plan_json(
        session.token,
        session.data or {},
        set(session.extracted_keys or []),
        session.source_documents or [],
    )
    plan["updated_at"] = session.updated_at.isoformat() + "Z"
    return jsonify(plan)


@app.route("/api/plan", methods=["PUT"])
def frontend_put_plan():
    session = get_or_create_browser_session()
    plan_json = request.get_json(force=True) or {}
    session.data = from_plan_json(plan_json)
    # Frontend is the source of truth once the user has touched a value
    # (per BACKEND_CONTRACT.md) -- clear extraction-confidence tracking so
    # everything reads as "verified" going forward.
    session.extracted_keys = []
    db.session.commit()
    return jsonify({"ok": True})


# ---- Plain-language chat widget ("Ask Emme") ----------------------------------
# Two callers, two shapes:
#   onboarding side panel: {"question": "..."}          -> {"answer": "..."}
#   compare page widget:   {"messages": [{role,content}]} -> {"reply": "..."}
# Independent of the intake/compare flow -- if this fails, the page must
# keep working on its own.

@app.route("/api/chat", methods=["POST"])
def chat():
    body = request.get_json(force=True) or {}

    if "messages" in body:
        messages = body.get("messages") or []
        if not messages:
            return jsonify({"error": "messages is required"}), 400
        session = get_or_create_browser_session()
        plan = to_plan_json(
            session.token, session.data or {}, set(session.extracted_keys or []), session.source_documents or []
        )
        try:
            return jsonify({"reply": answer_chat(messages, plan.get("fields"))})
        except Exception as e:
            app.logger.warning("chat failed: %s", e)
            return jsonify({"error": "The assistant is unavailable right now."}), 502

    question = (body.get("question") or "").strip()
    if not question:
        return jsonify({"error": "question or messages is required"}), 400
    return jsonify({"answer": answer_question(question)})


# ---- Finalize / structured export -------------------------------------------

@app.route("/api/session/<token>/finalize", methods=["POST"])
def finalize_session(token):
    session = Session.query.get(token)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    data = session.data or {}
    missing = []
    for section, fields in REQUIRED_FIELDS.items():
        section_data = data.get(section, {})
        for field in fields:
            if not section_data.get(field):
                missing.append(f"{section}.{field}")
    if missing:
        return jsonify({"error": "Cannot finalize, missing fields", "missingFields": missing}), 400

    session.status = "completed"
    db.session.commit()
    return jsonify(session.to_dict())


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(port=3000, debug=True)