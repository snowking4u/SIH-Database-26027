from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.asset import AssetMaster
from app.models.tdms_failure import TDMSFailure
from app.models.tdms_inspection import TDMSInspection
from app.models.tdms_maintenance import TDMSMaintenance
from app.schemas.tdms_failure import TDMSFailureCreate, TDMSFailureResponse
from app.schemas.tdms_inspection import TDMSInspectionCreate, TDMSInspectionResponse
from app.schemas.tdms_maintenance import TDMSMaintenanceCreate, TDMSMaintenanceResponse


router = APIRouter(prefix="/api/tdms", tags=["TDMS Source Data"])


@router.get(
    "/inspections",
    response_model=list[TDMSInspectionResponse],
    tags=["TDMS Inspections"],
    summary="List TDMS inspections",
    description=(
        "Return TDMS inspection records (source data only, normalised parameter "
        "representation). Optionally filter by asset_id."
    ),
)
def list_tdms_inspections(
    asset_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(TDMSInspection).order_by(TDMSInspection.inspection_date.desc())
    if asset_id is not None:
        statement = statement.where(TDMSInspection.asset_id == asset_id)
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.get(
    "/inspections/{inspection_id}",
    response_model=TDMSInspectionResponse,
    tags=["TDMS Inspections"],
    summary="Get a TDMS inspection",
    description="Return one TDMS inspection record by internal identifier.",
)
def get_tdms_inspection(inspection_id: int, db: Session = Depends(get_db)):
    inspection = db.get(TDMSInspection, inspection_id)
    if inspection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="TDMS inspection not found",
        )

    return inspection


@router.post(
    "/inspections",
    response_model=TDMSInspectionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["TDMS Inspections"],
    summary="Create a TDMS inspection",
    description="Create a TDMS inspection record linked to a master asset.",
)
def create_tdms_inspection(
    payload: TDMSInspectionCreate,
    db: Session = Depends(get_db),
):
    asset = db.get(AssetMaster, payload.asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    inspection = TDMSInspection(**payload.model_dump())
    db.add(inspection)
    db.commit()
    db.refresh(inspection)
    return inspection


@router.get(
    "/failures",
    response_model=list[TDMSFailureResponse],
    tags=["TDMS Failures"],
    summary="List TDMS failures",
    description=(
        "Return TDMS failure records linked to master assets (optionally to an "
        "inspection). Optionally filter by asset_id."
    ),
)
def list_tdms_failures(
    asset_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(TDMSFailure).order_by(TDMSFailure.failure_date.desc())
    if asset_id is not None:
        statement = statement.where(TDMSFailure.asset_id == asset_id)
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.get(
    "/failures/{failure_id}",
    response_model=TDMSFailureResponse,
    tags=["TDMS Failures"],
    summary="Get a TDMS failure",
    description="Return one TDMS failure record by internal identifier.",
)
def get_tdms_failure(failure_id: int, db: Session = Depends(get_db)):
    failure = db.get(TDMSFailure, failure_id)
    if failure is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="TDMS failure not found",
        )

    return failure


@router.post(
    "/failures",
    response_model=TDMSFailureResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["TDMS Failures"],
    summary="Create a TDMS failure",
    description=(
        "Create a TDMS failure record linked to a master asset. inspection_id is "
        "optional when the failure is not linked to a particular inspection."
    ),
)
def create_tdms_failure(payload: TDMSFailureCreate, db: Session = Depends(get_db)):
    asset = db.get(AssetMaster, payload.asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    if payload.inspection_id is not None:
        inspection = db.get(TDMSInspection, payload.inspection_id)
        if inspection is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="TDMS inspection not found",
            )

    failure = TDMSFailure(**payload.model_dump())
    db.add(failure)
    db.commit()
    db.refresh(failure)
    return failure


@router.get(
    "/maintenance",
    response_model=list[TDMSMaintenanceResponse],
    tags=["TDMS Maintenance"],
    summary="List TDMS maintenance records",
    description=(
        "Return TDMS maintenance records linked to master assets (optionally to a "
        "failure). Optionally filter by asset_id."
    ),
)
def list_tdms_maintenance(
    asset_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(TDMSMaintenance).order_by(TDMSMaintenance.id)
    if asset_id is not None:
        statement = statement.where(TDMSMaintenance.asset_id == asset_id)
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.get(
    "/maintenance/{maintenance_id}",
    response_model=TDMSMaintenanceResponse,
    tags=["TDMS Maintenance"],
    summary="Get a TDMS maintenance record",
    description="Return one TDMS maintenance record by internal identifier.",
)
def get_tdms_maintenance(maintenance_id: int, db: Session = Depends(get_db)):
    maintenance = db.get(TDMSMaintenance, maintenance_id)
    if maintenance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="TDMS maintenance record not found",
        )

    return maintenance


@router.post(
    "/maintenance",
    response_model=TDMSMaintenanceResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["TDMS Maintenance"],
    summary="Create a TDMS maintenance record",
    description=(
        "Create a TDMS maintenance record linked to a master asset. failure_id is "
        "optional when the activity is not linked to a recorded failure. planned_date "
        "is source-captured planning information only."
    ),
)
def create_tdms_maintenance(
    payload: TDMSMaintenanceCreate,
    db: Session = Depends(get_db),
):
    asset = db.get(AssetMaster, payload.asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    if payload.failure_id is not None:
        failure = db.get(TDMSFailure, payload.failure_id)
        if failure is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="TDMS failure not found",
            )

    maintenance = TDMSMaintenance(**payload.model_dump())
    db.add(maintenance)
    db.commit()
    db.refresh(maintenance)
    return maintenance