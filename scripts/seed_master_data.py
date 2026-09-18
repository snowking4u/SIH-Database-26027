from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.source_system import SourceSystem


SOURCE_SYSTEMS = [
    {
        "system_code": "TMS",
        "system_name": "TMS",
        "description": "Train Management System source records.",
    },
    {
        "system_code": "TDMS",
        "system_name": "TDMS",
        "description": "Track data source records.",
    },
    {
        "system_code": "SMMS",
        "system_name": "SMMS",
        "description": "Signal maintenance source records.",
    },
    {
        "system_code": "COA",
        "system_name": "COA",
        "description": "Control Office Application source records.",
    },
]


def seed_source_systems() -> None:
    with SessionLocal() as db:
        for source in SOURCE_SYSTEMS:
            existing = db.scalar(
                select(SourceSystem).where(
                    SourceSystem.system_code == source["system_code"]
                )
            )
            if existing is None:
                db.add(SourceSystem(**source))

        db.commit()


if __name__ == "__main__":
    seed_source_systems()
    print("Seeded source_system records: TMS, TDMS, SMMS, COA")
