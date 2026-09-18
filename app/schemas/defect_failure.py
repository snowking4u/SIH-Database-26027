from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DefectFailureResponse(BaseModel):
    id: int
    asset_id: int
    source_system_id: int
    source_record_type: str
    source_record_id: int
    defect_code: str | None = None
    defect_description: str | None = None
    severity: str | None = None
    detected_at: datetime
    status: str
    rectified_at: datetime | None = None
    remarks: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)