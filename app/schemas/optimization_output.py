from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

OutputType = Literal[
    "TASK_ASSIGNMENT",
    "WINDOW_ASSIGNMENT",
    "BLOCK_ASSIGNMENT",
    "UNASSIGNED_TASK",
    "PLAN_METADATA",
]
OutputStatus = Literal["PROPOSED", "REJECTED", "UNASSIGNED"]


class OptimizationOutputBase(BaseModel):
    optimization_run_id: int
    planning_task_id: int | None = None
    candidate_block_window_id: int | None = None
    output_type: OutputType
    output_status: OutputStatus
    selected: bool = False
    output_payload: dict | None = None


class OptimizationOutputCreate(OptimizationOutputBase):
    pass


class OptimizationOutputResponse(OptimizationOutputBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
