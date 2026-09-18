from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.location import LocationMaster
from app.schemas.location import LocationCreate, LocationResponse


router = APIRouter(prefix="/api/locations", tags=["Locations"])


@router.get(
    "",
    response_model=list[LocationResponse],
    summary="List locations",
    description="Return unified project locations used by master assets.",
)
def list_locations(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(LocationMaster).order_by(LocationMaster.id).offset(skip).limit(limit)
    return db.scalars(statement).all()


@router.get(
    "/{location_id}",
    response_model=LocationResponse,
    summary="Get a location",
    description="Return one unified project location by its internal identifier.",
)
def get_location(location_id: int, db: Session = Depends(get_db)):
    location = db.get(LocationMaster, location_id)
    if location is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found",
        )

    return location


@router.post(
    "",
    response_model=LocationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a location",
    description=(
        "Create a unified project location record. These fields are project schema "
        "concepts, not a claim of exact production Indian Railways column names."
    ),
)
def create_location(payload: LocationCreate, db: Session = Depends(get_db)):
    location = LocationMaster(**payload.model_dump())
    db.add(location)
    db.commit()
    db.refresh(location)
    return location
