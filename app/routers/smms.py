from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.asset import AssetMaster
from app.models.smms_alert import SMMSAlert
from app.models.smms_inspection import SMMSInspection
from app.models.smms_maintenance import SMMSMaintenance
from app.schemas.smms_alert import SMMSAlertCreate, SMMSAlertResponse
from app.schemas.smms_inspection import SMMSInspectionCreate, SMMSInspectionResponse
from app.schemas.smms_maintenance import SMMSMaintenanceCreate, SMMSMaintenanceResponse


router = APIRouter(prefix="/api/smms", tags=["SMMS Source Data"])


@router.get(
    "/inspections",
    response_model=list[SMMSInspectionResponse],
    tags=["SMMS Inspections"],
    summary="List SMMS inspections",
    description=(
        "Return SMMS inspection records (source data only, normalised parameter "
        "representation). Optionally filter by asset_id."
    ),
)
def list_smms_inspections(
    asset_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(SMMSInspection).order_by(SMMSInspection.inspection_date.desc())
    if asset_id is not None:
        statement = statement.where(SMMSInspection.asset_id == asset_id)
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.get(
    "/inspections/{inspection_id}",
    response_model=SMMSInspectionResponse,
    tags=["SMMS Inspections"],
    summary="Get an SMMS inspection",
    description="Return one SMMS inspection record by internal identifier.",
)
def get_smms_inspection(inspection_id: int, db: Session = Depends(get_db)):
    inspection = db.get(SMMSInspection, inspection_id)
    if inspection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SMMS inspection not found",
        )

    return inspection


@router.post(
    "/inspections",
    response_model=SMMSInspectionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["SMMS Inspections"],
    summary="Create an SMMS inspection",
    description="Create an SMMS inspection record linked to a master asset.",
)
def create_smms_inspection(
    payload: SMMSInspectionCreate,
    db: Session = Depends(get_db),
):
    asset = db.get(AssetMaster, payload.asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    inspection = SMMSInspection(**payload.model_dump())
    db.add(inspection)
    db.commit()
    db.refresh(inspection)
    return inspection


@router.get(
    "/alerts",
    response_model=list[SMMSAlertResponse],
    tags=["SMMS Alerts"],
    summary="List SMMS alerts",
    description=(
        "Return SMMS alert records linked to master assets (optionally to an "
        "inspection). Optionally filter by asset_id."
    ),
)
def list_smms_alerts(
    asset_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(SMMSAlert).order_by(SMMSAlert.incidence_date_time.desc())
    if asset_id is not None:
        statement = statement.where(SMMSAlert.asset_id == asset_id)
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.get(
    "/alerts/{alert_id}",
    response_model=SMMSAlertResponse,
    tags=["SMMS Alerts"],
    summary="Get an SMMS alert",
    description="Return one SMMS alert record by internal identifier.",
)
def get_smms_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.get(SMMSAlert, alert_id)
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SMMS alert not found",
        )

    return alert


@router.post(
    "/alerts",
    response_model=SMMSAlertResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["SMMS Alerts"],
    summary="Create an SMMS alert",
    description=(
        "Create an SMMS alert record linked to a master asset. inspection_id is "
        "optional when the alert is not linked to a particular inspection."
    ),
)
def create_smms_alert(payload: SMMSAlertCreate, db: Session = Depends(get_db)):
    asset = db.get(AssetMaster, payload.asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    if payload.inspection_id is not None:
        inspection = db.get(SMMSInspection, payload.inspection_id)
        if inspection is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="SMMS inspection not found",
            )

    alert = SMMSAlert(**payload.model_dump())
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


@router.get(
    "/maintenance",
    response_model=list[SMMSMaintenanceResponse],
    tags=["SMMS Maintenance"],
    summary="List SMMS maintenance records",
    description=(
        "Return SMMS maintenance records linked to master assets (optionally to an "
        "alert). Optionally filter by asset_id."
    ),
)
def list_smms_maintenance(
    asset_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(SMMSMaintenance).order_by(SMMSMaintenance.id)
    if asset_id is not None:
        statement = statement.where(SMMSMaintenance.asset_id == asset_id)
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.get(
    "/maintenance/{maintenance_id}",
    response_model=SMMSMaintenanceResponse,
    tags=["SMMS Maintenance"],
    summary="Get an SMMS maintenance record",
    description="Return one SMMS maintenance record by internal identifier.",
)
def get_smms_maintenance(maintenance_id: int, db: Session = Depends(get_db)):
    maintenance = db.get(SMMSMaintenance, maintenance_id)
    if maintenance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SMMS maintenance record not found",
        )

    return maintenance


@router.post(
    "/maintenance",
    response_model=SMMSMaintenanceResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["SMMS Maintenance"],
    summary="Create an SMMS maintenance record",
    description=(
        "Create an SMMS maintenance record linked to a master asset. alert_id is "
        "optional when the activity is not linked to a recorded alert. planned_date "
        "is source-captured planning information only."
    ),
)
def create_smms_maintenance(
    payload: SMMSMaintenanceCreate,
    db: Session = Depends(get_db),
):
    asset = db.get(AssetMaster, payload.asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    if payload.alert_id is not None:
        alert = db.get(SMMSAlert, payload.alert_id)
        if alert is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="SMMS alert not found",
            )

    maintenance = SMMSMaintenance(**payload.model_dump())
    db.add(maintenance)
    db.commit()
    db.refresh(maintenance)
    return maintenance