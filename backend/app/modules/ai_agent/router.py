from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import settings
from app.core.llm import get_llm_provider
from app.core.security import get_current_user
from app.models.schemas import CopilotAskIn, CopilotAskOut
from app.models.user import User

router = APIRouter(prefix="/ai", tags=["ai_agent"])


@router.post("/copilot/ask", response_model=CopilotAskOut)
def copilot_ask(
    body: CopilotAskIn,
    _: Annotated[User, Depends(get_current_user)],
) -> CopilotAskOut:
    """Week 1 scaffold: mock LLM. Week 3 binds real tools (leave balance, directory lookup)."""
    llm = get_llm_provider()
    system = (
        "You are Vera, the QuadrantHR copilot. Answer briefly using internal HR context when available."
    )
    reply = llm.complete(body.message, system=system)
    return CopilotAskOut(reply=reply, provider=settings.llm_provider)


@router.get("/health")
def ai_health() -> dict:
    llm = get_llm_provider()
    sample = llm.embed(["ping"])[0]
    return {"provider": settings.llm_provider, "embed_dims": len(sample)}
