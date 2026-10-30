import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.database import SessionLocal
from app.routers import (
    ai,
    alerts,
    analytics,
    audit,
    auth,
    cases,
    coordination,
    document_intelligence,
    institutions,
    monitoring,
    overlaps,
    portal,
    reference,
)

logging.basicConfig(level=get_settings().log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("caseconnect")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("CaseConnect starting")
    yield
    logger.info("CaseConnect stopping")


app = FastAPI(title="AICTE CaseConnect API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(ai.router)
app.include_router(institutions.router)
app.include_router(cases.router)
app.include_router(reference.router)
app.include_router(coordination.router)
app.include_router(overlaps.router)
app.include_router(alerts.router)
app.include_router(analytics.router)
app.include_router(monitoring.router)
app.include_router(audit.router)
app.include_router(portal.router)
app.include_router(document_intelligence.router)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    """Provide a useful API landing response for a browser visit."""
    return {
        "name": "AICTE CaseConnect",
        "status": "running",
        "documentation": "/docs",
    }


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    def _sanitize(obj: object) -> object:
        """Recursively replace non-JSON-serializable values (e.g. bytes) with strings."""
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        if isinstance(obj, dict):
            return {k: _sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sanitize(v) for v in obj]
        return obj

    details = _sanitize(exc.errors())
    message = details[0]["msg"] if details else "Validation failed"
    return JSONResponse(status_code=422, content={"error": {"code": "validation_error", "message": message, "details": details}})


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": "http_error", "message": exc.detail}}, headers=exc.headers)


@app.exception_handler(SQLAlchemyError)
async def database_error(_: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.exception("Database error")
    return JSONResponse(status_code=503, content={"error": {"code": "database_error", "message": "Database operation failed"}})


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.warning("Health check database failure: %s", exc.__class__.__name__)
        return {"status": "degraded", "database": "unavailable"}
    return {"status": "ok", "database": "connected"}
