from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.member import Member
from app.models.member import MemberCreate, MemberUpdate
from app.core.security import get_password_hash, verify_password
from typing import Optional, List

async def get_member(db: AsyncSession, member_id: int) -> Optional[Member]:
    """根据ID获取成员"""
    result = await db.execute(select(Member).filter(Member.id == member_id))
    return result.scalar_one_or_none()

async def get_member_by_account(db: AsyncSession, account: str) -> Optional[Member]:
    """根据账号获取成员"""
    result = await db.execute(select(Member).filter(Member.account == account))
    return result.scalar_one_or_none()

async def get_members_by_user(db: AsyncSession, user_id: int, skip: int = 0, limit: int = 100) -> List[Member]:
    """获取用户下的所有成员"""
    result = await db.execute(
        select(Member).filter(Member.user_id == user_id).offset(skip).limit(limit)
    )
    return result.scalars().all()

async def create_member(db: AsyncSession, member: MemberCreate) -> Member:
    """创建新成员"""
    hashed_password = None
    if member.password:
        hashed_password = get_password_hash(member.password)
    
    db_member = Member(
        user_id=member.user_id,
        name=member.name,
        gender=member.gender,
        account=member.account,
        password=hashed_password,
        phone=member.phone,
        email=member.email,
        avatar=member.avatar
    )
    db.add(db_member)
    await db.commit()
    await db.refresh(db_member)
    return db_member

async def update_member(db: AsyncSession, member_id: int, member: MemberUpdate) -> Optional[Member]:
    """更新成员信息"""
    db_member = await get_member(db, member_id)
    if not db_member:
        return None
    
    update_data = member.dict(exclude_unset=True)
    if "password" in update_data and update_data["password"]:
        update_data["password"] = get_password_hash(update_data["password"])
    
    for field, value in update_data.items():
        setattr(db_member, field, value)
    
    await db.commit()
    await db.refresh(db_member)
    return db_member

async def delete_member(db: AsyncSession, member_id: int) -> bool:
    """删除成员"""
    db_member = await get_member(db, member_id)
    if not db_member:
        return False
    
    await db.delete(db_member)
    await db.commit()
    return True

async def verify_member_password(member: Member, password: str) -> bool:
    """验证成员密码"""
    if not member.password:
        return False
    return verify_password(password, member.password)
