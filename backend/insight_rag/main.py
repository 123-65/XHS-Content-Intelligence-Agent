from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
from sqlalchemy import inspect, text
import logging
import time
from uuid import uuid4

from insight_rag.api.v1.router import api_router
from insight_rag.core.config import settings
from insight_rag.core.db import Base, engine
from insight_rag import models  # noqa: F401

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title=settings.project_name, version="0.1.0")

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        request_id = uuid4().hex[:10]
        start = time.perf_counter()
        logger.info("request.start id=%s method=%s path=%s", request_id, request.method, request.url.path)
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("request.error id=%s method=%s path=%s", request_id, request.method, request.url.path)
            raise
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "request.done id=%s method=%s path=%s status=%s duration_ms=%s",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        response.headers["X-Request-ID"] = request_id
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    Base.metadata.create_all(bind=engine)
    _ensure_multimodal_columns()
    app.include_router(api_router, prefix="/api/v1")
    return app


def _ensure_multimodal_columns() -> None:
    inspector = inspect(engine)
    if "multimodal_assets" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("multimodal_assets")}
    if "image_url" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE multimodal_assets ADD COLUMN image_url VARCHAR(1000)"))


app = create_app()

