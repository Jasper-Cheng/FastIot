from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import Optional, List

from app.db.models.user import User
from app.db.models.member import Member
from app.db.models.account import Account
from app.models.user import UserCreate, UserUpdate

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
    """删除用户及其所有关联数据（成员、房间、设备、日志、参数、权限等）

    实现方式：
    - 先删除该用户下所有成员的 account（将级联删除 member 记录）
    - 再删除该用户自身的 account（将级联删除 user 记录）
    - 依赖数据库外键的 ON DELETE CASCADE 清理 rooms、devices、room_device、device_*、alerts 等
    """
    db_user = await get_user(db, user_id)
    if not db_user:
        return False

    # 1) 删除所有成员的账户，级联删除 member 记录
    member_accounts = await db.execute(
        select(Member.account_id).where(Member.user_id == user_id)
    )
    member_account_ids: List[int] = [row[0] for row in member_accounts.all() if row[0] is not None]
    if member_account_ids:
        await db.execute(delete(Account).where(Account.id.in_(member_account_ids)))

    # 2) 删除用户自身账户，级联删除 user 记录
    if db_user.account_id is not None:
        await db.execute(delete(Account).where(Account.id == db_user.account_id))

    await db.commit()
    return True
