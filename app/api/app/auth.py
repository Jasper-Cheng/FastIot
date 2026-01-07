from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta
from typing import Optional
import re

from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.crud.account import (
    get_account,
    get_account_by_phone,
    get_account_by_email,
    create_account,
    delete_account,
    update_account,
)
from app.crud.family import get_family
from app.crud.user_operation_log import user_operation_log
from app.models.account import (
    AccountCreate,
    AccountUpdate,
    Account, 
    AccountRole,
    LoginRequest,
    TokenResponse,
    RegisterRequest,
)
from app.models.user_operation_log import UserOperationLogCreate, OperationTypeEnum
from app.api.dependencies import get_current_account, get_current_token
from app.db.session import get_db
from app.core.rsa_crypto import rsa_crypto
from app.services.mqtt_service import mqtt_service

router = APIRouter()


@router.get("/rsa_public_key")
async def get_rsa_public_key():
    """获取RSA公钥接口
    
    前端需要先调用此接口获取公钥，然后使用公钥加密密码。
    返回公钥（PEM格式），前端可以使用此公钥加密密码。
    """
    try:
        public_key = rsa_crypto.get_public_key()
        return {
            "public_key": public_key
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取公钥失败: {str(e)}"
        )


async def _generate_login_token_and_notify(
    acc: Account,
    db: AsyncSession,
    extra_log_data: dict = None
) -> TokenResponse:
    """生成登录token并发送通知的共用函数
    
    Args:
        acc: 账户对象
        db: 数据库会话
        login_type: 登录类型（normal等）
        extra_log_data: 额外的日志数据
    
    Returns:
        TokenResponse: 包含token和用户信息的响应
    """
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    extra_claims = {
        "account_id": acc.id,
        "role": acc.role,
        "platform": "app",  # app平台标识
    }
    
    token = create_access_token(expires_delta=access_token_expires, extra_claims=extra_claims)
    
    # 记录登录操作
    try:
        log_description = f"用户通过App登录系统（{acc.nickname or acc.phone}）"
        log_extra = extra_log_data or {}
        
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=OperationTypeEnum.login,
                description=log_description,
                extra=log_extra if log_extra else None
            ),
            account_id=acc.id
        )
    except Exception as e:
        # 记录操作失败不影响登录流程
        print(f"记录登录操作失败: {e}")
    
    return TokenResponse(
        access_token=token,
        role=acc.role,
        account=Account.model_validate(acc)
    )


@router.post("/login", response_model=TokenResponse)
async def login(db: AsyncSession = Depends(get_db), payload: LoginRequest = Body(...)):
    """用户登录：支持手机号登录

    说明：
    - phone 为手机号
    - 必须提供密码
    """
    # 验证手机号格式
    phone_pattern = r"^1\d{10}$"
    if not re.match(phone_pattern, payload.phone):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="手机号格式不正确")
    
    # 按手机号查找
    acc = await get_account_by_phone(db, payload.phone)

    if not acc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")

    # 手机号登录：必须提供密码
    if not payload.password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="手机号登录需要密码")
    
    # 解密密码
    try:
        plain_password = rsa_crypto.decrypt(payload.password)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"密码解密失败: {str(e)}"
        )
    
    if not acc.password or not verify_password(plain_password, acc.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")

    # 使用共用函数生成token并发送通知（app平台）
    return await _generate_login_token_and_notify(acc, db)


@router.post("/register", response_model=TokenResponse)
async def register(db: AsyncSession = Depends(get_db), req: RegisterRequest = Body(...)):
    """注册账号并自动登录

    必填: phone, password
    可选: nickname, gender, avatar
    """
    # 手机号格式校验
    phone_pattern = r"^1\d{10}$"
    if not re.match(phone_pattern, req.phone):
        raise HTTPException(status_code=400, detail="手机号格式不正确")

    # 手机号唯一性
    phone_exists = await get_account_by_phone(db, req.phone)
    if phone_exists:
        raise HTTPException(status_code=400, detail="手机号已被注册")

    # 规范化并校验邮箱（可选）
    norm_email = (req.email or None)
    if norm_email:
        v = norm_email.strip().lower()
        if v in ("", "string", "null", "undefined"):
            norm_email = None
        else:
            norm_email = v
            email_exists = await get_account_by_email(db, norm_email)
            if email_exists:
                raise HTTPException(status_code=400, detail="邮箱已被使用")

    # 如果有密码，先解密
    decrypted_password = None
    if req.password:
        try:
            decrypted_password = rsa_crypto.decrypt(req.password)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"密码解密失败: {str(e)}"
            )
    
    acc = await create_account(
        db,
        AccountCreate(
            password=decrypted_password,
            phone=req.phone,
            nickname=req.nickname,
            gender=req.gender,  # type: ignore[arg-type]
            email=norm_email,
            avatar=req.avatar,
            role=AccountRole.user,
        ),
    )

    # 记录注册操作
    try:
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=OperationTypeEnum.register,
                description=f"用户通过App注册新账号（{acc.nickname or acc.phone}）",
                extra={
                    "registration_type": "user",
                    "phone": acc.phone,
                    "email": acc.email,
                    "platform": "app"
                }
            ),
            account_id=acc.id
        )
    except Exception as e:
        # 记录操作失败不影响注册流程
        print(f"记录注册操作失败: {e}")

    # 注册成功后自动登录
    return await _generate_login_token_and_notify(acc, db)


