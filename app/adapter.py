"""Converts extraction.py's IntakeData (snake_case, our schema) into the
camelCase session shape server.py/the frontend actually use. Kept as a
thin translation layer so extraction.py's already-QA'd prompt and schema
don't need to change to match the session storage's naming.

    to_session_shape(IntakeData) -> dict matching server.py's REQUIRED_FIELDS
    naming: identity.{name,email,zipCode}, planDetails.{carrier,planName,
    metalTier,planType}, costSharing.{deductibleIndividual,oopMax,
    monthlyPremium,...}
"""

from .schema import IntakeData


def to_session_shape(data: IntakeData) -> dict:
    return {
        "identity": {
            "name": data.identity.name,
            "email": data.identity.email,
            "zipCode": data.identity.zip_code,
        },
        "household": {
            "householdSize": data.household.household_size,
            "incomeRange": data.household.income_range,
            "filingStatus": data.household.filing_status,
        },
        "planDetails": {
            "carrier": data.plan_details.carrier,
            "planName": data.plan_details.plan_name,
            "metalTier": data.plan_details.metal_tier,
            "planType": data.plan_details.plan_type.value if data.plan_details.plan_type else None,
        },
        "costSharing": {
            "deductibleIndividual": data.cost_sharing.deductible_individual,
            "deductibleFamily": data.cost_sharing.deductible_family,
            "deductibleUsed": data.cost_sharing.ytd_deductible_met,
            "oopMax": data.cost_sharing.oop_max,
            "oopSpent": data.cost_sharing.oop_met_ytd,
            "copays": data.cost_sharing.copays,
            "coinsurance": data.cost_sharing.coinsurance,
            "monthlyPremium": data.cost_sharing.monthly_premium,
        },
        "hsa": {
            "hsaEligible": data.hsa.hsa_eligible,
            "currentBalance": data.hsa.current_balance,
            "ytdContributions": data.hsa.ytd_contributions,
            "employerContribution": data.hsa.employer_contribution,
        },
        "prescriptions": [
            {
                "drugName": p.drug_name,
                "dosage": p.dosage,
                "frequency": p.frequency,
                "paymentMethod": p.payment_method.value if p.payment_method else None,
                "preferredPharmacy": p.preferred_pharmacy,
            }
            for p in data.prescriptions
        ],
        "upcomingCare": {
            "plannedProcedures": data.upcoming_care.planned_procedures,
            "chronicConditions": data.upcoming_care.chronic_conditions,
            "pregnancy": data.upcoming_care.pregnancy,
            "behavioralHealthNeeds": data.upcoming_care.behavioral_health_needs,
        },
    }


def prune_nulls(d):
    """Drop null leaves so a PATCH-style deep_merge only fills gaps
    instead of overwriting existing session values with nulls."""
    if isinstance(d, dict):
        cleaned = {k: prune_nulls(v) for k, v in d.items()}
        return {k: v for k, v in cleaned.items() if v not in (None, {}, [])}
    return d
