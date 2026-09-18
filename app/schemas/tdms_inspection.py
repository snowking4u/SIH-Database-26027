from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TDMSInspectionBase(BaseModel):
    asset_id: int
    inspection_date: datetime
    inspection_type: str = Field(min_length=1, max_length=100)
    parameter_code: str = Field(min_length=1, max_length=100)
    parameter_value: str | None = None
    remarks: str | None = None


class TDMSInspectionCreate(TDMSInspectionBase):
    pass


class TDMSInspectionResponse(TDMSInspectionBase):
    id: int

    model_config = ConfigDict(from_attributes=True)