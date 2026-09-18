"""create planning foundation tables

Revision ID: a4f1c9b2e8d3
Revises: c3a9f2e8b1d4
Create Date: 2026-09-18 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4f1c9b2e8d3'
down_revision: Union[str, Sequence[str], None] = 'c3a9f2e8b1d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "planning_task",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("maintenance_requirement_id", sa.Integer(), nullable=False),
        sa.Column("block_requirement_id", sa.Integer(), nullable=True),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("task_code", sa.String(length=100), nullable=False),
        sa.Column("task_type", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("earliest_start", sa.DateTime(), nullable=True),
        sa.Column("latest_end", sa.DateTime(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("location_code", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["maintenance_requirement_id"],
            ["maintenance_requirement.id"],
            name="fk_planning_task_maintenance_requirement_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["block_requirement_id"],
            ["block_requirement.id"],
            name="fk_planning_task_block_requirement_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["asset_master.id"],
            name="fk_planning_task_asset_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "maintenance_requirement_id",
            name="uq_planning_task_maintenance_requirement",
        ),
    )
    op.create_index(
        "ix_planning_task_block_requirement_id",
        "planning_task",
        ["block_requirement_id"],
        unique=False,
    )
    op.create_index(
        "ix_planning_task_asset_id", "planning_task", ["asset_id"], unique=False
    )
    op.create_index(
        "ix_planning_task_task_code", "planning_task", ["task_code"], unique=False
    )
    op.create_index(
        "ix_planning_task_status", "planning_task", ["status"], unique=False
    )
    op.create_index(
        "ix_planning_task_earliest_start",
        "planning_task",
        ["earliest_start"],
        unique=False,
    )
    op.create_index(
        "ix_planning_task_latest_end",
        "planning_task",
        ["latest_end"],
        unique=False,
    )

    op.create_table(
        "planning_resource",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("resource_code", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("resource_name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("capacity", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("location_code", sa.String(length=100), nullable=True),
        sa.Column("source_system_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_system_id"],
            ["source_system.id"],
            name="fk_planning_resource_source_system_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_planning_resource_resource_code",
        "planning_resource",
        ["resource_code"],
        unique=True,
    )
    op.create_index(
        "ix_planning_resource_resource_type",
        "planning_resource",
        ["resource_type"],
        unique=False,
    )
    op.create_index(
        "ix_planning_resource_status", "planning_resource", ["status"], unique=False
    )
    op.create_index(
        "ix_planning_resource_location_code",
        "planning_resource",
        ["location_code"],
        unique=False,
    )

    op.create_table(
        "planning_constraint",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("planning_task_id", sa.Integer(), nullable=False),
        sa.Column("constraint_type", sa.String(length=50), nullable=False),
        sa.Column("constraint_value", sa.String(length=255), nullable=False),
        sa.Column("hard_constraint", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("effective_start", sa.DateTime(), nullable=True),
        sa.Column("effective_end", sa.DateTime(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["planning_task_id"],
            ["planning_task.id"],
            name="fk_planning_constraint_planning_task_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_planning_constraint_planning_task_id",
        "planning_constraint",
        ["planning_task_id"],
        unique=False,
    )
    op.create_index(
        "ix_planning_constraint_constraint_type",
        "planning_constraint",
        ["constraint_type"],
        unique=False,
    )
    op.create_index(
        "ix_planning_constraint_hard_constraint",
        "planning_constraint",
        ["hard_constraint"],
        unique=False,
    )
    op.create_index(
        "ix_planning_constraint_effective_start",
        "planning_constraint",
        ["effective_start"],
        unique=False,
    )
    op.create_index(
        "ix_planning_constraint_effective_end",
        "planning_constraint",
        ["effective_end"],
        unique=False,
    )

    op.create_table(
        "task_resource",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("planning_task_id", sa.Integer(), nullable=False),
        sa.Column("planning_resource_id", sa.Integer(), nullable=False),
        sa.Column("required_quantity", sa.Integer(), nullable=False),
        sa.Column("allocation_status", sa.String(length=50), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["planning_task_id"],
            ["planning_task.id"],
            name="fk_task_resource_planning_task_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["planning_resource_id"],
            ["planning_resource.id"],
            name="fk_task_resource_planning_resource_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "planning_task_id",
            "planning_resource_id",
            name="uq_task_resource_planning_task_resource",
        ),
    )
    op.create_index(
        "ix_task_resource_planning_task_id",
        "task_resource",
        ["planning_task_id"],
        unique=False,
    )
    op.create_index(
        "ix_task_resource_planning_resource_id",
        "task_resource",
        ["planning_resource_id"],
        unique=False,
    )

    op.create_table(
        "task_dependency",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("predecessor_task_id", sa.Integer(), nullable=False),
        sa.Column("successor_task_id", sa.Integer(), nullable=False),
        sa.Column("dependency_type", sa.String(length=50), nullable=False),
        sa.Column("lag_minutes", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["predecessor_task_id"],
            ["planning_task.id"],
            name="fk_task_dependency_predecessor_task_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["successor_task_id"],
            ["planning_task.id"],
            name="fk_task_dependency_successor_task_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "predecessor_task_id",
            "successor_task_id",
            "dependency_type",
            name="uq_task_dependency_predecessor_successor_type",
        ),
        sa.CheckConstraint(
            "predecessor_task_id <> successor_task_id",
            name="ck_task_dependency_predecessor_ne_successor",
        ),
        sa.CheckConstraint(
            "lag_minutes >= 0",
            name="ck_task_dependency_lag_minutes_non_negative",
        ),
    )
    op.create_index(
        "ix_task_dependency_predecessor_task_id",
        "task_dependency",
        ["predecessor_task_id"],
        unique=False,
    )
    op.create_index(
        "ix_task_dependency_successor_task_id",
        "task_dependency",
        ["successor_task_id"],
        unique=False,
    )
    op.create_index(
        "ix_task_dependency_dependency_type",
        "task_dependency",
        ["dependency_type"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_task_dependency_dependency_type", table_name="task_dependency"
    )
    op.drop_index(
        "ix_task_dependency_successor_task_id", table_name="task_dependency"
    )
    op.drop_index(
        "ix_task_dependency_predecessor_task_id", table_name="task_dependency"
    )
    op.drop_table("task_dependency")

    op.drop_index(
        "ix_task_resource_planning_resource_id", table_name="task_resource"
    )
    op.drop_index("ix_task_resource_planning_task_id", table_name="task_resource")
    op.drop_table("task_resource")

    op.drop_index(
        "ix_planning_constraint_effective_end", table_name="planning_constraint"
    )
    op.drop_index(
        "ix_planning_constraint_effective_start", table_name="planning_constraint"
    )
    op.drop_index(
        "ix_planning_constraint_hard_constraint", table_name="planning_constraint"
    )
    op.drop_index(
        "ix_planning_constraint_constraint_type", table_name="planning_constraint"
    )
    op.drop_index(
        "ix_planning_constraint_planning_task_id", table_name="planning_constraint"
    )
    op.drop_table("planning_constraint")

    op.drop_index(
        "ix_planning_resource_location_code", table_name="planning_resource"
    )
    op.drop_index("ix_planning_resource_status", table_name="planning_resource")
    op.drop_index(
        "ix_planning_resource_resource_type", table_name="planning_resource"
    )
    op.drop_index(
        "ix_planning_resource_resource_code", table_name="planning_resource"
    )
    op.drop_table("planning_resource")

    op.drop_index("ix_planning_task_latest_end", table_name="planning_task")
    op.drop_index("ix_planning_task_earliest_start", table_name="planning_task")
    op.drop_index("ix_planning_task_status", table_name="planning_task")
    op.drop_index("ix_planning_task_task_code", table_name="planning_task")
    op.drop_index("ix_planning_task_asset_id", table_name="planning_task")
    op.drop_index(
        "ix_planning_task_block_requirement_id", table_name="planning_task"
    )
    op.drop_table("planning_task")