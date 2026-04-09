from datetime import datetime, timedelta, timezone
from typing import Optional
import secrets

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.responses import RedirectResponse
from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
import aiosmtplib
from email.message import EmailMessage

from src.config import settings
from src.database import get_db_session
from src.models.db_models import EmailOTP, User
from src.dependencies import get_current_user

router = APIRouter(prefix="/api/auth")
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    username: str = Field(min_length=2, max_length=50)
    referral_code: Optional[str] = None


class UserLogin(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    email: str
    username: str
    tokens: int


class SendOTPBody(BaseModel):
    email: EmailStr


class SendOTPResponse(BaseModel):
    status: str
    message: str


class VerifyOTPBody(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)
    username: Optional[str] = Field(default=None, max_length=50)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta
        else timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt

@router.post("/register", response_model=Token)
async def register(
    user_data: UserRegister, 
    response: Response,
    db: AsyncSession = Depends(get_db_session)
):
    user_data.email = user_data.email.lower()
    
    # Check if user exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
        
    # Check referral code if provided
    referrer = None
    if user_data.referral_code:
        ref_result = await db.execute(select(User).where(User.referral_code == user_data.referral_code))
        referrer = ref_result.scalar_one_or_none()
        
    hashed_password = pwd_context.hash(user_data.password)
    
    # +15 if referred, otherwise +10
    start_tokens = 15 if referrer else 10
    
    new_user = User(
        email=user_data.email, 
        hashed_password=hashed_password,
        username=user_data.username,
        tokens=start_tokens,
        referred_by=referrer.id if referrer else None
    )
    db.add(new_user)
    
    if referrer:
        referrer.tokens += 50
        db.add(referrer)
        
    await db.commit()
    await db.refresh(new_user)
    
    access_token = create_access_token(data={"sub": new_user.id})
    
    # Set HttpOnly cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=settings.access_token_expire_minutes * 60,
        samesite="lax",
        secure=True, 
    )
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user_id": new_user.id,
        "email": new_user.email,
        "username": new_user.username,
        "tokens": new_user.tokens
    }

@router.post("/login", response_model=Token)
async def login(
    payload: UserLogin, 
    response: Response,
    db: AsyncSession = Depends(get_db_session)
):
    payload.email = payload.email.lower()
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    
    if (
        not user
        or not user.hashed_password
        or not pwd_context.verify(payload.password, user.hashed_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token = create_access_token(data={"sub": user.id})
    
    # Set HttpOnly cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=settings.access_token_expire_minutes * 60,
        samesite="lax",
        secure=True,
    )
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user_id": user.id,
        "email": user.email,
        "username": user.username,
        "tokens": user.tokens
    }

async def _send_otp_email(to_email: str, code: str) -> None:
    if not settings.smtp_user or not settings.smtp_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Отправка почты временно недоступна (SMTP не настроен).",
        )
    msg = EmailMessage()
    msg["Subject"] = f"Ваш код входа в MagikBook: {code}"
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to_email
    msg.set_content(f"Ваш код: {code}. Действует 10 минут.")
    msg.add_alternative(
        f"<p>Ваш код: <b>{code}</b>. Действует 10 минут.</p>",
        subtype="html",
    )
    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user,
        password=settings.smtp_password,
        use_tls=settings.smtp_port == 465,
    )


@router.post("/send-otp", response_model=SendOTPResponse)
async def send_otp(body: SendOTPBody, db: AsyncSession = Depends(get_db_session)):
    from src.redis_client import get_redis

    email_norm = body.email.lower()
    redis = get_redis()
    rate_key = f"otp_rate:{email_norm}"
    if redis:
        if await redis.get(rate_key):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Подождите минуту перед повторной отправкой кода.",
            )
    await db.execute(delete(EmailOTP).where(EmailOTP.email == email_norm))
    await db.commit()

    code = f"{secrets.randbelow(900000) + 100000:d}"
    row = EmailOTP(email=email_norm, code=code)
    db.add(row)
    await db.commit()

    try:
        await _send_otp_email(email_norm, code)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Не удалось отправить письмо. Попробуйте позже.",
        ) from exc

    if redis:
        await redis.set(rate_key, "1", ex=60)

    return SendOTPResponse(
        status="sent",
        message=f"Код отправлен на {email_norm}",
    )


