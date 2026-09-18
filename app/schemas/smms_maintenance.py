from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SMMSMaintenanceBase(BaseModel):
    asset_id: int
    alert_id: int | None = None
    maintenance_type: str = Field(min_length=1, max_length=100)
    planned_date: datetime | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: str = Field(min_length=1, max_length=50)
    remarks: str | None = None


class SMMSMaintenanceCreate(SMMSMaintenanceBase):
    pass


class SMMSMaintenanceResponse(SMMSMaintenanceBase):
    id: int

    model_config = ConfigDict(from_attributes=True)