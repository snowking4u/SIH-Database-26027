from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.asset import AssetMaster
from app.models.asset_parameter import AssetParameter
from app.models.location import LocationMaster
from app.models.source_system import SourceSystem
from app.schemas.asset import AssetCreate, AssetResponse
from app.schemas.asset_parameter import AssetParameterCreate, AssetParameterResponse


router = APIRouter(prefix="/api/assets", tags=["Assets"])


@router.get(
    "",
    response_model=list[AssetResponse],
    summary="List assets",
    description="Return unified master assets traceable to their source systems.",
)
def list_assets(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(AssetMaster).order_by(AssetMaster.id).offset(skip).limit(limit)
    return db.scalars(statement).all()


@router.get(
    "/{asset_id}",
    response_model=AssetResponse,
    summary="Get an asset",
    description="Return one unified master asset by its internal identifier.",
)
def get_asset(asset_id: int, db: Session = Depends(get_db)):
    asset = db.get(AssetMaster, asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    return asset


@router.post(
    "",
    response_model=AssetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an asset",
    description=(
        "Create a master asset linked to a source system and optionally a unified "
        "project location."
    ),
)
def create_asset(payload: AssetCreate, db: Session = Depends(get_db)):
    source_system = db.get(SourceSystem, payload.source_system_id)
    if source_system is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source system not found",
        )

    if payload.location_id is not None:
        location = db.get(LocationMaster, payload.location_id)
        if location is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Location not found",
            )

    existing = db.scalar(
        select(AssetMaster).where(
            AssetMaster.source_system_id == payload.source_system_id,
            AssetMaster.source_asset_id == payload.source_asset_id,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Asset already exists for this source system",
        )

    asset = AssetMaster(**payload.model_dump())
    db.add(asset)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Asset already exists for this source system",
        ) from None

    db.refresh(asset)
    return asset


@router.get(
    "/{asset_id}/parameters",
    response_model=list[AssetParameterResponse],
    summary="List asset parameters",
    description="Return flexible technical parameters recorded for one master asset.",
)
def list_asset_parameters(asset_id: int, db: Session = Depends(get_db)):
    asset = db.get(AssetMaster, asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    statement = (
        select(AssetParameter)
        .where(AssetParameter.asset_id == asset_id)
        .order_by(AssetParameter.id)
    )
    return db.scalars(statement).all()


@router.post(
    "/{asset_id}/parameters",
    response_model=AssetParameterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an asset parameter",
    description="Create a flexible technical parameter for one master asset.",
)
def create_asset_parameter(
    asset_id: int,
    payload: AssetParameterCreate,
    db: Session = Depends(get_db),
):
    asset = db.get(AssetMaster, asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    source_system = db.get(SourceSystem, payload.source_system_id)
    if source_system is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source system not found",
        )

    parameter = AssetParameter(asset_id=asset_id, **payload.model_dump())
    db.add(parameter)
    db.commit()
    db.refresh(parameter)
    return parameter
