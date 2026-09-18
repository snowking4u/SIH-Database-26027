from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TDMSMaintenanceBase(BaseModel):
    asset_id: int
    failure_id: int | None = None
    maintenance_type: str = Field(min_length=1, max_length=100)
    planned_date: datetime | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: str = Field(min_length=1, max_length=50)
    remarks: str | None = None


class TDMSMaintenanceCreate(TDMSMaintenanceBase):
    pass


class TDMSMaintenanceResponse(TDMSMaintenanceBase):
    id: int

    model_config = ConfigDict(from_attributes=True)