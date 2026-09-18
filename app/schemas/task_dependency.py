from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TaskDependencyBase(BaseModel):
    predecessor_task_id: int
    successor_task_id: int
    dependency_type: str = Field(min_length=1, max_length=50)
    lag_minutes: int = Field(default=0, ge=0)
    description: str | None = None


class TaskDependencyCreate(TaskDependencyBase):
    @model_validator(mode="after")
    def reject_self_dependency(self):
        if self.predecessor_task_id == self.successor_task_id:
            raise ValueError("a task must not depend on itself")
        return self


class TaskDependencyResponse(TaskDependencyBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)