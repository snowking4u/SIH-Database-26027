from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.asset import AssetMaster
from app.models.tms_defect import TMSDefect
from app.models.tms_inspection import TMSInspection
from app.models.tms_maintenance import TMSMaintenance
from app.schemas.tms_defect import TMSDefectCreate, TMSDefectResponse
from app.schemas.tms_inspection import TMSInspectionCreate, TMSInspectionResponse
from app.schemas.tms_maintenance import TMSMaintenanceCreate, TMSMaintenanceResponse


router = APIRouter(prefix="/api/tms", tags=["TMS Source Data"])


@router.get(
    "/inspections",
    response_model=list[TMSInspectionResponse],
    tags=["TMS Inspections"],
    summary="List TMS inspections",
    description=(
        "Return TMS inspection records (source data only, normalised parameter "
        "representation). Optionally filter by asset_id."
    ),
)
def list_tms_inspections(
    asset_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(TMSInspection).order_by(TMSInspection.inspection_date.desc())
    if asset_id is not None:
        statement = statement.where(TMSInspection.asset_id == asset_id)
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.get(
    "/inspections/{inspection_id}",
    response_model=TMSInspectionResponse,
    tags=["TMS Inspections"],
    summary="Get a TMS inspection",
    description="Return one TMS inspection record by internal identifier.",
)
def get_tms_inspection(inspection_id: int, db: Session = Depends(get_db)):
    inspection = db.get(TMSInspection, inspection_id)
    if inspection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="TMS inspection not found",
        )

    return inspection


@router.post(
    "/inspections",
    response_model=TMSInspectionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["TMS Inspections"],
    summary="Create a TMS inspection",
    description="Create a TMS inspection record linked to a master asset.",
)
def create_tms_inspection(
    payload: TMSInspectionCreate,
    db: Session = Depends(get_db),
):
    asset = db.get(AssetMaster, payload.asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    inspection = TMSInspection(**payload.model_dump())
    db.add(inspection)
    db.commit()
    db.refresh(inspection)
    return inspection


@router.get(
    "/defects",
    response_model=list[TMSDefectResponse],
    tags=["TMS Defects"],
    summary="List TMS defects",
    description=(
        "Return TMS defect records linked to inspections and master assets. "
        "Optionally filter by asset_id."
    ),
)
def list_tms_defects(
    asset_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(TMSDefect).order_by(TMSDefect.id)
    if asset_id is not None:
        statement = statement.where(TMSDefect.asset_id == asset_id)
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.get(
    "/defects/{defect_id}",
    response_model=TMSDefectResponse,
    tags=["TMS Defects"],
    summary="Get a TMS defect",
    description="Return one TMS defect record by internal identifier.",
)
def get_tms_defect(defect_id: int, db: Session = Depends(get_db)):
    defect = db.get(TMSDefect, defect_id)
    if defect is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="TMS defect not found",
        )

    return defect


@router.post(
    "/defects",
    response_model=TMSDefectResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["TMS Defects"],
    summary="Create a TMS defect",
    description="Create a TMS defect record linked to an asset and its inspection.",
)
def create_tms_defect(payload: TMSDefectCreate, db: Session = Depends(get_db)):
    asset = db.get(AssetMaster, payload.asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    inspection = db.get(TMSInspection, payload.inspection_id)
    if inspection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="TMS inspection not found",
        )

    defect = TMSDefect(**payload.model_dump())
    db.add(defect)
    db.commit()
    db.refresh(defect)
    return defect


@router.get(
    "/maintenance",
    response_model=list[TMSMaintenanceResponse],
    tags=["TMS Maintenance"],
    summary="List TMS maintenance records",
    description=(
        "Return TMS maintenance records linked to defects and master assets. "
        "Optionally filter by asset_id."
    ),
)
def list_tms_maintenance(
    asset_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(TMSMaintenance).order_by(TMSMaintenance.id)
    if asset_id is not None:
        statement = statement.where(TMSMaintenance.asset_id == asset_id)
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.get(
    "/maintenance/{maintenance_id}",
    response_model=TMSMaintenanceResponse,
    tags=["TMS Maintenance"],
    summary="Get a TMS maintenance record",
    description="Return one TMS maintenance record by internal identifier.",
)
def get_tms_maintenance(maintenance_id: int, db: Session = Depends(get_db)):
    maintenance = db.get(TMSMaintenance, maintenance_id)
    if maintenance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="TMS maintenance record not found",
        )

    return maintenance


@router.post(
    "/maintenance",
    response_model=TMSMaintenanceResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["TMS Maintenance"],
    summary="Create a TMS maintenance record",
    description=(
        "Create a TMS maintenance record linked to a defect and a master asset. "
        "planned_date is source-captured planning information only."
    ),
)
def create_tms_maintenance(
    payload: TMSMaintenanceCreate,
    db: Session = Depends(get_db),
):
    asset = db.get(AssetMaster, payload.asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    defect = db.get(TMSDefect, payload.defect_id)
    if defect is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="TMS defect not found",
        )

    maintenance = TMSMaintenance(**payload.model_dump())
    db.add(maintenance)
    db.commit()
    db.refresh(maintenance)
    return maintenance