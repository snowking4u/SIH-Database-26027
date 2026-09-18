from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AssetParameterBase(BaseModel):
    source_system_id: int
    parameter_code: str = Field(min_length=1, max_length=100)
    parameter_name: str | None = Field(default=None, max_length=150)
    parameter_value: str | None = None
    unit: str | None = Field(default=None, max_length=50)
    recorded_date: datetime | None = None


class AssetParameterCreate(AssetParameterBase):
    pass


class AssetParameterResponse(AssetParameterBase):
    id: int
    asset_id: int

    model_config = ConfigDict(from_attributes=True)
