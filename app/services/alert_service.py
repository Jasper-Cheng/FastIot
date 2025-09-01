from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud.alert import create_alert, update_alert_status
from app.models.alert import AlertCreate, AlertStatus
from app.services.websocket_service import push_alert_notification, push_alert_update
import logging

logger = logging.getLogger(__name__)

class AlertService:
    """告警服务类，统一管理告警相关逻辑"""
    
    def __init__(self):
        self.alert_rules = {
            "temperature_high": {
                "threshold": 80,
                "field": "temperature",
                "message_template": "设备温度过高: {value}°C",
                "alert_type": "temperature_high"
            },
            "temperature_low": {
                "threshold": 10,
                "field": "temperature",
                "message_template": "设备温度过低: {value}°C",
                "alert_type": "temperature_low",
                "operator": "lt"  # less than
            },
            "pressure_high": {
                "threshold": 100,
                "field": "pressure",
                "message_template": "设备压力过高: {value}",
                "alert_type": "pressure_high"
            },
            "pressure_low": {
                "threshold": 20,
                "field": "pressure",
                "message_template": "设备压力过低: {value}",
                "alert_type": "pressure_low",
                "operator": "lt"
            },
            "humidity_high": {
                "threshold": 90,
                "field": "humidity",
                "message_template": "设备湿度过高: {value}%",
                "alert_type": "humidity_high"
            },
            "voltage_high": {
                "threshold": 250,
                "field": "voltage",
                "message_template": "设备电压过高: {value}V",
                "alert_type": "voltage_high"
            },
            "voltage_low": {
                "threshold": 180,
                "field": "voltage",
                "message_template": "设备电压过低: {value}V",
                "alert_type": "voltage_low",
                "operator": "lt"
            }
        }
    
    async def check_telemetry_alerts(
        self, 
        device_id: int, 
        telemetry_data: Dict[str, Any], 
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """检查遥测数据并自动创建告警"""
        created_alerts = []
        
        for rule_name, rule in self.alert_rules.items():
            field = rule["field"]
            if field in telemetry_data:
                value = telemetry_data[field]
                if not isinstance(value, (int, float)):
                    continue
                
                threshold = rule["threshold"]
                operator = rule.get("operator", "gt")  # 默认大于阈值告警
                
                should_alert = False
                if operator == "gt":
                    should_alert = value > threshold
                elif operator == "lt":
                    should_alert = value < threshold
                elif operator == "gte":
                    should_alert = value >= threshold
                elif operator == "lte":
                    should_alert = value <= threshold
                elif operator == "eq":
                    should_alert = value == threshold
                elif operator == "ne":
                    should_alert = value != threshold
                
                if should_alert:
                    try:
                        # 创建告警记录
                        alert_data = AlertCreate(
                            device_id=device_id,
                            alert_type=rule["alert_type"],
                            message=rule["message_template"].format(value=value)
                        )
                        
                        alert = await create_alert(db, alert_data)
                        
                        # 通过WebSocket推送告警通知
                        alert_info = {
                            "id": alert.id,
                            "alert_type": alert.alert_type,
                            "message": alert.message,
                            "status": alert.status.value,
                            "created_at": alert.created_at.isoformat()
                        }
                        
                        await push_alert_notification(device_id, alert_info)
                        
                        created_alerts.append(alert_info)
                        logger.info(f"✅ [AutoAlert] 设备 {device_id} {rule_name}: {value}")
                        
                    except Exception as e:
                        logger.error(f"❌ [AutoAlert] 创建 {rule_name} 告警失败: {e}")
        
        return created_alerts
    
    async def create_manual_alert(
        self, 
        device_id: int, 
        alert_type: str, 
        message: str, 
        db: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """手动创建告警"""
        try:
            alert_data = AlertCreate(
                device_id=device_id,
                alert_type=alert_type,
                message=message
            )
            
            alert = await create_alert(db, alert_data)
            
            # 通过WebSocket推送告警通知
            alert_info = {
                "id": alert.id,
                "alert_type": alert.alert_type,
                "message": alert.message,
                "status": alert.status.value,
                "created_at": alert.created_at.isoformat()
            }
            
            await push_alert_notification(device_id, alert_info)
            
            logger.info(f"✅ [ManualAlert] 设备 {device_id} 手动告警: {alert_type}")
            return alert_info
            
        except Exception as e:
            logger.error(f"❌ [ManualAlert] 创建手动告警失败: {e}")
            return None
    
    async def update_alert_status(
        self, 
        alert_id: int, 
        status: AlertStatus, 
        device_id: int, 
        db: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """更新告警状态"""
        try:
            updated_alert = await update_alert_status(db, alert_id, status)
            if updated_alert:
                # 通过WebSocket推送告警状态更新
                alert_info = {
                    "id": updated_alert.id,
                    "alert_type": updated_alert.alert_type,
                    "message": updated_alert.message,
                    "status": updated_alert.status.value,
                    "created_at": updated_alert.created_at.isoformat()
                }
                
                await push_alert_update(alert_id, device_id, alert_info)
                
                logger.info(f"✅ [AlertUpdate] 告警 {alert_id} 状态更新为: {status}")
                return alert_info
            
        except Exception as e:
            logger.error(f"❌ [AlertUpdate] 更新告警状态失败: {e}")
        
        return None
    
    def add_alert_rule(
        self, 
        rule_name: str, 
        field: str, 
        threshold: float, 
        message_template: str, 
        alert_type: str, 
        operator: str = "gt"
    ):
        """添加自定义告警规则"""
        self.alert_rules[rule_name] = {
            "threshold": threshold,
            "field": field,
            "message_template": message_template,
            "alert_type": alert_type,
            "operator": operator
        }
        logger.info(f"✅ [AlertRule] 添加告警规则: {rule_name}")
    
    def remove_alert_rule(self, rule_name: str):
        """移除告警规则"""
        if rule_name in self.alert_rules:
            del self.alert_rules[rule_name]
            logger.info(f"✅ [AlertRule] 移除告警规则: {rule_name}")
    
    def get_alert_rules(self) -> Dict[str, Any]:
        """获取所有告警规则"""
        return self.alert_rules.copy()

# 全局告警服务实例
alert_service = AlertService()
