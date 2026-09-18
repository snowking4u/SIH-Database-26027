from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OperationalEventBase(BaseModel):
    train_id: int | None = None
    station_code: str | None = Field(default=None, max_length=50)
    event_type: str = Field(min_length=1, max_length=100)
    event_datetime: datetime
    description: str | None = None
    source_event_id: str | None = Field(default=None, max_length=100)
    remarks: str | None = None


class OperationalEventCreate(OperationalEventBase):
    pass


class OperationalEventResponse(OperationalEventBase):
    id: int

    model_config = ConfigDict(from_attributes=True)