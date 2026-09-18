from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.planning_constraint import PlanningConstraint
from app.models.planning_resource import PlanningResource
from app.models.planning_task import PlanningTask
from app.models.source_system import SourceSystem
from app.models.task_dependency import TaskDependency
from app.models.task_resource import TaskResource
from app.schemas.planning import GenerateSummary
from app.schemas.planning_constraint import (
    PlanningConstraintCreate,
    PlanningConstraintResponse,
)
from app.schemas.planning_resource import (
    PlanningResourceCreate,
    PlanningResourceResponse,
)
from app.schemas.planning_task import PlanningTaskResponse
from app.schemas.task_dependency import TaskDependencyCreate, TaskDependencyResponse
from app.schemas.task_resource import TaskResourceCreate, TaskResourceResponse
from app.services.planning_foundation import (
    generate_planning_constraints,
    generate_planning_tasks,
)


router = APIRouter(prefix="/api/planning", tags=["Planning Foundation"])


@router.get(
    "/tasks",
    response_model=list[PlanningTaskResponse],
    summary="List planning tasks",
    description=(
        "Return planning-ready maintenance tasks. Optionally filter by asset_id, "
        "maintenance_requirement_id or status."
    ),
)
def list_planning_tasks(
    asset_id: int | None = None,
    maintenance_requirement_id: int | None = None,
    status: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(PlanningTask).order_by(PlanningTask.id)
    if asset_id is not None:
        statement = statement.where(PlanningTask.asset_id == asset_id)
    if maintenance_requirement_id is not None:
        statement = statement.where(
            PlanningTask.maintenance_requirement_id == maintenance_requirement_id
        )
    if status is not None:
        statement = statement.where(PlanningTask.status == status)
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.get(
    "/tasks/{planning_task_id}",
    response_model=PlanningTaskResponse,
    summary="Get a planning task",
    description="Return one planning task by internal identifier.",
)
def get_planning_task(planning_task_id: int, db: Session = Depends(get_db)):
    task = db.get(PlanningTask, planning_task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Planning task not found",
        )
    return task


@router.get(
    "/constraints",
    response_model=list[PlanningConstraintResponse],
    summary="List planning constraints",
    description=(
        "Return constraints a planning algorithm must respect. Optionally filter "
        "by planning_task_id, constraint_type or hard_constraint."
    ),
)
def list_planning_constraints(
    planning_task_id: int | None = None,
    constraint_type: str | None = None,
    hard_constraint: bool | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(PlanningConstraint).order_by(PlanningConstraint.id)
    if planning_task_id is not None:
        statement = statement.where(
            PlanningConstraint.planning_task_id == planning_task_id
        )
    if constraint_type is not None:
        statement = statement.where(
            PlanningConstraint.constraint_type == constraint_type
        )
    if hard_constraint is not None:
        statement = statement.where(
            PlanningConstraint.hard_constraint == hard_constraint
        )
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.post(
    "/constraints",
    response_model=PlanningConstraintResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a planning constraint",
    description=(
        "Create a constraint that a planning algorithm must respect. This is a "
        "requirement, not an optimization result."
    ),
)
def create_planning_constraint(
    payload: PlanningConstraintCreate,
    db: Session = Depends(get_db),
):
    task = db.get(PlanningTask, payload.planning_task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Planning task not found",
        )

    constraint = PlanningConstraint(**payload.model_dump())
    db.add(constraint)
    db.commit()
    db.refresh(constraint)
    return constraint


@router.get(
    "/constraints/{constraint_id}",
    response_model=PlanningConstraintResponse,
    summary="Get a planning constraint",
    description="Return one planning constraint by internal identifier.",
)
def get_planning_constraint(constraint_id: int, db: Session = Depends(get_db)):
    constraint = db.get(PlanningConstraint, constraint_id)
    if constraint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Planning constraint not found",
        )
    return constraint


@router.get(
    "/resources",
    response_model=list[PlanningResourceResponse],
    summary="List planning resources",
    description=(
        "Return resources that may be required/available for maintenance planning. "
        "Optionally filter by resource_type, status or location_code."
    ),
)
def list_planning_resources(
    resource_type: str | None = None,
    status: str | None = None,
    location_code: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(PlanningResource).order_by(PlanningResource.id)
    if resource_type is not None:
        statement = statement.where(PlanningResource.resource_type == resource_type)
    if status is not None:
        statement = statement.where(PlanningResource.status == status)
    if location_code is not None:
        statement = statement.where(PlanningResource.location_code == location_code)
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.post(
    "/resources",
    response_model=PlanningResourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a planning resource",
    description=(
        "Create a planning resource. Resources may be manually maintained in this "
        "project; no external resource systems are integrated yet."
    ),
)
def create_planning_resource(
    payload: PlanningResourceCreate,
    db: Session = Depends(get_db),
):
    if payload.source_system_id is not None:
        source = db.get(SourceSystem, payload.source_system_id)
        if source is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source system not found",
            )

    existing = db.scalar(
        select(PlanningResource).where(
            PlanningResource.resource_code == payload.resource_code
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Planning resource code already exists",
        )

    resource = PlanningResource(**payload.model_dump())
    db.add(resource)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Planning resource code already exists",
        ) from None

    db.refresh(resource)
    return resource


@router.get(
    "/resources/{resource_id}",
    response_model=PlanningResourceResponse,
    summary="Get a planning resource",
    description="Return one planning resource by internal identifier.",
)
def get_planning_resource(resource_id: int, db: Session = Depends(get_db)):
    resource = db.get(PlanningResource, resource_id)
    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Planning resource not found",
        )
    return resource


