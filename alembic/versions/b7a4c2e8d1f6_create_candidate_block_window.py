"""create candidate_block_window table

Revision ID: b7a4c2e8d1f6
Revises: a4f1c9b2e8d3
Create Date: 2026-09-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7a4c2e8d1f6'
down_revision: Union[str, Sequence[str], None] = 'a4f1c9b2e8d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "candidate_block_window",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("planning_task_id", sa.Integer(), nullable=False),
        sa.Column("block_requirement_id", sa.Integer(), nullable=True),
        sa.Column("available_window_id", sa.Integer(), nullable=False),
        sa.Column("candidate_start", sa.DateTime(), nullable=False),
        sa.Column("candidate_end", sa.DateTime(), nullable=False),
        sa.Column("candidate_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("feasible", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("feasibility_status", sa.String(length=50), nullable=False),
        sa.Column("feasibility_reason", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["planning_task_id"],
            ["planning_task.id"],
            name="fk_candidate_block_window_planning_task_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["block_requirement_id"],
            ["block_requirement.id"],
            name="fk_candidate_block_window_block_requirement_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["available_window_id"],
            ["available_window.id"],
            name="fk_candidate_block_window_available_window_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "planning_task_id",
            "available_window_id",
            name="uq_candidate_block_window_task_window",
        ),
        sa.CheckConstraint(
            "candidate_end > candidate_start",
            name="ck_candidate_block_window_end_gt_start",
        ),
        sa.CheckConstraint(
            "candidate_duration_minutes >= 0",
            name="ck_candidate_block_window_duration_non_negative",
        ),
    )
    op.create_index(
        "ix_candidate_block_window_planning_task_id",
        "candidate_block_window",
        ["planning_task_id"],
        unique=False,
    )
    op.create_index(
        "ix_candidate_block_window_block_requirement_id",
        "candidate_block_window",
        ["block_requirement_id"],
        unique=False,
    )
    op.create_index(
        "ix_candidate_block_window_available_window_id",
        "candidate_block_window",
        ["available_window_id"],
        unique=False,
    )
    op.create_index(
        "ix_candidate_block_window_feasible",
        "candidate_block_window",
        ["feasible"],
        unique=False,
    )
    op.create_index(
        "ix_candidate_block_window_feasibility_status",
        "candidate_block_window",
        ["feasibility_status"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_candidate_block_window_feasibility_status",
        table_name="candidate_block_window",
    )
    op.drop_index(
        "ix_candidate_block_window_feasible", table_name="candidate_block_window"
    )
    op.drop_index(
        "ix_candidate_block_window_available_window_id",
        table_name="candidate_block_window",
    )
    op.drop_index(
        "ix_candidate_block_window_block_requirement_id",
        table_name="candidate_block_window",
    )
    op.drop_index(
        "ix_candidate_block_window_planning_task_id",
        table_name="candidate_block_window",
    )
    op.drop_table("candidate_block_window")