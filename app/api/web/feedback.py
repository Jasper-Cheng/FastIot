from fastapi import APIRouter, Depends, Query, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.api.dependencies import get_current_token, get_family_clients
from app.db.session import get_db
from app.crud.feedback import feedback
from app.models.feedback import Feedback, FeedbackCreate, SourceEnum
from app.models.account import AccountRole
from app.services.websocket_tool import websocket_tool

router = APIRouter()


@router.post("/", response_model=Feedback)
async def create_feedback(
    *,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    family_clients: list[str] = Depends(get_family_clients),
    feedback_in: FeedbackCreate = Body(...)
):
    """创建意见反馈
    
    参数说明：
    - name: 反馈人姓名（可选）
    - type: 反馈类型（bug/feature/improvement/complaint/praise/other）
    - content: 反馈内容（必填）
    - contact_info: 联系方式（可选）
    - extra: 扩展信息，JSON格式（可选）
    
    注意：source字段会自动从token中的platform获取，无需传入
    """
    # 从token中获取platform并转换为source
    platform_str = token_info.get("platform", "web")
    
    # 将platform字符串直接转换为SourceEnum枚举
    try:
        source = SourceEnum(platform_str)
    except ValueError:
        # 如果platform字符串不是有效的SourceEnum枚举值，抛出异常
        valid_sources = [s.value for s in SourceEnum]
        raise HTTPException(
            status_code=400,
            detail=f"Token中的平台标识 '{platform_str}' 无效。有效值: {', '.join(valid_sources)}"
        )
    
    # 创建反馈数据，添加source字段（使用枚举的value值）
    feedback_data = feedback_in.dict()
    feedback_data["source"] = source.value
    
    # 直接创建Feedback对象（因为Feedback模型需要source字段）
    from app.db.models.feedback import Feedback as DBFeedback
    db_obj = DBFeedback(**feedback_data, account_id=token_info["account_id"])
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    
    created_feedback = db_obj
    
    # 发送family消息通知创建意见反馈
    try:
        platform = token_info.get("platform", "web")
        role = token_info.get("role")
        account_id = token_info.get("account_id")
        if account_id is not None:
            client_id = f"{platform}_{account_id}"
            await websocket_tool.send_family_message(
                client_id=client_id,
                message_type="feedback.create",
                data={
                    "senderId": account_id,
                    "senderRole": role,
                    "title": "意见反馈",
                    "message": f"用户 {feedback_in.name} 创建了意见反馈",
                    "level": "normal",
                    "feedbackId": created_feedback.id,
                    "feedbackType": feedback_in.type if hasattr(feedback_in, 'type') else None,
                    "feedbackContent": feedback_in.content[:100] if len(feedback_in.content) > 100 else feedback_in.content
                },
                family_clients=family_clients
            )
    except Exception as e:
        # 发送消息失败不影响业务流程
        print(f"发送意见反馈创建通知失败: {e}")
    
    return created_feedback


@router.get("/", response_model=List[Feedback])
async def get_feedbacks(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
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
            status=status
        )
    else:
        # 普通用户可以看到自己和所在家庭所有成员的反馈
        return await feedback.get_by_family_members(
            db=db,
            account_id=token_info["account_id"],
            skip=skip,
            limit=limit,
            type=type,
            status=status
        )

