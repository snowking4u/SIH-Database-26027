from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

CriticalityLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
UrgencyLevel = Literal["LOW", "MEDIUM", "HIGH", "IMMEDIATE"]
ImpactLevel = Literal["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
RecurrenceLevel = Literal["NONE", "LOW", "MEDIUM", "HIGH"]
PriorityBand = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class PlanningPriorityResponse(BaseModel):
    """Read shape for a deterministic priority assessment."""

    id: int
    planning_task_id: int
    criticality_level: CriticalityLevel
    urgency_level: UrgencyLevel
    safety_impact: ImpactLevel
    asset_availability_impact: ImpactLevel
    traffic_impact: ImpactLevel
    failure_recurrence: RecurrenceLevel
    defect_age_days: int
    priority_score: float
    priority_band: PriorityBand
    calculation_version: str
    calculated_at: datetime
    calculation_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)