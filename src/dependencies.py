from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from fastapi.security import OAuth2PasswordBearer
from fastapi import Request
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from src.config import settings
from src.database import get_db_session
from src.models.db_models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request, db: AsyncSession = Depends(get_db_session)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = request.cookies.get("access_token")
    if not token:
        # Try authorization header fallback
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await db.get(User, user_id)
    if user is None:
        raise credentials_exception
    return user


async def get_optional_user(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> Optional[User]:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        return None

    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        user_id: str = payload.get("sub")
        if not user_id:
            return None
    except JWTError:
        return None
    return await db.get(User, user_id)
