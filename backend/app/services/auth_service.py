from app.core.security import verify_password, create_access_token
from app.schemas.auth import LoginRequest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pwdlib import PasswordHash

from app.models.user import User
from app.schemas.auth import RegisterRequest


password_hash = PasswordHash.recommended()


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

    user = db.scalar(
        select(User).where(
            (User.username == username_or_email)
            | (User.email == username_or_email.lower())
        )
    )

    if not user or not verify_password(
        data.password,
        user.password_hash,
    ):
        raise ValueError("Tên đăng nhập hoặc mật khẩu không chính xác")

    if not user.is_active:
        raise ValueError("Tài khoản đã bị vô hiệu hóa")

    return create_access_token(str(user.id))