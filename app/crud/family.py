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

async def count_created_families_by_account(db: AsyncSession, account_id: int) -> int:
    """统计账号作为创建者创建的家庭数量"""
    from app.db.models.family_member import FamilyMember
    from app.models.family_member import FamilyMemberRole
    from sqlalchemy import func
    
    result = await db.execute(
        select(func.count(FamilyMember.id))
        .filter(
            FamilyMember.account_id == account_id,
            FamilyMember.role == FamilyMemberRole.creator
        )
    )
    return result.scalar() or 0

async def create_family(db: AsyncSession, family: FamilyCreate, creator_account_id: int) -> Family:
    """创建家庭
    
    限制：每个账号最多只能创建6个家庭
    """
    # 检查创建家庭数量限制
    created_count = await count_created_families_by_account(db, creator_account_id)
    if created_count >= 6:
        raise ValueError("每个账号最多只能创建6个家庭")
    
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
    
    # 获取创建者账号信息，用于设置nickname
    from app.crud.account import get_account
    creator_account = await get_account(db, creator_account_id)
    nickname = None
    if creator_account and creator_account.nickname:
        nickname = creator_account.nickname
    
    # 创建家庭成员记录（创建者）
    from app.db.models.family_member import FamilyMember
    from app.models.family_member import FamilyMemberRole
    family_member = FamilyMember(
        family_id=db_family.id,
        account_id=creator_account_id,
        role=FamilyMemberRole.creator,
        nickname=nickname
    )
    db.add(family_member)
    await db.commit()
    
    # 自动将创建者的所有设备添加到家庭
    from app.crud.family_device import add_account_devices_to_family
    await add_account_devices_to_family(db, creator_account_id, db_family.id)
    
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

