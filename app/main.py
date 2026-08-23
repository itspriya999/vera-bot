import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger("vera")

app = FastAPI(
    title="Vera Merchant Message Engine",
    description="Merchant growth message engine for the magicpin Vera challenge",
    version=settings.version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    start = time.perf_counter()
    response = await call_next(request)
    latency_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "request_id=%s method=%s path=%s status=%s latency_ms=%.1f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        latency_ms,
    )
    return response


app.include_router(router)


@app.get("/")
async def root():
    return {"service": "vera-bot", "docs": "/docs", "health": "/v1/healthz"}
