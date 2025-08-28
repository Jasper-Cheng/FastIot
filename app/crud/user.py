from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.user import User
from app.models.user import UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password
from typing import Optional, List

async def get_user(db: AsyncSession, user_id: int) -> Optional[User]:
    """根据ID获取用户"""
    result = await db.execute(select(User).filter(User.id == user_id))
    return result.scalar_one_or_none()

async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """根据用户名获取用户"""
    result = await db.execute(select(User).filter(User.username == username))
    return result.scalar_one_or_none()

async def get_users(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[User]:
    """获取用户列表"""
    result = await db.execute(select(User).offset(skip).limit(limit))
    return result.scalars().all()

async def create_user(db: AsyncSession, user: UserCreate) -> User:
    """创建新用户"""
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        password=hashed_password,
        role=user.role
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def update_user(db: AsyncSession, user_id: int, user: UserUpdate) -> Optional[User]:
    """更新用户信息"""
    db_user = await get_user(db, user_id)
    if not db_user:
        return None
    
    update_data = user.dict(exclude_unset=True)
    if "password" in update_data:
        update_data["password"] = get_password_hash(update_data["password"])
    
    for field, value in update_data.items():
        setattr(db_user, field, value)
    
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def delete_user(db: AsyncSession, user_id: int) -> bool:
    """删除用户"""
    db_user = await get_user(db, user_id)
    if not db_user:
        return False
    
    await db.delete(db_user)
    await db.commit()
    return True

async def authenticate_user(db: AsyncSession, username: str, password: str) -> Optional[User]:
    """验证用户凭据"""
    print(f"🔍 [AUTH] 验证用户: {username}")
    
    user = await get_user_by_username(db, username)
    if not user:
        print(f"❌ [AUTH] 用户不存在: {username}")
        return None
    
    print(f"✅ [AUTH] 找到用户: {username}, 角色: {user.role}")
    
    if not verify_password(password, user.password):
        print(f"❌ [AUTH] 密码验证失败: {username}")
        return None
    
    print(f"✅ [AUTH] 认证成功: {username}")
    return user
