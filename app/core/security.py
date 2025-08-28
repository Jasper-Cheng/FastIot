from datetime import datetime, timedelta
from typing import Any, Union, Optional, Dict
from jose import jwt
from app.core.config import settings


def create_access_token(
    subject: Union[str, int], expires_delta: timedelta | None = None, extra_claims: Optional[Dict[str, Any]] = None
) -> str:
    """创建访问令牌
    - subject: 放在JWT的sub中（建议传用户ID）
    - extra_claims: 额外载荷，如用户名、角色等
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode: Dict[str, Any] = {"exp": expire, "sub": str(subject)}
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
