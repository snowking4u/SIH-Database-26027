from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MaintenanceRequirementResponse(BaseModel):
    id: int
    asset_id: int
    source_system_id: int
    source_record_type: str
    source_record_id: int
    defect_failure_id: int | None = None
    maintenance_type: str
    description: str | None = None
    required_duration_minutes: int | None = None
    planned_date: datetime | None = None
    status: str
    remarks: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)