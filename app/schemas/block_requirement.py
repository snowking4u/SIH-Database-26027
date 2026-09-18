from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BlockRequirementBase(BaseModel):
    maintenance_requirement_id: int
    station_code: str | None = Field(default=None, max_length=50)
    line_number: str | None = Field(default=None, max_length=50)
    block_type: str = Field(min_length=1, max_length=50)
    required_duration_minutes: int | None = Field(default=None, gt=0)
    earliest_start: datetime | None = None
    latest_end: datetime | None = None
    power_block_required: bool = False
    traffic_block_required: bool = False
    resource_notes: str | None = None
    status: str = Field(min_length=1, max_length=50)
    remarks: str | None = None


class BlockRequirementCreate(BlockRequirementBase):
    @model_validator(mode="after")
    def validate_time_range(self):
        if (
            self.earliest_start is not None
            and self.latest_end is not None
            and self.earliest_start >= self.latest_end
        ):
            raise ValueError("earliest_start must be earlier than latest_end")
        return self


class BlockRequirementResponse(BlockRequirementBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)