@router.post("/logout")
async def logout(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    current_account: Account = Depends(get_current_account)
):
    """用户登出"""
    
    # 记录登出操作
    try:
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=OperationTypeEnum.logout,
                description=f"用户从App登出系统（{current_account.nickname or current_account.phone}）",
                extra={"platform": "app"}
            ),
            account_id=current_account.id
        )
    except Exception as e:
        # 记录操作失败不影响登出流程
        print(f"记录登出操作失败: {e}")

    return {}


@router.get("/profile", response_model=Account)
async def get_profile(
    db: AsyncSession = Depends(get_db),
    current_account: Account = Depends(get_current_account)
):
    """获取当前用户信息"""
    return Account.model_validate(current_account)


@router.patch("/profile", response_model=Account)
async def update_profile(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    current_account: Account = Depends(get_current_account),
    account_update: AccountUpdate = Body(...)
):
    """更新当前用户信息
    
    接收一个对象，只更新提供的字段：
    - nickname: 昵称
    - gender: 性别 (male/female/other)
    - email: 邮箱
    - phone: 手机号
    - avatar: 头像URL
    - password: 密码（RSA加密的Base64字符串，会自动解密）
    """
    # 如果提供了密码，需要先解密
    update_data = account_update.dict(exclude_unset=True)
    
    if "password" in update_data and update_data["password"]:
        try:
            # RSA解密密码
            plain_password = rsa_crypto.decrypt(update_data["password"])
            # 验证密码长度
            if len(plain_password) < 6:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="密码长度至少6位"
                )
            update_data["password"] = plain_password
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"密码解密失败: {str(e)}"
            )
    
    # 如果提供了手机号，检查是否已被其他账号使用
    if "phone" in update_data and update_data["phone"]:
        existing_account = await get_account_by_phone(db, update_data["phone"])
        if existing_account and existing_account.id != current_account.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该手机号已被其他账号使用"
            )
    
    # 如果提供了邮箱，检查是否已被其他账号使用
    if "email" in update_data and update_data["email"]:
        existing_account = await get_account_by_email(db, update_data["email"])
        if existing_account and existing_account.id != current_account.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该邮箱已被其他账号使用"
            )
    
    # 创建更新对象
    update_obj = AccountUpdate(**update_data)
    
    # 更新账号信息
    updated_account = await update_account(db, current_account.id, update_obj)
    
    if not updated_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="账号不存在"
        )
    
    # 记录操作日志
    try:
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=OperationTypeEnum.account_update,
                description="通过App更新用户信息",
                extra={
                    "updated_fields": list(update_data.keys()),
                    "platform": "app"
                }
            ),
            account_id=current_account.id
        )
    except Exception as e:
        # 记录操作失败不影响更新流程
        print(f"记录操作日志失败: {e}")
    
    # 暂时不发送家庭消息通知用户信息更新
    # try:
    #     account_id = token_info.get("account_id")
    #     role = token_info.get("role")
    #     if account_id is not None:
    #         # 构建更新的字段描述和值
    #         updated_fields = {}
    #         field_names = {
    #             "nickname": "昵称",
    #             "gender": "性别",
    #             "email": "邮箱",
    #             "phone": "手机号",
    #             "avatar": "头像",
    #             "password": "密码"
    #         }
    #         
    #         # 构建包含字段名和值的字典（使用英文字段名作为键）
    #         for field, value in update_data.items():
    #             if field == "password":
    #                 # 密码字段不显示值，只显示已更新
    #                 updated_fields[field] = "已更新"
    #             else:
    #                 updated_fields[field] = value
    #         
    #         # 构建显示名称列表用于消息文本
    #         field_display_names = []
    #         for field in update_data.keys():
    #             if field == "password":
    #                 field_display_names.append("密码")
    #             else:
    #                 field_display_names.append(field_names.get(field, field))
    #         
    #         if field_display_names:
    #             message_text = f"用户信息已更新：{', '.join(field_display_names)}"
    #         else:
    #             message_text = "用户信息已更新"
    #         
    #         # 查询该用户的所有家庭，然后为每个家庭发送消息
    #         from app.crud.family import get_families_by_account
    #         families = await get_families_by_account(db, account_id)
    #         
    #         for family in families:
    #             if family.id is not None:
    #                 try:
    #                     await mqtt_service.publish_home_notice(
    #                         home_id=str(family.id),
    #                         payload={
    #                             "method": "family.message",
    #                             "params": {
    #                                 "type": "account.update",
    #                                 "data": {
    #                                     "senderId": account_id,
    #                                     "senderRole": role,
    #                                     "title": f"{current_account.nickname} 用户信息更新",
    #                                     "message": message_text,
    #                                     "level": "normal",
    #                                     "accountId": account_id,
    #                                     "updatedFields": updated_fields
    #                                 }
    #                             }
    #                         }
    #                     )
    #                 except Exception as e:
    #                     print(f"发送用户信息更新消息失败 (family_id={family.id}): {e}")
    # except Exception as e:
    #     # 发送消息失败不影响更新流程
    #     print(f"发送用户信息更新消息失败: {e}")
    
    return Account.model_validate(updated_account)


