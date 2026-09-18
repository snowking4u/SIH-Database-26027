"""create tdms source data tables

Revision ID: 955830817cbe
Revises: 5c78fb8f4f64
Create Date: 2026-09-17 22:16:14.993463

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '955830817cbe'
down_revision: Union[str, Sequence[str], None] = '5c78fb8f4f64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tdms_inspection",
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
            name="fk_tdms_inspection_asset_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_tdms_inspection_asset_id",
        "tdms_inspection",
        ["asset_id"],
        unique=False,
    )
    op.create_index(
        "ix_tdms_inspection_inspection_date",
        "tdms_inspection",
        ["inspection_date"],
        unique=False,
    )
    op.create_index(
        "ix_tdms_inspection_asset_inspection_date",
        "tdms_inspection",
        ["asset_id", "inspection_date"],
        unique=False,
    )

    op.create_table(
        "tdms_failure",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("inspection_id", sa.Integer(), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=False),
        sa.Column("failure_description", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(length=50), nullable=True),
        sa.Column("failure_date", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("rectification_date", sa.DateTime(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["asset_master.id"],
            name="fk_tdms_failure_asset_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["inspection_id"],
            ["tdms_inspection.id"],
            name="fk_tdms_failure_inspection_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_tdms_failure_asset_id",
        "tdms_failure",
        ["asset_id"],
        unique=False,
    )
    op.create_index(
        "ix_tdms_failure_inspection_id",
        "tdms_failure",
        ["inspection_id"],
        unique=False,
    )
    op.create_index(
        "ix_tdms_failure_failure_date",
        "tdms_failure",
        ["failure_date"],
        unique=False,
    )

    op.create_table(
        "tdms_maintenance",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("failure_id", sa.Integer(), nullable=True),
        sa.Column("maintenance_type", sa.String(length=100), nullable=False),
        sa.Column("planned_date", sa.DateTime(), nullable=True),
        sa.Column("start_date", sa.DateTime(), nullable=True),
        sa.Column("end_date", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["asset_master.id"],
            name="fk_tdms_maintenance_asset_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["failure_id"],
            ["tdms_failure.id"],
            name="fk_tdms_maintenance_failure_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_tdms_maintenance_asset_id",
        "tdms_maintenance",
        ["asset_id"],
        unique=False,
    )
    op.create_index(
        "ix_tdms_maintenance_failure_id",
        "tdms_maintenance",
        ["failure_id"],
        unique=False,
    )
    op.create_index(
        "ix_tdms_maintenance_planned_date",
        "tdms_maintenance",
        ["planned_date"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_tdms_maintenance_planned_date", table_name="tdms_maintenance")
    op.drop_index("ix_tdms_maintenance_failure_id", table_name="tdms_maintenance")
    op.drop_index("ix_tdms_maintenance_asset_id", table_name="tdms_maintenance")
    op.drop_table("tdms_maintenance")

    op.drop_index("ix_tdms_failure_failure_date", table_name="tdms_failure")
    op.drop_index("ix_tdms_failure_inspection_id", table_name="tdms_failure")
    op.drop_index("ix_tdms_failure_asset_id", table_name="tdms_failure")
    op.drop_table("tdms_failure")

    op.drop_index("ix_tdms_inspection_asset_inspection_date", table_name="tdms_inspection")
    op.drop_index("ix_tdms_inspection_inspection_date", table_name="tdms_inspection")
    op.drop_index("ix_tdms_inspection_asset_id", table_name="tdms_inspection")
    op.drop_table("tdms_inspection")
