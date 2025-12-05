from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.config import settings
from app.crud.account import get_account
from app.models.account import Account

# 让 Swagger 的 Authorize 使用表单登录端点
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/web/auth/login/form")

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
        role: str | None = payload.get("role")  # 直接使用token中的role字段
        platform: str | None = payload.get("platform", "web")  # 平台信息，默认为"web"
        
        if not account_id or not role:
            raise credentials_exception
            
        return {
            "account_id": account_id,
            "role": role,
            "platform": platform
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

async def get_family_clients(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
) -> list[str]:
    """获取当前成员的所有family_client列表
    
    根据账号的 current_family_id 判断：
    - 如果为 null，返回空列表 []
    - 如果有值，查询该家庭的所有成员，构建 web 和 app 两个平台的 family_clients
    
    返回格式: ["web_{account_id}", "app_{account_id}", ...]
    """
    account_id = token_info["account_id"]
    
    # 获取账号信息，检查 current_family_id
    account = await get_account(db, account_id)
    if not account:
        return []
    
    # 如果 current_family_id 为 null，返回空列表
    if account.current_family_id is None:
        return []
    
    # 根据 current_family_id 查询该家庭的所有成员
    from app.crud.family_member import get_family_members_by_family
    members = await get_family_members_by_family(db, account.current_family_id)
    
    # 构建 web 和 app 两个平台的 family_clients
    family_clients = []
    platforms = ["web", "app"]
    
    for member in members:
        for platform in platforms:
            member_client_id = f"{platform}_{member.account_id}"
            if member_client_id not in family_clients:
                family_clients.append(member_client_id)
    
    return family_clients

# 重新导出数据库会话依赖和认证依赖
__all__ = [
    "get_db",
    "get_current_token",
    "get_current_account",
    "get_family_clients",
]
