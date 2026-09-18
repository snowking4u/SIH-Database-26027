from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class LocationBase(BaseModel):
    zone_code: str | None = Field(default=None, max_length=50)
    zone_name: str | None = Field(default=None, max_length=100)
    division_code: str | None = Field(default=None, max_length=50)
    division_name: str | None = Field(default=None, max_length=100)
    section_code: str | None = Field(default=None, max_length=50)
    section_name: str | None = Field(default=None, max_length=100)
    station_code: str | None = Field(default=None, max_length=50)
    station_name: str | None = Field(default=None, max_length=100)
    line_code: str | None = Field(default=None, max_length=50)
    line_name: str | None = Field(default=None, max_length=100)
    km_start: Decimal | None = None
    km_end: Decimal | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None


class LocationCreate(LocationBase):
    pass


class LocationResponse(LocationBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
