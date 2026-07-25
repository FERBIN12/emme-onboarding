"""Primary document extraction path: turn an uploaded SBC/EOB (PDF or
image) into a partial IntakeData record, using Gemini vision.

    extract_from_document(file_bytes, media_type) -> IntakeData

Local Ollama (extraction.py) was tried first for privacy (nothing leaves
the laptop) but the vision models that actually fit in 6GB VRAM were
either unreliable (qwen2.5vl:3b degrades to garbage past page 1) or
useless (llava:7b returned nothing). Gemini was validated against the
real sample EOB and extracted every present field correctly.

Security/privacy safeguards, since this is health-plan data going to a
third party:

  1. Identity fields (name, email, zip code) are never sent. The prompt
     doesn't ask for them and the schema hint below omits the "identity"
     block entirely -- the member already types this into the form
     directly, so there's no reason to have Gemini read it off a
     document. This is the one safeguard worth actually coding: the most
     sensitive fields simply never leave the machine.
  2. Uploaded bytes are processed in memory only, never written to disk.
  3. The API key lives in an env var, never logged or hardcoded.
  4. Production note (for the pitch, not built today): a real deployment
     would route extraction through a BAA'd / HIPAA-compliant endpoint,
     or fall back to on-prem inference for real patient documents.
"""

import json
import os

from google import genai
from google.genai import types

from .schema import IntakeData

_MODEL = "gemini-flash-latest"

_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

# Deliberately excludes "identity" (name/email/zip) -- see module docstring.
_SCHEMA_HINT = """
Extract any of the following fields you can find in this insurance
document. It may be a Summary of Benefits and Coverage (SBC) or an
Explanation of Benefits (EOB) statement -- either is fine, just pull
whatever is actually present. Leave anything not present as null.

Do NOT extract or report any patient name, email address, or other
personal identifying information, even if visible in the document. Only
extract the plan/financial/clinical fields listed below.

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


def extract_from_document(file_bytes: bytes, media_type: str) -> IntakeData:
    """media_type: e.g. "application/pdf", "image/png", "image/jpeg".

    Gemini accepts PDFs directly, no page rasterization needed.
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
    if start == -1 or end == -1 or end < start:
        raise ValueError(
            f"Model response had no parseable JSON object (likely truncated). "
            f"Raw response: {raw_text[:300]!r}"
        )
    raw_text = raw_text[start : end + 1]

    data = json.loads(raw_text)
    return IntakeData.model_validate(data)
