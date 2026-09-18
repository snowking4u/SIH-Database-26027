from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TrainMovementBase(BaseModel):
    train_id: int
    station_code: str = Field(min_length=1, max_length=50)
    movement_flag: Literal["A", "D", "T"]
    movement_datetime: datetime
    line_number: str | None = Field(default=None, max_length=50)
    source_event_id: str | None = Field(default=None, max_length=100)
    remarks: str | None = None


class TrainMovementCreate(TrainMovementBase):
    pass


class TrainMovementResponse(TrainMovementBase):
    id: int

    model_config = ConfigDict(from_attributes=True)