from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class AssetBase(BaseModel):
    source_system_id: int
    source_asset_id: str = Field(min_length=1, max_length=100)
    asset_type: str | None = Field(default=None, max_length=100)
    asset_subtype: str | None = Field(default=None, max_length=100)
    asset_name: str | None = Field(default=None, max_length=150)
    location_id: int | None = None
    installation_date: date | None = None
    status: str | None = Field(default=None, max_length=50)
    remarks: str | None = None


class AssetCreate(AssetBase):
    pass


class AssetResponse(AssetBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
