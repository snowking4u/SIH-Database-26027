"""create coa source data and available window tables

Revision ID: fba530afe681
Revises: 5455c8c6bd94
Create Date: 2026-09-17 22:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fba530afe681'
down_revision: Union[str, Sequence[str], None] = '5455c8c6bd94'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "train",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("train_id", sa.String(length=100), nullable=False),
        sa.Column("train_number", sa.String(length=50), nullable=True),
        sa.Column("train_name", sa.String(length=150), nullable=True),
        sa.Column("schedule_date", sa.DateTime(), nullable=True),
        sa.Column("start_date", sa.DateTime(), nullable=True),
        sa.Column("loco_number", sa.String(length=50), nullable=True),
        sa.Column("direction", sa.String(length=50), nullable=True),
        sa.Column("source_system_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["source_system_id"],
            ["source_system.id"],
            name="fk_train_source_system_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "source_system_id",
            "train_id",
            name="uq_train_source_system_train_id",
        ),
    )
    op.create_index("ix_train_source_system_id", "train", ["source_system_id"], unique=False)
    op.create_index("ix_train_train_id", "train", ["train_id"], unique=False)

    op.create_table(
        "train_movement",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("train_id", sa.Integer(), nullable=False),
        sa.Column("station_code", sa.String(length=50), nullable=False),
        sa.Column("movement_flag", sa.String(length=1), nullable=False),
        sa.Column("movement_datetime", sa.DateTime(), nullable=False),
        sa.Column("line_number", sa.String(length=50), nullable=True),
        sa.Column("source_event_id", sa.String(length=100), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["train_id"],
            ["train.id"],
            name="fk_train_movement_train_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_train_movement_train_id", "train_movement", ["train_id"], unique=False
    )
    op.create_index(
        "ix_train_movement_station_code",
        "train_movement",
        ["station_code"],
        unique=False,
    )
    op.create_index(
        "ix_train_movement_movement_datetime",
        "train_movement",
        ["movement_datetime"],
        unique=False,
    )

    op.create_table(
        "train_schedule",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("train_id", sa.Integer(), nullable=False),
        sa.Column("station_code", sa.String(length=50), nullable=False),
        sa.Column("scheduled_arrival", sa.DateTime(), nullable=True),
        sa.Column("scheduled_departure", sa.DateTime(), nullable=True),
        sa.Column("scheduled_run_through", sa.DateTime(), nullable=True),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("line_number", sa.String(length=50), nullable=True),
        sa.Column("source_schedule_id", sa.String(length=100), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["train_id"],
            ["train.id"],
            name="fk_train_schedule_train_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_train_schedule_train_id", "train_schedule", ["train_id"], unique=False
    )
    op.create_index(
        "ix_train_schedule_station_code",
        "train_schedule",
        ["station_code"],
        unique=False,
    )
    op.create_index(
        "ix_train_schedule_sequence_number",
        "train_schedule",
        ["sequence_number"],
        unique=False,
    )

    op.create_table(
        "line_occupancy",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("station_code", sa.String(length=50), nullable=False),
        sa.Column("line_number", sa.String(length=50), nullable=False),
        sa.Column("occupancy_start", sa.DateTime(), nullable=False),
        sa.Column("occupancy_end", sa.DateTime(), nullable=True),
        sa.Column("occupancy_status", sa.String(length=50), nullable=False),
        sa.Column("train_id", sa.Integer(), nullable=True),
        sa.Column("source_event_id", sa.String(length=100), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["train_id"],
            ["train.id"],
            name="fk_line_occupancy_train_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_line_occupancy_station_code", "line_occupancy", ["station_code"], unique=False
    )
    op.create_index(
        "ix_line_occupancy_line_number", "line_occupancy", ["line_number"], unique=False
    )
    op.create_index(
        "ix_line_occupancy_occupancy_start",
        "line_occupancy",
        ["occupancy_start"],
        unique=False,
    )
    op.create_index(
        "ix_line_occupancy_train_id", "line_occupancy", ["train_id"], unique=False
    )

    op.create_table(
        "operational_event",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("train_id", sa.Integer(), nullable=True),
        sa.Column("station_code", sa.String(length=50), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("event_datetime", sa.DateTime(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_event_id", sa.String(length=100), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["train_id"],
            ["train.id"],
            name="fk_operational_event_train_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_operational_event_train_id", "operational_event", ["train_id"], unique=False
    )
    op.create_index(
        "ix_operational_event_station_code",
        "operational_event",
        ["station_code"],
        unique=False,
    )
    op.create_index(
        "ix_operational_event_event_datetime",
        "operational_event",
        ["event_datetime"],
        unique=False,
    )
    op.create_index(
        "ix_operational_event_event_type",
        "operational_event",
        ["event_type"],
        unique=False,
    )

    op.create_table(
        "available_window",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("station_code", sa.String(length=50), nullable=False),
        sa.Column("line_number", sa.String(length=50), nullable=False),
        sa.Column("window_start", sa.DateTime(), nullable=False),
        sa.Column("window_end", sa.DateTime(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("window_status", sa.String(length=50), nullable=False),
        sa.Column("calculation_source", sa.String(length=200), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.Column("source_schedule_id", sa.Integer(), nullable=True),
        sa.Column("source_occupancy_id", sa.Integer(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["source_schedule_id"],
            ["train_schedule.id"],
            name="fk_available_window_source_schedule_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_occupancy_id"],
            ["line_occupancy.id"],
            name="fk_available_window_source_occupancy_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_available_window_station_code",
        "available_window",
        ["station_code"],
        unique=False,
    )
    op.create_index(
        "ix_available_window_line_number",
        "available_window",
        ["line_number"],
        unique=False,
    )
    op.create_index(
        "ix_available_window_window_start",
        "available_window",
        ["window_start"],
        unique=False,
    )
    op.create_index(
        "ix_available_window_window_end",
        "available_window",
        ["window_end"],
        unique=False,
    )
    op.create_index(
        "ix_available_window_window_status",
        "available_window",
        ["window_status"],
        unique=False,
    )
    op.create_index(
        "ix_available_window_sc_line_start_end",
        "available_window",
        ["station_code", "line_number", "window_start", "window_end"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_available_window_sc_line_start_end", table_name="available_window"
    )
    op.drop_index("ix_available_window_window_status", table_name="available_window")
    op.drop_index("ix_available_window_window_end", table_name="available_window")
    op.drop_index("ix_available_window_window_start", table_name="available_window")
    op.drop_index("ix_available_window_line_number", table_name="available_window")
    op.drop_index("ix_available_window_station_code", table_name="available_window")
    op.drop_table("available_window")

    op.drop_index("ix_operational_event_event_type", table_name="operational_event")
    op.drop_index(
        "ix_operational_event_event_datetime", table_name="operational_event"
    )
    op.drop_index("ix_operational_event_station_code", table_name="operational_event")
    op.drop_index("ix_operational_event_train_id", table_name="operational_event")
    op.drop_table("operational_event")

    op.drop_index("ix_line_occupancy_train_id", table_name="line_occupancy")
    op.drop_index("ix_line_occupancy_occupancy_start", table_name="line_occupancy")
    op.drop_index("ix_line_occupancy_line_number", table_name="line_occupancy")
    op.drop_index("ix_line_occupancy_station_code", table_name="line_occupancy")
    op.drop_table("line_occupancy")

    op.drop_index("ix_train_schedule_sequence_number", table_name="train_schedule")
    op.drop_index("ix_train_schedule_station_code", table_name="train_schedule")
    op.drop_index("ix_train_schedule_train_id", table_name="train_schedule")
    op.drop_table("train_schedule")

    op.drop_index(
        "ix_train_movement_movement_datetime", table_name="train_movement"
    )
    op.drop_index("ix_train_movement_station_code", table_name="train_movement")
    op.drop_index("ix_train_movement_train_id", table_name="train_movement")
    op.drop_table("train_movement")

    op.drop_index("ix_train_train_id", table_name="train")
    op.drop_index("ix_train_source_system_id", table_name="train")
    op.drop_table("train")