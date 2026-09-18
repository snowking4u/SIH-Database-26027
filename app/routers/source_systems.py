from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.source_system import SourceSystem
from app.schemas.source_system import SourceSystemCreate, SourceSystemResponse


router = APIRouter(prefix="/api/source-systems", tags=["Source Systems"])


@router.get(
    "",
    response_model=list[SourceSystemResponse],
    summary="List source systems",
    description="Return Railway source systems configured for master data ingestion.",
)
def list_source_systems(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(SourceSystem).order_by(SourceSystem.id).offset(skip).limit(limit)
    return db.scalars(statement).all()


@router.get(
    "/{source_system_id}",
    response_model=SourceSystemResponse,
    summary="Get a source system",
    description="Return one source system by its internal identifier.",
)
def get_source_system(source_system_id: int, db: Session = Depends(get_db)):
    source_system = db.get(SourceSystem, source_system_id)
    if source_system is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source system not found",
        )

    return source_system


@router.post(
    "",
    response_model=SourceSystemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a source system",
    description="Create a source system such as TMS, TDMS, SMMS, or COA.",
)
def create_source_system(
    payload: SourceSystemCreate,
    db: Session = Depends(get_db),
):
    existing = db.scalar(
        select(SourceSystem).where(SourceSystem.system_code == payload.system_code)
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Source system code already exists",
        )

    source_system = SourceSystem(**payload.model_dump())
    db.add(source_system)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Source system code already exists",
        ) from None

    db.refresh(source_system)
    return source_system
