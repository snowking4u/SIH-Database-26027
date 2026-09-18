from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ExecutionStatus = Literal[
    "NOT_STARTED",
    "STARTED",
    "COMPLETED",
    "PARTIALLY_COMPLETED",
    "CANCELLED",
    "FAILED",
]


class ExecutionOutcomeBase(BaseModel):
    block_plan_id: int
    block_plan_task_id: int | None = None
    execution_status: ExecutionStatus
    actual_start: datetime | None = None
    actual_end: datetime | None = None
    actual_duration_minutes: int | None = Field(default=None, ge=0)
    outcome_code: str | None = Field(default=None, max_length=100)
    remarks: str | None = None


class ExecutionOutcomeCreate(ExecutionOutcomeBase):
    recorded_at: datetime | None = None

    @model_validator(mode="after")
    def validate_actual_range(self):
        if (
            self.actual_start is not None
            and self.actual_end is not None
            and self.actual_start >= self.actual_end
        ):
            raise ValueError("actual_start must be earlier than actual_end")
        return self


class ExecutionOutcomeResponse(ExecutionOutcomeBase):
    id: int
    recorded_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
