from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PlanningTaskResponse(BaseModel):
    id: int
    maintenance_requirement_id: int
    block_requirement_id: int | None = None
    asset_id: int
    task_code: str
    task_type: str
    description: str | None = None
    status: str
    earliest_start: datetime | None = None
    latest_end: datetime | None = None
    duration_minutes: int
    location_code: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)