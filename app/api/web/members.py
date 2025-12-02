from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db.session import get_db
from app.crud.member import get_members_by_user, get_member, create_member, delete_member
from app.crud.user import get_user
from sqlalchemy import select
from app.db.models.device import Device
from app.db.models.member_device_permission import MemberDevicePermission
from app.crud.account import create_account, get_account_by_phone, get_account_by_email, update_account, get_account, delete_account
from app.models.member import Member, MemberCreate, MemberInDB, MemberRegisterRequest, MemberUpdateRequest
from app.models.account import AccountCreate, AccountRole, AccountGender, AccountUpdate
from app.crud.user_operation_log import user_operation_log
from app.models.user_operation_log import UserOperationLogCreate, OperationTypeEnum
from app.api.dependencies import get_current_token
from app.services.websocket_tool import websocket_tool
from app.core.rsa_crypto import rsa_crypto
from fastapi import status
router = APIRouter()


@router.get("/", response_model=List[Member], response_model_exclude={"user"})
async def list_members(
    db: AsyncSession = Depends(get_db), 
    skip: int = Query(0, ge=0), 
    limit: int = Query(100, ge=1, le=200),
    token_info: dict = Depends(get_current_token)
):
    user_id = token_info["user_id"]
    return await get_members_by_user(db, user_id=user_id, skip=skip, limit=limit)


@router.post("/", response_model=MemberInDB)
async def create_member_for_user(
    payload: MemberRegisterRequest, 
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    # 验证只有 owner 角色才能创建成员
    if token_info["role"] != AccountRole.owner:
        raise HTTPException(status_code=403, detail="无权创建成员")
    
    # 从 token 中获取 user_id
    user_id = token_info["user_id"]
    
    # 校验 user 是否存在
    owner = await get_user(db, user_id)
    if not owner:
        raise HTTPException(status_code=400, detail="归属的用户不存在")

    # 规范化可选字符串字段
    norm_email = (payload.email or None)
    if norm_email:
        v = norm_email.strip().lower()
        if v in ("", "string", "null", "undefined"):
            norm_email = None

    # 验证手机号格式并校验唯一
    import re
    if not re.match(r"^1\d{10}$", payload.phone):
        raise HTTPException(status_code=400, detail="手机号格式不正确")
    
    phone_exists = await get_account_by_phone(db, payload.phone)
    if phone_exists:
        raise HTTPException(status_code=400, detail="手机号已被使用")

    # 校验邮箱唯一（如果提供）
    if norm_email:
        email_exists = await get_account_by_email(db, norm_email)
        if email_exists:
            raise HTTPException(status_code=400, detail="邮箱已被使用")
    
    # 解密密码（如果提供）
    decrypted_password = None
    if payload.password:
        try:
            decrypted_password = rsa_crypto.decrypt(payload.password)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"密码解密失败: {str(e)}"
            )
    
    # 1) 先创建 account，role 强制为 member
    acc = await create_account(
        db,
        AccountCreate(
            password=decrypted_password,
            phone=payload.phone,
            nickname=payload.nickname,
            gender=payload.gender,  # type: ignore[arg-type]
            email=norm_email,
            avatar=payload.avatar,
            role=AccountRole.member,
        ),
    )

    # 2) 创建 member 绑定 user_id 与 account_id
    m = await create_member(
        db,
        MemberCreate(user_id=user_id, account_id=acc.id),
    )
    
    # 3) 为成员添加该用户下所有设备默认控制权限
    device_ids_result = await db.execute(
        select(Device.id).where(Device.user_id == user_id)
    )
    device_ids = [row[0] for row in device_ids_result.all()]
    if device_ids:
        db.add_all([
            MemberDevicePermission(member_id=m.id, device_id=d_id)
            for d_id in device_ids
        ])
        await db.commit()

    # 记录添加成员操作
    try:
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=OperationTypeEnum.member_add,
                description=f"添加新成员：{acc.nickname or acc.phone}",
                extra={
                    "member_id": m.id,
                    "member_nickname": acc.nickname,
                    "member_phone": acc.phone,
                    "member_email": acc.email,
                    "user_id": user_id,
                    "account_id": acc.id
                }
            ),
            account_id=owner.account_id
        )
    except Exception as e:
        # 记录操作失败不影响创建流程
        print(f"记录添加成员操作失败: {e}")

    # 发送family消息通知创建成员
    try:
        role = token_info.get("role")
        real_id = token_info.get("id")
        if role and real_id is not None:
            client_id = f"{role}_{real_id}"
            await websocket_tool.send_family_message(
                client_id=client_id,
                message_type="member.create",
                data={
                    "senderId": real_id,
                    "senderRole": role,
                    "title": "创建成员",
                    "message": f"已创建成员：{acc.nickname or acc.phone}",
                    "level": "normal",
                    "memberId": m.id,
                    "memberName": acc.nickname,
                    "memberPhone": acc.phone
                }
            )
    except Exception as e:
        # 发送消息失败不影响业务流程
        print(f"发送创建成员通知失败: {e}")

    return m