@router.get("/current-family")
async def get_current_family(
    db: AsyncSession = Depends(get_db),
    current_account: Account = Depends(get_current_account)
):
    """获取当前家庭信息"""
    if not current_account.current_family_id:
        raise HTTPException(status_code=404, detail="未设置当前家庭")
    
    family = await get_family(db, current_account.current_family_id)
    if not family:
        raise HTTPException(status_code=404, detail="当前家庭不存在")
    
    return {
        "id": family.id,
        "name": family.name,
        "avatar": family.avatar,
        "description": family.description,
        "invite_code": family.invite_code,
        "created_at": family.created_at,
        "updated_at": family.updated_at
    }


@router.patch("/current-family", response_model=Account)
async def update_current_family(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    current_account: Account = Depends(get_current_account),
    family_id: Optional[int] = Query(None, description="家庭ID，如果提供则设置为当前家庭；如果为None则设置为个人使用")
):
    """更新当前使用的家庭ID
    
    - 如果提供 family_id：验证用户是否是家庭成员，然后设置为当前家庭
    - 如果 family_id 为 None：设置为个人使用（current_family_id = NULL）
    """
    account_id = token_info["account_id"]
    
    # 如果提供了 family_id，验证用户是否是家庭成员
    if family_id is not None:
        from app.crud.family_member import get_family_member_by_family_and_account
        
        # 验证家庭是否存在
        family = await get_family(db, family_id)
        if not family:
            raise HTTPException(status_code=404, detail="家庭不存在")
        
        # 验证用户是否是家庭成员
        family_member = await get_family_member_by_family_and_account(db, family_id, account_id)
        if not family_member:
            raise HTTPException(status_code=403, detail="无权访问此家庭")
    
    # 直接更新 current_family_id（因为 update_account 使用 exclude_unset=True 可能排除 None 值）
    current_account.current_family_id = family_id
    await db.commit()
    await db.refresh(current_account)
    
    return current_account


