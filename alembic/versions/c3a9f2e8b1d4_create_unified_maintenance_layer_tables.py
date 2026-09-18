"""create unified maintenance layer tables

Revision ID: c3a9f2e8b1d4
Revises: fba530afe681
Create Date: 2026-09-17 23:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3a9f2e8b1d4'
down_revision: Union[str, Sequence[str], None] = 'fba530afe681'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "defect_failure",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("source_system_id", sa.Integer(), nullable=False),
        sa.Column("source_record_type", sa.String(length=50), nullable=False),
        sa.Column("source_record_id", sa.Integer(), nullable=False),
        sa.Column("defect_code", sa.String(length=100), nullable=True),
        sa.Column("defect_description", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(length=50), nullable=True),
        sa.Column("detected_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("rectified_at", sa.DateTime(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["asset_master.id"],
            name="fk_defect_failure_asset_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_system_id"],
            ["source_system.id"],
            name="fk_defect_failure_source_system_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "source_system_id",
            "source_record_type",
            "source_record_id",
            name="uq_defect_failure_source",
        ),
    )
    op.create_index(
        "ix_defect_failure_asset_id", "defect_failure", ["asset_id"], unique=False
    )
    op.create_index(
        "ix_defect_failure_source_system_id",
        "defect_failure",
        ["source_system_id"],
        unique=False,
    )
    op.create_index(
        "ix_defect_failure_source_record_type",
        "defect_failure",
        ["source_record_type"],
        unique=False,
    )
    op.create_index(
        "ix_defect_failure_detected_at", "defect_failure", ["detected_at"], unique=False
    )
    op.create_index(
        "ix_defect_failure_status", "defect_failure", ["status"], unique=False
    )

    op.create_table(
        "maintenance_requirement",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("source_system_id", sa.Integer(), nullable=False),
        sa.Column("source_record_type", sa.String(length=50), nullable=False),
        sa.Column("source_record_id", sa.Integer(), nullable=False),
        sa.Column("defect_failure_id", sa.Integer(), nullable=True),
        sa.Column("maintenance_type", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("required_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("planned_date", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["asset_master.id"],
            name="fk_maintenance_requirement_asset_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_system_id"],
            ["source_system.id"],
            name="fk_maintenance_requirement_source_system_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["defect_failure_id"],
            ["defect_failure.id"],
            name="fk_maintenance_requirement_defect_failure_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "source_system_id",
            "source_record_type",
            "source_record_id",
            name="uq_maintenance_requirement_source",
        ),
    )
    op.create_index(
        "ix_maintenance_requirement_asset_id",
        "maintenance_requirement",
        ["asset_id"],
        unique=False,
    )
    op.create_index(
        "ix_maintenance_requirement_source_system_id",
        "maintenance_requirement",
        ["source_system_id"],
        unique=False,
    )
    op.create_index(
        "ix_maintenance_requirement_defect_failure_id",
        "maintenance_requirement",
        ["defect_failure_id"],
        unique=False,
    )
    op.create_index(
        "ix_maintenance_requirement_planned_date",
        "maintenance_requirement",
        ["planned_date"],
        unique=False,
    )
    op.create_index(
        "ix_maintenance_requirement_status",
        "maintenance_requirement",
        ["status"],
        unique=False,
    )

    op.create_table(
        "block_requirement",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("maintenance_requirement_id", sa.Integer(), nullable=False),
        sa.Column("station_code", sa.String(length=50), nullable=True),
        sa.Column("line_number", sa.String(length=50), nullable=True),
        sa.Column("block_type", sa.String(length=50), nullable=False),
        sa.Column("required_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("earliest_start", sa.DateTime(), nullable=True),
        sa.Column("latest_end", sa.DateTime(), nullable=True),
        sa.Column("power_block_required", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("traffic_block_required", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("resource_notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["maintenance_requirement_id"],
            ["maintenance_requirement.id"],
            name="fk_block_requirement_maintenance_requirement_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_block_requirement_maintenance_requirement_id",
        "block_requirement",
        ["maintenance_requirement_id"],
        unique=False,
    )
    op.create_index(
        "ix_block_requirement_station_code", "block_requirement", ["station_code"], unique=False
    )
    op.create_index(
        "ix_block_requirement_line_number", "block_requirement", ["line_number"], unique=False
    )
    op.create_index(
        "ix_block_requirement_earliest_start",
        "block_requirement",
        ["earliest_start"],
        unique=False,
    )
    op.create_index(
        "ix_block_requirement_latest_end", "block_requirement", ["latest_end"], unique=False
    )
    op.create_index(
        "ix_block_requirement_status", "block_requirement", ["status"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_block_requirement_status", table_name="block_requirement"
    )
    op.drop_index(
        "ix_block_requirement_latest_end", table_name="block_requirement"
    )
    op.drop_index(
        "ix_block_requirement_earliest_start", table_name="block_requirement"
    )
    op.drop_index(
        "ix_block_requirement_line_number", table_name="block_requirement"
    )
    op.drop_index(
        "ix_block_requirement_station_code", table_name="block_requirement"
    )
    op.drop_index(
        "ix_block_requirement_maintenance_requirement_id",
        table_name="block_requirement",
    )
    op.drop_table("block_requirement")

    op.drop_index(
        "ix_maintenance_requirement_status", table_name="maintenance_requirement"
    )
    op.drop_index(
        "ix_maintenance_requirement_planned_date", table_name="maintenance_requirement"
    )
    op.drop_index(
        "ix_maintenance_requirement_defect_failure_id",
        table_name="maintenance_requirement",
    )
    op.drop_index(
        "ix_maintenance_requirement_source_system_id",
        table_name="maintenance_requirement",
    )
    op.drop_index(
        "ix_maintenance_requirement_asset_id", table_name="maintenance_requirement"
    )
    op.drop_table("maintenance_requirement")

    op.drop_index("ix_defect_failure_status", table_name="defect_failure")
    op.drop_index("ix_defect_failure_detected_at", table_name="defect_failure")
    op.drop_index(
        "ix_defect_failure_source_record_type", table_name="defect_failure"
    )
    op.drop_index(
        "ix_defect_failure_source_system_id", table_name="defect_failure"
    )
    op.drop_index("ix_defect_failure_asset_id", table_name="defect_failure")
    op.drop_table("defect_failure")