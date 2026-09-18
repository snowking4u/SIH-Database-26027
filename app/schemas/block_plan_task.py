from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

BlockPlanTaskStatus = Literal["PROPOSED", "CONFIRMED", "REMOVED", "COMPLETED"]


class BlockPlanTaskBase(BaseModel):
    block_plan_id: int
    planning_task_id: int
    candidate_block_window_id: int | None = None
    planned_start: datetime
    planned_end: datetime
    planned_duration_minutes: int = Field(gt=0)
    sequence_number: int | None = None
    status: BlockPlanTaskStatus
    remarks: str | None = None


class BlockPlanTaskCreate(BlockPlanTaskBase):
    @model_validator(mode="after")
    def validate_planned_range(self):
        if self.planned_start >= self.planned_end:
            raise ValueError("planned_start must be earlier than planned_end")
        return self


class BlockPlanTaskResponse(BlockPlanTaskBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
