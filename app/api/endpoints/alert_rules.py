from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from app.api.dependencies import get_current_user
from app.services.alert_service import alert_service
from app.models.user import User

router = APIRouter()

@router.get("/", response_model=Dict[str, Any])
async def get_alert_rules(
    current_user: User = Depends(get_current_user)
):
    """获取所有告警规则"""
    try:
        rules = alert_service.get_alert_rules()
        return {"rules": rules, "count": len(rules)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"获取告警规则失败: {str(e)}")

@router.post("/")
async def add_alert_rule(
    rule_name: str,
    field: str,
    threshold: float,
    message_template: str,
    alert_type: str,
    operator: str = "gt",
    current_user: User = Depends(get_current_user)
):
    """添加自定义告警规则"""
    try:
        alert_service.add_alert_rule(
            rule_name=rule_name,
            field=field,
            threshold=threshold,
            message_template=message_template,
            alert_type=alert_type,
            operator=operator
        )
        return {
            "message": "告警规则添加成功",
            "rule": {
                "name": rule_name,
                "field": field,
                "threshold": threshold,
                "message_template": message_template,
                "alert_type": alert_type,
                "operator": operator
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"添加告警规则失败: {str(e)}")

@router.delete("/{rule_name}")
async def remove_alert_rule(
    rule_name: str,
    current_user: User = Depends(get_current_user)
):
    """移除告警规则"""
    try:
        if rule_name in alert_service.get_alert_rules():
            alert_service.remove_alert_rule(rule_name)
            return {"message": f"告警规则 {rule_name} 已移除"}
        else:
            raise HTTPException(status_code=404, detail=f"告警规则 {rule_name} 不存在")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"移除告警规则失败: {str(e)}")

@router.put("/{rule_name}")
async def update_alert_rule(
    rule_name: str,
    field: str = None,
    threshold: float = None,
    message_template: str = None,
    alert_type: str = None,
    operator: str = None,
    current_user: User = Depends(get_current_user)
):
    """更新告警规则"""
    try:
        current_rules = alert_service.get_alert_rules()
        if rule_name not in current_rules:
            raise HTTPException(status_code=404, detail=f"告警规则 {rule_name} 不存在")
        
        # 获取当前规则
        current_rule = current_rules[rule_name]
        
        # 更新字段
        if field is not None:
            current_rule["field"] = field
        if threshold is not None:
            current_rule["threshold"] = threshold
        if message_template is not None:
            current_rule["message_template"] = message_template
        if alert_type is not None:
            current_rule["alert_type"] = alert_type
        if operator is not None:
            current_rule["operator"] = operator
        
        # 重新添加规则
        alert_service.add_alert_rule(
            rule_name=rule_name,
            field=current_rule["field"],
            threshold=current_rule["threshold"],
            message_template=current_rule["message_template"],
            alert_type=current_rule["alert_type"],
            operator=current_rule["operator"]
        )
        
        return {
            "message": f"告警规则 {rule_name} 更新成功",
            "rule": current_rule
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"更新告警规则失败: {str(e)}")

@router.post("/test")
async def test_alert_rule(
    field: str,
    threshold: float,
    operator: str = "gt",
    test_value: float = None,
    current_user: User = Depends(get_current_user)
):
    """测试告警规则逻辑"""
    try:
        if test_value is None:
            raise HTTPException(status_code=400, detail="请提供测试值")
        
        should_alert = False
        if operator == "gt":
            should_alert = test_value > threshold
        elif operator == "lt":
            should_alert = test_value < threshold
        elif operator == "gte":
            should_alert = test_value >= threshold
        elif operator == "lte":
            should_alert = test_value <= threshold
        elif operator == "eq":
            should_alert = test_value == threshold
        elif operator == "ne":
            should_alert = test_value != threshold
        else:
            raise HTTPException(status_code=400, detail=f"不支持的运算符: {operator}")
        
        return {
            "test_result": {
                "field": field,
                "threshold": threshold,
                "operator": operator,
                "test_value": test_value,
                "should_alert": should_alert,
                "condition": f"{test_value} {operator} {threshold}"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"测试告警规则失败: {str(e)}")
