"""Shared data model for the Emme onboarding intake flow.

Every field is Optional: the flow supports partial completion (autosave,
skip-upload, graceful fallback), so nothing can be required at the model
level. "Is this submittable" is a separate check, not a schema constraint.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, BeforeValidator
from typing_extensions import Annotated


def _clean_money(v):
    """LLM extraction sometimes returns dollar-formatted strings like
    "$500.00" or "1,234.56" instead of a bare number. Strip formatting
    before Pydantic's float parser sees it."""
    if isinstance(v, str):
        v = v.replace("$", "").replace(",", "").strip()
        if v == "":
            return None
    return v


def _stringify(v):
    """Cost-sharing fields like coinsurance/copays are free-text ("20%",
    "$30 per visit") but the model sometimes returns a bare number when
    the document only shows a dollar amount. Normalize to string either way."""
    if v is None or isinstance(v, str):
        return v
    return str(v)


Money = Annotated[Optional[float], BeforeValidator(_clean_money)]
FlexibleText = Annotated[Optional[str], BeforeValidator(_stringify)]


class PlanType(str, Enum):
    HMO = "HMO"
    PPO = "PPO"
    EPO = "EPO"
    HDHP = "HDHP"


class PaymentMethod(str, Enum):
    CASH = "cash"
    INSURANCE = "insurance"


class Identity(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    zip_code: Optional[str] = None


class Household(BaseModel):
    household_size: Optional[int] = None
    income_range: Optional[str] = None
    filing_status: Optional[str] = None


class PlanDetails(BaseModel):
    carrier: Optional[str] = None
    plan_name: Optional[str] = None
    metal_tier: Optional[str] = None
    plan_type: Optional[PlanType] = None


class CostSharing(BaseModel):
    deductible_individual: Money = None
    deductible_family: Money = None
    ytd_deductible_met: Money = None
    oop_max: Money = None
    oop_met_ytd: Money = None
    copays: FlexibleText = None
    coinsurance: FlexibleText = None
    monthly_premium: Money = None


class HSA(BaseModel):
    hsa_eligible: Optional[bool] = None
    current_balance: Money = None
    ytd_contributions: Money = None
    employer_contribution: Money = None


class Prescription(BaseModel):
    drug_name: Optional[str] = None
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    payment_method: Optional[PaymentMethod] = None
    preferred_pharmacy: Optional[str] = None


class UpcomingCare(BaseModel):
    planned_procedures: Optional[str] = None
    chronic_conditions: Optional[str] = None
    pregnancy: Optional[bool] = None
    behavioral_health_needs: Optional[str] = None


class IntakeData(BaseModel):
    """The full onboarding record. One instance per session."""

    identity: Identity = Identity()
    household: Household = Household()
    plan_details: PlanDetails = PlanDetails()
    cost_sharing: CostSharing = CostSharing()
    hsa: HSA = HSA()
    prescriptions: list[Prescription] = []
    upcoming_care: UpcomingCare = UpcomingCare()
