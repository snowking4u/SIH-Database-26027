from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PlanningConstraintBase(BaseModel):
    planning_task_id: int
    constraint_type: str = Field(min_length=1, max_length=50)
    constraint_value: str = Field(min_length=1, max_length=255)
    hard_constraint: bool = True
    effective_start: datetime | None = None
    effective_end: datetime | None = None
    description: str | None = None
    source: str | None = Field(default=None, max_length=100)


class PlanningConstraintCreate(PlanningConstraintBase):
    @model_validator(mode="after")
    def validate_time_range(self):
        if (
            self.effective_start is not None
            and self.effective_end is not None
            and self.effective_start >= self.effective_end
        ):
            raise ValueError("effective_start must be earlier than effective_end")
        return self


class PlanningConstraintResponse(PlanningConstraintBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)