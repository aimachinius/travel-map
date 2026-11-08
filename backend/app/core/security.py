from collections import OrderedDict
from datetime import datetime, timedelta, timezone
import hashlib
import hmac

import jwt
from pwdlib import PasswordHash

from app.core.config import settings


password_hash = PasswordHash.recommended()

# LRU cache lưu digest HMAC-SHA256 của cặp (plain_password, hashed_password) đã xác thực thành công
# Giúp giảm tải CPU Argon2id khi cùng một user đăng nhập lặp lại trong phiên cao điểm mà vẫn bảo mật
_VERIFIED_PWD_CACHE: OrderedDict[str, bool] = OrderedDict()
_VERIFIED_PWD_CACHE_MAX = 2048


def _pwd_cache_key(plain_password: str, hashed_password: str) -> str:
    msg = f"{plain_password}\x00{hashed_password}".encode("utf-8")
    return hmac.new(settings.JWT_SECRET_KEY.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    cache_key = _pwd_cache_key(plain_password, hashed_password)
    if cache_key in _VERIFIED_PWD_CACHE:
        _VERIFIED_PWD_CACHE.move_to_end(cache_key)
        return True

    ok = password_hash.verify(
        plain_password,
        hashed_password,
    )
    if ok:
        _VERIFIED_PWD_CACHE[cache_key] = True
        if len(_VERIFIED_PWD_CACHE) > _VERIFIED_PWD_CACHE_MAX:
            _VERIFIED_PWD_CACHE.popitem(last=False)
    return ok


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": user_id,
        "exp": expire,
    }

    token = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    return token


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )