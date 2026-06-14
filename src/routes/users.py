"""Public user-related API routes (portfolio, etc.)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db_session
from src.models.schemas import PortfolioResponse
from src.services.prompt_service import PromptService

router = APIRouter(prefix="/api/users", tags=["users"])


def _service(db: AsyncSession = Depends(get_db_session)) -> PromptService:
    """Dependency to get PromptService instance."""
    return PromptService(db)


@router.get("/{username}/portfolio", response_model=PortfolioResponse)
async def get_user_portfolio(
    username: str,
    svc: PromptService = Depends(_service),
) -> PortfolioResponse:
    """Return public profile stub and published image/video prompts for this user."""
    return await svc.get_public_portfolio(username)
