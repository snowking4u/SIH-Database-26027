from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.block_requirement import BlockRequirement
from app.models.defect_failure import DefectFailure
from app.models.maintenance_requirement import MaintenanceRequirement
from app.schemas.block_requirement import BlockRequirementCreate, BlockRequirementResponse
from app.schemas.defect_failure import DefectFailureResponse
from app.schemas.maintenance_requirement import MaintenanceRequirementResponse
from app.schemas.unified import NormalizeSummary
from app.services.unified_maintenance import (
    normalize_smms,
    normalize_tdms,
    normalize_tms,
)


router = APIRouter(prefix="/api/unified", tags=["Unified Maintenance Layer"])


@router.get(
    "/defects",
    response_model=list[DefectFailureResponse],
    tags=["Unified Defect/Failure"],
    summary="List unified defect/failure records",
    description=(
        "Return normalized defect/failure/alert records from TMS, TDMS and SMMS. "
        "Optionally filter by asset_id, source_system_id or status."
    ),
)
def list_defect_failures(
    asset_id: int | None = None,
    source_system_id: int | None = None,
    status: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(DefectFailure).order_by(DefectFailure.detected_at.desc())
    if asset_id is not None:
        statement = statement.where(DefectFailure.asset_id == asset_id)
    if source_system_id is not None:
        statement = statement.where(DefectFailure.source_system_id == source_system_id)
    if status is not None:
        statement = statement.where(DefectFailure.status == status)
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.get(
    "/defects/{defect_failure_id}",
    response_model=DefectFailureResponse,
    tags=["Unified Defect/Failure"],
    summary="Get a unified defect/failure record",
    description="Return one normalized defect/failure record by internal identifier.",
)
def get_defect_failure(defect_failure_id: int, db: Session = Depends(get_db)):
    record = db.get(DefectFailure, defect_failure_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Defect/failure record not found",
        )

    return record


@router.get(
    "/maintenance",
    response_model=list[MaintenanceRequirementResponse],
    tags=["Unified Maintenance Requirement"],
    summary="List unified maintenance requirements",
    description=(
        "Return normalized maintenance requirements from TMS, TDMS and SMMS. "
        "Optionally filter by asset_id, source_system_id or status."
    ),
)
def list_maintenance_requirements(
    asset_id: int | None = None,
    source_system_id: int | None = None,
    status: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(MaintenanceRequirement).order_by(MaintenanceRequirement.id)
    if asset_id is not None:
        statement = statement.where(
            MaintenanceRequirement.asset_id == asset_id
        )
    if source_system_id is not None:
        statement = statement.where(
            MaintenanceRequirement.source_system_id == source_system_id
        )
    if status is not None:
        statement = statement.where(MaintenanceRequirement.status == status)
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.get(
    "/maintenance/{maintenance_requirement_id}",
    response_model=MaintenanceRequirementResponse,
    tags=["Unified Maintenance Requirement"],
    summary="Get a unified maintenance requirement",
    description="Return one normalized maintenance requirement by internal identifier.",
)
def get_maintenance_requirement(
    maintenance_requirement_id: int, db: Session = Depends(get_db)
):
    record = db.get(MaintenanceRequirement, maintenance_requirement_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Maintenance requirement not found",
        )

    return record


@router.get(
    "/block-requirements",
    response_model=list[BlockRequirementResponse],
    tags=["Block Requirement"],
    summary="List block requirements",
    description=(
        "Return operational block requirement records (requirements only, not "
        "approved blocks). Optionally filter by station_code, line_number or status."
    ),
)
def list_block_requirements(
    station_code: str | None = None,
    line_number: str | None = None,
    status: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(BlockRequirement).order_by(BlockRequirement.id)
    if station_code is not None:
        statement = statement.where(BlockRequirement.station_code == station_code)
    if line_number is not None:
        statement = statement.where(BlockRequirement.line_number == line_number)
    if status is not None:
        statement = statement.where(BlockRequirement.status == status)
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.get(
    "/block-requirements/{block_requirement_id}",
    response_model=BlockRequirementResponse,
    tags=["Block Requirement"],
    summary="Get a block requirement",
    description="Return one block requirement record by internal identifier.",
)
def get_block_requirement(block_requirement_id: int, db: Session = Depends(get_db)):
    record = db.get(BlockRequirement, block_requirement_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Block requirement not found",
        )

    return record


@router.post(
    "/block-requirements",
    response_model=BlockRequirementResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Block Requirement"],
    summary="Create a block requirement",
    description=(
        "Create an operational block requirement linked to a unified maintenance "
        "requirement. This is a REQUIREMENT, not an approved or optimised block."
    ),
)
def create_block_requirement(
    payload: BlockRequirementCreate,
    db: Session = Depends(get_db),
):
    requirement = db.get(MaintenanceRequirement, payload.maintenance_requirement_id)
    if requirement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Maintenance requirement not found",
        )

    block_requirement = BlockRequirement(**payload.model_dump())
    db.add(block_requirement)
    db.commit()
    db.refresh(block_requirement)
    return block_requirement


@router.post(
    "/normalize/tms",
    response_model=NormalizeSummary,
    status_code=status.HTTP_200_OK,
    tags=["Unified Normalization"],
    summary="Normalize TMS source data",
    description=(
        "Deterministically normalize TMS defects and maintenance into the unified "
        "layer. Idempotent; source records are never modified; no AI/optimization."
    ),
)
def normalize_tms_records(db: Session = Depends(get_db)):
    try:
        return normalize_tms(db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from None


@router.post(
    "/normalize/tdms",
    response_model=NormalizeSummary,
    status_code=status.HTTP_200_OK,
    tags=["Unified Normalization"],
    summary="Normalize TDMS source data",
    description=(
        "Deterministically normalize TDMS failures and maintenance into the unified "
        "layer. Idempotent; source records are never modified; no AI/optimization."
    ),
)
def normalize_tdms_records(db: Session = Depends(get_db)):
    try:
        return normalize_tdms(db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from None


@router.post(
    "/normalize/smms",
    response_model=NormalizeSummary,
    status_code=status.HTTP_200_OK,
    tags=["Unified Normalization"],
    summary="Normalize SMMS source data",
    description=(
        "Deterministically normalize SMMS alerts and maintenance into the unified "
        "layer. Idempotent; source records are never modified; no AI/optimization."
    ),
)
def normalize_smms_records(db: Session = Depends(get_db)):
    try:
        return normalize_smms(db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from None