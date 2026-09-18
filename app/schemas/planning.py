from pydantic import BaseModel


class GenerateSummary(BaseModel):
    processed: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0