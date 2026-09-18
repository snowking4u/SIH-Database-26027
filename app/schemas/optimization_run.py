from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RunType = Literal["PLANNING", "BACKTEST", "SIMULATION", "EVALUATION"]
RunStatus = Literal["REQUESTED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]


class OptimizationRunBase(BaseModel):
    run_code: str = Field(min_length=1, max_length=100)
    run_type: RunType
    status: RunStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    model_name: str | None = Field(default=None, max_length=150)
    model_version: str | None = Field(default=None, max_length=50)
    input_snapshot_hash: str | None = Field(default=None, max_length=128)
    output_snapshot_hash: str | None = Field(default=None, max_length=128)
    objective_description: str | None = None
    error_message: str | None = None


class OptimizationRunCreate(OptimizationRunBase):
    requested_at: datetime | None = None


class OptimizationRunResponse(OptimizationRunBase):
    id: int
    requested_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
