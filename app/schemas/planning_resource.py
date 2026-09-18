from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PlanningResourceBase(BaseModel):
    resource_code: str = Field(min_length=1, max_length=100)
    resource_type: str = Field(min_length=1, max_length=50)
    resource_name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    capacity: float | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, max_length=50)
    status: str = Field(min_length=1, max_length=50)
    location_code: str | None = Field(default=None, max_length=100)
    source_system_id: int | None = None


class PlanningResourceCreate(PlanningResourceBase):
    pass


class PlanningResourceResponse(PlanningResourceBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)