from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from app.db.models.account import Account
from app.models.account import AccountCreate, AccountUpdate
from app.core.security import get_password_hash
from typing import Optional, List, Tuple

async def get_account(db: AsyncSession, account_id: int) -> Optional[Account]:
    """根据ID获取账号"""
    result = await db.execute(select(Account).filter(Account.id == account_id))
    return result.scalar_one_or_none()

async def get_account_by_unionid(db: AsyncSession, unionid: str) -> Optional[Account]:
    """根据unionid获取账号"""
    result = await db.execute(select(Account).filter(Account.unionid == unionid))
    return result.scalar_one_or_none()

async def get_account_by_email(db: AsyncSession, email: str) -> Optional[Account]:
    """根据邮箱获取账号"""
    result = await db.execute(select(Account).filter(Account.email == email))
    return result.scalar_one_or_none()

async def get_account_by_phone(db: AsyncSession, phone: str) -> Optional[Account]:
    """根据手机号获取账号"""
    result = await db.execute(select(Account).filter(Account.phone == phone))
    return result.scalar_one_or_none()

async def create_account(db: AsyncSession, account: AccountCreate) -> Account:
    """创建新账号"""
    password_hash = None
    if account.password:
        password_hash = get_password_hash(account.password)
    
    db_account = Account(
        password=password_hash,
        nickname=account.nickname,
        gender=account.gender,
        phone=account.phone,
        email=account.email,
        avatar=account.avatar,
        role=account.role or 'member'
    )
    db.add(db_account)
    await db.commit()
    await db.refresh(db_account)
    return db_account

async def update_account(db: AsyncSession, account_id: int, account: AccountUpdate) -> Optional[Account]:
    """更新账号信息"""
    db_account = await get_account(db, account_id)
    if not db_account:
        return None
    
    update_data = account.dict(exclude_unset=True)
    if "password" in update_data and update_data["password"]:
        update_data["password"] = get_password_hash(update_data["password"])
    elif "password" in update_data and update_data["password"] is None:
        # 如果密码为None，则不更新密码字段
        update_data.pop("password")
    
    for field, value in update_data.items():
        setattr(db_account, field, value)
    
    await db.commit()
    await db.refresh(db_account)
    return db_account

async def delete_account(db: AsyncSession, account_id: int) -> bool:
    """删除账号"""
    db_account = await get_account(db, account_id)
    if not db_account:
        return False
    
    await db.delete(db_account)
    await db.commit()
    return True

async def get_accounts_with_pagination(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 10,
    nickname: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    role: Optional[str] = None
) -> Tuple[List[Account], int]:
    """获取管理员列表（支持分页和搜索）"""
    query = select(Account)
    count_query = select(func.count(Account.id))
    
    # 构建搜索条件
    conditions = []
    if nickname:
        conditions.append(Account.nickname.like(f"%{nickname}%"))
    if phone:
        conditions.append(Account.phone.like(f"%{phone}%"))
    if email:
        conditions.append(Account.email.like(f"%{email}%"))
    if role:
        conditions.append(Account.role == role)
    
    if conditions:
        query = query.filter(or_(*conditions))
        count_query = count_query.filter(or_(*conditions))
    
    # 获取总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # 获取分页数据
    result = await db.execute(query.offset(skip).limit(limit))
    accounts = result.scalars().all()
    
    return accounts, total
