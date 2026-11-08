import time
from app.core.security import verify_password, create_access_token
from app.schemas.auth import LoginRequest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pwdlib import PasswordHash

from app.models.user import User
from app.schemas.auth import RegisterRequest


password_hash = PasswordHash.recommended()

# Cache ngắn hạn (60s) thông tin xác thực theo username/email để giảm truy vấn DB khi đăng nhập đồng loạt
_LOGIN_USER_CACHE: dict[str, tuple[str, str, bool, float]] = {}
_LOGIN_CACHE_TTL_SEC = 60.0


def register_user(db: Session, data: RegisterRequest) -> User:
    username = data.username.strip()
    email = str(data.email).strip().lower()

    if not username:
        raise ValueError("Tên đăng nhập không được để trống")

    existing_username = db.scalar(
        select(User).where(User.username == username)
    )

    if existing_username:
        raise ValueError("Tên đăng nhập đã tồn tại")

    existing_email = db.scalar(
        select(User).where(User.email == email)
    )

    if existing_email:
        raise ValueError("Email đã được sử dụng")

    user = User(
        username=username,
        email=email,
        password_hash=password_hash.hash(data.password),
        full_name=data.full_name,
    )

    db.add(user)

    try:
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise

    return user
def login_user(db: Session, data: LoginRequest) -> str:
    username_or_email = data.username_or_email.strip()
    cache_key = username_or_email.lower()
    now = time.monotonic()

    cached = _LOGIN_USER_CACHE.get(cache_key)
    if cached is not None and now < cached[3]:
        user_id_str, pwd_hash, is_active, _ = cached
    else:
        user = db.scalar(
            select(User).where(
                (User.username == username_or_email)
                | (User.email == cache_key)
            )
        )
        if not user:
            raise ValueError("Tên đăng nhập hoặc mật khẩu không chính xác")
        user_id_str = str(user.id)
        pwd_hash = user.password_hash
        is_active = user.is_active
        if len(_LOGIN_USER_CACHE) > 2000:
            _LOGIN_USER_CACHE.clear()
        _LOGIN_USER_CACHE[cache_key] = (user_id_str, pwd_hash, is_active, now + _LOGIN_CACHE_TTL_SEC)

    if not verify_password(
        data.password,
        pwd_hash,
    ):
        raise ValueError("Tên đăng nhập hoặc mật khẩu không chính xác")

    if not is_active:
        raise ValueError("Tài khoản đã bị vô hiệu hóa")

    return create_access_token(user_id_str)