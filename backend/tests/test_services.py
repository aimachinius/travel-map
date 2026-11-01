import pytest
from app.services.video_service import extract_video_info
from app.core.security import verify_password, create_access_token, decode_access_token
from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()


def test_extract_video_info_tiktok():
    url = "https://www.tiktok.com/@foodie/video/7123456789012345678"
    platform, video_id = extract_video_info(url)
    assert platform == "tiktok"
    assert video_id == "7123456789012345678"


def test_extract_video_info_youtube():
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    platform, video_id = extract_video_info(url)
    assert platform == "youtube"
    assert video_id == "dQw4w9WgXcQ"

    short_url = "https://youtu.be/dQw4w9WgXcQ"
    platform2, video_id2 = extract_video_info(short_url)
    assert platform2 == "youtube"
    assert video_id2 == "dQw4w9WgXcQ"


def test_extract_video_info_unsupported():
    with pytest.raises(ValueError):
        extract_video_info("https://vimeo.com/12345678")


def test_password_hash_and_verify():
    raw_password = "mySecretPassword123"
    hashed = password_hash.hash(raw_password)
    assert verify_password(raw_password, hashed) is True
    assert verify_password("wrongPassword", hashed) is False


def test_jwt_token_encode_decode():
    user_id = "123e4567-e89b-12d3-a456-426614174000"
    token = create_access_token(user_id)
    decoded = decode_access_token(token)
    assert decoded["sub"] == user_id
    assert "exp" in decoded
