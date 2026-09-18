from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TrainBase(BaseModel):
    train_id: str = Field(min_length=1, max_length=100)
    train_number: str | None = Field(default=None, max_length=50)
    train_name: str | None = Field(default=None, max_length=150)
    schedule_date: datetime | None = None
    start_date: datetime | None = None
    loco_number: str | None = Field(default=None, max_length=50)
    direction: str | None = Field(default=None, max_length=50)
    source_system_id: int


class TrainCreate(TrainBase):
    pass


class TrainResponse(TrainBase):
    id: int
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)