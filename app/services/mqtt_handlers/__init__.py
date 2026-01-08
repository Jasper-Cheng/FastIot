"""
MQTT 设备处理器注册模块
所有设备的具体处理器都在此模块中注册
"""
from app.services.mqtt_service import mqtt_service

# 导入所有设备处理器
from app.services.mqtt_handlers.m701001 import (
    handle_m701001_data,
    handle_m701001_status
)


def register_all_handlers():
    """注册所有设备处理器"""
    # 注册 M701001 处理器
    mqtt_service.register_data_handler("M701001", handle_m701001_data)
    mqtt_service.register_status_handler("M701001", handle_m701001_status)
    
    # 未来添加新设备时，在此处注册
    # mqtt_service.register_data_handler("M702001", handle_m702001_data)
    # mqtt_service.register_status_handler("M702001", handle_m702001_status)


# 自动注册所有处理器
register_all_handlers()

