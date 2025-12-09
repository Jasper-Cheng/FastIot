from fastapi import APIRouter, Depends, Query, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.api.dependencies import get_current_token
from app.db.session import get_db
from app.crud.feedback import feedback
from app.crud.user_operation_log import user_operation_log
from app.models.feedback import Feedback, FeedbackCreate, SourceEnum
from app.models.account import AccountRole
from app.models.user_operation_log import UserOperationLogCreate, OperationTypeEnum

router = APIRouter()


@router.post("/", response_model=Feedback)
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
    
    # 记录操作日志
    try:
        account_id = token_info["account_id"]
        feedback_type = feedback_in.type if hasattr(feedback_in, 'type') and feedback_in.type else 'other'
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=OperationTypeEnum.feedback_create,
                description=f"创建意见反馈：{feedback_type}",
                extra={
                    "feedback_id": created_feedback.id,
                    "feedback_type": feedback_type,
                    "feedback_name": feedback_in.name if hasattr(feedback_in, 'name') else None,
                    "source": source.value
                }
            ),
            account_id=account_id
        )
    except Exception as e:
        # 记录操作失败不影响创建流程
        print(f"记录意见反馈创建操作日志失败: {e}")
    
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
    return await feedback.get_multi(
        db=db,
        skip=skip,
        limit=limit,
        account_id=token_info["account_id"],
        type=type,
        status=status
    )

