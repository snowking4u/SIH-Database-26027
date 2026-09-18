from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TaskResourceBase(BaseModel):
    planning_task_id: int
    planning_resource_id: int
    required_quantity: int = Field(gt=0)
    allocation_status: str = Field(min_length=1, max_length=50)
    remarks: str | None = None


class TaskResourceCreate(TaskResourceBase):
    pass


class TaskResourceResponse(TaskResourceBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)