@router.delete("/account")
async def delete_account_endpoint(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    current_account: Account = Depends(get_current_account)
):
    """注销账号（删除当前登录用户的账号）
    
    不需要接收参数，会自动删除当前登录用户的账号。
    删除前会：
    1. 如果账号是家庭创建者，自动删除这些家庭（会级联删除家庭成员和设备关联）
    2. 从所有家庭中移除设备关联（family_device 表）
    3. 更新设备状态为 unbound
    4. 记录操作日志
    5. 删除账号（会级联删除家庭成员关系、签到记录、积分记录、反馈、操作日志等）
    
    注意：
    - device.account_id 会在删除账号时自动设为 NULL（ON DELETE SET NULL）
    - family_member 记录会在删除账号时自动删除（ON DELETE CASCADE）
    """
    account_id = token_info["account_id"]
    
    # 如果账号是任何家庭的创建者，先删除这些家庭
    from app.crud.family_member import get_family_members_by_account
    from app.models.family_member import FamilyMemberRole
    from app.crud.family import get_family, delete_family
    
    family_members = await get_family_members_by_account(db, account_id)
    creator_families = [fm for fm in family_members if fm.role == FamilyMemberRole.creator]
    
    # 删除所有创建的家庭
    deleted_families = []  # 记录成功删除的家庭信息
    for fm in creator_families:
        family = await get_family(db, fm.family_id)
        if family:
            # 保存家庭信息用于后续日志
            family_id = family.id
            family_name = family.name
            
            # 先删除家庭（会级联删除家庭成员和设备关联）
            # delete_family 内部已经提交事务
            success = await delete_family(db, fm.family_id)
            
            # 删除成功后保存家庭信息
            if success:
                deleted_families.append({
                    "familyId": family_id,
                    "familyName": family_name
                })
    
    # 如果删除了家庭，记录一条日志
    if deleted_families:
        # 记录删除家庭的操作日志（仅一条）
        try:
            if len(deleted_families) == 1:
                description = f"通过App删除家庭: {deleted_families[0]['familyName']}（账号注销时自动删除）"
                extra = {
                    "family_id": deleted_families[0]["familyId"],
                    "family_name": deleted_families[0]["familyName"],
                    "reason": "account_deletion",
                    "platform": "app"
                }
            else:
                family_names = [f["familyName"] for f in deleted_families]
                description = f"通过App删除 {len(deleted_families)} 个家庭（账号注销时自动删除）: {', '.join(family_names)}"
                extra = {
                    "families": deleted_families,
                    "count": len(deleted_families),
                    "reason": "account_deletion",
                    "platform": "app"
                }
            
            await user_operation_log.create(
                db=db,
                obj_in=UserOperationLogCreate(
                    operation_type=OperationTypeEnum.family_delete,
                    description=description,
                    extra=extra
                ),
                account_id=account_id
            )
        except Exception as e:
            print(f"记录删除家庭操作日志失败: {e}")
        
        # 暂时不发送家庭消息通知
        # try:
        #     role = token_info.get("role")
        #     for deleted_family in deleted_families:
        #         deleted_family_id = deleted_family.get("familyId")
        #         if deleted_family_id is not None:
        #             try:
        #                 await mqtt_service.publish_home_notice(
        #                     home_id=str(deleted_family_id),
        #                     payload={
        #                         "method": "family.message",
        #                         "params": {
        #                             "type": "family.delete",
        #                             "data": {
        #                                 "senderId": account_id,
        #                                 "senderRole": role,
        #                                 "title": "家庭删除",
        #                                 "message": f"家庭 {deleted_family['familyName']} 已删除",
        #                                 "level": "warning",
        #                                 "familyId": deleted_family_id,
        #                                 "familyName": deleted_family["familyName"]
        #                             }
        #                         }
        #                     }
        #                 )
        #             except Exception as e:
        #                 print(f"发送删除家庭消息失败 (family_id={deleted_family_id}): {e}")
        # except Exception as e:
        #     # 发送消息失败不影响删除流程
        #     print(f"发送删除家庭消息失败: {e}")
    
    # 记录操作日志（在删除前记录，因为删除后日志也会被级联删除）
    try:
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=OperationTypeEnum.account_delete,
                description=f"通过App注销账号：{current_account.nickname or current_account.phone}",
                extra={
                    "account_id": account_id,
                    "nickname": current_account.nickname,
                    "phone": current_account.phone,
                    "platform": "app"
                }
            ),
            account_id=account_id
        )
    except Exception as e:
        # 记录操作失败不影响注销流程
        print(f"记录操作日志失败: {e}")
    
    # 处理设备：从所有家庭中移除，并更新状态
    # 注意：device.account_id 会在删除账号时自动设为 NULL（ON DELETE SET NULL）
    from app.crud.device import get_devices_by_account
    from app.crud.family_device import delete_all_family_devices_by_device
    from app.models.device import DeviceStatus
    
    devices = await get_devices_by_account(db, account_id)
    for device in devices:
        # 从所有家庭中移除设备（必须手动处理，因为 family_device 没有 account_id 外键）
        await delete_all_family_devices_by_device(db, device.id)
        # 更新设备状态为 unbound（数据库不会自动更新状态）
        device.status = DeviceStatus.unbound
        # 不需要手动设置 device.account_id = None，数据库会自动处理（ON DELETE SET NULL）
    
    await db.commit()
    
    # 删除账号（会级联删除家庭成员关系、签到记录、积分记录、反馈、操作日志等）
    # device.account_id 会自动设为 NULL（ON DELETE SET NULL）
    from app.crud.account import delete_account as delete_account_crud
    success = await delete_account_crud(db, account_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="账号不存在"
        )
    
    await db.commit()
    
    return {"message": "账号已成功注销"}

