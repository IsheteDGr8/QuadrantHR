"""Stub routers for Week 2–3 modules — keep import surface stable."""

from fastapi import APIRouter

hiring_router = APIRouter(prefix="/hiring", tags=["hiring"])
training_router = APIRouter(prefix="/training", tags=["training"])
policies_router = APIRouter(prefix="/policies", tags=["policies"])


@hiring_router.get("/status")
def hiring_status() -> dict:
    return {"module": "hiring", "status": "scaffolded", "week": 3}


@training_router.get("/status")
def training_status() -> dict:
    return {"module": "training", "status": "scaffolded", "week": 2}


@policies_router.get("/status")
def policies_status() -> dict:
    return {"module": "policies", "status": "scaffolded", "week": 3}
