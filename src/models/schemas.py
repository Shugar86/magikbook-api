"""Pydantic schemas for API request/response models."""

from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, model_validator, ConfigDict
import json


class PromptOut(BaseModel):
    """Full Prompt serialization with camelCase aliases for frontend compatibility."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    id: str
    title: str
    prompt_text: str
    preview_url: Optional[str] = None
    media_type: str
    category: str
    tone: Optional[str] = None
    copies: int = 0
    remixes: int = 0
    likes_count: int = 0
    elo_rating: int = 1200

    # camelCase aliases for frontend compatibility
    is_trending: bool = Field(default=False, serialization_alias="isTrending")
    is_new: bool = Field(default=True, serialization_alias="isNew")
    created_at: Optional[datetime] = Field(
        default=None, serialization_alias="createdAt"
    )
    author_id: Optional[str] = None
    author_username: Optional[str] = None
    author_avatar_url: Optional[str] = None

    variables: list[str] = []
    target_models: list[str] = Field(default=[], serialization_alias="targetModels")

    # New fields for monetization and virality
    result_example: Optional[str] = None
    result_image_url: Optional[str] = None
    affiliate_links: Optional[Dict[str, str]] = None

    vk_video_owner_id: Optional[int] = Field(
        default=None, serialization_alias="vkVideoOwnerId"
    )
    vk_video_id: Optional[int] = Field(default=None, serialization_alias="vkVideoId")
    vk_video_hash: Optional[str] = Field(
        default=None, serialization_alias="vkVideoHash"
    )

    @model_validator(mode="before")
    @classmethod
    def parse_json_fields(cls, data: Any) -> Any:
        """Parse JSON string fields from SQLModel objects."""
        if hasattr(data, "variables_str"):
            raw = getattr(data, "variables_str", None)
            if raw and isinstance(raw, str):
                try:
                    data.__dict__["variables"] = json.loads(raw)
                except (json.JSONDecodeError, AttributeError):
                    pass

        if hasattr(data, "target_models_str"):
            raw = getattr(data, "target_models_str", None)
            if raw and isinstance(raw, str):
                try:
                    data.__dict__["target_models"] = json.loads(raw)
                except (json.JSONDecodeError, AttributeError):
                    pass

        if hasattr(data, "affiliate_links_str"):
            raw = getattr(data, "affiliate_links_str", None)
            if raw and isinstance(raw, str):
                try:
                    data.__dict__["affiliate_links"] = json.loads(raw)
                except (json.JSONDecodeError, AttributeError):
                    pass

        return data


class PromptCreate(BaseModel):
    """Request model for creating a new prompt."""

    title: str = Field(..., min_length=3, max_length=200)
    prompt_text: str = Field(..., min_length=20, max_length=5000)
    category: str = Field(..., min_length=2, max_length=100)
    media_type: str = Field(default="text", pattern="^(text|image|video)$")
    preview_url: Optional[str] = None
    result_example: Optional[str] = Field(default=None, max_length=2000)
    result_image_url: Optional[str] = None
    affiliate_links: Optional[Dict[str, str]] = None
    target_models: Optional[list[str]] = None  # Allow user to specify target models


class AffiliateLinksUpdate(BaseModel):
    """Request model for updating affiliate links (admin only)."""

    affiliate_links: Dict[str, str] = Field(
        ...,
        description="Dictionary of partner links, e.g. {'midjourney': 'https://...'}",
    )


class SiteStats(BaseModel):
    """Site-wide prompt statistics."""

    text_count: int
    image_count: int
    total_count: int


class HomepageResponse(BaseModel):
    """Response model for homepage data."""

    model_config = ConfigDict(populate_by_name=True)

    trending_text: list[PromptOut]
    trending_media: list[PromptOut]
    daily_prompt: Optional[PromptOut] = None
    stats: SiteStats


class FeedResponse(BaseModel):
    """Paginated feed response."""

    prompts: list[PromptOut]
    total_count: int
    page: int
    page_size: int
    has_more: bool


class OgMeta(BaseModel):
    """OpenGraph metadata for prompt sharing."""

    title: str
    description: str
    image: Optional[str] = None
    category: str
    media_type: str
    prompt_id: str


class LikeResponse(BaseModel):
    """Response after liking a prompt."""

    status: str
    likes_count: int
    message: Optional[str] = None


class CopyCountResponse(BaseModel):
    """Response after incrementing copy count."""

    status: str
    copies: int


class UserOut(BaseModel):
    """User profile response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    avatar_url: Optional[str] = None
    tokens: int
    referral_code: str
    auth_provider: str
    is_admin: bool = False


# Legacy schema for generate endpoint (keep for compatibility)
class GenerateRequest(BaseModel):
    """Request model for AI generation."""

    category: str
    model: str
    style: str
    input: str


class CabinetStats(BaseModel):
    """User statistics for cabinet overview."""

    saved_count: int
    submitted_count: int
    approved_count: int
    pending_count: int
    rejected_count: int
    total_likes: int
    total_copies: int


class CabinetTopPrompt(BaseModel):
    """User's top performing prompt."""

    id: str
    title: str
    likes_count: int
    copies: int


class CabinetUserOut(UserOut):
    """Extended user info with daily bonus status."""

    can_claim_bonus: bool


class CabinetOverview(BaseModel):
    """Complete cabinet overview response."""

    user: CabinetUserOut
    stats: CabinetStats
    top_prompt: Optional[CabinetTopPrompt] = None


class PortfolioUserPublic(BaseModel):
    """Public user stub for portfolio page."""

    username: str
    avatar_url: Optional[str] = None


class PortfolioResponse(BaseModel):
    """Public portfolio: user info and published media prompts."""

    model_config = ConfigDict(populate_by_name=True)

    user: PortfolioUserPublic
    prompts: list[PromptOut]
