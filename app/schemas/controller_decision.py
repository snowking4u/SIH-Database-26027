from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Decision = Literal["APPROVED", "REJECTED", "RETURNED_FOR_REVISION"]


class ControllerDecisionBase(BaseModel):
    block_plan_id: int
    decision: Decision
    controller_code: str | None = Field(default=None, max_length=100)
    remarks: str | None = None


class ControllerDecisionCreate(ControllerDecisionBase):
    decided_at: datetime | None = None


class ControllerDecisionResponse(ControllerDecisionBase):
    id: int
    decided_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
