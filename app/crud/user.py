from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.user import User
from app.models.user import UserCreate, UserUpdate
from typing import Optional, List

async def get_user(db: AsyncSession, user_id: int) -> Optional[User]:
    """根据ID获取用户"""
    result = await db.execute(select(User).filter(User.id == user_id))
    return result.scalar_one_or_none()

async def get_user_by_account_id(db: AsyncSession, account_id: int) -> Optional[User]:
    """根据账号ID获取用户"""
    result = await db.execute(select(User).filter(User.account_id == account_id))
    return result.scalar_one_or_none()

async def get_users(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[User]:
    """获取用户列表"""
    result = await db.execute(select(User).offset(skip).limit(limit))
    return result.scalars().all()

async def create_user(db: AsyncSession, user: UserCreate) -> User:
    """创建新用户"""
    db_user = User(account_id=user.account_id)
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def update_user(db: AsyncSession, user_id: int, user: UserUpdate) -> Optional[User]:
    """更新用户信息（用户信息通过 account 表管理）"""
    # 用户表本身没有需要更新的字段，所有信息都在 account 表中
    return await get_user(db, user_id)

async def delete_user(db: AsyncSession, user_id: int) -> bool:
    """删除用户"""
    db_user = await get_user(db, user_id)
    if not db_user:
        return False
    
    await db.delete(db_user)
    await db.commit()
    return True