@router.get(
    "/task-resources",
    response_model=list[TaskResourceResponse],
    summary="List task-resource links",
    description=(
        "Return many-to-many planning task / planning resource links. Optionally "
        "filter by planning_task_id or planning_resource_id."
    ),
)
def list_task_resources(
    planning_task_id: int | None = None,
    planning_resource_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(TaskResource).order_by(TaskResource.id)
    if planning_task_id is not None:
        statement = statement.where(TaskResource.planning_task_id == planning_task_id)
    if planning_resource_id is not None:
        statement = statement.where(
            TaskResource.planning_resource_id == planning_resource_id
        )
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.post(
    "/task-resources",
    response_model=TaskResourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a task-resource link",
    description=(
        "Link a planning task to a planning resource with a required quantity and "
        "allocation status. Assignment data only; not an optimized schedule."
    ),
)
def create_task_resource(
    payload: TaskResourceCreate,
    db: Session = Depends(get_db),
):
    task = db.get(PlanningTask, payload.planning_task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Planning task not found",
        )
    resource = db.get(PlanningResource, payload.planning_resource_id)
    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Planning resource not found",
        )

    existing = db.scalar(
        select(TaskResource).where(
            TaskResource.planning_task_id == payload.planning_task_id,
            TaskResource.planning_resource_id == payload.planning_resource_id,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task resource link already exists",
        )

    link = TaskResource(**payload.model_dump())
    db.add(link)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task resource link already exists",
        ) from None

    db.refresh(link)
    return link


@router.get(
    "/task-resources/{task_resource_id}",
    response_model=TaskResourceResponse,
    summary="Get a task-resource link",
    description="Return one task-resource link by internal identifier.",
)
def get_task_resource(task_resource_id: int, db: Session = Depends(get_db)):
    link = db.get(TaskResource, task_resource_id)
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task resource link not found",
        )
    return link


@router.get(
    "/dependencies",
    response_model=list[TaskDependencyResponse],
    summary="List task dependencies",
    description=(
        "Return ordering/dependency relationships between planning tasks. "
        "Optionally filter by predecessor_task_id or successor_task_id."
    ),
)
def list_task_dependencies(
    predecessor_task_id: int | None = None,
    successor_task_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(TaskDependency).order_by(TaskDependency.id)
    if predecessor_task_id is not None:
        statement = statement.where(
            TaskDependency.predecessor_task_id == predecessor_task_id
        )
    if successor_task_id is not None:
        statement = statement.where(
            TaskDependency.successor_task_id == successor_task_id
        )
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.post(
    "/dependencies",
    response_model=TaskDependencyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a task dependency",
    description=(
        "Create an ordering dependency between two planning tasks. A task must not "
        "depend on itself and duplicate dependencies are rejected."
    ),
)
def create_task_dependency(
    payload: TaskDependencyCreate,
    db: Session = Depends(get_db),
):
    predecessor = db.get(PlanningTask, payload.predecessor_task_id)
    if predecessor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Predecessor planning task not found",
        )
    successor = db.get(PlanningTask, payload.successor_task_id)
    if successor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Successor planning task not found",
        )

    existing = db.scalar(
        select(TaskDependency).where(
            TaskDependency.predecessor_task_id == payload.predecessor_task_id,
            TaskDependency.successor_task_id == payload.successor_task_id,
            TaskDependency.dependency_type == payload.dependency_type,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task dependency already exists",
        )

    dependency = TaskDependency(**payload.model_dump())
    db.add(dependency)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task dependency already exists",
        ) from None

    db.refresh(dependency)
    return dependency


@router.get(
    "/dependencies/{dependency_id}",
    response_model=TaskDependencyResponse,
    summary="Get a task dependency",
    description="Return one task dependency by internal identifier.",
)
def get_task_dependency(dependency_id: int, db: Session = Depends(get_db)):
    dependency = db.get(TaskDependency, dependency_id)
    if dependency is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task dependency not found",
        )
    return dependency


@router.post(
    "/generate-tasks",
    response_model=GenerateSummary,
    status_code=status.HTTP_200_OK,
    summary="Generate planning tasks",
    description=(
        "Deterministically create planning tasks from unified maintenance/"
        "block requirements. Idempotent; never modifies source/unified records; "
        "no AI, no optimization, no window assignment."
    ),
)
def generate_planning_task_records(db: Session = Depends(get_db)):
    return generate_planning_tasks(db)


@router.post(
    "/generate-constraints",
    response_model=GenerateSummary,
    status_code=status.HTTP_200_OK,
    summary="Generate planning constraints",
    description=(
        "Deterministically convert existing block requirement data into explicit "
        "planning constraint records. Idempotent; no constraints are invented "
        "where source data does not provide them."
    ),
)
def generate_planning_constraint_records(db: Session = Depends(get_db)):
    return generate_planning_constraints(db)