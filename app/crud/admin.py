from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from typing import Optional, List

from app.db.models.admin import Admin
from app.db.models.account import Account
from app.models.admin import AdminBase


async def get_admin(db: AsyncSession, admin_id: int) -> Optional[Admin]:
    result = await db.execute(
        select(Admin)
        .options(selectinload(Admin.account))
        .filter(Admin.id == admin_id)
    )
    return result.scalar_one_or_none()


async def get_admin_by_account_id(db: AsyncSession, account_id: int) -> Optional[Admin]:
    result = await db.execute(
        select(Admin)
        .options(selectinload(Admin.account))
        .filter(Admin.account_id == account_id)
    )
    return result.scalar_one_or_none()


async def get_admins(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Admin]:
    result = await db.execute(
        select(Admin)
        .options(selectinload(Admin.account))
        .offset(skip).limit(limit)
    )
    return result.scalars().all()


async def create_admin(db: AsyncSession, payload: AdminBase) -> Admin:
    # 校验账号存在且角色为 admin
    acc = await db.get(Account, payload.account_id)
    if acc is None:
        raise ValueError("账号不存在")
    if getattr(acc, "role", None) != "admin":
        raise ValueError("账号角色不是 admin")
    existed = await get_admin_by_account_id(db, payload.account_id)
    if existed:
        return existed

    admin = Admin(account_id=payload.account_id)
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    return admin


async def delete_admin(db: AsyncSession, admin_id: int) -> bool:
    admin = await get_admin(db, admin_id)
    if not admin:
        return False
    await db.delete(admin)
    await db.commit()
    return True


