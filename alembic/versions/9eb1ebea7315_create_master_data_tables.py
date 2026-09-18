"""create master data tables

Revision ID: 9eb1ebea7315
Revises: 
Create Date: 2026-09-17 21:07:43.143856

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9eb1ebea7315'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "source_system",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("system_code", sa.String(length=50), nullable=False),
        sa.Column("system_name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.UniqueConstraint("system_code", name="uq_source_system_system_code"),
    )
    op.create_index(
        op.f("ix_source_system_system_code"),
        "source_system",
        ["system_code"],
        unique=True,
    )

    op.create_table(
        "location_master",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("zone_code", sa.String(length=50), nullable=True),
        sa.Column("zone_name", sa.String(length=100), nullable=True),
        sa.Column("division_code", sa.String(length=50), nullable=True),
        sa.Column("division_name", sa.String(length=100), nullable=True),
        sa.Column("section_code", sa.String(length=50), nullable=True),
        sa.Column("section_name", sa.String(length=100), nullable=True),
        sa.Column("station_code", sa.String(length=50), nullable=True),
        sa.Column("station_name", sa.String(length=100), nullable=True),
        sa.Column("line_code", sa.String(length=50), nullable=True),
        sa.Column("line_name", sa.String(length=100), nullable=True),
        sa.Column("km_start", sa.Numeric(10, 3), nullable=True),
        sa.Column("km_end", sa.Numeric(10, 3), nullable=True),
        sa.Column("latitude", sa.Numeric(10, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(10, 6), nullable=True),
    )

    op.create_table(
        "asset_master",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("source_system_id", sa.Integer(), nullable=False),
        sa.Column("source_asset_id", sa.String(length=100), nullable=False),
        sa.Column("asset_type", sa.String(length=100), nullable=True),
        sa.Column("asset_subtype", sa.String(length=100), nullable=True),
        sa.Column("asset_name", sa.String(length=150), nullable=True),
        sa.Column("location_id", sa.Integer(), nullable=True),
        sa.Column("installation_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["location_master.id"],
            name="fk_asset_master_location_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_system_id"],
            ["source_system.id"],
            name="fk_asset_master_source_system_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "source_system_id",
            "source_asset_id",
            name="uq_asset_master_source_system_asset",
        ),
    )
    op.create_index(
        "ix_asset_master_location_id",
        "asset_master",
        ["location_id"],
        unique=False,
    )
    op.create_index(
        "ix_asset_master_source_asset_id",
        "asset_master",
        ["source_asset_id"],
        unique=False,
    )
    op.create_index(
        "ix_asset_master_source_system_id",
        "asset_master",
        ["source_system_id"],
        unique=False,
    )

    op.create_table(
        "asset_parameter",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("source_system_id", sa.Integer(), nullable=False),
        sa.Column("parameter_code", sa.String(length=100), nullable=False),
        sa.Column("parameter_name", sa.String(length=150), nullable=True),
        sa.Column("parameter_value", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("recorded_date", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["asset_master.id"],
            name="fk_asset_parameter_asset_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_system_id"],
            ["source_system.id"],
            name="fk_asset_parameter_source_system_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_asset_parameter_asset_id",
        "asset_parameter",
        ["asset_id"],
        unique=False,
    )
    op.create_index(
        "ix_asset_parameter_code",
        "asset_parameter",
        ["parameter_code"],
        unique=False,
    )
    op.create_index(
        "ix_asset_parameter_source_system_id",
        "asset_parameter",
        ["source_system_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_asset_parameter_source_system_id", table_name="asset_parameter")
    op.drop_index("ix_asset_parameter_code", table_name="asset_parameter")
    op.drop_index("ix_asset_parameter_asset_id", table_name="asset_parameter")
    op.drop_table("asset_parameter")

    op.drop_index("ix_asset_master_source_system_id", table_name="asset_master")
    op.drop_index("ix_asset_master_source_asset_id", table_name="asset_master")
    op.drop_index("ix_asset_master_location_id", table_name="asset_master")
    op.drop_table("asset_master")

    op.drop_table("location_master")

    op.drop_index(op.f("ix_source_system_system_code"), table_name="source_system")
    op.drop_table("source_system")
