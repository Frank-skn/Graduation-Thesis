"""
Xác thực đơn giản cho DSS (single-user demo).

Không dùng thư viện JWT ngoài (tránh phải rebuild image khi thêm dependency).
Token tự ký bằng HMAC-SHA256 trên (username, thời điểm hết hạn), dùng
`hmac.compare_digest` để so sánh an toàn (chống timing attack).
"""
import hashlib
import hmac
import time
from typing import Optional

from fastapi import Header, HTTPException, status

from backend.core.config import get_settings

settings = get_settings()

# Tài khoản demo duy nhất của hệ thống (single-user DSS, chưa có bảng user).
DEMO_USERNAME = "admin"
DEMO_PASSWORD = "123123"

# Khóa ký token — nên đặt qua biến môi trường SECRET_KEY khi triển khai thật.
_SECRET_KEY = getattr(settings, "secret_key", None) or "smi-dss-dev-secret-change-me"
_TOKEN_TTL_SECONDS = 8 * 3600  # 8 giờ


def _sign(payload: str) -> str:
    return hmac.new(_SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()


def create_token(username: str) -> str:
    expires_at = int(time.time()) + _TOKEN_TTL_SECONDS
    payload = f"{username}:{expires_at}"
    signature = _sign(payload)
    return f"{payload}:{signature}"


def verify_token(token: str) -> Optional[str]:
    """Trả về username nếu token hợp lệ và chưa hết hạn, ngược lại None."""
    try:
        username, expires_at_str, signature = token.split(":")
        payload = f"{username}:{expires_at_str}"
        expected_signature = _sign(payload)
        if not hmac.compare_digest(signature, expected_signature):
            return None
        if int(expires_at_str) < int(time.time()):
            return None
        return username
    except (ValueError, AttributeError):
        return None


def require_auth(authorization: Optional[str] = Header(None)) -> str:
    """FastAPI dependency: bắt buộc header `Authorization: Bearer <token>` hợp lệ."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chưa đăng nhập hoặc thiếu token xác thực",
        )
    token = authorization.removeprefix("Bearer ").strip()
    username = verify_token(token)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ hoặc đã hết hạn",
        )
    return username
