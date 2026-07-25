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
"""

import base64
import json

import anthropic

from .schema import IntakeData

_client = anthropic.Anthropic()

_MODEL = "claude-sonnet-5"

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
found -- do not guess or fabricate values):

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


def extract_from_document(file_bytes: bytes, media_type: str) -> IntakeData:
    """media_type: e.g. "application/pdf", "image/png", "image/jpeg"."""

    block_type = "document" if media_type == "application/pdf" else "image"

    response = _client.messages.create(
        model=_MODEL,
        max_tokens=2000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": block_type,
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64.b64encode(file_bytes).decode("utf-8"),
                        },
                    },
                    {"type": "text", "text": _SCHEMA_HINT},
                ],
            }
        ],
    )

    raw_text = response.content[0].text.strip()
    # Model may wrap JSON in a fenced code block; strip it defensively.
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    data = json.loads(raw_text)
    return IntakeData.model_validate(data)
