"""
M701001 室内空气质量监测器处理器
处理设备数据和状态消息
"""
from typing import Dict, Any
from app.services.mqtt_service import mqtt_service


async def handle_m701001_data(sn: str, payload: Dict[str, Any]):
    """处理 M701001 室内空气质量监测器数据
    
    数据格式示例:
    {'sn': 'M701001-220403-000001', 'co2': 485, 'hcho': 17, 'tvoc': 27, 'pm25': 21, 'pm10': 26, 'temp': 26.1, 'humi': 41.0}
    SN 格式: M701001-{生产日期}-{流水号}
    """
    # print(f"🌡️ [M701001] 处理设备 {sn} 的空气质量数据")
    
    # 提取数据
    co2 = payload.get("co2")      # 二氧化碳 (ppm)
    hcho = payload.get("hcho")    # 甲醛 (μg/m³)
    tvoc = payload.get("tvoc")    # 总挥发性有机化合物 (μg/m³)
    pm25 = payload.get("pm25")    # PM2.5 (μg/m³)
    pm10 = payload.get("pm10")    # PM10 (μg/m³)
    temp = payload.get("temp")    # 温度 (°C)
    humi = payload.get("humi")    # 湿度 (%)
    
    # print(f"   CO2: {co2} ppm, HCHO: {hcho} μg/m³, TVOC: {tvoc} μg/m³")
    # print(f"   PM2.5: {pm25} μg/m³, PM10: {pm10} μg/m³")
    # print(f"   温度: {temp} °C, 湿度: {humi} %")
    
    # TODO: 保存到数据库
    # from app.crud.device_data import save_device_data
    # await save_device_data(sn, payload)
    
    # 通过 MQTT 推送给 web/app 客户端
    try:
        # 构建数据对象
        device_data = {
            "co2": co2,
            "hcho": hcho,
            "tvoc": tvoc,
            "pm25": pm25,
            "pm10": pm10,
            "temp": temp,
            "humi": humi
        }
        
        # 发送设备数据到客户端（web/app）
        await mqtt_service.publish_client_data(sn, device_data)
    except Exception as e:
        print(f"❌ [M701001] MQTT 推送数据失败 ({sn}): {e}")
        import traceback
        traceback.print_exc()
    
    # 阈值告警检查
    alerts = []
    alert_details = []
    
    if co2 and co2 > 1000:
        alert_msg = f"CO2 超标: {co2} ppm (阈值: 1000 ppm)"
        alerts.append(alert_msg)
        alert_details.append({"type": "co2", "value": co2, "threshold": 1000, "unit": "ppm"})
    
    if hcho and hcho > 100:
        alert_msg = f"甲醛超标: {hcho} μg/m³ (阈值: 100 μg/m³)"
        alerts.append(alert_msg)
        alert_details.append({"type": "hcho", "value": hcho, "threshold": 100, "unit": "μg/m³"})
    
    if tvoc and tvoc > 600:
        alert_msg = f"TVOC 超标: {tvoc} μg/m³ (阈值: 600 μg/m³)"
        alerts.append(alert_msg)
        alert_details.append({"type": "tvoc", "value": tvoc, "threshold": 600, "unit": "μg/m³"})
    
    if pm25 and pm25 > 75:
        alert_msg = f"PM2.5 超标: {pm25} μg/m³ (阈值: 75 μg/m³)"
        alerts.append(alert_msg)
        alert_details.append({"type": "pm25", "value": pm25, "threshold": 75, "unit": "μg/m³"})
    
    if pm10 and pm10 > 150:
        alert_msg = f"PM10 超标: {pm10} μg/m³ (阈值: 150 μg/m³)"
        alerts.append(alert_msg)
        alert_details.append({"type": "pm10", "value": pm10, "threshold": 150, "unit": "μg/m³"})
    
    if alerts:
        print(f"⚠️ [M701001] 设备 {sn} 告警:")
        for alert in alerts:
            print(f"   - {alert}")
        
        # 插入数据库并发送 family message
        try:
            from app.db.session import AsyncSessionLocal
            from app.crud.device import get_device_by_sn
            from app.crud.device_message import create_device_message
            from app.models.device_message import DeviceMessageCreate, DeviceMessageLevel
            from app.crud.family_device import get_device_families
            
            async with AsyncSessionLocal() as db:
                # 查找设备
                device = await get_device_by_sn(db, sn)
                if not device:
                    print(f"⚠️ [M701001] 设备 {sn} 不存在于数据库中，无法插入告警消息")
                    return
                
                # 构建告警消息
                alert_message = "；".join(alerts)  # 用分号连接多个告警
                
                # 创建设备消息记录
                device_message = DeviceMessageCreate(
                    device_id=device.id,
                    level=DeviceMessageLevel.error,  # 告警使用 error 级别
                    message=alert_message,
                    detail={
                        "alerts": alert_details,
                        "deviceSn": sn,
                        "currentData": {
                            "co2": co2,
                            "hcho": hcho,
                            "tvoc": tvoc,
                            "pm25": pm25,
                            "pm10": pm10,
                            "temp": temp,
                            "humi": humi
                        }
                    }
                )
                
                created_message = await create_device_message(db, device_message)
                print(f"✅ [M701001] 告警消息已插入数据库，消息ID: {created_message.id}")
                
                # 获取设备所属的家庭，发送 MQTT 家庭通知
                device_families = await get_device_families(db, device.id)
                for family in device_families:
                    if family.id is not None:
                        try:
                            await mqtt_service.publish_home_notice(
                                home_id=str(family.id),
                                payload={
                                    "method": "family.message",
                                    "params": {
                                        "type": "device.alert",
                                        "data": {
                                            "title": "设备告警",
                                            "message": alert_message,
                                            "level": "error",
                                            "deviceId": device.id,
                                            "deviceSn": sn,
                                            "deviceName": device.name,
                                            "messageId": created_message.id,
                                            "alerts": alert_details
                                        }
                                    }
                                }
                            )
                        except Exception as e:
                            print(f"❌ [M701001] 发送家庭通知失败 (family_id={family.id}): {e}")
                    
        except Exception as e:
            print(f"❌ [M701001] 处理告警失败 ({sn}): {e}")
            import traceback
            traceback.print_exc()


