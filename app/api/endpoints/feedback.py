from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.api.dependencies import get_db, get_current_token
from app.crud.feedback import feedback
from app.models.feedback import Feedback, FeedbackCreate
from app.models.account import AccountRole
from app.services.websocket_tool import websocket_tool

router = APIRouter()


@router.post("/", response_model=Feedback)
async def create_feedback(
    *,
    db: AsyncSession = Depends(get_db),
    feedback_in: FeedbackCreate,
    token_info: dict = Depends(get_current_token)
):
    """创建意见反馈"""
    created_feedback = await feedback.create(db=db, obj_in=feedback_in, account_id=token_info["account_id"])
    
    # 发送family消息通知创建意见反馈
    try:
        role = token_info.get("role")
        real_id = token_info.get("id")
        if role and real_id is not None:
            client_id = f"{role}_{real_id}"
            await websocket_tool.send_family_message(
                client_id=client_id,
                message_type="feedback.create",
                data={
                    "senderId": real_id,
                    "senderRole": role,
                    "title": "意见反馈",
                    "message": f"已创建意见反馈：{feedback_in.content[:50] if len(feedback_in.content) > 50 else feedback_in.content}",
                    "level": "normal",
                    "feedbackId": created_feedback.id,
                    "feedbackType": feedback_in.type if hasattr(feedback_in, 'type') else None,
                    "feedbackContent": feedback_in.content[:100] if len(feedback_in.content) > 100 else feedback_in.content
                }
            )
    except Exception as e:
        # 发送消息失败不影响业务流程
        print(f"发送意见反馈创建通知失败: {e}")
    
    return created_feedback


@router.get("/", response_model=List[Feedback])
async def get_feedbacks(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    order_by: str = Query("created_at"),
    order_desc: bool = Query(True),
    token_info: dict = Depends(get_current_token)
):
    """获取意见反馈列表"""
    # 根据用户角色决定返回的数据
    if token_info["role"] == AccountRole.admin:
        # 管理员可以看到所有反馈
        return await feedback.get_multi(
            db=db,
            skip=skip,
            limit=limit,
            type=type,
            status=status,
            source=source,
            order_by=order_by,
            order_desc=order_desc
        )
    elif token_info["role"] == AccountRole.owner:
        # 主账号可以看到自己和所有成员的反馈
        return await feedback.get_by_user_and_members(
            db=db,
            user_account_id=token_info["account_id"],
            skip=skip,
            limit=limit
        )
    elif token_info["role"] == AccountRole.member:
        # 成员可以看到自己和所属user的所有反馈
        # 获取成员所属的user的account_id
        from app.crud.member import get_user_account_id_by_member_account_id
        user_account_id = await get_user_account_id_by_member_account_id(db, token_info["account_id"])
        
        if user_account_id:
            # 返回user及其所有成员的反馈
            return await feedback.get_by_user_and_members(
                db=db,
                user_account_id=user_account_id,
                skip=skip,
                limit=limit
            )
        else:
            # 如果找不到所属user，只返回自己的反馈
            return await feedback.get_multi(
                db=db,
                skip=skip,
                limit=limit,
                account_id=token_info["account_id"],
                type=type,
                status=status,
                source=source,
                order_by=order_by,
                order_desc=order_desc
            )
    else:
        # 其他角色只能看到自己的反馈
        return await feedback.get_multi(
            db=db,
            skip=skip,
            limit=limit,
            account_id=token_info["account_id"],
            type=type,
            status=status,
            source=source,
            order_by=order_by,
            order_desc=order_desc
        )

