from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.modules.ai_agent.router import router as ai_router
from app.modules.auth.router import router as auth_router
from app.modules.directory.router import router as directory_router
from app.modules.stubs import hiring_router, policies_router, training_router
from app.modules.ticketing.router import router as ticketing_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield


app = FastAPI(
    title=settings.app_name,
    description="Unified HR modular monolith (plan.md). Hackathon folders are reference only.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = settings.api_prefix
app.include_router(auth_router, prefix=api)
app.include_router(directory_router, prefix=api)
app.include_router(ticketing_router, prefix=api)
app.include_router(ai_router, prefix=api)
app.include_router(hiring_router, prefix=api)
app.include_router(training_router, prefix=api)
app.include_router(policies_router, prefix=api)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.app_name, "environment": settings.environment}
