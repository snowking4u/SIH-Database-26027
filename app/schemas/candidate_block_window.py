from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CandidateBlockWindowBase(BaseModel):
    planning_task_id: int
    block_requirement_id: int | None = None
    available_window_id: int
    candidate_start: datetime
    candidate_end: datetime
    candidate_duration_minutes: int = Field(ge=0)
    feasible: bool
    feasibility_status: str
    feasibility_reason: str | None = None

    @model_validator(mode="after")
    def candidate_window_is_ordered(self):
        if self.candidate_end <= self.candidate_start:
            raise ValueError("candidate_end must be after candidate_start")
        return self


class CandidateBlockWindowResponse(CandidateBlockWindowBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CandidateCheckRequest(BaseModel):
    planning_task_id: int
    available_window_id: int


class CandidateCheckResponse(BaseModel):
    planning_task_id: int
    block_requirement_id: int | None = None
    available_window_id: int
    candidate_start: datetime
    candidate_end: datetime
    candidate_duration_minutes: int = Field(ge=0)
    feasible: bool
    feasibility_status: str
    feasibility_reason: str | None = None
    existing_candidate_id: int | None = None


class CandidateGenerationSummary(BaseModel):
    processed: int = 0
    created: int = 0
    skipped: int = 0
    infeasible: int = 0
    requires_review: int = 0