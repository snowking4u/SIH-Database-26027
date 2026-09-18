from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ValidationType = Literal[
    "TIME_CONFLICT",
    "WINDOW_FIT",
    "DURATION",
    "LOCATION",
    "LINE",
    "RESOURCE",
    "DEPENDENCY",
    "POWER_BLOCK",
    "TRAFFIC_BLOCK",
    "PLAN_COMPLETENESS",
    "GENERAL",
]
ValidationStatus = Literal["PASSED", "FAILED", "WARNING"]


class PlanValidationBase(BaseModel):
    block_plan_id: int
    validation_type: ValidationType
    validation_status: ValidationStatus
    validation_message: str | None = None
    validator_version: str | None = Field(default=None, max_length=50)


class PlanValidationCreate(PlanValidationBase):
    validated_at: datetime | None = None


class PlanValidationResponse(PlanValidationBase):
    id: int
    validated_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
