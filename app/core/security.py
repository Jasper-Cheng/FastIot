from datetime import datetime, timedelta
from typing import Any, Optional, Dict
from jose import jwt
from app.core.config import settings
from app.utils.time_utils import get_local_time


def create_access_token(
    expires_delta: timedelta | None = None,
    extra_claims: Optional[Dict[str, Any]] = None
) -> str:
    """创建访问令牌
    - 不再使用JWT的sub
    - extra_claims: 额外载荷，如 user_id、username、role 等
    """
    if expires_delta:
        expire = get_local_time() + expires_delta
    else:
        expire = get_local_time() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode: Dict[str, Any] = {"exp": expire}
    if extra_claims:
        to_encode.update(extra_claims)
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt


def verify_password(plain_password: str, stored_password: str) -> bool:
    """验证密码 - 直接比较明文"""
    return plain_password == stored_password


def get_password_hash(password: str) -> str:
    """获取密码 - 直接返回明文"""
    return password
