from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.available_window import AvailableWindow
from app.models.line_occupancy import LineOccupancy
from app.models.operational_event import OperationalEvent
from app.models.source_system import SourceSystem
from app.models.train import Train
from app.models.train_movement import TrainMovement
from app.models.train_schedule import TrainSchedule
from app.schemas.available_window import AvailableWindowResponse
from app.schemas.line_occupancy import LineOccupancyCreate, LineOccupancyResponse
from app.schemas.operational_event import (
    OperationalEventCreate,
    OperationalEventResponse,
)
from app.schemas.train import TrainCreate, TrainResponse
from app.schemas.train_movement import TrainMovementCreate, TrainMovementResponse
from app.schemas.train_schedule import TrainScheduleCreate, TrainScheduleResponse
from app.services.available_window_derivation import derive_available_windows


router = APIRouter(prefix="/api/coa", tags=["COA/CTC Source Data"])


@router.get(
    "/trains",
    response_model=list[TrainResponse],
    tags=["COA Trains"],
    summary="List trains",
    description="Return COA train records. Optionally filter by train_id.",
)
def list_trains(
    train_id: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(Train).order_by(Train.id)
    if train_id is not None:
        statement = statement.where(Train.train_id == train_id)
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.get(
    "/trains/{train_id}",
    response_model=TrainResponse,
    tags=["COA Trains"],
    summary="Get a train",
    description="Return one COA train record by internal identifier.",
)
def get_train(train_id: int, db: Session = Depends(get_db)):
    train = db.get(Train, train_id)
    if train is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Train not found",
        )

    return train


@router.post(
    "/trains",
    response_model=TrainResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["COA Trains"],
    summary="Create a train",
    description=(
        "Create a COA train record referenced to a source system. created_at and "
        "updated_at are managed automatically."
    ),
)
def create_train(payload: TrainCreate, db: Session = Depends(get_db)):
    source_system = db.get(SourceSystem, payload.source_system_id)
    if source_system is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source system not found",
        )

    train = Train(**payload.model_dump())
    db.add(train)
    db.commit()
    db.refresh(train)
    return train


@router.get(
    "/movements",
    response_model=list[TrainMovementResponse],
    tags=["COA Movements"],
    summary="List train movements",
    description=(
        "Return recorded train movement events. Optionally filter by train_id or "
        "station_code."
    ),
)
def list_train_movements(
    train_id: int | None = None,
    station_code: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(TrainMovement).order_by(
        TrainMovement.movement_datetime.desc()
    )
    if train_id is not None:
        statement = statement.where(TrainMovement.train_id == train_id)
    if station_code is not None:
        statement = statement.where(TrainMovement.station_code == station_code)
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.get(
    "/movements/{movement_id}",
    response_model=TrainMovementResponse,
    tags=["COA Movements"],
    summary="Get a train movement",
    description="Return one recorded train movement by internal identifier.",
)
def get_train_movement(movement_id: int, db: Session = Depends(get_db)):
    movement = db.get(TrainMovement, movement_id)
    if movement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Train movement not found",
        )

    return movement


@router.post(
    "/movements",
    response_model=TrainMovementResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["COA Movements"],
    summary="Create a train movement",
    description=(
        "Create a recorded train movement event. movement_flag is a recorded "
        "operational value only (A = arrival, D = departure, T = run-through)."
    ),
)
def create_train_movement(
    payload: TrainMovementCreate,
    db: Session = Depends(get_db),
):
    train = db.get(Train, payload.train_id)
    if train is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Train not found",
        )

    movement = TrainMovement(**payload.model_dump())
    db.add(movement)
    db.commit()
    db.refresh(movement)
    return movement


@router.get(
    "/schedules",
    response_model=list[TrainScheduleResponse],
    tags=["COA Schedules"],
    summary="List train schedules",
    description=(
        "Return source timetable records. Optionally filter by train_id or "
        "station_code."
    ),
)
def list_train_schedules(
    train_id: int | None = None,
    station_code: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(TrainSchedule).order_by(TrainSchedule.sequence_number)
    if train_id is not None:
        statement = statement.where(TrainSchedule.train_id == train_id)
    if station_code is not None:
        statement = statement.where(TrainSchedule.station_code == station_code)
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.get(
    "/schedules/{schedule_id}",
    response_model=TrainScheduleResponse,
    tags=["COA Schedules"],
    summary="Get a train schedule record",
    description="Return one source timetable record by internal identifier.",
)
def get_train_schedule(schedule_id: int, db: Session = Depends(get_db)):
    schedule = db.get(TrainSchedule, schedule_id)
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Train schedule not found",
        )

    return schedule


@router.post(
    "/schedules",
    response_model=TrainScheduleResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["COA Schedules"],
    summary="Create a train schedule record",
    description="Create a source timetable record for a train.",
)
def create_train_schedule(
    payload: TrainScheduleCreate,
    db: Session = Depends(get_db),
):
    train = db.get(Train, payload.train_id)
    if train is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Train not found",
        )

    schedule = TrainSchedule(**payload.model_dump())
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


