import asyncio
import time
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal, get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=True,
)

oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)

# In-memory TTL cache (60s) cho User đang active để giảm truy vấn lặp DB trên mỗi request xác thực JWT
_ACTIVE_USER_CACHE: dict[UUID, tuple[User, float]] = {}
_USER_CACHE_TTL_SEC = 60.0


def _fetch_user_sync(user_uuid: UUID) -> User | None:
    with SessionLocal() as db:
        user = db.get(User, user_uuid)
        if user is None or not user.is_active:
            _ACTIVE_USER_CACHE.pop(user_uuid, None)
            return None

        # Nạp sẵn các thuộc tính scalar trước khi tách khỏi session để tái sử dụng an toàn
        _ = (
            user.id,
            user.username,
            user.email,
            user.full_name,
            user.avatar_url,
            user.is_active,
            user.created_at,
            user.updated_at,
        )
        db.expunge(user)
        if len(_ACTIVE_USER_CACHE) > 2000:
            _ACTIVE_USER_CACHE.clear()
        _ACTIVE_USER_CACHE[user_uuid] = (user, time.monotonic() + _USER_CACHE_TTL_SEC)
        return user


async def _get_cached_active_user(user_uuid: UUID) -> User | None:
    now = time.monotonic()
    cached = _ACTIVE_USER_CACHE.get(user_uuid)
    if cached is not None:
        user_obj, exp_ts = cached
        if now < exp_ts:
            return user_obj
    return await asyncio.to_thread(_fetch_user_sync, user_uuid)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Không thể xác thực thông tin đăng nhập",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )

        user_id = payload.get("sub")
        if not user_id:
            raise credentials_exception

        user_uuid = UUID(user_id)

    except (InvalidTokenError, ValueError, TypeError):
        raise credentials_exception

    user = await _get_cached_active_user(user_uuid)
    if user is None:
        raise credentials_exception

    return user


async def get_optional_current_user(
    token: str | None = Depends(oauth2_scheme_optional),
) -> User | None:
    if not token:
        return None

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id = payload.get("sub")
        if not user_id:
            return None
        user_uuid = UUID(user_id)
        return await _get_cached_active_user(user_uuid)
    except Exception:
        return None