from datetime import datetime, timedelta
from typing import Any, Optional, Dict
from jose import jwt
from app.core.config import settings
from app.utils.time_utils import get_utc_time


def create_access_token(
    expires_delta: timedelta | None = None,
    extra_claims: Optional[Dict[str, Any]] = None
) -> str:
    """创建访问令牌
    - 不再使用JWT的sub
    - extra_claims: 额外载荷，包含以下字段：
      - account_id: 账户ID（必填）
      - role: 账户角色（必填，如 user/admin）
      - platform: 平台标识（必填，如 web/mobile/app）
    """
    if expires_delta:
        expire = get_utc_time() + expires_delta
    else:
        expire = get_utc_time() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": int(expire.timestamp())}  # ✅ 转为时间戳
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
