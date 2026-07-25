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
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

from app.adapter import prune_nulls, to_session_shape
from app.chatbot import answer_question
from app.extraction import ExtractionError, extract_from_document

app = Flask(__name__)
CORS(app)

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


# ---- Plain-language chat widget ----------------------------------------------
# Independent of the intake flow -- if this fails, the form must keep working.

@app.route("/api/chat", methods=["POST"])
def chat():
    body = request.get_json(force=True) or {}
    question = (body.get("question") or "").strip()
    if not question:
        return jsonify({"error": "question is required"}), 400
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