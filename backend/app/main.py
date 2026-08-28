from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import (
    advisory,
    auth,
    exposure,
    ingestion,
    locations,
    privacy,
    risk,
    symptoms,
    ws,
)
from app.config import settings
from app.services import scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.upload_dir, exist_ok=True)
    scheduler.start(app)
    try:
        yield
    finally:
        await scheduler.stop()


app = FastAPI(
    title="AirEcho – Air-Quality Health Risk Correlator",
    version="0.1.0",
    summary="AirEcho: personalized, lag-aware air-quality risk with grounded WHO/CPCB advisory.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev; tighten to the frontend origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=settings.upload_dir, check_dir=False), name="uploads")

for r in (auth, locations, ingestion, exposure, symptoms, risk, advisory, privacy, ws):
    app.include_router(r.router)


@app.get("/health", tags=["meta"])
def health():
    return {
        "status": "ok",
        "scheduler_enabled": settings.scheduler_enabled,
        "synthetic_ingest": settings.synthetic_ingest,
        "last_ingest": scheduler.last_run(),
    }


@app.get("/", tags=["meta"])
def root():
    return {"service": "air-quality-backend", "docs": "/docs", "health": "/health"}
