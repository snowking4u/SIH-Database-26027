from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AvailableWindowBase(BaseModel):
    station_code: str = Field(min_length=1, max_length=50)
    line_number: str = Field(min_length=1, max_length=50)
    window_start: datetime
    window_end: datetime
    duration_minutes: int
    window_status: str = Field(min_length=1, max_length=50)
    calculation_source: str = Field(min_length=1, max_length=200)
    generated_at: datetime
    source_schedule_id: int | None = None
    source_occupancy_id: int | None = None
    remarks: str | None = None


class AvailableWindowCreate(AvailableWindowBase):
    pass


class AvailableWindowResponse(AvailableWindowBase):
    id: int

    model_config = ConfigDict(from_attributes=True)