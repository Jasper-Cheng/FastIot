from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Optional

from app.db.models.admin import Admin


async def get_admin_by_account_id(db: AsyncSession, account_id: int) -> Optional[Admin]:
    result = await db.execute(
        select(Admin)
        .options(selectinload(Admin.account))
        .filter(Admin.account_id == account_id)
    )
    return result.scalar_one_or_none()

