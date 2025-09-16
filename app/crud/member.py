from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.db.models.member import Member
from app.models.member import MemberCreate, MemberUpdate
from typing import Optional, List

async def get_member(db: AsyncSession, member_id: int) -> Optional[Member]:
    """根据ID获取成员"""
    result = await db.execute(
        select(Member)
        .options(selectinload(Member.account))
        .filter(Member.id == member_id)
    )
    return result.scalar_one_or_none()

async def get_member_by_account_id(db: AsyncSession, account_id: int) -> Optional[Member]:
    """根据账号ID获取成员"""
    result = await db.execute(
        select(Member)
        .options(selectinload(Member.account))
        .filter(Member.account_id == account_id)
    )
    return result.scalar_one_or_none()

async def get_members_by_user(db: AsyncSession, user_id: int, skip: int = 0, limit: int = 100) -> List[Member]:
    """获取用户下的所有成员"""
    result = await db.execute(
        select(Member)
        .options(selectinload(Member.account))
        .filter(Member.user_id == user_id)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def create_member(db: AsyncSession, member: MemberCreate) -> Member:
    """创建新成员"""
    db_member = Member(
        user_id=member.user_id,
        account_id=member.account_id
    )
    db.add(db_member)
    await db.commit()
    await db.refresh(db_member)
    return db_member

async def update_member(db: AsyncSession, member_id: int, member: MemberUpdate) -> Optional[Member]:
    """更新成员信息（成员信息通过 account 表管理）"""
    # 成员表本身没有需要更新的字段，所有信息都在 account 表中
    return await get_member(db, member_id)

async def delete_member(db: AsyncSession, member_id: int) -> bool:
    """删除成员"""
    db_member = await get_member(db, member_id)
    if not db_member:
        return False
    
    await db.delete(db_member)
    await db.commit()
    return True
