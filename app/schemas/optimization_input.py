from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

InputRole = Literal[
    "TASK",
    "CANDIDATE_WINDOW",
    "CONSTRAINT",
    "RESOURCE",
    "DEPENDENCY",
]


class OptimizationInputBase(BaseModel):
    optimization_run_id: int
    planning_task_id: int | None = None
    candidate_block_window_id: int | None = None
    planning_constraint_id: int | None = None
    planning_resource_id: int | None = None
    task_dependency_id: int | None = None
    input_role: InputRole


class OptimizationInputCreate(OptimizationInputBase):
    @model_validator(mode="after")
    def require_at_least_one_reference(self):
        references = (
            self.planning_task_id,
            self.candidate_block_window_id,
            self.planning_constraint_id,
            self.planning_resource_id,
            self.task_dependency_id,
        )
        if all(reference is None for reference in references):
            raise ValueError(
                "at least one planning reference must be populated"
            )
        return self


class OptimizationInputResponse(OptimizationInputBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
