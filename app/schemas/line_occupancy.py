from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LineOccupancyBase(BaseModel):
    station_code: str = Field(min_length=1, max_length=50)
    line_number: str = Field(min_length=1, max_length=50)
    occupancy_start: datetime
    occupancy_end: datetime | None = None
    occupancy_status: str = Field(min_length=1, max_length=50)
    train_id: int | None = None
    source_event_id: str | None = Field(default=None, max_length=100)
    remarks: str | None = None


class LineOccupancyCreate(LineOccupancyBase):
    pass


class LineOccupancyResponse(LineOccupancyBase):
    id: int

    model_config = ConfigDict(from_attributes=True)