@router.post("/verify-otp", response_model=Token)
async def verify_otp(
    body: VerifyOTPBody,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
):
    email_norm = body.email.lower()
    code_digits = "".join(c for c in body.code if c.isdigit())
    if len(code_digits) != 6:
        raise HTTPException(status_code=400, detail="Код неверный или истёк")

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=10)
    result = await db.execute(
        select(EmailOTP)
        .where(
            EmailOTP.email == email_norm,
            EmailOTP.used == False,  # noqa: E712
        )
        .order_by(EmailOTP.created_at.desc())
        .limit(1)
    )
    otp_row = result.scalar_one_or_none()
    if not otp_row:
        raise HTTPException(status_code=400, detail="Код неверный или истёк")
    created = otp_row.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    if created < cutoff or otp_row.code != code_digits:
        raise HTTPException(status_code=400, detail="Код неверный или истёк")

    otp_row.used = True
    db.add(otp_row)

    ures = await db.execute(select(User).where(User.email == email_norm))
    user = ures.scalar_one_or_none()
    if user:
        pass
    else:
        uname = (body.username or "").strip() or email_norm.split("@")[0]
        if len(uname) < 2:
            uname = email_norm.split("@")[0] or "user"
        user = User(
            email=email_norm,
            username=uname[:50],
            hashed_password=None,
            tokens=10,
            auth_provider="email",
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(data={"sub": user.id})
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=settings.access_token_expire_minutes * 60,
        samesite="lax",
        secure=True,
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "email": user.email or "",
        "username": user.username,
        "tokens": user.tokens,
    }


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key="access_token")
    return {"status": "ok", "message": "Logged out successfully"}

@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "tokens": current_user.tokens,
        "referral_code": current_user.referral_code
    }


@router.post("/daily-bonus")
async def claim_daily_bonus(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Claim a daily mana bonus (+5). Can only be claimed once per calendar day (UTC).
    Uses Redis to track the claim with a 24h TTL.
    """
    from src.redis_client import get_redis
    redis = get_redis()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = f"daily_bonus:{current_user.id}:{today}"

    if not redis:
        raise HTTPException(
            status_code=503,
            detail="Бонусная система временно недоступна. Попробуй позже."
        )

    already_claimed = await redis.get(key)
    if already_claimed:
        raise HTTPException(
            status_code=400,
            detail="Ежедневный бонус уже получен сегодня. Возвращайся завтра!"
        )
    await redis.incr(key)
    await redis.expire(key, 86400)

    bonus = 5
    current_user.tokens += bonus
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)

    return {
        "status": "ok",
        "message": f"+{bonus} маны! Возвращайся завтра за следующим бонусом.",
        "tokens": current_user.tokens,
        "bonus": bonus,
    }


import hashlib
import hmac
import time as time_module


def _verify_telegram_hash(payload: "TelegramAuthRequest") -> bool:
    """
    Verify Telegram Login Widget data per official spec:
    https://core.telegram.org/widgets/login#checking-authorization
    """
    bot_token = settings.telegram_bot_token
    if not bot_token:
        # If no bot token configured, skip verification (dev only)
        return True

    received_hash = payload.hash
    data_check_fields = {
        "id": str(payload.id),
        "first_name": payload.first_name,
        "auth_date": str(payload.auth_date),
    }
    if payload.username:
        data_check_fields["username"] = payload.username
    if payload.photo_url:
        data_check_fields["photo_url"] = payload.photo_url

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(data_check_fields.items())
    )

    secret_key = hashlib.sha256(bot_token.encode()).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    # Also validate freshness (max 86400 seconds = 1 day)
    age = int(time_module.time()) - payload.auth_date
    if age > 86400:
        return False

    return hmac.compare_digest(computed_hash, received_hash)


class TelegramAuthRequest(BaseModel):
    id: int
    first_name: str
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str


@router.post("/telegram", response_model=Token)
async def telegram_auth(
    payload: TelegramAuthRequest, 
    response: Response,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Authenticate or register via Telegram Login Widget.
    Verifies the HMAC-SHA256 hash as per Telegram's official spec.
    """
    if not _verify_telegram_hash(payload):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram auth verification failed",
        )

    # Check if user exists by telegram_id
    result = await db.execute(select(User).where(User.telegram_id == str(payload.id)))
    user = result.scalar_one_or_none()

    if user:
        access_token = create_access_token(data={"sub": user.id})
        
        # Set HttpOnly cookie
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=settings.access_token_expire_minutes * 60,
            samesite="lax",
            secure=True,
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": user.id,
            "email": user.email or "",
            "username": user.username,
            "tokens": user.tokens,
        }

    # New user — create account
    username = payload.username or f"tg_{payload.id}"
    new_user = User(
        telegram_id=str(payload.id),
        username=username,
        email=None,
        tokens=10,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    access_token = create_access_token(data={"sub": new_user.id})
    
    # Set HttpOnly cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=settings.access_token_expire_minutes * 60,
        samesite="lax",
        secure=True,
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": new_user.id,
        "email": "",
        "username": new_user.username,
        "tokens": new_user.tokens,
    }


