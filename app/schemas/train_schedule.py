from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TrainScheduleBase(BaseModel):
    train_id: int
    station_code: str = Field(min_length=1, max_length=50)
    scheduled_arrival: datetime | None = None
    scheduled_departure: datetime | None = None
    scheduled_run_through: datetime | None = None
    sequence_number: int
    line_number: str | None = Field(default=None, max_length=50)
    source_schedule_id: str | None = Field(default=None, max_length=100)
    remarks: str | None = None


class TrainScheduleCreate(TrainScheduleBase):
    pass


class TrainScheduleResponse(TrainScheduleBase):
    id: int

    model_config = ConfigDict(from_attributes=True)