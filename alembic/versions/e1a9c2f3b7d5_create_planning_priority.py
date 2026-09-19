"""create planning_priority (STEP 12 criticality & priority foundation)

Revision ID: e1a9c2f3b7d5
Revises: d2e6b9c4f1a7
Create Date: 2026-09-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1a9c2f3b7d5'
down_revision: Union[str, Sequence[str], None] = 'd2e6b9c4f1a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "planning_priority",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("planning_task_id", sa.Integer(), nullable=False),
        sa.Column("criticality_level", sa.String(length=20), nullable=False),
        sa.Column("urgency_level", sa.String(length=20), nullable=False),
        sa.Column("safety_impact", sa.String(length=20), nullable=False),
        sa.Column(
            "asset_availability_impact", sa.String(length=20), nullable=False
        ),
        sa.Column("traffic_impact", sa.String(length=20), nullable=False),
        sa.Column("failure_recurrence", sa.String(length=20), nullable=False),
        sa.Column("defect_age_days", sa.Integer(), nullable=False),
        sa.Column("priority_score", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("priority_band", sa.String(length=20), nullable=False),
        sa.Column("calculation_version", sa.String(length=50), nullable=False),
        sa.Column(
            "calculated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("calculation_reason", sa.Text(), nullable=True),
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
            ["planning_task_id"],
            ["planning_task.id"],
            name="fk_planning_priority_planning_task_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "planning_task_id",
            name="uq_planning_priority_planning_task",
        ),
        sa.CheckConstraint(
            "priority_score >= 0 AND priority_score <= 100",
            name="ck_planning_priority_score_range",
        ),
        sa.CheckConstraint(
            "defect_age_days >= 0",
            name="ck_planning_priority_defect_age_non_negative",
        ),
    )
    op.create_index(
        "ix_planning_priority_planning_task_id",
        "planning_priority",
        ["planning_task_id"],
        unique=False,
    )
    op.create_index(
        "ix_planning_priority_priority_score",
        "planning_priority",
        ["priority_score"],
        unique=False,
    )
    op.create_index(
        "ix_planning_priority_priority_band",
        "planning_priority",
        ["priority_band"],
        unique=False,
    )
    op.create_index(
        "ix_planning_priority_criticality_level",
        "planning_priority",
        ["criticality_level"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    for index in (
        "ix_planning_priority_criticality_level",
        "ix_planning_priority_priority_band",
        "ix_planning_priority_priority_score",
        "ix_planning_priority_planning_task_id",
    ):
        op.drop_index(index, table_name="planning_priority")
    op.drop_table("planning_priority")