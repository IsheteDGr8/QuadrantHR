import asyncio
import logging
import os
import sys

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from api.admin import router as admin_router
from api.analytics import router as analytics_router
from api.announcements import router as announcements_router
from api.chatbot import router as chatbot_router
from api.genie import router as genie_router
from api.knowledge import router as knowledge_router
from api.notifications import router as notifications_router
from api.onboarding import router as onboarding_router
from api.tickets import router as ticket_router
from api.users import router as users_router
from database.connection import SessionLocal, init_db_schema
from database.seed import seed_initial_data
from services.prompt_cache_service import seed_warm_cache
from services.synthetic_ticket_service import ensure_synthetic_tickets
from telemetry import setup_telemetry

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("ticketgenie").setLevel(logging.INFO)
logging.getLogger("ticketgenie.telemetry").setLevel(logging.INFO)

app = FastAPI(
    title="TicketGenie API",
    description="AI-powered HR & IT Helpdesk System",
    version="1.0",
)

# Initialize Database Schema & Seed Initial Data
init_db_schema()
seed_initial_data()
seed_warm_cache()
if os.getenv("ENABLE_SYNTHETIC_ANALYTICS", "false").lower() == "true":
    with SessionLocal() as synthetic_db:
        synthetic_result = ensure_synthetic_tickets(synthetic_db)
        print(f"Synthetic analytics data: {synthetic_result}")

# Enable CORS for frontend dynamic requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def disable_api_response_caching(request: Request, call_next):
    """Prevent intermediaries from caching authenticated API payloads.

    NGINX default cache keys ignore Authorization. Backend responses under
    /api/ are marked private/no-store so a later user cannot be served
    another caller's RAG, SQL, or ticket body from an edge cache.
    """
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/api/"):
        response.headers["Cache-Control"] = (
            "private, no-store, no-cache, must-revalidate"
        )
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# Initialize Azure Monitor telemetry
setup_telemetry(app)

# Include API Routers under /api
app.include_router(ticket_router, prefix="/api")
app.include_router(genie_router, prefix="/api")
app.include_router(chatbot_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(knowledge_router, prefix="/api")
app.include_router(announcements_router, prefix="/api")
app.include_router(notifications_router, prefix="/api")
app.include_router(onboarding_router, prefix="/api")
app.include_router(users_router, prefix="/api")


@app.get("/")
def root():
    return {"message": "Welcome to TicketGenie API!", "status": "Running"}


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "TicketGenie API"}


@app.get("/api/config")
def get_public_config():
    import os

    return {
        "appInsightsConnectionString": os.getenv(
            "APPLICATIONINSIGHTS_CONNECTION_STRING", ""
        ),
        "azureClientId": os.getenv("AZURE_CLIENT_ID", ""),
        "azureTenantId": os.getenv("AZURE_TENANT_ID", ""),
    }


logger = logging.getLogger("ticketgenie.main")


async def _daily_digest_scheduler_loop():
    """Background loop that runs daily digest every 24 hours inside the container."""
    # Initial delay after container startup
    await asyncio.sleep(15)
    while True:
        try:
            from services.daily_digest_service import send_daily_admin_digest

            logger.info("Executing scheduled daily admin digest email dispatch...")
            send_daily_admin_digest()
        except Exception as e:
            logger.error(f"Error in background daily digest loop: {e}")
        # Sleep for 24 hours (86400 seconds)
        await asyncio.sleep(86400)


@app.on_event("startup")
def start_daily_scheduler():
    is_testing = "pytest" in sys.modules or os.getenv("TESTING", "").lower() == "true"
    enabled = os.getenv("ENABLE_DAILY_DIGEST_CRON", "true").lower() in (
        "true",
        "1",
        "yes",
    )

    if enabled and not is_testing:
        logger.info("Starting background Daily Admin Digest scheduler (24h loop)...")
        asyncio.create_task(_daily_digest_scheduler_loop())
