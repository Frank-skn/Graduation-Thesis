"""
Auth endpoints (single-user demo login cho DSS).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.core.auth import (
    DEMO_USERNAME,
    DEMO_PASSWORD,
    create_token,
    require_auth,
)

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    """Đăng nhập bằng tài khoản demo (admin/123123)."""
    if payload.username != DEMO_USERNAME or payload.password != DEMO_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tên đăng nhập hoặc mật khẩu không đúng",
        )
    token = create_token(payload.username)
    return LoginResponse(access_token=token, username=payload.username)


@router.get("/me")
def me(username: str = Depends(require_auth)):
    """Trả về thông tin user hiện tại nếu token hợp lệ (dùng để verify session)."""
    return {"username": username}
