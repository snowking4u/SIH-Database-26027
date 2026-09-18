from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.block_plan import BlockPlan
from app.models.block_plan_task import BlockPlanTask
from app.models.candidate_block_window import CandidateBlockWindow
from app.models.controller_decision import ControllerDecision
from app.models.execution_outcome import ExecutionOutcome
from app.models.optimization_input import OptimizationInput
from app.models.optimization_output import OptimizationOutput
from app.models.optimization_run import OptimizationRun
from app.models.plan_validation import PlanValidation
from app.models.planning_constraint import PlanningConstraint
from app.models.planning_resource import PlanningResource
from app.models.planning_task import PlanningTask
from app.models.task_dependency import TaskDependency
from app.schemas.block_plan import BlockPlanCreate, BlockPlanResponse
from app.schemas.block_plan_task import (
    BlockPlanTaskCreate,
    BlockPlanTaskResponse,
)
from app.schemas.controller_decision import (
    ControllerDecisionCreate,
    ControllerDecisionResponse,
)
from app.schemas.execution_outcome import (
    ExecutionOutcomeCreate,
    ExecutionOutcomeResponse,
)
from app.schemas.optimization_input import (
    OptimizationInputCreate,
    OptimizationInputResponse,
)
from app.schemas.optimization_output import (
    OptimizationOutputCreate,
    OptimizationOutputResponse,
)
from app.schemas.optimization_run import (
    OptimizationRunCreate,
    OptimizationRunResponse,
)
from app.schemas.plan_validation import (
    PlanValidationCreate,
    PlanValidationResponse,
)
from app.services.plan_validation import store_plan_validations


router = APIRouter(prefix="/api/optimization", tags=["Optimization Foundation"])


def require(db: Session, model, identifier: int, label: str):
    obj = db.get(model, identifier)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{label} not found",
        )
    return obj


