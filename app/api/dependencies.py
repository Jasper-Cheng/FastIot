from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.config import settings
from app.crud.user import get_user_by_username
from app.crud.device import get_device
from app.models.user import User, UserRole
from typing import Optional

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    """获取当前用户（从数据库读取完整信息）"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        username: str | None = payload.get("username")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await get_user_by_username(db, username=str(username))
    if user is None:
        raise credentials_exception
    return user

async def check_alert_permission(
    db: AsyncSession,
    current_user: User,
    alert_id: int
) -> bool:
    """检查用户是否有权限操作告警"""
    from app.crud.alert import get_alert
    from app.db.models.device import Device
    
    # Admin用户有所有权限
    if current_user.role == UserRole.admin:
        return True
    
    # 获取告警信息
    alert = await get_alert(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")
    
    # 获取设备信息
    device = await get_device(db, alert.device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 检查用户是否为设备拥有者
    if device.owner_id == current_user.id:
        return True
    
    return False

async def check_device_alert_permission(
    db: AsyncSession,
    current_user: User,
    device_id: int
) -> bool:
    """检查用户是否有权限操作设备的告警"""
    # Admin用户有所有权限
    if current_user.role == UserRole.admin:
        return True
    
    # 获取设备信息
    device = await get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 检查用户是否为设备拥有者
    if device.owner_id == current_user.id:
        return True
    
    return False

# 重新导出数据库会话依赖和认证依赖
__all__ = ["get_db", "get_current_user", "check_alert_permission", "check_device_alert_permission"]
