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

#获取所有包含当前用户且正在使用当前家庭组的家庭客户端列表
async def get_family_clients(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
) -> list[str]:
    """获取当前成员的所有family_client列表
    
    先获取该用户的所有family，然后查询account表根据current_family_id匹配所有的用户。
    构建所有用户的web/app clients。
    当前用户应该始终包含在返回列表。
    
    返回格式: ["web_{account_id}", "app_{account_id}", ...]
    """
    from sqlalchemy import select
    from app.db.models.account import Account
    
    account_id = token_info["account_id"]
    
    # 获取账号信息
    account = await get_account(db, account_id)
    if not account:
        # 如果账号不存在，抛出异常
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 获取该用户的所有 family
    from app.crud.family import get_families_by_account
    families = await get_families_by_account(db, account_id)
    
    # 收集所有相关的账户ID（使用集合去重）
    account_ids = set()
    # 当前用户始终包含在列表中
    account_ids.add(account_id)
    
    # 对于每个家庭，查询 account 表中 current_family_id 等于该家庭 ID 的所有账户
    for family in families:
        result = await db.execute(
            select(Account.id).filter(Account.current_family_id == family.id)
        )
        family_account_ids = result.scalars().all()
        account_ids.update(family_account_ids)
    
    # 构建 web 和 app 两个平台的 family_clients
    family_clients = []
    platforms = ["web", "app"]
    
    for acc_id in account_ids:
        for platform in platforms:
            client_id = f"{platform}_{acc_id}"
            family_clients.append(client_id)
    
    return family_clients

# 重新导出数据库会话依赖和认证依赖
__all__ = [
    "get_db",
    "get_current_token",
    "get_current_account",
    "get_family_clients",
]