@router.get(
    "/line-occupancy",
    response_model=list[LineOccupancyResponse],
    tags=["COA Line Occupancy"],
    summary="List line occupancy records",
    description=(
        "Return recorded source line occupancy information. Optionally filter by "
        "station_code, line_number or train_id."
    ),
)
def list_line_occupancy(
    station_code: str | None = None,
    line_number: str | None = None,
    train_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(LineOccupancy).order_by(
        LineOccupancy.occupancy_start.desc()
    )
    if station_code is not None:
        statement = statement.where(LineOccupancy.station_code == station_code)
    if line_number is not None:
        statement = statement.where(LineOccupancy.line_number == line_number)
    if train_id is not None:
        statement = statement.where(LineOccupancy.train_id == train_id)
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.get(
    "/line-occupancy/{occupancy_id}",
    response_model=LineOccupancyResponse,
    tags=["COA Line Occupancy"],
    summary="Get a line occupancy record",
    description="Return one recorded source line occupancy by internal identifier.",
)
def get_line_occupancy(occupancy_id: int, db: Session = Depends(get_db)):
    occupancy = db.get(LineOccupancy, occupancy_id)
    if occupancy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Line occupancy not found",
        )

    return occupancy


@router.post(
    "/line-occupancy",
    response_model=LineOccupancyResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["COA Line Occupancy"],
    summary="Create a line occupancy record",
    description="Create a recorded source line occupancy record (optionally for a train).",
)
def create_line_occupancy(
    payload: LineOccupancyCreate,
    db: Session = Depends(get_db),
):
    if payload.train_id is not None:
        train = db.get(Train, payload.train_id)
        if train is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Train not found",
            )

    occupancy = LineOccupancy(**payload.model_dump())
    db.add(occupancy)
    db.commit()
    db.refresh(occupancy)
    return occupancy


@router.get(
    "/events",
    response_model=list[OperationalEventResponse],
    tags=["COA Operational Events"],
    summary="List operational events",
    description=(
        "Return recorded operational events. Optionally filter by train_id or "
        "station_code."
    ),
)
def list_operational_events(
    train_id: int | None = None,
    station_code: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(OperationalEvent).order_by(
        OperationalEvent.event_datetime.desc()
    )
    if train_id is not None:
        statement = statement.where(OperationalEvent.train_id == train_id)
    if station_code is not None:
        statement = statement.where(OperationalEvent.station_code == station_code)
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.get(
    "/events/{event_id}",
    response_model=OperationalEventResponse,
    tags=["COA Operational Events"],
    summary="Get an operational event",
    description="Return one recorded operational event by internal identifier.",
)
def get_operational_event(event_id: int, db: Session = Depends(get_db)):
    event = db.get(OperationalEvent, event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Operational event not found",
        )

    return event


@router.post(
    "/events",
    response_model=OperationalEventResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["COA Operational Events"],
    summary="Create an operational event",
    description="Create a recorded operational event (optionally linked to a train).",
)
def create_operational_event(
    payload: OperationalEventCreate,
    db: Session = Depends(get_db),
):
    if payload.train_id is not None:
        train = db.get(Train, payload.train_id)
        if train is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Train not found",
            )

    event = OperationalEvent(**payload.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get(
    "/available-windows",
    response_model=list[AvailableWindowResponse],
    tags=["COA Available Windows"],
    summary="List derived available windows",
    description=(
        "Return derived operational availability intervals. Optionally filter by "
        "station_code, line_number or window_status."
    ),
)
def list_available_windows(
    station_code: str | None = None,
    line_number: str | None = None,
    window_status: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(AvailableWindow).order_by(AvailableWindow.window_start)
    if station_code is not None:
        statement = statement.where(AvailableWindow.station_code == station_code)
    if line_number is not None:
        statement = statement.where(AvailableWindow.line_number == line_number)
    if window_status is not None:
        statement = statement.where(AvailableWindow.window_status == window_status)
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.get(
    "/available-windows/{window_id}",
    response_model=AvailableWindowResponse,
    tags=["COA Available Windows"],
    summary="Get a derived available window",
    description="Return one derived available window by internal identifier.",
)
def get_available_window(window_id: int, db: Session = Depends(get_db)):
    window = db.get(AvailableWindow, window_id)
    if window is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Available window not found",
        )

    return window


@router.post(
    "/available-windows/generate",
    response_model=list[AvailableWindowResponse],
    status_code=status.HTTP_200_OK,
    tags=["COA Available Windows"],
    summary="Generate derived available windows",
    description=(
        "Deterministically derive available windows from the currently available "
        "COA/CTC source data (train_schedule and line_occupancy). This is derived "
        "operational availability only, not an AI/ML output, not an optimisation "
        "and not a railway block approval. Source records are never modified."
    ),
)
def generate_available_windows(db: Session = Depends(get_db)):
    return derive_available_windows(db)