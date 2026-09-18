from pydantic import BaseModel, ConfigDict, Field


class SourceSystemBase(BaseModel):
    system_code: str = Field(min_length=1, max_length=50)
    system_name: str = Field(min_length=1, max_length=100)
    description: str | None = None


class SourceSystemCreate(SourceSystemBase):
    pass


class SourceSystemResponse(SourceSystemBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
