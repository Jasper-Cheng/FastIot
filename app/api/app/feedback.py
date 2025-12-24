from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.feedback import create_feedback
from app.models.feedback import FeedbackCreate, FeedbackInDB
from app.api.dependencies import get_current_token
from app.db.session import get_db

router = APIRouter()


@router.post("/", response_model=FeedbackInDB, status_code=201)
async def submit_feedback(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    feedback: FeedbackCreate = Body(...)
):
    """提交用户反馈
    
    - type: 反馈类型 (bug/feature/improvement/other)
    - content: 反馈内容
    - contact: 联系方式（可选）
    """
    account_id = token_info["account_id"]
    
    # 创建反馈记录
    db_feedback = await create_feedback(db, feedback, account_id)
    if not db_feedback:
        raise HTTPException(status_code=500, detail="提交反馈失败")
    
    return FeedbackInDB.model_validate(db_feedback)