# ============================================================================
# Google OAuth
# ============================================================================

@router.get("/google")
async def google_login():
    """
    Начало авторизации через Google OAuth.
    Редиректит пользователя на Google authorization endpoint.
    """
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth not configured"
        )

    # Генерируем state для защиты от CSRF
    state = secrets.token_urlsafe(32)

    # Формируем URL для Google OAuth
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }

    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{query_string}"

    # Редирект на Google
    response = RedirectResponse(url=auth_url)
    # Сохраняем state в куки для проверки при callback
    response.set_cookie(key="oauth_state", value=state, httponly=True, max_age=600)
    return response


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Callback от Google OAuth.
    Обмениваем code на access_token, получаем userinfo,
    создаем или авторизуем пользователя.
    """
    # Проверяем state для защиты от CSRF
    cookie_state = request.cookies.get("oauth_state")
    if not cookie_state or cookie_state != state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state"
        )

    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth not configured"
        )

    # 1. Обмениваем code на access_token
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": settings.google_redirect_uri,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient() as client:
        token_response = await client.post(token_url, data=token_data)

    if token_response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to exchange code for token"
        )

    token_json = token_response.json()
    access_token = token_json.get("access_token")

    # 2. Получаем userinfo
    userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    async with httpx.AsyncClient() as client:
        userinfo_response = await client.get(
            userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"}
        )

    if userinfo_response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to fetch user info"
        )

    userinfo = userinfo_response.json()
    google_id = userinfo.get("id")
    email = userinfo.get("email", "").lower()
    username = userinfo.get("name", email.split("@")[0] if email else f"google_{google_id[:8]}")
    avatar_url = userinfo.get("picture")

    # 3. Ищем или создаем пользователя с логикой связывания по email
    user = await _find_or_create_oauth_user(
        db=db,
        oauth_id=google_id,
        email=email,
        username=username,
        avatar_url=avatar_url,
        provider="google",
        provider_id_field="google_id"
    )

    # 4. Создаем JWT и устанавливаем cookie на редиректе
    jwt_token = create_access_token(data={"sub": user.id})

    # Редирект на фронтенд
    from fastapi.responses import RedirectResponse as _RedirectResponse
    redirect = _RedirectResponse(url=settings.frontend_url or "/")
    redirect.set_cookie(
        key="access_token",
        value=jwt_token,
        httponly=True,
        max_age=settings.access_token_expire_minutes * 60,
        samesite="lax",
        secure=True,
    )
    redirect.delete_cookie(key="oauth_state")
    return redirect


# ============================================================================
# VK ID OAuth
# ============================================================================

@router.get("/vk")
async def vk_login():
    """
    Начало авторизации через VK ID.
    Редиректит пользователя на VK ID authorization endpoint.
    """
    if not settings.vk_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VK OAuth not configured"
        )

    # Генерируем state для защиты от CSRF
    state = secrets.token_urlsafe(32)

    # Формируем URL для VK ID OAuth
    params = {
        "client_id": settings.vk_client_id,
        "redirect_uri": settings.vk_redirect_uri,
        "response_type": "code",
        "scope": "email",  # Запрашиваем email
        "state": state,
    }

    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    auth_url = f"https://id.vk.com/authorize?{query_string}"

    # Редирект на VK
    response = RedirectResponse(url=auth_url)
    # Сохраняем state в куки для проверки при callback
    response.set_cookie(key="oauth_state", value=state, httponly=True, max_age=600)
    return response


@router.get("/vk/callback")
async def vk_callback(
    request: Request,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Callback от VK ID OAuth.
    Обмениваем code на access_token, получаем userinfo,
    создаем или авторизуем пользователя.
    """
    # Проверяем state для защиты от CSRF
    cookie_state = request.cookies.get("oauth_state")
    if not cookie_state or cookie_state != state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state"
        )

    if not settings.vk_client_id or not settings.vk_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VK OAuth not configured"
        )

    # 1. Обмениваем code на access_token
    token_url = "https://id.vk.com/oauth2/auth"
    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": settings.vk_client_id,
        "device_id": "magikbook_web",  # device_id required by VK ID
        "state": state,
    }

    async with httpx.AsyncClient() as client:
        token_response = await client.post(token_url, data=token_data)

    if token_response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Failed to exchange code for token: {token_response.text}"
        )

    token_json = token_response.json()

    if "error" in token_json:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"VK OAuth error: {token_json.get('error_description', token_json['error'])}"
        )

    access_token = token_json.get("access_token")
    email = token_json.get("email", "").lower() if token_json.get("email") else None

    # 2. Получаем userinfo через VK API
    # VK ID использует OpenID Connect userinfo endpoint
    userinfo_url = "https://id.vk.com/oauth2/user_info"
    userinfo_data = {
        "client_id": settings.vk_client_id,
        "access_token": access_token,
    }

    async with httpx.AsyncClient() as client:
        userinfo_response = await client.post(userinfo_url, data=userinfo_data)

    if userinfo_response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to fetch user info from VK"
        )

    userinfo_json = userinfo_response.json()

    if "error" in userinfo_json:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"VK userinfo error: {userinfo_json.get('error_description', userinfo_json['error'])}"
        )

    user_data = userinfo_json.get("user", {})
    vk_user_id = str(user_data.get("user_id"))
    first_name = user_data.get("first_name", "")
    last_name = user_data.get("last_name", "")
    username = f"{first_name} {last_name}".strip() or f"vk_{vk_user_id[:8]}"
    avatar_url = user_data.get("avatar")

    # Если email не получили из токена, используем фейковый
    if not email:
        email = f"vk_{vk_user_id}@vk.local"

    # 3. Ищем или создаем пользователя с логикой связывания по email
    user = await _find_or_create_oauth_user(
        db=db,
        oauth_id=vk_user_id,
        email=email,
        username=username,
        avatar_url=avatar_url,
        provider="vk",
        provider_id_field="vk_id"
    )

    # 4. Создаем JWT и устанавливаем cookie на редиректе
    jwt_token = create_access_token(data={"sub": user.id})

    # Редирект на фронтенд
    from fastapi.responses import RedirectResponse as _RedirectResponse
    redirect = _RedirectResponse(url=settings.frontend_url or "/")
    redirect.set_cookie(
        key="access_token",
        value=jwt_token,
        httponly=True,
        max_age=settings.access_token_expire_minutes * 60,
        samesite="lax",
        secure=True,
    )
    redirect.delete_cookie(key="oauth_state")
    return redirect


