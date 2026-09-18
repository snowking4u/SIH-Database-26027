from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TDMSFailureBase(BaseModel):
    asset_id: int
    inspection_id: int | None = None
    failure_code: str = Field(min_length=1, max_length=100)
    failure_description: str | None = None
    severity: str | None = Field(default=None, max_length=50)
    failure_date: datetime
    status: str = Field(min_length=1, max_length=50)
    rectification_date: datetime | None = None
    remarks: str | None = None


class TDMSFailureCreate(TDMSFailureBase):
    pass


class TDMSFailureResponse(TDMSFailureBase):
    id: int

    model_config = ConfigDict(from_attributes=True)