async def handle_m701001_status(sn: str, payload: Dict[str, Any]):
    """处理 M701001 室内空气质量监测器状态"""
    # print(f"📡 [M701001] 处理设备 {sn} 的状态: {payload}")
    
    status = payload.get("status", "").lower()
    if status not in ["online", "offline"]:
        print(f"⚠️ [M701001] 设备 {sn} 状态值无效: {status}")
        return
    
    # 更新数据库设备状态
    try:
        from app.db.session import AsyncSessionLocal
        from app.crud.device import get_device_by_sn, update_device
        from app.models.device import DeviceUpdate, DeviceStatus
        
        async with AsyncSessionLocal() as db:
            # 查找设备
            device = await get_device_by_sn(db, sn)
            if not device:
                print(f"⚠️ [M701001] 设备 {sn} 不存在于数据库中")
                return
            
            # 检查设备是否绑定账号
            if device.account_id is None:
                print(f"⚠️ [M701001] 设备 {sn} 未绑定账号，跳过状态更新和消息发送")
                return
            
            # 更新设备状态
            device_status = DeviceStatus.online if status == "online" else DeviceStatus.offline
            device_update = DeviceUpdate(status=device_status)
            updated_device = await update_device(db, device.id, device_update)
            
            if updated_device:
                # print(f"✅ [M701001] 设备 {sn} 状态已更新为: {device_status.value}")
                pass
            else:
                print(f"❌ [M701001] 设备 {sn} 状态更新失败")
    except Exception as e:
        print(f"❌ [M701001] 更新设备状态失败 ({sn}): {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 通过 MQTT 通知 web/app 客户端
    try:
        # 发送设备状态变更到客户端（web/app）
        status_data = {"status": status}
        await mqtt_service.publish_client_status(sn, status_data)
    except Exception as e:
        print(f"❌ [M701001] MQTT 通知失败 ({sn}): {e}")
        import traceback
        traceback.print_exc()

