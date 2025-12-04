from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import Optional, List
from app.db.models.family_member import FamilyMember
from app.models.family_member import FamilyMemberCreate, FamilyMemberUpdate, FamilyMemberRole

async def get_family_member(db: AsyncSession, family_member_id: int) -> Optional[FamilyMember]:
    """根据ID获取家庭成员"""
    result = await db.execute(select(FamilyMember).filter(FamilyMember.id == family_member_id))
    return result.scalar_one_or_none()

async def get_family_member_by_family_and_account(
    db: AsyncSession, family_id: int, account_id: int
) -> Optional[FamilyMember]:
    """根据家庭ID和账号ID获取家庭成员"""
    result = await db.execute(
        select(FamilyMember).filter(
            FamilyMember.family_id == family_id,
            FamilyMember.account_id == account_id
        )
    )
    return result.scalar_one_or_none()

async def get_family_members_by_family(
    db: AsyncSession, family_id: int, skip: int = 0, limit: int = 100
) -> List[FamilyMember]:
    """根据家庭ID获取所有家庭成员"""
    result = await db.execute(
        select(FamilyMember)
        .filter(FamilyMember.family_id == family_id)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def get_family_members_by_account(
    db: AsyncSession, account_id: int, skip: int = 0, limit: int = 100
) -> List[FamilyMember]:
    """根据账号ID获取该账号的所有家庭成员记录"""
    result = await db.execute(
        select(FamilyMember)
        .filter(FamilyMember.account_id == account_id)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def create_family_member(db: AsyncSession, family_member: FamilyMemberCreate) -> FamilyMember:
    """创建家庭成员"""
    db_family_member = FamilyMember(
        family_id=family_member.family_id,
        account_id=family_member.account_id,
        role=family_member.role,
        nickname=family_member.nickname
    )
    db.add(db_family_member)
    await db.commit()
    await db.refresh(db_family_member)
    return db_family_member

async def update_family_member(
    db: AsyncSession, family_member_id: int, family_member: FamilyMemberUpdate
) -> Optional[FamilyMember]:
    """更新家庭成员信息"""
    db_family_member = await get_family_member(db, family_member_id)
    if not db_family_member:
        return None
    
    update_data = family_member.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_family_member, field, value)
    
    await db.commit()
    await db.refresh(db_family_member)
    return db_family_member

async def delete_family_member(db: AsyncSession, family_member_id: int) -> bool:
    """删除家庭成员"""
    db_family_member = await get_family_member(db, family_member_id)
    if not db_family_member:
        return False
    
    await db.delete(db_family_member)
    await db.commit()
    return True

async def remove_family_member_by_family_and_account(
    db: AsyncSession, family_id: int, account_id: int
) -> bool:
    """根据家庭ID和账号ID移除家庭成员"""
    result = await db.execute(
        delete(FamilyMember).filter(
            FamilyMember.family_id == family_id,
            FamilyMember.account_id == account_id
        )
    )
    await db.commit()
    return result.rowcount > 0

