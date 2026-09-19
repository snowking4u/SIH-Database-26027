from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routers import assets, candidates, coa, locations, optimization, planning, planning_priority, smms, source_systems, tdms, tms, unified


app = FastAPI(title="SIH 26027 API")

app.include_router(source_systems.router)
app.include_router(locations.router)
app.include_router(assets.router)
app.include_router(tms.router)
app.include_router(tdms.router)
app.include_router(smms.router)
app.include_router(coa.router)
app.include_router(unified.router)
app.include_router(planning.router)
app.include_router(planning_priority.router)
app.include_router(candidates.router)
app.include_router(optimization.router)


@app.get("/")
def root():
    return {"message": "SIH 26027 API is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/health/db")
def database_health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": "disconnected"},
        )

    return {"status": "healthy", "database": "connected"}
