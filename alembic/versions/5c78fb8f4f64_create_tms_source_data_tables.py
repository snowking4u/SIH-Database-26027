"""create tms source data tables

Revision ID: 5c78fb8f4f64
Revises: 9eb1ebea7315
Create Date: 2026-09-17 22:06:50.001823

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c78fb8f4f64'
down_revision: Union[str, Sequence[str], None] = '9eb1ebea7315'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tms_inspection",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("inspection_date", sa.DateTime(), nullable=False),
        sa.Column("inspection_type", sa.String(length=100), nullable=False),
        sa.Column("parameter_code", sa.String(length=100), nullable=False),
        sa.Column("parameter_value", sa.Text(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["asset_master.id"],
            name="fk_tms_inspection_asset_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_tms_inspection_asset_id",
        "tms_inspection",
        ["asset_id"],
        unique=False,
    )
    op.create_index(
        "ix_tms_inspection_inspection_date",
        "tms_inspection",
        ["inspection_date"],
        unique=False,
    )

    op.create_table(
        "tms_defect",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("inspection_id", sa.Integer(), nullable=False),
        sa.Column("defect_code", sa.String(length=100), nullable=False),
        sa.Column("defect_description", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(length=50), nullable=True),
        sa.Column("detected_date", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["asset_master.id"],
            name="fk_tms_defect_asset_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["inspection_id"],
            ["tms_inspection.id"],
            name="fk_tms_defect_inspection_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_tms_defect_asset_id",
        "tms_defect",
        ["asset_id"],
        unique=False,
    )
    op.create_index(
        "ix_tms_defect_inspection_id",
        "tms_defect",
        ["inspection_id"],
        unique=False,
    )

    op.create_table(
        "tms_maintenance",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("defect_id", sa.Integer(), nullable=False),
        sa.Column("maintenance_type", sa.String(length=100), nullable=False),
        sa.Column("planned_date", sa.DateTime(), nullable=True),
        sa.Column("start_date", sa.DateTime(), nullable=True),
        sa.Column("end_date", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["asset_master.id"],
            name="fk_tms_maintenance_asset_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["defect_id"],
            ["tms_defect.id"],
            name="fk_tms_maintenance_defect_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_tms_maintenance_asset_id",
        "tms_maintenance",
        ["asset_id"],
        unique=False,
    )
    op.create_index(
        "ix_tms_maintenance_defect_id",
        "tms_maintenance",
        ["defect_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_tms_maintenance_defect_id", table_name="tms_maintenance")
    op.drop_index("ix_tms_maintenance_asset_id", table_name="tms_maintenance")
    op.drop_table("tms_maintenance")

    op.drop_index("ix_tms_defect_inspection_id", table_name="tms_defect")
    op.drop_index("ix_tms_defect_asset_id", table_name="tms_defect")
    op.drop_table("tms_defect")

    op.drop_index("ix_tms_inspection_inspection_date", table_name="tms_inspection")
    op.drop_index("ix_tms_inspection_asset_id", table_name="tms_inspection")
    op.drop_table("tms_inspection")