# --------------------------------------------------------------------------- #
# Optimization run
# --------------------------------------------------------------------------- #
@router.get(
    "/runs",
    response_model=list[OptimizationRunResponse],
    summary="List optimization runs",
    description=(
        "Return optimization run lifecycle records. Filter by run_type, status, "
        "model_name or model_version. No optimization is executed."
    ),
)
def list_runs(
    run_type: str | None = None,
    status: str | None = None,
    model_name: str | None = None,
    model_version: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(OptimizationRun).order_by(OptimizationRun.id)
    if run_type is not None:
        statement = statement.where(OptimizationRun.run_type == run_type)
    if status is not None:
        statement = statement.where(OptimizationRun.status == status)
    if model_name is not None:
        statement = statement.where(OptimizationRun.model_name == model_name)
    if model_version is not None:
        statement = statement.where(OptimizationRun.model_version == model_version)
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.post(
    "/runs",
    response_model=OptimizationRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an optimization run",
    description=(
        "Create a lifecycle/storage record for a future optimization process. "
        "This does NOT run any optimizer."
    ),
)
def create_run(payload: OptimizationRunCreate, db: Session = Depends(get_db)):
    existing = db.scalar(
        select(OptimizationRun).where(OptimizationRun.run_code == payload.run_code)
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Optimization run code already exists",
        )
    run = OptimizationRun(**payload.model_dump())
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


@router.get(
    "/runs/{run_id}",
    response_model=OptimizationRunResponse,
    summary="Get an optimization run",
    description="Return one optimization run by internal identifier.",
)
def get_run(run_id: int, db: Session = Depends(get_db)):
    return require(db, OptimizationRun, run_id, "Optimization run")


# --------------------------------------------------------------------------- #
# Optimization input
# --------------------------------------------------------------------------- #
@router.get(
    "/inputs",
    response_model=list[OptimizationInputResponse],
    summary="List optimization inputs",
    description=(
        "Return planning inputs supplied to optimization runs. Filter by "
        "optimization_run_id, planning_task_id, candidate_block_window_id or "
        "input_role."
    ),
)
def list_inputs(
    optimization_run_id: int | None = None,
    planning_task_id: int | None = None,
    candidate_block_window_id: int | None = None,
    input_role: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(OptimizationInput).order_by(OptimizationInput.id)
    if optimization_run_id is not None:
        statement = statement.where(
            OptimizationInput.optimization_run_id == optimization_run_id
        )
    if planning_task_id is not None:
        statement = statement.where(
            OptimizationInput.planning_task_id == planning_task_id
        )
    if candidate_block_window_id is not None:
        statement = statement.where(
            OptimizationInput.candidate_block_window_id == candidate_block_window_id
        )
    if input_role is not None:
        statement = statement.where(OptimizationInput.input_role == input_role)
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.post(
    "/inputs",
    response_model=OptimizationInputResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an optimization input",
    description=(
        "Record a planning input reference for an optimization run. At least "
        "one planning reference must be populated."
    ),
)
def create_input(payload: OptimizationInputCreate, db: Session = Depends(get_db)):
    require(db, OptimizationRun, payload.optimization_run_id, "Optimization run")
    if payload.planning_task_id is not None:
        require(db, PlanningTask, payload.planning_task_id, "Planning task")
    if payload.candidate_block_window_id is not None:
        require(
            db,
            CandidateBlockWindow,
            payload.candidate_block_window_id,
            "Candidate block window",
        )
    if payload.planning_constraint_id is not None:
        require(
            db,
            PlanningConstraint,
            payload.planning_constraint_id,
            "Planning constraint",
        )
    if payload.planning_resource_id is not None:
        require(db, PlanningResource, payload.planning_resource_id, "Planning resource")
    if payload.task_dependency_id is not None:
        require(db, TaskDependency, payload.task_dependency_id, "Task dependency")

    record = OptimizationInput(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get(
    "/inputs/{input_id}",
    response_model=OptimizationInputResponse,
    summary="Get an optimization input",
    description="Return one optimization input by internal identifier.",
)
def get_input(input_id: int, db: Session = Depends(get_db)):
    return require(db, OptimizationInput, input_id, "Optimization input")


# --------------------------------------------------------------------------- #
# Optimization output
# --------------------------------------------------------------------------- #
@router.get(
    "/outputs",
    response_model=list[OptimizationOutputResponse],
    summary="List optimization outputs",
    description=(
        "Return stored optimization output records. Filter by "
        "optimization_run_id, planning_task_id, candidate_block_window_id, "
        "selected or output_type."
    ),
)
def list_outputs(
    optimization_run_id: int | None = None,
    planning_task_id: int | None = None,
    candidate_block_window_id: int | None = None,
    selected: bool | None = None,
    output_type: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(OptimizationOutput).order_by(OptimizationOutput.id)
    if optimization_run_id is not None:
        statement = statement.where(
            OptimizationOutput.optimization_run_id == optimization_run_id
        )
    if planning_task_id is not None:
        statement = statement.where(
            OptimizationOutput.planning_task_id == planning_task_id
        )
    if candidate_block_window_id is not None:
        statement = statement.where(
            OptimizationOutput.candidate_block_window_id == candidate_block_window_id
        )
    if selected is not None:
        statement = statement.where(OptimizationOutput.selected == selected)
    if output_type is not None:
        statement = statement.where(OptimizationOutput.output_type == output_type)
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.post(
    "/outputs",
    response_model=OptimizationOutputResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an optimization output",
    description=(
        "Store an optimization output record. This is a storage contract only; "
        "STEP 10 never generates an algorithmically optimized result."
    ),
)
def create_output(payload: OptimizationOutputCreate, db: Session = Depends(get_db)):
    require(db, OptimizationRun, payload.optimization_run_id, "Optimization run")
    if payload.planning_task_id is not None:
        require(db, PlanningTask, payload.planning_task_id, "Planning task")
    if payload.candidate_block_window_id is not None:
        require(
            db,
            CandidateBlockWindow,
            payload.candidate_block_window_id,
            "Candidate block window",
        )

    record = OptimizationOutput(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get(
    "/outputs/{output_id}",
    response_model=OptimizationOutputResponse,
    summary="Get an optimization output",
    description="Return one optimization output by internal identifier.",
)
def get_output(output_id: int, db: Session = Depends(get_db)):
    return require(db, OptimizationOutput, output_id, "Optimization output")


# --------------------------------------------------------------------------- #
# Block plan
# --------------------------------------------------------------------------- #
@router.get(
    "/plans",
    response_model=list[BlockPlanResponse],
    summary="List block plans",
    description=(
        "Return block plan proposals/versions. Filter by optimization_run_id, "
        "plan_date or status."
    ),
)
def list_plans(
    optimization_run_id: int | None = None,
    plan_date: date | None = None,
    status: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(BlockPlan).order_by(BlockPlan.id)
    if optimization_run_id is not None:
        statement = statement.where(
            BlockPlan.optimization_run_id == optimization_run_id
        )
    if plan_date is not None:
        statement = statement.where(BlockPlan.plan_date == plan_date)
    if status is not None:
        statement = statement.where(BlockPlan.status == status)
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.post(
    "/plans",
    response_model=BlockPlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a block plan",
    description=(
        "Create a planning proposal/version. Creating a plan does NOT approve "
        "it; only a controller_decision represents human approval."
    ),
)
def create_plan(payload: BlockPlanCreate, db: Session = Depends(get_db)):
    if payload.optimization_run_id is not None:
        require(db, OptimizationRun, payload.optimization_run_id, "Optimization run")
    existing = db.scalar(
        select(BlockPlan).where(BlockPlan.plan_code == payload.plan_code)
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Block plan code already exists",
        )
    plan = BlockPlan(**payload.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.get(
    "/plans/{plan_id}",
    response_model=BlockPlanResponse,
    summary="Get a block plan",
    description="Return one block plan by internal identifier.",
)
def get_plan(plan_id: int, db: Session = Depends(get_db)):
    return require(db, BlockPlan, plan_id, "Block plan")


@router.post(
    "/plans/{plan_id}/validate",
    response_model=list[PlanValidationResponse],
    status_code=status.HTTP_200_OK,
    summary="Run deterministic validation for a block plan",
    description=(
        "Run deterministic validation checks and persist plan_validation "
        "records. This never optimizes, ranks, approves or changes the plan "
        "status."
    ),
)
def validate_plan(plan_id: int, db: Session = Depends(get_db)):
    try:
        return store_plan_validations(db, plan_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Block plan not found",
        ) from None


# --------------------------------------------------------------------------- #
# Block plan task
# --------------------------------------------------------------------------- #
@router.get(
    "/plan-tasks",
    response_model=list[BlockPlanTaskResponse],
    summary="List block plan tasks",
    description=(
        "Return planning tasks placed into block plans. Filter by block_plan_id, "
        "planning_task_id, candidate_block_window_id or status."
    ),
)
def list_plan_tasks(
    block_plan_id: int | None = None,
    planning_task_id: int | None = None,
    candidate_block_window_id: int | None = None,
    status: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(BlockPlanTask).order_by(BlockPlanTask.id)
    if block_plan_id is not None:
        statement = statement.where(BlockPlanTask.block_plan_id == block_plan_id)
    if planning_task_id is not None:
        statement = statement.where(
            BlockPlanTask.planning_task_id == planning_task_id
        )
    if candidate_block_window_id is not None:
        statement = statement.where(
            BlockPlanTask.candidate_block_window_id == candidate_block_window_id
        )
    if status is not None:
        statement = statement.where(BlockPlanTask.status == status)
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.post(
    "/plan-tasks",
    response_model=BlockPlanTaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a block plan task",
    description=(
        "Place a planning task into a block plan. Values are supplied "
        "explicitly; STEP 10 never calculates or optimizes them. A planning task "
        "may appear at most once per block plan."
    ),
)
def create_plan_task(payload: BlockPlanTaskCreate, db: Session = Depends(get_db)):
    require(db, BlockPlan, payload.block_plan_id, "Block plan")
    require(db, PlanningTask, payload.planning_task_id, "Planning task")
    if payload.candidate_block_window_id is not None:
        require(
            db,
            CandidateBlockWindow,
            payload.candidate_block_window_id,
            "Candidate block window",
        )
    existing = db.scalar(
        select(BlockPlanTask).where(
            BlockPlanTask.block_plan_id == payload.block_plan_id,
            BlockPlanTask.planning_task_id == payload.planning_task_id,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Planning task already exists in this block plan",
        )
    plan_task = BlockPlanTask(**payload.model_dump())
    db.add(plan_task)
    db.commit()
    db.refresh(plan_task)
    return plan_task


@router.get(
    "/plan-tasks/{plan_task_id}",
    response_model=BlockPlanTaskResponse,
    summary="Get a block plan task",
    description="Return one block plan task by internal identifier.",
)
def get_plan_task(plan_task_id: int, db: Session = Depends(get_db)):
    return require(db, BlockPlanTask, plan_task_id, "Block plan task")


# --------------------------------------------------------------------------- #
# Plan validation
# --------------------------------------------------------------------------- #
@router.get(
    "/validations",
    response_model=list[PlanValidationResponse],
    summary="List plan validations",
    description=(
        "Return stored deterministic validation results. Filter by block_plan_id, "
        "validation_type or validation_status."
    ),
)
def list_validations(
    block_plan_id: int | None = None,
    validation_type: str | None = None,
    validation_status: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(PlanValidation).order_by(PlanValidation.id)
    if block_plan_id is not None:
        statement = statement.where(PlanValidation.block_plan_id == block_plan_id)
    if validation_type is not None:
        statement = statement.where(
            PlanValidation.validation_type == validation_type
        )
    if validation_status is not None:
        statement = statement.where(
            PlanValidation.validation_status == validation_status
        )
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.post(
    "/validations",
    response_model=PlanValidationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a plan validation record",
    description=(
        "Store a deterministic validation result for a block plan. No scores or "
        "AI confidence are stored."
    ),
)
def create_validation(payload: PlanValidationCreate, db: Session = Depends(get_db)):
    require(db, BlockPlan, payload.block_plan_id, "Block plan")
    record = PlanValidation(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get(
    "/validations/{validation_id}",
    response_model=PlanValidationResponse,
    summary="Get a plan validation",
    description="Return one plan validation by internal identifier.",
)
def get_validation(validation_id: int, db: Session = Depends(get_db)):
    return require(db, PlanValidation, validation_id, "Plan validation")


# --------------------------------------------------------------------------- #
# Controller decision
# --------------------------------------------------------------------------- #
@router.get(
    "/decisions",
    response_model=list[ControllerDecisionResponse],
    summary="List controller decisions",
    description="Return human review decisions. Filter by block_plan_id or decision.",
)
def list_decisions(
    block_plan_id: int | None = None,
    decision: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(ControllerDecision).order_by(ControllerDecision.id)
    if block_plan_id is not None:
        statement = statement.where(
            ControllerDecision.block_plan_id == block_plan_id
        )
    if decision is not None:
        statement = statement.where(ControllerDecision.decision == decision)
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.post(
    "/decisions",
    response_model=ControllerDecisionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a controller decision",
    description=(
        "Record a human decision on a block plan. This never automatically "
        "approves a plan and never changes plan status by itself."
    ),
)
def create_decision(payload: ControllerDecisionCreate, db: Session = Depends(get_db)):
    require(db, BlockPlan, payload.block_plan_id, "Block plan")
    record = ControllerDecision(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get(
    "/decisions/{decision_id}",
    response_model=ControllerDecisionResponse,
    summary="Get a controller decision",
    description="Return one controller decision by internal identifier.",
)
def get_decision(decision_id: int, db: Session = Depends(get_db)):
    return require(db, ControllerDecision, decision_id, "Controller decision")


# --------------------------------------------------------------------------- #
# Execution outcome
# --------------------------------------------------------------------------- #
@router.get(
    "/execution-outcomes",
    response_model=list[ExecutionOutcomeResponse],
    summary="List execution outcomes",
    description=(
        "Return execution outcome records. Filter by block_plan_id, "
        "block_plan_task_id or execution_status."
    ),
)
def list_execution_outcomes(
    block_plan_id: int | None = None,
    block_plan_task_id: int | None = None,
    execution_status: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(ExecutionOutcome).order_by(ExecutionOutcome.id)
    if block_plan_id is not None:
        statement = statement.where(ExecutionOutcome.block_plan_id == block_plan_id)
    if block_plan_task_id is not None:
        statement = statement.where(
            ExecutionOutcome.block_plan_task_id == block_plan_task_id
        )
    if execution_status is not None:
        statement = statement.where(
            ExecutionOutcome.execution_status == execution_status
        )
    return db.scalars(statement.offset(skip).limit(limit)).all()


@router.post(
    "/execution-outcomes",
    response_model=ExecutionOutcomeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an execution outcome",
    description=(
        "Record what actually happened after execution. STEP 10 never invents "
        "execution results."
    ),
)
def create_execution_outcome(
    payload: ExecutionOutcomeCreate, db: Session = Depends(get_db)
):
    require(db, BlockPlan, payload.block_plan_id, "Block plan")
    if payload.block_plan_task_id is not None:
        require(db, BlockPlanTask, payload.block_plan_task_id, "Block plan task")
    record = ExecutionOutcome(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get(
    "/execution-outcomes/{outcome_id}",
    response_model=ExecutionOutcomeResponse,
    summary="Get an execution outcome",
    description="Return one execution outcome by internal identifier.",
)
def get_execution_outcome(outcome_id: int, db: Session = Depends(get_db)):
    return require(db, ExecutionOutcome, outcome_id, "Execution outcome")
