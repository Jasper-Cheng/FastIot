from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.crud.feedback import feedback as feedback_crud
from app.models.feedback import Feedback, FeedbackCreate, SourceEnum
from app.models.user_operation_log import OperationTypeEnum
from app.api.dependencies import get_current_token
from app.db.session import get_db
from app.api.utils import (
    extract_token_info,
    log_operation_with_token,
    send_personal_notice
)

router = APIRouter()

"""
用户反馈模块 - Client API

【App + Web 通用】
所有接口支持 App 和 Web 平台，平台信息通过 token.platform 字段识别。
"""


@router.post("/", response_model=Feedback, status_code=201)
async def create_feedback(
    *,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
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
    account_id, platform_str, _ = extract_token_info(token_info)
    
    # 将platform字符串直接转换为SourceEnum枚举
    try:
        source = SourceEnum(platform_str)
    except ValueError:
        valid_sources = [s.value for s in SourceEnum]
        raise HTTPException(status_code=400, detail=f"Token中的平台标识 '{platform_str}' 无效。有效值: {', '.join(valid_sources)}")
    
    # 创建反馈数据，添加source字段
    feedback_data = feedback_in.dict()
    feedback_data["source"] = source.value
    
    # 直接创建Feedback对象
    from app.db.models.feedback import Feedback as DBFeedback
    db_obj = DBFeedback(**feedback_data, account_id=account_id)
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    
    created_feedback = db_obj
    
    # 记录操作日志
    feedback_type = feedback_in.type if hasattr(feedback_in, 'type') and feedback_in.type else 'other'
    await log_operation_with_token(
        db=db,
        token_info=token_info,
        operation_type=OperationTypeEnum.feedback_create,
        description=f"创建意见反馈：{feedback_type}",
        extra={
            "feedback_id": created_feedback.id,
            "feedback_type": feedback_type,
            "feedback_name": feedback_in.name if hasattr(feedback_in, 'name') else None,
            "source": source.value
        }
    )

    # 发送个人通知
    await send_personal_notice(
        account_id=account_id,
        payload={
            "type": "feedback_created",
            "message": f"创建意见反馈：{feedback_type}",
            "feedback_id": created_feedback.id,
            "feedback_type": feedback_type,
            "feedback_name": feedback_in.name if hasattr(feedback_in, 'name') else None,
            "source": source.value,
            "operator_account_id": account_id
        }
    )
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
    """获取意见反馈列表（用户只能看到自己的反馈）"""
    return await feedback_crud.get_multi(
        db=db,
        skip=skip,
        limit=limit,
        account_id=extract_token_info(token_info)[0],
        type=type,
        status=status
    )

