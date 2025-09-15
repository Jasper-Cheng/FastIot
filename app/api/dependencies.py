from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.config import settings
from app.crud.account import get_account
from app.crud.user import get_user, get_user_by_account_id
from app.crud.member import get_member, get_member_by_account_id
from app.crud.device import get_device
from app.models.account import Account
from app.models.user import User
from app.models.member import Member
from typing import Optional, Union

# 让 Swagger 的 Authorize 使用表单登录端点
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login/form")

async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> Union[User, Member]:
    """获取当前用户或成员（从数据库读取完整信息）"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_type: str | None = payload.get("user_type")
        account_id: int | None = payload.get("account_id")
        user_id: int | None = payload.get("user_id")
        member_id: int | None = payload.get("member_id")
        
        if not account_id:
            raise credentials_exception
            
        if user_type == "account" and member_id:
            # 获取成员信息
            member = await get_member(db, member_id)
            if member is None:
                raise credentials_exception
            return member
        elif user_type == "account" and user_id:
            # 获取用户信息
            user = await get_user(db, user_id)
            if user is None:
                raise credentials_exception
            return user
        else:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

async def get_current_user_id(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> int:
    """获取当前用户或成员的ID（轻量级版本，不查询数据库）"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_type: str | None = payload.get("user_type")
        user_id: int | None = payload.get("user_id")
        member_id: int | None = payload.get("member_id")
        
        if user_type == "account" and user_id:
            return user_id
        elif user_type == "account" and member_id:
            # 对于成员，我们需要获取其所属的用户ID
            member = await get_member(db, member_id)
            if member is None:
                raise credentials_exception
            return member.user_id
        else:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

async def check_alert_permission(
    db: AsyncSession,
    current_user: Union[User, Member],
    alert_id: int
) -> bool:
    """检查用户是否有权限操作告警"""
    from app.crud.alert import get_alert
    from app.db.models.device import Device
    
    # 获取告警信息
    alert = await get_alert(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")
    
    # 获取设备信息
    device = await get_device(db, alert.device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 检查权限
    if isinstance(current_user, User):
        # 主用户：检查是否为设备拥有者
        if device.user_id == current_user.id:
            return True
    elif isinstance(current_user, Member):
        # 成员：检查是否有设备权限
        from app.crud.member_device_permission import get_member_device_permission
        permission = await get_member_device_permission(db, current_user.id, device.id)
        if permission and permission.can_control:
            return True
    
    return False

async def check_device_alert_permission(
    db: AsyncSession,
    current_user: Union[User, Member],
    device_id: int
) -> bool:
    """检查用户是否有权限操作设备的告警"""
    # 获取设备信息
    device = await get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 检查权限
    if isinstance(current_user, User):
        # 主用户：检查是否为设备拥有者
        if device.user_id == current_user.id:
            return True
    elif isinstance(current_user, Member):
        # 成员：检查是否有设备权限
        from app.crud.member_device_permission import get_member_device_permission
        permission = await get_member_device_permission(db, current_user.id, device.id)
        if permission and permission.can_control:
            return True
    
    return False

# 重新导出数据库会话依赖和认证依赖
__all__ = ["get_db", "get_current_user", "get_current_user_id", "check_alert_permission", "check_device_alert_permission"]
