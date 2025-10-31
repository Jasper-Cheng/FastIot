from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db.session import get_db
from app.crud.member_device_permission import (
    get_permissions_by_member,
    batch_update_member_permissions,
)
from app.crud.member import get_member, get_member_by_account_id
from app.crud.device import get_device
from app.crud.user_operation_log import user_operation_log
from app.models.user_operation_log import UserOperationLogCreate, OperationTypeEnum
from app.models.member_device_permission import (
    MemberDevicePermissionInDB,
    MemberPermissionBatchUpdateRequest,
    MemberPermissionBatchUpdateResponse,
)
from app.api.dependencies import get_current_token
from app.models.account import AccountRole

router = APIRouter()


@router.get("/", response_model=List[MemberDevicePermissionInDB])
async def list_member_device_permissions(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    member_id: int = Query(..., description="成员ID"),
    token_info: dict = Depends(get_current_token)
):
    """获取成员设备权限列表
    
    owner 可以查看自己 user 下所有成员的权限，member 只能查看自己的权限
    """
    # 权限验证：owner 验证成员归属，member 验证是否是自己
    if token_info["role"] == AccountRole.owner:
        user_id = token_info["user_id"]
        if not user_id:
            raise HTTPException(status_code=400, detail="当前账号没有关联的用户ID")
        member = await get_member(db, member_id)
        if not member or member.user_id != user_id:
            raise HTTPException(status_code=403, detail="无权查看此成员的权限")
    elif token_info["role"] == AccountRole.member:
        current_member = await get_member_by_account_id(db, token_info["account_id"])
        if not current_member or current_member.id != member_id:
            raise HTTPException(status_code=403, detail="无权查看此成员的权限")
    else:
        raise HTTPException(status_code=403, detail="无权查看成员权限")
    
    return await get_permissions_by_member(db, member_id, skip, limit)


@router.put("/member/{member_id}/batch-update", response_model=MemberPermissionBatchUpdateResponse)
async def batch_update_member_permissions_endpoint(
    member_id: int,
    payload: MemberPermissionBatchUpdateRequest,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    """批量更新成员设备权限
    
    根据传入的member_id，先删除该成员的所有权限，
    然后根据传入的设备ID列表重新添加权限
    
    只有 owner 才能更新成员权限，且只能更新自己 user 下的成员
    
    请求体示例：
    {
        "device_ids": [1, 2, 3]
    }
    """
    # 验证只有 owner 角色才能更新成员权限
    if token_info["role"] != AccountRole.owner:
        raise HTTPException(status_code=403, detail="无权更新成员权限")
    
    # 从 token 中获取 user_id
    user_id = token_info["user_id"]
    if not user_id:
        raise HTTPException(status_code=400, detail="当前账号没有关联的用户ID")
    
    # 验证成员存在
    member = await get_member(db, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    
    # 验证该成员是否属于当前 owner 的 user
    if member.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权更新此成员的权限")
    
    # 验证所有设备存在，并且都属于当前 owner 的 user
    for device_id in payload.device_ids:
        device = await get_device(db, device_id)
        if not device:
            raise HTTPException(status_code=400, detail=f"设备ID {device_id} 不存在")
        # 验证设备属于当前 owner 的 user
        if device.user_id != user_id:
            raise HTTPException(status_code=403, detail=f"无权为设备ID {device_id} 设置权限")
    
    try:
        # 执行批量更新
        updated_permissions = await batch_update_member_permissions(
            db=db,
            member_id=member_id,
            device_ids=payload.device_ids
        )
        
        # 记录权限更新操作
        try:
            # 获取成员账号信息
            from app.crud.account import get_account
            member_account = await get_account(db, member.account_id)
            member_account_name = member_account.account if member_account else f"成员ID:{member_id}"
            
            # 获取设备名称用于记录
            device_names = []
            for device_id in payload.device_ids:
                device = await get_device(db, device_id)
                if device:
                    device_names.append(device.name)
                else:
                    device_names.append(f"设备ID:{device_id}")
            
            await user_operation_log.create(
                db=db,
                obj_in=UserOperationLogCreate(
                    operation_type=OperationTypeEnum.permission_update,
                    description=f"更新成员设备权限：{member_account_name}（共{len(payload.device_ids)}个设备）",
                    extra={
                        "member_id": member_id,
                        "member_account_id": member.account_id,
                        "device_count": len(payload.device_ids),
                        "device_ids": payload.device_ids,
                        "device_names": device_names,
                        "user_id": member.user_id
                    }
                ),
                account_id=token_info["account_id"]
            )
        except Exception as e:
            # 记录操作失败不影响权限更新流程
            print(f"记录权限更新操作失败: {e}")
        
        return MemberPermissionBatchUpdateResponse(
            success=True,
            message="批量更新成功",
            data=updated_permissions
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量更新失败: {str(e)}")