"""create optimization and block plan foundation tables

Revision ID: d2e6b9c4f1a7
Revises: b7a4c2e8d1f6
Create Date: 2026-09-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd2e6b9c4f1a7'
down_revision: Union[str, Sequence[str], None] = 'b7a4c2e8d1f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "optimization_run",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("run_code", sa.String(length=100), nullable=False),
        sa.Column("run_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("model_name", sa.String(length=150), nullable=True),
        sa.Column("model_version", sa.String(length=50), nullable=True),
        sa.Column("input_snapshot_hash", sa.String(length=128), nullable=True),
        sa.Column("output_snapshot_hash", sa.String(length=128), nullable=True),
        sa.Column("objective_description", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("run_code", name="uq_optimization_run_run_code"),
    )
    op.create_index(
        "ix_optimization_run_status",
        "optimization_run",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_optimization_run_run_type",
        "optimization_run",
        ["run_type"],
        unique=False,
    )
    op.create_index(
        "ix_optimization_run_requested_at",
        "optimization_run",
        ["requested_at"],
        unique=False,
    )

    op.create_table(
        "optimization_input",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("optimization_run_id", sa.Integer(), nullable=False),
        sa.Column("planning_task_id", sa.Integer(), nullable=True),
        sa.Column("candidate_block_window_id", sa.Integer(), nullable=True),
        sa.Column("planning_constraint_id", sa.Integer(), nullable=True),
        sa.Column("planning_resource_id", sa.Integer(), nullable=True),
        sa.Column("task_dependency_id", sa.Integer(), nullable=True),
        sa.Column("input_role", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["optimization_run_id"],
            ["optimization_run.id"],
            name="fk_optimization_input_optimization_run_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["planning_task_id"],
            ["planning_task.id"],
            name="fk_optimization_input_planning_task_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_block_window_id"],
            ["candidate_block_window.id"],
            name="fk_optimization_input_candidate_block_window_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["planning_constraint_id"],
            ["planning_constraint.id"],
            name="fk_optimization_input_planning_constraint_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["planning_resource_id"],
            ["planning_resource.id"],
            name="fk_optimization_input_planning_resource_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["task_dependency_id"],
            ["task_dependency.id"],
            name="fk_optimization_input_task_dependency_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_optimization_input_optimization_run_id",
        "optimization_input",
        ["optimization_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_optimization_input_planning_task_id",
        "optimization_input",
        ["planning_task_id"],
        unique=False,
    )
    op.create_index(
        "ix_optimization_input_candidate_block_window_id",
        "optimization_input",
        ["candidate_block_window_id"],
        unique=False,
    )
    op.create_index(
        "ix_optimization_input_input_role",
        "optimization_input",
        ["input_role"],
        unique=False,
    )

    op.create_table(
        "optimization_output",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("optimization_run_id", sa.Integer(), nullable=False),
        sa.Column("planning_task_id", sa.Integer(), nullable=True),
        sa.Column("candidate_block_window_id", sa.Integer(), nullable=True),
        sa.Column("output_type", sa.String(length=50), nullable=False),
        sa.Column("output_status", sa.String(length=50), nullable=False),
        sa.Column(
            "selected",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("output_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["optimization_run_id"],
            ["optimization_run.id"],
            name="fk_optimization_output_optimization_run_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["planning_task_id"],
            ["planning_task.id"],
            name="fk_optimization_output_planning_task_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_block_window_id"],
            ["candidate_block_window.id"],
            name="fk_optimization_output_candidate_block_window_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_optimization_output_optimization_run_id",
        "optimization_output",
        ["optimization_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_optimization_output_planning_task_id",
        "optimization_output",
        ["planning_task_id"],
        unique=False,
    )
    op.create_index(
        "ix_optimization_output_candidate_block_window_id",
        "optimization_output",
        ["candidate_block_window_id"],
        unique=False,
    )
    op.create_index(
        "ix_optimization_output_output_type",
        "optimization_output",
        ["output_type"],
        unique=False,
    )
    op.create_index(
        "ix_optimization_output_selected",
        "optimization_output",
        ["selected"],
        unique=False,
    )

    op.create_table(
        "block_plan",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("optimization_run_id", sa.Integer(), nullable=True),
        sa.Column("plan_code", sa.String(length=100), nullable=False),
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("planning_horizon_start", sa.DateTime(), nullable=False),
        sa.Column("planning_horizon_end", sa.DateTime(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["optimization_run_id"],
            ["optimization_run.id"],
            name="fk_block_plan_optimization_run_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("plan_code", name="uq_block_plan_plan_code"),
    )
    op.create_index(
        "ix_block_plan_optimization_run_id",
        "block_plan",
        ["optimization_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_block_plan_plan_date",
        "block_plan",
        ["plan_date"],
        unique=False,
    )
    op.create_index(
        "ix_block_plan_status",
        "block_plan",
        ["status"],
        unique=False,
    )

    op.create_table(
        "block_plan_task",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("block_plan_id", sa.Integer(), nullable=False),
        sa.Column("planning_task_id", sa.Integer(), nullable=False),
        sa.Column("candidate_block_window_id", sa.Integer(), nullable=True),
        sa.Column("planned_start", sa.DateTime(), nullable=False),
        sa.Column("planned_end", sa.DateTime(), nullable=False),
        sa.Column("planned_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["block_plan_id"],
            ["block_plan.id"],
            name="fk_block_plan_task_block_plan_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["planning_task_id"],
            ["planning_task.id"],
            name="fk_block_plan_task_planning_task_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_block_window_id"],
            ["candidate_block_window.id"],
            name="fk_block_plan_task_candidate_block_window_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "block_plan_id",
            "planning_task_id",
            name="uq_block_plan_task_plan_task",
        ),
        sa.CheckConstraint(
            "planned_start < planned_end",
            name="ck_block_plan_task_start_lt_end",
        ),
        sa.CheckConstraint(
            "planned_duration_minutes > 0",
            name="ck_block_plan_task_duration_positive",
        ),
    )
    op.create_index(
        "ix_block_plan_task_block_plan_id",
        "block_plan_task",
        ["block_plan_id"],
        unique=False,
    )
    op.create_index(
        "ix_block_plan_task_planning_task_id",
        "block_plan_task",
        ["planning_task_id"],
        unique=False,
    )
    op.create_index(
        "ix_block_plan_task_candidate_block_window_id",
        "block_plan_task",
        ["candidate_block_window_id"],
        unique=False,
    )
    op.create_index(
        "ix_block_plan_task_planned_start",
        "block_plan_task",
        ["planned_start"],
        unique=False,
    )
    op.create_index(
        "ix_block_plan_task_planned_end",
        "block_plan_task",
        ["planned_end"],
        unique=False,
    )
    op.create_index(
        "ix_block_plan_task_status",
        "block_plan_task",
        ["status"],
        unique=False,
    )

    op.create_table(
        "plan_validation",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("block_plan_id", sa.Integer(), nullable=False),
        sa.Column("validation_type", sa.String(length=50), nullable=False),
        sa.Column("validation_status", sa.String(length=50), nullable=False),
        sa.Column("validation_message", sa.Text(), nullable=True),
        sa.Column(
            "validated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("validator_version", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["block_plan_id"],
            ["block_plan.id"],
            name="fk_plan_validation_block_plan_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_plan_validation_block_plan_id",
        "plan_validation",
        ["block_plan_id"],
        unique=False,
    )
    op.create_index(
        "ix_plan_validation_validation_type",
        "plan_validation",
        ["validation_type"],
        unique=False,
    )
    op.create_index(
        "ix_plan_validation_validation_status",
        "plan_validation",
        ["validation_status"],
        unique=False,
    )

    op.create_table(
        "controller_decision",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("block_plan_id", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=50), nullable=False),
        sa.Column(
            "decided_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("controller_code", sa.String(length=100), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["block_plan_id"],
            ["block_plan.id"],
            name="fk_controller_decision_block_plan_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_controller_decision_block_plan_id",
        "controller_decision",
        ["block_plan_id"],
        unique=False,
    )
    op.create_index(
        "ix_controller_decision_decision",
        "controller_decision",
        ["decision"],
        unique=False,
    )
    op.create_index(
        "ix_controller_decision_decided_at",
        "controller_decision",
        ["decided_at"],
        unique=False,
    )

    op.create_table(
        "execution_outcome",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("block_plan_id", sa.Integer(), nullable=False),
        sa.Column("block_plan_task_id", sa.Integer(), nullable=True),
        sa.Column("execution_status", sa.String(length=50), nullable=False),
        sa.Column("actual_start", sa.DateTime(), nullable=True),
        sa.Column("actual_end", sa.DateTime(), nullable=True),
        sa.Column("actual_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("outcome_code", sa.String(length=100), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["block_plan_id"],
            ["block_plan.id"],
            name="fk_execution_outcome_block_plan_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["block_plan_task_id"],
            ["block_plan_task.id"],
            name="fk_execution_outcome_block_plan_task_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "actual_start IS NULL OR actual_end IS NULL OR actual_start < actual_end",
            name="ck_execution_outcome_actual_start_lt_end",
        ),
        sa.CheckConstraint(
            "actual_duration_minutes IS NULL OR actual_duration_minutes >= 0",
            name="ck_execution_outcome_actual_duration_non_negative",
        ),
    )
    op.create_index(
        "ix_execution_outcome_block_plan_id",
        "execution_outcome",
        ["block_plan_id"],
        unique=False,
    )
    op.create_index(
        "ix_execution_outcome_block_plan_task_id",
        "execution_outcome",
        ["block_plan_task_id"],
        unique=False,
    )
    op.create_index(
        "ix_execution_outcome_execution_status",
        "execution_outcome",
        ["execution_status"],
        unique=False,
    )
    op.create_index(
        "ix_execution_outcome_actual_start",
        "execution_outcome",
        ["actual_start"],
        unique=False,
    )
    op.create_index(
        "ix_execution_outcome_actual_end",
        "execution_outcome",
        ["actual_end"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    for index in (
        "ix_execution_outcome_actual_end",
        "ix_execution_outcome_actual_start",
        "ix_execution_outcome_execution_status",
        "ix_execution_outcome_block_plan_task_id",
        "ix_execution_outcome_block_plan_id",
    ):
        op.drop_index(index, table_name="execution_outcome")
    op.drop_table("execution_outcome")

    for index in (
        "ix_controller_decision_decided_at",
        "ix_controller_decision_decision",
        "ix_controller_decision_block_plan_id",
    ):
        op.drop_index(index, table_name="controller_decision")
    op.drop_table("controller_decision")

    for index in (
        "ix_plan_validation_validation_status",
        "ix_plan_validation_validation_type",
        "ix_plan_validation_block_plan_id",
    ):
        op.drop_index(index, table_name="plan_validation")
    op.drop_table("plan_validation")

    for index in (
        "ix_block_plan_task_status",
        "ix_block_plan_task_planned_end",
        "ix_block_plan_task_planned_start",
        "ix_block_plan_task_candidate_block_window_id",
        "ix_block_plan_task_planning_task_id",
        "ix_block_plan_task_block_plan_id",
    ):
        op.drop_index(index, table_name="block_plan_task")
    op.drop_table("block_plan_task")

    for index in (
        "ix_block_plan_status",
        "ix_block_plan_plan_date",
        "ix_block_plan_optimization_run_id",
    ):
        op.drop_index(index, table_name="block_plan")
    op.drop_table("block_plan")

    for index in (
        "ix_optimization_output_selected",
        "ix_optimization_output_output_type",
        "ix_optimization_output_candidate_block_window_id",
        "ix_optimization_output_planning_task_id",
        "ix_optimization_output_optimization_run_id",
    ):
        op.drop_index(index, table_name="optimization_output")
    op.drop_table("optimization_output")

    for index in (
        "ix_optimization_input_input_role",
        "ix_optimization_input_candidate_block_window_id",
        "ix_optimization_input_planning_task_id",
        "ix_optimization_input_optimization_run_id",
    ):
        op.drop_index(index, table_name="optimization_input")
    op.drop_table("optimization_input")

    for index in (
        "ix_optimization_run_requested_at",
        "ix_optimization_run_run_type",
        "ix_optimization_run_status",
    ):
        op.drop_index(index, table_name="optimization_run")
    op.drop_table("optimization_run")
