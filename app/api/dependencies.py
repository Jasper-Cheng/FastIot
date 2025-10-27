from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.config import settings
from app.crud.account import get_account
from app.models.account import Account

# 让 Swagger 的 Authorize 使用表单登录端点
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login/form")

async def get_current_token(
    token: str = Depends(oauth2_scheme)
) -> dict:
    """获取当前token的解码信息"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        account_id: int | None = payload.get("account_id")
        id: int | None = payload.get("id")  # 使用统一的id字段
        role: str | None = payload.get("role")  # 直接使用token中的role字段
        
        if not account_id or not id or not role:
            raise credentials_exception
            
        return {
            "account_id": account_id,
            "id": id,
            "role": role
        }
    except JWTError:
        raise credentials_exception


async def get_current_account(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> Account:
    """获取当前账号信息"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        account_id: int | None = payload.get("account_id")
        
        if not account_id:
            raise credentials_exception
            
        # 获取账号信息
        account = await get_account(db, account_id)
        if account is None:
            raise credentials_exception
        return account
        
    except JWTError:
        raise credentials_exception

# 重新导出数据库会话依赖和认证依赖
__all__ = [
    "get_db",
    "get_current_token",
    "get_current_account",
]
