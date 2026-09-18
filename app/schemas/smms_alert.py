from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field


class SMMSAlertBase(BaseModel):
    asset_id: int
    inspection_id: int | None = None
    alert_type_code: str = Field(min_length=1, max_length=100)
    alert_feedback_code: str | None = Field(default=None, max_length=100)
    alert_status_code: str = Field(min_length=1, max_length=100)
    cause_code: str | None = Field(default=None, max_length=100)
    incidence_date_time: datetime
    rectification_date_time: datetime | None = None
    incidence_duration: timedelta | None = None
    alert_feedback_date_time: datetime | None = None
    remarks: str | None = None
    maintainer_name: str | None = Field(default=None, max_length=100)
    maintainer_designation: str | None = Field(default=None, max_length=100)
    maintainer_mobile: str | None = Field(default=None, max_length=50)


class SMMSAlertCreate(SMMSAlertBase):
    pass


class SMMSAlertResponse(SMMSAlertBase):
    id: int

    model_config = ConfigDict(from_attributes=True)