from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TMSMaintenanceBase(BaseModel):
    asset_id: int
    defect_id: int
    maintenance_type: str = Field(min_length=1, max_length=100)
    planned_date: datetime | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: str | None = Field(default=None, max_length=50)
    remarks: str | None = None


class TMSMaintenanceCreate(TMSMaintenanceBase):
    pass


class TMSMaintenanceResponse(TMSMaintenanceBase):
    id: int

    model_config = ConfigDict(from_attributes=True)