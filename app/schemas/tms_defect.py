from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TMSDefectBase(BaseModel):
    asset_id: int
    inspection_id: int
    defect_code: str = Field(min_length=1, max_length=100)
    defect_description: str | None = None
    severity: str | None = Field(default=None, max_length=50)
    detected_date: datetime | None = None
    status: str | None = Field(default=None, max_length=50)
    remarks: str | None = None


class TMSDefectCreate(TMSDefectBase):
    pass


class TMSDefectResponse(TMSDefectBase):
    id: int

    model_config = ConfigDict(from_attributes=True)