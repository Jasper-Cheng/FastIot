from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.account import AccountUpdate

from app.db.session import get_db
from app.crud.user import get_user, delete_user
from app.crud.account import get_account, update_account, get_account_by_phone, get_account_by_email
from app.crud.user_operation_log import user_operation_log
from app.models.user import User, UserUpdateRequest
from app.models.user_operation_log import UserOperationLogCreate, OperationTypeEnum
from app.api.dependencies import get_current_token
from app.models.account import AccountRole
from app.services.websocket_tool import websocket_tool
router = APIRouter()


@router.get("/", response_model=User)
async def get_user_detail(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    user_id = token_info["user_id"]
    user = await get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.put("/", response_model=User)
async def update_user_detail(
    payload: UserUpdateRequest, 
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """更新用户信息
    
    更新用户的账号信息，包括账号名、姓名、性别、手机号、邮箱、头像、密码等
    """
    user_id = token_info["user_id"]

    if token_info["role"] != AccountRole.owner:
        raise HTTPException(status_code=403, detail="无权更新用户信息")

    # 读取用户
    u = await get_user(db, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 至少提供一个可更新字段
    if not any([
        payload.nickname is not None,
        payload.gender is not None,
        payload.phone is not None,
        payload.email is not None,
        payload.avatar is not None,
        payload.password is not None,
    ]):
        raise HTTPException(status_code=400, detail="至少提供一个可更新字段")

    # 变更手机号时验证格式并检重
    if payload.phone is not None:
        # 验证手机号格式
        import re
        if not re.match(r"^1\d{10}$", payload.phone):
            raise HTTPException(status_code=400, detail="手机号格式不正确")
        
        existed_phone = await get_account_by_phone(db, payload.phone)
        if existed_phone and existed_phone.id != u.account_id:
            raise HTTPException(status_code=400, detail="手机号已被使用")

    # 规范化并检重邮箱
    norm_email = None
    if payload.email is not None:
        v = (payload.email or "").strip().lower()
        if v in ("", "string", "null", "undefined"):
            norm_email = None
        else:
            norm_email = v
            existed_email = await get_account_by_email(db, norm_email)
            if existed_email and existed_email.id != u.account_id:
                raise HTTPException(status_code=400, detail="邮箱已被使用")

    # 仅传递有值的字段
    updated: dict = {}
    if payload.nickname is not None:
        updated["nickname"] = payload.nickname
    if payload.gender is not None:
        updated["gender"] = payload.gender  # type: ignore[assignment]
    if payload.phone is not None:
        updated["phone"] = payload.phone
    if payload.email is not None:
        updated["email"] = norm_email
    if payload.avatar is not None:
        updated["avatar"] = payload.avatar
    if payload.password is not None:
        updated["password"] = payload.password

    # 更新账号信息并获取更新后的账号
    updated_account = await update_account(
        db,
        u.account_id,
        AccountUpdate(**updated),
    )
    
    if not updated_account:
        raise HTTPException(status_code=404, detail="账号不存在")
    
    # 构建更新数据（排除密码）
    update_data = {k: v for k, v in updated.items() if k != "password"}
    
    # 记录用户更新操作
    try:
        # 构建更新字段的描述
        updated_fields = []
        for field, value in updated.items():
            if field == "password":
                updated_fields.append("密码: [已更新]")
            else:
                updated_fields.append(f"{field}: {value}")
        
        description = f"更新用户信息（{updated_account.nickname or updated_account.phone if updated_account else f'ID:{user_id}'}）: {', '.join(updated_fields)}"
        
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=OperationTypeEnum.user_update,
                description=description,
                extra={
                    "updated_user_id": user_id,
                    "updated_account_id": u.account_id,
                    "updated_account_nickname": updated_account.nickname if updated_account else None,
                    "updated_fields": list(updated.keys()),
                    "updated_values": update_data
                }
            ),
            account_id=u.account_id
        )
    except Exception as e:
        # 记录操作失败不影响更新流程
        print(f"记录用户更新操作失败: {e}")
    
    # 发送family消息通知更新用户信息
    try:
        role = token_info.get("role")
        real_id = token_info.get("id")
        if role and real_id is not None:
            client_id = f"{role}_{real_id}"
            
            await websocket_tool.send_family_message(
                client_id=client_id,
                message_type="user.update",
                data={
                    "senderId": real_id,
                    "senderRole": role,
                    "title": "更新用户信息",
                    "message": f"已更新用户信息：{updated_account.nickname or updated_account.phone if updated_account else f'ID:{user_id}'}",
                    "level": "normal",
                    "userId": user_id,
                    "userName": updated_account.nickname if updated_account else None,
                    "updateData": update_data
                }
            )
    except Exception as e:
        # 发送消息失败不影响业务流程
        print(f"发送更新用户信息通知失败: {e}")
    
    # 刷新 user 对象以包含最新的 account 信息
    await db.refresh(u)
    return u


@router.delete("/")
async def remove_user(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """删除用户
    
    删除用户时会：
    - 将该用户的所有设备状态更新为 unbound，user_id 设为 NULL
    - 删除该用户下的所有成员
    - 删除该用户的所有房间
    - 删除该用户的账号信息
    - 设备保留但变为未绑定状态，可以被其他用户重新激活
    """
    user_id = token_info["user_id"]
    if token_info["role"] != AccountRole.owner:
        raise HTTPException(status_code=403, detail="无权删除用户")
    # 先获取要删除的用户信息，用于记录操作
    user_to_delete = await get_user(db, user_id)
    if not user_to_delete:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 获取用户账号信息
    account_to_delete = await get_account(db, user_to_delete.account_id)
    
    # 执行删除操作
    ok = await delete_user(db, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 记录删除用户操作
    try:
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=OperationTypeEnum.user_delete,  # 使用user_delete表示删除用户
                description=f"删除用户：{account_to_delete.nickname or account_to_delete.phone if account_to_delete else f'ID:{user_id}'}",
                extra={
                    "deleted_user_id": user_id,
                    "deleted_account_id": user_to_delete.account_id,
                    "deleted_account_nickname": account_to_delete.nickname if account_to_delete else None,
                    "deleted_user_name": account_to_delete.nickname if account_to_delete else None
                }
            ),
            account_id=user_to_delete.account_id  # 记录在被删除用户的账号下
        )
    except Exception as e:
        # 记录操作失败不影响删除流程
        print(f"记录删除用户操作失败: {e}")
    
    # 发送family消息通知删除用户
    try:
        role = token_info.get("role")
        real_id = token_info.get("id")
        if role and real_id is not None:
            client_id = f"{role}_{real_id}"
            await websocket_tool.send_family_message(
                client_id=client_id,
                message_type="user.delete",
                data={
                    "senderId": real_id,
                    "senderRole": role,
                    "title": "删除用户",
                    "message": f"已删除用户：{account_to_delete.nickname or account_to_delete.phone if account_to_delete else f'ID:{user_id}'}",
                    "level": "normal",
                    "userId": user_id,
                    "userName": account_to_delete.nickname if account_to_delete else None
                }
            )
    except Exception as e:
        # 发送消息失败不影响业务流程
        print(f"发送删除用户通知失败: {e}")
    
    return {"message": "删除成功，该用户的设备已变为未绑定状态"}