@router.put("/{member_id}", response_model=MemberInDB)
async def update_member_detail(
    member_id: int, 
    payload: MemberUpdateRequest, 
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    # 从 token 中获取 user_id
    user_id = token_info["user_id"]
    
    # 读取成员
    m = await get_member(db, member_id)
    if not m:
        raise HTTPException(status_code=404, detail="成员不存在")
    
    # 验证该成员是否属于当前 owner 的 user
    if m.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权修改此成员")

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
        
        from app.crud.account import get_account_by_phone
        existed_phone = await get_account_by_phone(db, payload.phone)
        if existed_phone and existed_phone.id != m.account_id:
            raise HTTPException(status_code=400, detail="手机号已被使用")

    # 规范化并检重邮箱
    norm_email = None
    if payload.email is not None:
        v = (payload.email or "").strip().lower()
        if v in ("", "string", "null", "undefined"):
            norm_email = None
        else:
            norm_email = v
            from app.crud.account import get_account_by_email
            existed_email = await get_account_by_email(db, norm_email)
            if existed_email and existed_email.id != m.account_id:
                raise HTTPException(status_code=400, detail="邮箱已被使用")

    # 解密密码（如果提供）
    decrypted_password = None
    if payload.password is not None:
        try:
            decrypted_password = rsa_crypto.decrypt(payload.password)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"密码解密失败: {str(e)}"
            )

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
    if decrypted_password is not None:
        updated["password"] = decrypted_password

    await update_account(
        db,
        m.account_id,
        AccountUpdate(**updated),
    )

    # 记录更新成员操作
    try:
        # 获取更新后的账号信息
        updated_account = await get_account(db, m.account_id)
        
        # 构建更新字段的描述
        updated_fields = []
        for field, value in updated.items():
            if field == "password":
                updated_fields.append("密码: [已更新]")
            else:
                updated_fields.append(f"{field}: {value}")

        description = f"更新成员信息（{updated_account.nickname or updated_account.phone if updated_account else f'ID:{member_id}'}）: {', '.join(updated_fields)}"

        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=OperationTypeEnum.member_update,
                description=description,
                extra={
                    "member_id": member_id,
                    "member_account_id": m.account_id,
                    "member_account_nickname": updated_account.nickname if updated_account else None,
                    "updated_fields": list(updated.keys()),
                    "updated_values": {k: v for k, v in updated.items() if k != "password"},  # 不记录密码
                    "user_id": m.user_id
                }
            ),
            account_id=m.account_id
        )
    except Exception as e:
        # 记录操作失败不影响更新流程
        print(f"记录更新成员操作失败: {e}")

    # 发送family消息通知更新成员
    try:
        role = token_info.get("role")
        real_id = token_info.get("id")
        if role and real_id is not None:
            client_id = f"{role}_{real_id}"
            # 获取更新后的账号信息
            updated_account = await get_account(db, m.account_id)
            await websocket_tool.send_family_message(
                client_id=client_id,
                message_type="member.update",
                data={
                    "senderId": real_id,
                    "senderRole": role,
                    "title": "更新成员",
                    "message": f"已更新成员：{updated_account.nickname or updated_account.phone if updated_account else f'ID:{member_id}'} 的信息",
                    "level": "normal",
                    "memberId": member_id,
                    "memberName": updated_account.nickname if updated_account else None,
                    "updateData": {k: v for k, v in updated.items() if k != "password"}
                }
            )
    except Exception as e:
        # 发送消息失败不影响业务流程
        print(f"发送更新成员通知失败: {e}")

    # 重新返回成员（不展开 account）
    m = await get_member(db, member_id)
    return m


@router.delete("/{member_id}")
async def remove_member(
    member_id: int, 
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    
    # 从 token 中获取 user_id
    user_id = token_info["user_id"]
    
    # 先查询成员
    m = await get_member(db, member_id)
    if not m:
        raise HTTPException(status_code=404, detail="成员不存在")
    
    # 验证该成员是否属于当前 owner 的 user
    if m.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权删除此成员")

    try:
        # 在删除前获取成员账号信息（用于记录和发送消息）
        member_account = await get_account(db, m.account_id)
        member_account_name = member_account.nickname or member_account.phone if member_account else f"ID:{m.account_id}"
        member_name = member_account.nickname if member_account else None
        
        # 先删除 member（会级联删除权限等依赖）
        success = await delete_member(db, member_id)
        if not success:
            raise HTTPException(status_code=404, detail="成员删除失败")

        # 手动删除相关的 check_in 和 points 记录
        from sqlalchemy import delete
        from app.db.models.check_in import CheckIn
        from app.db.models.points import Points
        
        # 删除 check_in 记录
        await db.execute(delete(CheckIn).where(CheckIn.account_id == m.account_id))
        
        # 删除 points 记录
        await db.execute(delete(Points).where(Points.account_id == m.account_id))

        # 再删除其 account
        success = await delete_account(db, m.account_id)
        if not success:
            raise HTTPException(status_code=404, detail="账号删除失败")
        
        # 统一提交事务
        await db.commit()
        
        # 记录删除成员操作
        try:

            await user_operation_log.create(
                db=db,
                obj_in=UserOperationLogCreate(
                    operation_type=OperationTypeEnum.member_delete,
                    description=f"删除成员：{member_account_name}",
                    extra={
                        "member_id": member_id,
                        "member_account_id": m.account_id,
                        "member_account_nickname": member_account.nickname if member_account else None,
                        "member_name": member_name,
                        "member_phone": member_account.phone if member_account else None,
                        "member_email": member_account.email if member_account else None,
                        "user_id": m.user_id
                    }
                ),
                account_id=token_info["account_id"]
            )
        except Exception as e:
            # 记录操作失败不影响删除流程
            print(f"记录删除成员操作失败: {e}")
        
        # 发送family消息通知删除成员
        try:
            role = token_info.get("role")
            real_id = token_info.get("id")
            if role and real_id is not None:
                client_id = f"{role}_{real_id}"
                await websocket_tool.send_family_message(
                    client_id=client_id,
                    message_type="member.delete",
                    data={
                        "senderId": real_id,
                        "senderRole": role,
                        "title": "删除成员",
                        "message": f"已删除成员：{member_name or member_account_name}",
                        "level": "normal",
                        "memberId": member_id,
                        "memberName": member_name
                    }
                )
        except Exception as e:
            # 发送消息失败不影响业务流程
            print(f"发送删除成员通知失败: {e}")
        
        return {"message": "删除成功"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


