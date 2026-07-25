"""Translates between the session's internal nested storage (what
server.py's Session model and /api/session/<token> use) and the flat
plan.json shape the frontend (emme-onboarding.html) actually reads and
writes, per frontend/BACKEND_CONTRACT.md.

Two directions:
    to_plan_json(session_data, extracted_keys, source_documents) -> plan.json
    from_plan_json(plan_json) -> session_data (nested, for storage)

extracted_keys is a set of flat field names that came from document
extraction rather than manual entry -- used to mark confidence as
"needs_confirmation" (extraction, per the contract's own guidance: "when
in doubt, send needs_confirmation rather than verified") vs. "verified"
(the member typed it in themselves).
"""

# Flat frontend key -> nested (section, key) in session storage.
FIELD_MAP = {
    "carrier": ("planDetails", "carrier"),
    "plan_name": ("planDetails", "planName"),
    "plan_type": ("planDetails", "planType"),
    "network": ("planDetails", "network"),
    "monthly_premium": ("costSharing", "monthlyPremium"),
    "deductible_individual": ("costSharing", "deductibleIndividual"),
    "deductible_used": ("costSharing", "deductibleUsed"),
    "oop_max_individual": ("costSharing", "oopMax"),
    "oop_spent": ("costSharing", "oopSpent"),
    "coinsurance": ("costSharing", "coinsurance"),
    "copay_primary": ("costSharing", "copayPrimary"),
    "copay_specialist": ("costSharing", "copaySpecialist"),
    "copay_urgent_care": ("costSharing", "copayUrgentCare"),
    "copay_er": ("costSharing", "copayEr"),
    "rx_generic": ("costSharing", "rxGeneric"),
    "hsa_eligible": ("hsa", "hsaEligible"),
}


def to_plan_json(session_token: str, session_data: dict, extracted_keys: set, source_documents: list) -> dict:
    fields = {}
    for flat_key, (section, nested_key) in FIELD_MAP.items():
        value = (session_data.get(section) or {}).get(nested_key)
        if value is None:
            fields[flat_key] = {"value": None, "confidence": "missing", "source": None}
        elif flat_key in extracted_keys:
            doc = source_documents[0] if source_documents else None
            fields[flat_key] = {
                "value": value,
                "confidence": "needs_confirmation",
                "source": {"doc_id": doc["id"], "doc_type": doc["doc_type"]} if doc else None,
            }
        else:
            fields[flat_key] = {"value": value, "confidence": "verified", "source": None}

    return {
        "session_id": session_token,
        "source_documents": source_documents,
        "fields": fields,
    }


def from_plan_json(plan_json: dict) -> dict:
    """Frontend PUTs the full plan.json back after edits. Convert to
    nested session storage shape."""
    session_data = {}
    fields = plan_json.get("fields", {})
    for flat_key, (section, nested_key) in FIELD_MAP.items():
        if flat_key not in fields:
            continue
        value = fields[flat_key].get("value")
        session_data.setdefault(section, {})[nested_key] = value
    return session_data
