import uuid
from typing import Optional
from sqlmodel import SQLModel, Field, String, Integer

from sqlalchemy import UniqueConstraint
import json
from datetime import datetime

class PromptBase(SQLModel):
    title: str
    prompt_text: str
    preview_url: Optional[str] = None
    media_type: str = Field(default="text", index=True)
    category: str = Field(index=True)
    variables_str: Optional[str] = Field(default=None) # JSON list
    target_models_str: Optional[str] = Field(default=None) # JSON list
    tone: Optional[str] = Field(default=None)

    @property
    def variables(self) -> list[str]:
        if not self.variables_str:
            return []
        return json.loads(self.variables_str)
        
    @property
    def target_models(self) -> list[str]:
        if not self.target_models_str:
            return []
        return json.loads(self.target_models_str)

class User(SQLModel, table=True):
    __tablename__ = "users"
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    email: Optional[str] = Field(default=None, unique=True, index=True)
    telegram_id: Optional[str] = Field(default=None, unique=True, index=True)
    google_id: Optional[str] = Field(default=None, unique=True, index=True)
    vk_id: Optional[str] = Field(default=None, unique=True, index=True)
    hashed_password: Optional[str] = Field(default=None)
    username: str
    tokens: int = Field(default=10)  # стартовый баланс генераций
    referral_code: str = Field(unique=True, index=True, default_factory=lambda: str(uuid.uuid4())[:8])
    referred_by: Optional[str] = Field(default=None)  # код человека, который привел
    auth_provider: str = Field(default="email")  # "email" | "google" | "vk" | "telegram"
    avatar_url: Optional[str] = Field(default=None)

class Prompt(PromptBase, table=True):
    __tablename__ = "prompts"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    elo_rating: int = Field(default=1200, index=True)
    likes_count: int = Field(default=0, index=True)
    copies: int = Field(default=0)
    remixes: int = Field(default=0)
    is_trending: bool = Field(default=False)
    is_new: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    author_id: Optional[str] = Field(default=None, foreign_key="users.id")

    # Moderation fields
    moderation_status: str = Field(default="pending", index=True)  # "pending" | "approved" | "rejected" | "published"
    moderated_by: Optional[str] = Field(default=None, foreign_key="users.id")
    moderated_at: Optional[datetime] = Field(default=None)
    ai_model: Optional[str] = Field(default=None)  # Для image/video: Midjourney, DALL-E и т.д.
    file_path: Optional[str] = Field(default=None)  # Локальный путь к файлу
    vk_post_url: Optional[str] = Field(default=None)
    telegram_message_url: Optional[str] = Field(default=None)

class SavedPrompt(SQLModel, table=True):
    __tablename__ = "saved_prompts"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    session_token: str = Field(index=True)
    prompt_id: str = Field(foreign_key="prompts.id")

class Like(SQLModel, table=True):
    __tablename__ = "likes"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_session: str = Field(index=True)  # session_token или user_id
    prompt_id: str = Field(foreign_key="prompts.id")
    
    __table_args__ = (UniqueConstraint("user_session", "prompt_id", name="uq_like_user_prompt"),)
