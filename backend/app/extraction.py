"""Document extraction: turn an uploaded SBC/EOB (PDF or image) into a
partial IntakeData record.

Contract with the rest of the backend (session/autosave, owned separately):
    extract_from_document(file_bytes, media_type) -> IntakeData

The returned IntakeData has only the fields the document actually contained;
everything else stays at its default (None / empty). The caller merges this
into the session's existing data and leaves untouched fields for manual
entry or later correction, per the "graceful fallback" requirement.

We deliberately do NOT try to classify the document as "SBC" vs "EOB" first.
An EOB only carries cost-sharing-to-date figures (deductible met, OOP met,
coinsurance) and identity/carrier info; an SBC carries the static plan
details (metal tier, plan type, premium) and HSA info. Asking the model to
extract "whatever of the full schema you can find" handles both uniformly
and matches the requirement that unextracted fields just fall through to
manual entry.

Runs against a local Ollama vision model (qwen2.5vl:7b) instead of a cloud
API, since real EOB/SBC documents carry PHI-adjacent data and the team
wanted extraction to never leave the laptop. Ollama's vision models take
images only, so PDFs are rasterized page-by-page with pdf2image first.
"""

import base64
import io
import json

import ollama
from pdf2image import convert_from_bytes

from .schema import IntakeData

_MODEL = "llava:7b"

_SCHEMA_HINT = """
Extract any of the following fields you can find in this insurance
document. It may be a Summary of Benefits and Coverage (SBC) or an
Explanation of Benefits (EOB) statement -- either is fine, just pull
whatever is actually present. Leave anything not present as null.

Watch for EOB-specific phrasing such as: "Amount approved", "Blue Cross
discount" (or other carrier discount), "Coinsurance you pay", "In-network
deductible applied to date", "In-network out-of-pocket maximum applied to
date", "Amount You Pay". These map to cost_sharing fields (ytd_deductible_met,
oop_met_ytd, coinsurance).

Watch for SBC-specific phrasing such as plan tier (Bronze/Silver/Gold/
Platinum), plan type (HMO/PPO/EPO/HDHP), monthly premium, deductible
(individual/family) as fixed plan terms, and HSA eligibility/contribution
details.

Return ONLY a JSON object with this exact shape (omit or null any field not
found -- do not guess or fabricate values), and nothing else -- no
markdown fences, no commentary:

{
  "identity": {"name": null, "email": null, "zip_code": null},
  "household": {"household_size": null, "income_range": null, "filing_status": null},
  "plan_details": {"carrier": null, "plan_name": null, "metal_tier": null, "plan_type": null},
  "cost_sharing": {
    "deductible_individual": null, "deductible_family": null,
    "ytd_deductible_met": null, "oop_max": null, "oop_met_ytd": null,
    "copays": null, "coinsurance": null, "monthly_premium": null
  },
  "hsa": {"hsa_eligible": null, "current_balance": null, "ytd_contributions": null, "employer_contribution": null},
  "prescriptions": [],
  "upcoming_care": {"planned_procedures": null, "chronic_conditions": null, "pregnancy": null, "behavioral_health_needs": null}
}

plan_type must be one of "HMO", "PPO", "EPO", "HDHP" or null -- infer from
context if the document names it, otherwise leave null. Never invent a
value that is not directly supported by the document text.
"""


def _pdf_to_page_images(file_bytes: bytes) -> list[bytes]:
    """Rasterize each PDF page to PNG bytes. Ollama vision models take
    images, not PDFs directly."""
    pages = convert_from_bytes(file_bytes, dpi=200)
    out = []
    for page in pages:
        buf = io.BytesIO()
        page.save(buf, format="PNG")
        out.append(buf.getvalue())
    return out


def _merge(base: dict, incoming: dict) -> dict:
    """Fill in only the fields base doesn't already have, first page wins
    on conflicts since page 1 usually carries the summary/identity info."""
    for key, value in incoming.items():
        if isinstance(value, dict):
            base.setdefault(key, {})
            base[key] = _merge(base[key], value)
        elif isinstance(value, list):
            if value and not base.get(key):
                base[key] = value
        else:
            if base.get(key) is None and value is not None:
                base[key] = value
    return base


def _call_model(image_bytes: bytes) -> dict:
    response = ollama.chat(
        model=_MODEL,
        messages=[
            {
                "role": "user",
                "content": _SCHEMA_HINT,
                "images": [base64.b64encode(image_bytes).decode("utf-8")],
            }
        ],
        options={"temperature": 0, "num_ctx": 4096},
    )

    raw_text = response["message"]["content"].strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    # Model may still add stray text around the JSON; take the outermost braces.
    start, end = raw_text.find("{"), raw_text.rfind("}")
    raw_text = raw_text[start : end + 1]

    return json.loads(raw_text)


def extract_from_document(file_bytes: bytes, media_type: str) -> IntakeData:
    """media_type: e.g. "application/pdf", "image/png", "image/jpeg"."""

    if media_type == "application/pdf":
        page_images = _pdf_to_page_images(file_bytes)
    else:
        page_images = [file_bytes]

    merged: dict = {}
    for image_bytes in page_images:
        page_result = _call_model(image_bytes)
        merged = _merge(merged, page_result)

    return IntakeData.model_validate(merged)