# ============================================================================
# OAuth Account Linking Helper
# ============================================================================

async def _find_or_create_oauth_user(
    db: AsyncSession,
    oauth_id: str,
    email: str,
    username: str,
    avatar_url: Optional[str],
    provider: str,
    provider_id_field: str
) -> User:
    """
    Универсальная функция для поиска или создания пользователя через OAuth.
    Реализует логику связывания аккаунтов по email.

    Args:
        db: Сессия базы данных
        oauth_id: ID пользователя в OAuth провайдере
        email: Email пользователя
        username: Имя пользователя
        avatar_url: URL аватара
        provider: Название провайдера (google, vk, telegram)
        provider_id_field: Название поля в модели User (google_id, vk_id, telegram_id)

    Returns:
        User: Найденный или созданный пользователь
    """
    # 1. Ищем по OAuth ID
    id_result = await db.execute(
        select(User).where(getattr(User, provider_id_field) == oauth_id)
    )
    existing_by_id = id_result.scalar_one_or_none()
    if existing_by_id:
        # Обновляем аватар если изменился
        if avatar_url and existing_by_id.avatar_url != avatar_url:
            existing_by_id.avatar_url = avatar_url
            await db.commit()
        return existing_by_id

    # 2. Если email предоставлен, ищем по email для связывания
    if email and not email.endswith("@vk.local") and not email.endswith("@telegram.local"):
        email_result = await db.execute(select(User).where(User.email == email))
        existing_by_email = email_result.scalar_one_or_none()
        if existing_by_email:
            # Связываем OAuth с существующим аккаунтом
            setattr(existing_by_email, provider_id_field, oauth_id)
            if avatar_url:
                existing_by_email.avatar_url = avatar_url
            if not existing_by_email.auth_provider or existing_by_email.auth_provider == "email":
                existing_by_email.auth_provider = provider
            await db.commit()
            await db.refresh(existing_by_email)
            return existing_by_email

    # 3. Создаем нового пользователя
    # Проверяем уникальность username
    base_username = username
    counter = 1
    while True:
        username_check = await db.execute(select(User).where(User.username == username))
        if not username_check.scalar_one_or_none():
            break
        username = f"{base_username}_{counter}"
        counter += 1

    new_user = User(
        email=email if email and not email.endswith("@vk.local") else None,
        username=username,
        tokens=10,  # Стартовый баланс
        auth_provider=provider,
        avatar_url=avatar_url,
    )
    setattr(new_user, provider_id_field, oauth_id)

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user
