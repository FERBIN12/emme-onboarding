"""Shared data model for the Emme onboarding intake flow.

Every field is Optional: the flow supports partial completion (autosave,
skip-upload, graceful fallback), so nothing can be required at the model
level. "Is this submittable" is a separate check, not a schema constraint.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel


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
    deductible_individual: Optional[float] = None
    deductible_family: Optional[float] = None
    ytd_deductible_met: Optional[float] = None
    oop_max: Optional[float] = None
    oop_met_ytd: Optional[float] = None
    copays: Optional[str] = None
    coinsurance: Optional[str] = None
    monthly_premium: Optional[float] = None


class HSA(BaseModel):
    hsa_eligible: Optional[bool] = None
    current_balance: Optional[float] = None
    ytd_contributions: Optional[float] = None
    employer_contribution: Optional[float] = None


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
