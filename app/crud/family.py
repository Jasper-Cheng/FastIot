from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from app.db.models.family import Family
from app.models.family import FamilyCreate, FamilyUpdate
import secrets
import string

async def get_family(db: AsyncSession, family_id: int) -> Optional[Family]:
    """根据ID获取家庭"""
    result = await db.execute(select(Family).filter(Family.id == family_id))
    return result.scalar_one_or_none()

async def get_family_by_invite_code(db: AsyncSession, invite_code: str) -> Optional[Family]:
    """根据邀请码获取家庭"""
    result = await db.execute(select(Family).filter(Family.invite_code == invite_code))
    return result.scalar_one_or_none()

async def get_families_by_account(db: AsyncSession, account_id: int, skip: int = 0, limit: int = 100) -> List[Family]:
    """根据账号ID获取该账号所在的所有家庭"""
    from app.db.models.family_member import FamilyMember
    result = await db.execute(
        select(Family)
        .join(FamilyMember, Family.id == FamilyMember.family_id)
        .filter(FamilyMember.account_id == account_id)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def create_family(db: AsyncSession, family: FamilyCreate, creator_account_id: int) -> Family:
    """创建家庭"""
    # 生成邀请码
    invite_code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
    
    db_family = Family(
        name=family.name,
        avatar=family.avatar,
        description=family.description,
        invite_code=invite_code
    )
    db.add(db_family)
    await db.commit()
    await db.refresh(db_family)
    
    # 创建家庭成员记录（创建者）
    from app.db.models.family_member import FamilyMember
    from app.models.family_member import FamilyMemberRole
    family_member = FamilyMember(
        family_id=db_family.id,
        account_id=creator_account_id,
        role=FamilyMemberRole.creator
    )
    db.add(family_member)
    await db.commit()
    
    return db_family

async def update_family(db: AsyncSession, family_id: int, family: FamilyUpdate) -> Optional[Family]:
    """更新家庭信息"""
    db_family = await get_family(db, family_id)
    if not db_family:
        return None
    
    update_data = family.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_family, field, value)
    
    await db.commit()
    await db.refresh(db_family)
    return db_family

async def delete_family(db: AsyncSession, family_id: int) -> bool:
    """删除家庭"""
    db_family = await get_family(db, family_id)
    if not db_family:
        return False
    
    await db.delete(db_family)
    await db.commit()
    return True

async def regenerate_invite_code(db: AsyncSession, family_id: int) -> Optional[str]:
    """重新生成家庭邀请码"""
    db_family = await get_family(db, family_id)
    if not db_family:
        return None
    
    invite_code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
    db_family.invite_code = invite_code
    await db.commit()
    await db.refresh(db_family)
    return invite_code

