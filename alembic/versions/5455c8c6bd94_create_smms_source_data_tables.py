"""create smms source data tables

Revision ID: 5455c8c6bd94
Revises: 955830817cbe
Create Date: 2026-09-17 22:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5455c8c6bd94'
down_revision: Union[str, Sequence[str], None] = '955830817cbe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "smms_inspection",
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
            name="fk_smms_inspection_asset_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_smms_inspection_asset_id",
        "smms_inspection",
        ["asset_id"],
        unique=False,
    )
    op.create_index(
        "ix_smms_inspection_inspection_date",
        "smms_inspection",
        ["inspection_date"],
        unique=False,
    )
    op.create_index(
        "ix_smms_inspection_asset_inspection_date",
        "smms_inspection",
        ["asset_id", "inspection_date"],
        unique=False,
    )

    op.create_table(
        "smms_alert",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("inspection_id", sa.Integer(), nullable=True),
        sa.Column("alert_type_code", sa.String(length=100), nullable=False),
        sa.Column("alert_feedback_code", sa.String(length=100), nullable=True),
        sa.Column("alert_status_code", sa.String(length=100), nullable=False),
        sa.Column("cause_code", sa.String(length=100), nullable=True),
        sa.Column("incidence_date_time", sa.DateTime(), nullable=False),
        sa.Column("rectification_date_time", sa.DateTime(), nullable=True),
        sa.Column("incidence_duration", sa.Interval(), nullable=True),
        sa.Column("alert_feedback_date_time", sa.DateTime(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("maintainer_name", sa.String(length=100), nullable=True),
        sa.Column("maintainer_designation", sa.String(length=100), nullable=True),
        sa.Column("maintainer_mobile", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["asset_master.id"],
            name="fk_smms_alert_asset_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["inspection_id"],
            ["smms_inspection.id"],
            name="fk_smms_alert_inspection_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_smms_alert_asset_id",
        "smms_alert",
        ["asset_id"],
        unique=False,
    )
    op.create_index(
        "ix_smms_alert_inspection_id",
        "smms_alert",
        ["inspection_id"],
        unique=False,
    )
    op.create_index(
        "ix_smms_alert_incidence_date_time",
        "smms_alert",
        ["incidence_date_time"],
        unique=False,
    )

    op.create_table(
        "smms_maintenance",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("alert_id", sa.Integer(), nullable=True),
        sa.Column("maintenance_type", sa.String(length=100), nullable=False),
        sa.Column("planned_date", sa.DateTime(), nullable=True),
        sa.Column("start_date", sa.DateTime(), nullable=True),
        sa.Column("end_date", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["asset_master.id"],
            name="fk_smms_maintenance_asset_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["alert_id"],
            ["smms_alert.id"],
            name="fk_smms_maintenance_alert_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_smms_maintenance_asset_id",
        "smms_maintenance",
        ["asset_id"],
        unique=False,
    )
    op.create_index(
        "ix_smms_maintenance_alert_id",
        "smms_maintenance",
        ["alert_id"],
        unique=False,
    )
    op.create_index(
        "ix_smms_maintenance_planned_date",
        "smms_maintenance",
        ["planned_date"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_smms_maintenance_planned_date", table_name="smms_maintenance")
    op.drop_index("ix_smms_maintenance_alert_id", table_name="smms_maintenance")
    op.drop_index("ix_smms_maintenance_asset_id", table_name="smms_maintenance")
    op.drop_table("smms_maintenance")

    op.drop_index("ix_smms_alert_incidence_date_time", table_name="smms_alert")
    op.drop_index("ix_smms_alert_inspection_id", table_name="smms_alert")
    op.drop_index("ix_smms_alert_asset_id", table_name="smms_alert")
    op.drop_table("smms_alert")

    op.drop_index("ix_smms_inspection_asset_inspection_date", table_name="smms_inspection")
    op.drop_index("ix_smms_inspection_inspection_date", table_name="smms_inspection")
    op.drop_index("ix_smms_inspection_asset_id", table_name="smms_inspection")
    op.drop_table("smms_inspection")