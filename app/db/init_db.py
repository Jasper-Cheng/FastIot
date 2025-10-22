import asyncio
import sys
from datetime import datetime, timedelta
from app.utils.time_utils import get_local_time
import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.base import Base
from app.db.session import engine
from app.db.models.account import Account
from app.db.models.admin import Admin
from app.db.models.user import User
from app.db.models.member import Member
from app.db.models.room import Room
from app.db.models.device import Device
from app.db.models.device_thing_model import DeviceThingModel
from app.db.models.device_model import DeviceModel
from app.db.models.device_log import DeviceLog
from app.db.models.device_message import DeviceMessage
from app.db.models.room_device import RoomDevice
from app.db.models.member_device_permission import MemberDevicePermission
from app.db.models.device_network import DeviceNetwork
from app.db.models.check_in import CheckIn
from app.db.models.points import Points
from app.db.models.system_message import SystemMessage
from app.db.models.version_info import VersionInfo
from app.db.models.feedback import Feedback
from app.core.security import get_password_hash

async def init_db(reset=False) -> None:
    """初始化数据库"""
    try:
        if reset:
            print("开始重置数据库...")
            # 删除所有表
            async with engine.begin() as conn:
                print("删除现有表...")
                await conn.run_sync(lambda sync_conn: sync_conn.execute(text("SET FOREIGN_KEY_CHECKS = 0")))
                
                # 获取所有表名
                result = await conn.execute(text("SHOW TABLES"))
                tables = [row[0] for row in result.fetchall()]
                
                # 删除所有表
                for table in tables:
                    await conn.execute(text(f"DROP TABLE IF EXISTS `{table}`"))
                    print(f"   删除表: {table}")
                
                await conn.run_sync(lambda sync_conn: sync_conn.execute(text("SET FOREIGN_KEY_CHECKS = 1")))
                print("所有表已删除")
        
        # 创建所有表
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # 插入初始数据
        async with AsyncSession(engine) as session:
            await insert_initial_data(session)
        
        if reset:
            print("数据库重置完成！")
            print("\n创建的测试数据包括:")
            print("   3个管理员账号")
            print("   15个主账号")
            print("   35个成员账号")
            print("   多个房间")
            print("   11种物模型类型")
            print("   33种设备型号")
            print("   50+个设备")
            print("   房间设备关联")
            print("   成员设备权限")
            print("   设备参数数据")
            print("   设备日志记录")
            print("   告警记录")
            print("   签到记录")
            print("   积分记录")
            print("   版本信息")
            print("   意见反馈")
            print("\n数据库结构说明：")
            print("   account 表：统一管理所有登录账号（管理员、主账号和子账号）")
            print("   admin 表：管理员，与 account 一一对应")
            print("   user 表：主账号，与 account 一一对应")
            print("   member 表：子账号，与 account 一一对应，属于某个 user")
            print("   thing_model 表：物模型定义")
            print("   device_model 表：设备型号定义")
            print("   device 表：具体设备实例")
    finally:
        # 确保引擎正确关闭
        await engine.dispose()

async def insert_initial_data(session: AsyncSession) -> None:
    """插入丰富的测试数据"""
    # 检查是否已有数据
    result = await session.execute(text("SELECT COUNT(*) FROM account"))
    count = result.scalar()
    
    if count == 0:
        print("开始创建测试数据...")
        
        # 1. 创建账号（含一个管理员）
        accounts = await create_accounts(session)
        # 1.1 创建管理员记录
        await create_admins(session, accounts)
        
        # 2. 创建用户
        users = await create_users(session, accounts)
        
        # 3. 创建成员
        members = await create_members(session, users, accounts)
        
        # 4. 创建房间
        rooms = await create_rooms(session, users)
        
        # 5. 创建物模型
        thing_models = await create_thing_models(session)
        
        # 6. 创建设备型号
        device_models = await create_device_models(session, thing_models)
        
        # 7. 创建设备
        devices = await create_devices(session, users, device_models)
        
        # 8. 创建房间设备关联
        await create_room_devices(session, rooms, devices)
        
        # 9. 创建成员设备权限
        await create_member_device_permissions(session, members, devices)
        
        # 10. 创建设备日志
        await create_device_logs(session, devices)
        
        # 11. 创建设备消息
        await create_device_messages(session, devices)
        
        # 12. 创建设备网络信息
        await create_device_networks(session, devices)
        
        # 13. 创建签到记录
        await create_check_ins(session, accounts, devices)
        
        # 14. 创建积分记录
        await create_points(session, accounts)
        
        # 15. 创建系统消息
        await create_system_messages(session)
        
        # 16. 创建版本信息
        await create_version_infos(session)
        
        # 17. 创建意见反馈
        await create_feedbacks(session, accounts)
        
        await session.commit()
        print("测试数据创建完成！")

async def create_accounts(session: AsyncSession):
    """创建账号"""
    print("创建账号...")
    accounts = []
    
    # 创建3个管理员账号
    admin_names = ["系统管理员", "运维管理员", "数据管理员"]
    for i in range(3):
        admin_account = Account(
            account=f"admin{i + 1}",
            password_hash=get_password_hash("admin123"),
            name=admin_names[i],
            gender=random.choice(['male', 'female', 'other']),
            phone=f"1370000000{i}",
            email=f"admin{i + 1}@fastiot.com",
            role='admin'
        )
        session.add(admin_account)
        accounts.append(admin_account)

    # 创建15个主账号
    for i in range(15):
        account = Account(
            account=f"user{i+1}",
            password_hash=get_password_hash("password123"),
            name=f"用户{i+1}",
            gender=random.choice(['male', 'female', 'other']),
            phone=f"1380000000{i}" if i < 9 else f"138000000{i}",
            email=f"user{i+1}@example.com",
            role='owner'
        )
        session.add(account)
        accounts.append(account)

    # 创建35个子账号
    for i in range(35):
        account = Account(
            account=f"member{i+1}",
            password_hash=get_password_hash("password123"),
            name=f"成员{i+1}",
            gender=random.choice(['male', 'female', 'other']),
            phone=f"1390000000{i}" if i < 9 else f"139000000{i}",
            email=f"member{i+1}@example.com",
            role='member'
        )
        session.add(account)
        accounts.append(account)

    await session.flush()
    return accounts

async def create_admins(session: AsyncSession, accounts):
    """根据 admin 账号创建管理员记录"""
    print("创建管理员...")
    from sqlalchemy import select
    for acc in accounts:
        if acc.role == 'admin':
            # 检查是否已存在对应 Admin 记录
            result = await session.execute(select(Admin).where(Admin.account_id == acc.id))
            exists = result.scalar_one_or_none()
            if exists is None:
                session.add(Admin(account_id=acc.id))
    await session.flush()

async def create_users(session: AsyncSession, accounts):
    """创建用户"""
    print("创建用户...")
    users = []

    # 为前15个账号（owner角色）创建用户
    for i, account in enumerate(accounts[3:18]):  # 跳过3个admin账号
        user = User(account_id=account.id)
        session.add(user)
        users.append(user)

    await session.flush()
    return users

async def create_members(session: AsyncSession, users, accounts):
    """创建成员"""
    print("创建成员...")
    members = []

    # 为后35个账号（member角色）创建成员
    member_accounts = accounts[18:]  # 后35个账号
    for i, account in enumerate(member_accounts):
        # 随机分配给某个用户
        user = random.choice(users)
        member = Member(user_id=user.id, account_id=account.id)
        session.add(member)
        members.append(member)

    await session.flush()
    return members

async def create_rooms(session: AsyncSession, users):
    """创建房间"""
    print("创建房间...")
    rooms = []
    room_names = ["客厅", "卧室", "厨房", "卫生间", "书房", "阳台", "储藏室", "玄关"]

    for user in users:
        # 每个用户创建2-4个房间
        num_rooms = random.randint(2, 4)
        for i in range(num_rooms):
            room = Room(
                user_id=user.id,
                name=f"{random.choice(room_names)}{i+1}"
            )
            session.add(room)
            rooms.append(room)

    await session.flush()
    return rooms

async def create_thing_models(session: AsyncSession):
    """创建物模型"""
    print("创建物模型...")
    thing_models = []

    thing_models_data = [
        # 空调物模型
        ("空调物模型", "智能空调功能定义",
         {"power": {"type": "boolean", "unit": "on/off", "default": False},
          "temperature": {"type": "int", "unit": "°C", "min": 16, "max": 30, "default": 26},
          "mode": {"type": "string", "unit": "mode", "enum": ["制冷", "制热", "送风", "除湿", "自动"], "default": "制冷"},
          "fan_speed": {"type": "string", "unit": "speed", "enum": ["低", "中", "高", "自动"], "default": "自动"},
          "swing": {"type": "boolean", "unit": "on/off", "default": False}},
         ["set_temperature", "set_mode", "set_fan_speed", "set_swing", "power_on", "power_off"],
         ["temperature_reached", "filter_clean_reminder", "maintenance_required", "power_fault"]),

        # 摄像头物模型
        ("摄像头物模型", "智能摄像头功能定义",
         {"recording": {"type": "boolean", "unit": "on/off", "default": False},
          "motion_detected": {"type": "boolean", "unit": "yes/no", "default": False},
          "night_vision": {"type": "boolean", "unit": "on/off", "default": True},
          "resolution": {"type": "string", "unit": "pixels", "enum": ["720p", "1080p", "4K"], "default": "1080p"},
          "storage_used": {"type": "float", "unit": "GB", "min": 0, "max": 1000, "precision": 2}},
         ["start_recording", "stop_recording", "take_photo", "set_resolution", "enable_motion_detection"],
         ["motion_detected", "storage_full", "camera_fault", "low_light_alert"]),

        # 智能灯物模型
        ("智能灯物模型", "智能灯泡功能定义",
         {"power": {"type": "boolean", "unit": "on/off", "default": False},
          "brightness": {"type": "int", "unit": "%", "min": 0, "max": 100, "default": 50},
          "color": {"type": "string", "unit": "hex", "default": "#FFFFFF"},
          "color_temp": {"type": "int", "unit": "K", "min": 2700, "max": 6500, "default": 4000},
          "scene": {"type": "string", "unit": "scene", "enum": ["阅读", "休闲", "睡眠", "聚会", "自定义"], "default": "休闲"}},
         ["set_brightness", "set_color", "set_color_temp", "set_scene", "toggle", "power_on", "power_off"],
         ["bulb_fault", "overheating", "color_error", "brightness_error"]),

        # 智能TV物模型
        ("智能TV物模型", "智能电视功能定义",
         {"power": {"type": "boolean", "unit": "on/off", "default": False},
          "volume": {"type": "int", "unit": "%", "min": 0, "max": 100, "default": 30},
          "channel": {"type": "int", "unit": "channel", "min": 1, "max": 999, "default": 1},
          "input_source": {"type": "string", "unit": "source", "enum": ["HDMI1", "HDMI2", "USB", "网络", "蓝牙"], "default": "HDMI1"},
          "resolution": {"type": "string", "unit": "resolution", "enum": ["720p", "1080p", "4K"], "default": "1080p"}},
         ["power_on", "power_off", "set_volume", "change_channel", "set_input", "set_resolution"],
         ["no_signal", "audio_fault", "display_fault", "remote_disconnected"]),

        # 跌倒检测物模型
        ("跌倒检测物模型", "跌倒检测器功能定义",
         {"power": {"type": "boolean", "unit": "on/off", "default": True},
          "battery_level": {"type": "int", "unit": "%", "min": 0, "max": 100, "default": 100},
          "fall_detected": {"type": "boolean", "unit": "yes/no", "default": False},
          "sensitivity": {"type": "string", "unit": "level", "enum": ["低", "中", "高"], "default": "中"},
          "emergency_mode": {"type": "boolean", "unit": "on/off", "default": False}},
         ["set_sensitivity", "test_device", "emergency_call", "reset_alarm"],
         ["fall_detected", "low_battery", "device_fault", "emergency_triggered"]),

        # WiFi路由器物模型
        ("WiFi路由器物模型", "智能WiFi路由器功能定义",
         {"power": {"type": "boolean", "unit": "on/off", "default": True},
          "wifi_enabled": {"type": "boolean", "unit": "on/off", "default": True},
          "guest_network": {"type": "boolean", "unit": "on/off", "default": False},
          "connected_devices": {"type": "int", "unit": "count", "min": 0, "max": 50, "default": 0},
          "signal_strength": {"type": "int", "unit": "%", "min": 0, "max": 100, "default": 80}},
         ["restart_router", "enable_guest_network", "block_device", "update_firmware", "reset_settings"],
         ["device_connected", "device_disconnected", "signal_weak", "firmware_update_available"]),

        # 扫地机器人物模型
        ("扫地机器人物模型", "智能扫地机器人功能定义",
         {"power": {"type": "boolean", "unit": "on/off", "default": False},
          "battery_level": {"type": "int", "unit": "%", "min": 0, "max": 100, "default": 100},
          "cleaning_mode": {"type": "string", "unit": "mode", "enum": ["标准", "强力", "静音", "定点", "沿边"], "default": "标准"},
          "work_status": {"type": "string", "unit": "status", "enum": ["待机", "清扫中", "充电中", "暂停", "故障"], "default": "待机"},
          "dustbin_full": {"type": "boolean", "unit": "yes/no", "default": False}},
         ["start_cleaning", "stop_cleaning", "return_home", "set_mode", "schedule_cleaning"],
         ["cleaning_completed", "dustbin_full", "low_battery", "stuck_obstacle", "maintenance_required"]),

        # 洗衣机物模型
        ("洗衣机物模型", "智能洗衣机功能定义",
         {"power": {"type": "boolean", "unit": "on/off", "default": False},
          "work_status": {"type": "string", "unit": "status", "enum": ["待机", "洗涤中", "漂洗中", "脱水", "完成", "故障"], "default": "待机"},
          "wash_mode": {"type": "string", "unit": "mode", "enum": ["标准", "快洗", "强力", "轻柔", "羊毛", "羽绒"], "default": "标准"},
          "water_level": {"type": "string", "unit": "level", "enum": ["低", "中", "高", "自动"], "default": "自动"},
          "temperature": {"type": "int", "unit": "°C", "min": 20, "max": 90, "default": 40},
          "remaining_time": {"type": "int", "unit": "minutes", "min": 0, "max": 180, "default": 0}},
         ["start_washing", "stop_washing", "set_mode", "set_temperature", "set_water_level"],
         ["washing_completed", "water_shortage", "door_open", "drainage_fault", "maintenance_required"]),

        # 冰箱物模型
        ("冰箱物模型", "智能冰箱功能定义",
         {"power": {"type": "boolean", "unit": "on/off", "default": True},
          "temperature_fresh": {"type": "int", "unit": "°C", "min": 0, "max": 10, "default": 4},
          "temperature_frozen": {"type": "int", "unit": "°C", "min": -25, "max": -10, "default": -18},
          "door_open": {"type": "boolean", "unit": "yes/no", "default": False},
          "ice_maker": {"type": "boolean", "unit": "on/off", "default": True},
          "energy_mode": {"type": "string", "unit": "mode", "enum": ["节能", "标准", "速冷"], "default": "标准"}},
         ["set_temperature", "enable_ice_maker", "set_energy_mode", "defrost", "reset_settings"],
         ["door_open_alert", "temperature_abnormal", "ice_maker_fault", "defrost_required"]),

        # 智能音箱物模型
        ("智能音箱物模型", "智能音箱功能定义",
         {"power": {"type": "boolean", "unit": "on/off", "default": True},
          "volume": {"type": "int", "unit": "%", "min": 0, "max": 100, "default": 30},
          "mute": {"type": "boolean", "unit": "on/off", "default": False},
          "playing": {"type": "boolean", "unit": "yes/no", "default": False},
          "wifi_connected": {"type": "boolean", "unit": "yes/no", "default": True},
          "voice_assistant": {"type": "boolean", "unit": "on/off", "default": True}},
         ["play_music", "pause_music", "set_volume", "mute", "enable_voice", "connect_wifi"],
         ["music_playing", "voice_command", "wifi_disconnected", "low_battery", "speaker_fault"]),

        # 空气净化器物模型
        ("空气净化器物模型", "智能空气净化器功能定义",
         {"power": {"type": "boolean", "unit": "on/off", "default": False},
          "fan_speed": {"type": "string", "unit": "speed", "enum": ["低", "中", "高", "自动", "睡眠"], "default": "自动"},
          "pm25_level": {"type": "float", "unit": "μg/m³", "min": 0, "max": 500, "precision": 1, "default": 50},
          "air_quality": {"type": "string", "unit": "level", "enum": ["优", "良", "轻度污染", "中度污染", "重度污染"], "default": "良"},
          "filter_life": {"type": "int", "unit": "%", "min": 0, "max": 100, "default": 80},
          "auto_mode": {"type": "boolean", "unit": "on/off", "default": True}},
         ["set_fan_speed", "enable_auto_mode", "reset_filter", "set_timer", "power_on", "power_off"],
         ["air_quality_changed", "filter_replacement_needed", "sensor_fault", "purifier_fault"])
    ]

    for name, description, properties, services, events in thing_models_data:
        thing_model = DeviceThingModel(
            name=name,
            description=description,
            properties=properties,
            services=services,
            events=events
        )
        session.add(thing_model)
        thing_models.append(thing_model)

    await session.flush()
    return thing_models

async def create_device_models(session: AsyncSession, thing_models):
    """创建设备型号"""
    print("创建设备型号...")
    device_models = []
    
    def get_device_services_events(device_type: str, model_code: str):
        """根据设备类型生成服务和事件"""
        services_events_map = {
            "AC": (["power_on", "power_off", "set_temperature", "set_mode", "set_fan_speed", "set_swing", "auto_mode", "timer_set"], 
                   ["temperature_reached", "filter_clean_reminder", "maintenance_required", "power_fault", "temperature_error", "mode_changed"]),
            "CAM": (["start_recording", "stop_recording", "take_photo", "set_resolution", "set_night_vision", "pan_tilt", "zoom"], 
                    ["motion_detected", "storage_full", "camera_fault", "low_light_alert", "recording_started", "recording_stopped"]),
            "LIGHT": (["power_on", "power_off", "set_brightness", "set_color", "set_color_temp", "set_scene", "dim", "brighten"], 
                      ["bulb_fault", "overheating", "color_error", "brightness_error", "scene_changed", "power_changed"]),
            "TV": (["power_on", "power_off", "set_volume", "change_channel", "set_input", "set_resolution", "mute", "unmute"], 
                   ["no_signal", "audio_fault", "display_fault", "remote_disconnected", "channel_changed", "volume_changed"]),
            "FALL": (["power_on", "power_off", "set_sensitivity", "test_alarm", "reset_emergency", "calibrate"], 
                     ["fall_detected", "low_battery", "device_fault", "emergency_triggered", "sensitivity_changed"]),
            "WIFI": (["power_on", "power_off", "restart", "update_firmware", "set_guest_network", "block_device", "unblock_device"], 
                     ["wifi_disconnected", "device_connected", "device_disconnected", "signal_weak", "firmware_updated"]),
            "ROBOT": (["start_cleaning", "stop_cleaning", "return_home", "set_cleaning_mode", "schedule_cleaning", "empty_dustbin"], 
                      ["cleaning_completed", "dustbin_full", "stuck", "low_battery", "charging_started", "charging_completed"]),
            "WASH": (["start_washing", "stop_washing", "set_wash_mode", "set_temperature", "set_water_level", "schedule_wash"], 
                     ["washing_completed", "water_shortage", "door_open", "drainage_fault", "maintenance_required", "cycle_changed"]),
            "FRIDGE": (["power_on", "power_off", "set_temperature_fresh", "set_temperature_frozen", "set_ice_maker", "set_energy_mode"], 
                       ["door_open_alert", "temperature_abnormal", "ice_maker_fault", "defrost_required", "temperature_changed"]),
            "SPEAKER": (["power_on", "power_off", "set_volume", "play_music", "stop_music", "set_voice_assistant", "mute", "unmute"], 
                        ["music_playing", "voice_command", "wifi_disconnected", "low_battery", "speaker_fault", "volume_changed"]),
            "AIR": (["power_on", "power_off", "set_fan_speed", "set_auto_mode", "set_timer", "reset_filter", "set_pm25_threshold"], 
                    ["air_quality_changed", "filter_replacement_needed", "sensor_fault", "purifier_fault", "pm25_high", "filter_changed"])
        }
        
        device_prefix = model_code[:3] if len(model_code) >= 3 else model_code
        for prefix, (services, events) in services_events_map.items():
            if device_prefix.startswith(prefix):
                return services, events
        
        # Default fallback
        return ["power_on", "power_off", "reset"], ["device_fault", "low_battery", "status_changed"]

    models_data = [
        ("AC001", "格力空调KFR-35GW", "格力", 0, {
            "power": {"type": "boolean", "unit": "on/off", "default": False},
            "temperature": {"type": "int", "unit": "°C", "min": 16, "max": 30, "default": 26},
            "mode": {"type": "string", "unit": "mode", "enum": ["制冷", "制热", "送风", "除湿", "自动"], "default": "制冷"},
            "fan_speed": {"type": "string", "unit": "speed", "enum": ["低", "中", "高", "自动"], "default": "自动"},
            "swing": {"type": "boolean", "unit": "on/off", "default": False}
        }),
        ("AC002", "美的空调KFR-50LW", "美的", 0, {
            "power": {"type": "boolean", "unit": "on/off", "default": False},
            "temperature": {"type": "int", "unit": "°C", "min": 16, "max": 30, "default": 26},
            "mode": {"type": "string", "unit": "mode", "enum": ["制冷", "制热", "送风", "除湿", "自动"], "default": "制冷"},
            "fan_speed": {"type": "string", "unit": "speed", "enum": ["低", "中", "高", "自动"], "default": "自动"},
            "swing": {"type": "boolean", "unit": "on/off", "default": False}
        }),
        ("AC003", "海尔空调KFR-72LW", "海尔", 0, {
            "power": {"type": "boolean", "unit": "on/off", "default": False},
            "temperature": {"type": "int", "unit": "°C", "min": 16, "max": 30, "default": 26},
            "mode": {"type": "string", "unit": "mode", "enum": ["制冷", "制热", "送风", "除湿", "自动"], "default": "制冷"},
            "fan_speed": {"type": "string", "unit": "speed", "enum": ["低", "中", "高", "自动"], "default": "自动"},
            "swing": {"type": "boolean", "unit": "on/off", "default": False}
        }),
        ("CAM001", "小米智能摄像头", "小米", 1, {
            "recording": {"type": "boolean", "unit": "on/off", "default": False},
            "motion_detected": {"type": "boolean", "unit": "yes/no", "default": False},
            "night_vision": {"type": "boolean", "unit": "on/off", "default": True},
            "resolution": {"type": "string", "unit": "pixels", "enum": ["720p", "1080p", "4K"], "default": "1080p"},
            "storage_used": {"type": "float", "unit": "GB", "min": 0, "max": 1000, "precision": 2}
        }),
        ("CAM002", "海康威视摄像头", "海康威视", 1, {
            "recording": {"type": "boolean", "unit": "on/off", "default": False},
            "motion_detected": {"type": "boolean", "unit": "yes/no", "default": False},
            "night_vision": {"type": "boolean", "unit": "on/off", "default": True},
            "resolution": {"type": "string", "unit": "pixels", "enum": ["720p", "1080p", "4K"], "default": "1080p"},
            "storage_used": {"type": "float", "unit": "GB", "min": 0, "max": 1000, "precision": 2}
        }),
        ("CAM003", "萤石摄像头", "萤石", 1, {
            "recording": {"type": "boolean", "unit": "on/off", "default": False},
            "motion_detected": {"type": "boolean", "unit": "yes/no", "default": False},
            "night_vision": {"type": "boolean", "unit": "on/off", "default": True},
            "resolution": {"type": "string", "unit": "pixels", "enum": ["720p", "1080p", "4K"], "default": "1080p"},
            "storage_used": {"type": "float", "unit": "GB", "min": 0, "max": 1000, "precision": 2}
        }),
        ("LIGHT001", "飞利浦智能灯泡", "飞利浦", 2, {
            "power": {"type": "boolean", "unit": "on/off", "default": False},
            "brightness": {"type": "int", "unit": "%", "min": 0, "max": 100, "default": 50},
            "color": {"type": "string", "unit": "hex", "default": "#FFFFFF"},
            "color_temp": {"type": "int", "unit": "K", "min": 2700, "max": 6500, "default": 4000},
            "scene": {"type": "string", "unit": "scene", "enum": ["阅读", "休闲", "睡眠", "聚会", "自定义"], "default": "休闲"}
        }),
        ("LIGHT002", "欧普智能灯带", "欧普", 2, {
            "power": {"type": "boolean", "unit": "on/off", "default": False},
            "brightness": {"type": "int", "unit": "%", "min": 0, "max": 100, "default": 50},
            "color": {"type": "string", "unit": "hex", "default": "#FFFFFF"},
            "color_temp": {"type": "int", "unit": "K", "min": 2700, "max": 6500, "default": 4000},
            "scene": {"type": "string", "unit": "scene", "enum": ["阅读", "休闲", "睡眠", "聚会", "自定义"], "default": "休闲"}
        }),
        ("LIGHT003", "雷士智能吸顶灯", "雷士", 2, {
            "power": {"type": "boolean", "unit": "on/off", "default": False},
            "brightness": {"type": "int", "unit": "%", "min": 0, "max": 100, "default": 50},
            "color": {"type": "string", "unit": "hex", "default": "#FFFFFF"},
            "color_temp": {"type": "int", "unit": "K", "min": 2700, "max": 6500, "default": 4000},
            "scene": {"type": "string", "unit": "scene", "enum": ["阅读", "休闲", "睡眠", "聚会", "自定义"], "default": "休闲"}
        }),

        # 智能TV设备型号 (3种)
        ("TV001", "小米智能电视", "小米", 3, {
            "power": {"type": "boolean", "unit": "on/off", "default": False},
            "volume": {"type": "int", "unit": "%", "min": 0, "max": 100, "default": 30},
            "channel": {"type": "int", "unit": "channel", "min": 1, "max": 999, "default": 1},
            "input_source": {"type": "string", "unit": "source", "enum": ["HDMI1", "HDMI2", "USB", "网络", "蓝牙"], "default": "HDMI1"},
            "resolution": {"type": "string", "unit": "resolution", "enum": ["720p", "1080p", "4K"], "default": "1080p"}
        }),
        ("TV002", "海信智能电视", "海信", 3, {
            "power": {"type": "boolean", "unit": "on/off", "default": False},
            "volume": {"type": "int", "unit": "%", "min": 0, "max": 100, "default": 30},
            "channel": {"type": "int", "unit": "channel", "min": 1, "max": 999, "default": 1},
            "input_source": {"type": "string", "unit": "source", "enum": ["HDMI1", "HDMI2", "USB", "网络", "蓝牙"], "default": "HDMI1"},
            "resolution": {"type": "string", "unit": "resolution", "enum": ["720p", "1080p", "4K"], "default": "1080p"}
        }),
        ("TV003", "TCL智能电视", "TCL", 3, {
            "power": {"type": "boolean", "unit": "on/off", "default": False},
            "volume": {"type": "int", "unit": "%", "min": 0, "max": 100, "default": 30},
            "channel": {"type": "int", "unit": "channel", "min": 1, "max": 999, "default": 1},
            "input_source": {"type": "string", "unit": "source", "enum": ["HDMI1", "HDMI2", "USB", "网络", "蓝牙"], "default": "HDMI1"},
            "resolution": {"type": "string", "unit": "resolution", "enum": ["720p", "1080p", "4K"], "default": "1080p"}
        }),

        # 跌倒检测设备型号 (3种)
        ("FALL001", "小米跌倒检测器", "小米", 4, {
            "power": {"type": "boolean", "unit": "on/off", "default": True},
            "battery_level": {"type": "int", "unit": "%", "min": 0, "max": 100, "default": 100},
            "fall_detected": {"type": "boolean", "unit": "yes/no", "default": False},
            "sensitivity": {"type": "string", "unit": "level", "enum": ["低", "中", "高"], "default": "中"},
            "emergency_mode": {"type": "boolean", "unit": "on/off", "default": False}
        }),
        ("FALL002", "华为跌倒检测器", "华为", 4, {
            "power": {"type": "boolean", "unit": "on/off", "default": True},
            "battery_level": {"type": "int", "unit": "%", "min": 0, "max": 100, "default": 100},
            "fall_detected": {"type": "boolean", "unit": "yes/no", "default": False},
            "sensitivity": {"type": "string", "unit": "level", "enum": ["低", "中", "高"], "default": "中"},
            "emergency_mode": {"type": "boolean", "unit": "on/off", "default": False}
        }),
        ("FALL003", "苹果跌倒检测器", "苹果", 4, {
            "power": {"type": "boolean", "unit": "on/off", "default": True},
            "battery_level": {"type": "int", "unit": "%", "min": 0, "max": 100, "default": 100},
            "fall_detected": {"type": "boolean", "unit": "yes/no", "default": False},
            "sensitivity": {"type": "string", "unit": "level", "enum": ["低", "中", "高"], "default": "中"},
            "emergency_mode": {"type": "boolean", "unit": "on/off", "default": False}
        }),

        # WiFi路由器设备型号 (3种)
        ("WIFI001", "小米路由器AX6000", "小米", 5, {
            "power": {"type": "boolean", "unit": "on/off", "default": True},
            "wifi_enabled": {"type": "boolean", "unit": "on/off", "default": True},
            "guest_network": {"type": "boolean", "unit": "on/off", "default": False},
            "connected_devices": {"type": "int", "unit": "count", "min": 0, "max": 50, "default": 0},
            "signal_strength": {"type": "int", "unit": "%", "min": 0, "max": 100, "default": 80}
        }),
        ("WIFI002", "华为路由器AX3", "华为", 5, {
            "power": {"type": "boolean", "unit": "on/off", "default": True},
            "wifi_enabled": {"type": "boolean", "unit": "on/off", "default": True},
            "guest_network": {"type": "boolean", "unit": "on/off", "default": False},
            "connected_devices": {"type": "int", "unit": "count", "min": 0, "max": 50, "default": 0},
            "signal_strength": {"type": "int", "unit": "%", "min": 0, "max": 100, "default": 80}
        }),
        ("WIFI003", "TP-Link路由器", "TP-Link", 5, {
            "power": {"type": "boolean", "unit": "on/off", "default": True},
            "wifi_enabled": {"type": "boolean", "unit": "on/off", "default": True},
            "guest_network": {"type": "boolean", "unit": "on/off", "default": False},
            "connected_devices": {"type": "int", "unit": "count", "min": 0, "max": 50, "default": 0},
            "signal_strength": {"type": "int", "unit": "%", "min": 0, "max": 100, "default": 80}
        }),

        # 扫地机器人设备型号 (3种)
        ("ROBOT001", "小米扫地机器人", "小米", 6, {
            "power": {"type": "boolean", "unit": "on/off", "default": False},
            "battery_level": {"type": "int", "unit": "%", "min": 0, "max": 100, "default": 100},
            "cleaning_mode": {"type": "string", "unit": "mode", "enum": ["标准", "强力", "静音", "定点", "沿边"], "default": "标准"},
            "work_status": {"type": "string", "unit": "status", "enum": ["待机", "清扫中", "充电中", "暂停", "故障"], "default": "待机"},
            "dustbin_full": {"type": "boolean", "unit": "yes/no", "default": False}
        }),
        ("ROBOT002", "科沃斯扫地机器人", "科沃斯", 6, {
            "power": {"type": "boolean", "unit": "on/off", "default": False},
            "battery_level": {"type": "int", "unit": "%", "min": 0, "max": 100, "default": 100},
            "cleaning_mode": {"type": "string", "unit": "mode", "enum": ["标准", "强力", "静音", "定点", "沿边"], "default": "标准"},
            "work_status": {"type": "string", "unit": "status", "enum": ["待机", "清扫中", "充电中", "暂停", "故障"], "default": "待机"},
            "dustbin_full": {"type": "boolean", "unit": "yes/no", "default": False}
        }),
        ("ROBOT003", "石头扫地机器人", "石头", 6, {
            "power": {"type": "boolean", "unit": "on/off", "default": False},
            "battery_level": {"type": "int", "unit": "%", "min": 0, "max": 100, "default": 100},
            "cleaning_mode": {"type": "string", "unit": "mode", "enum": ["标准", "强力", "静音", "定点", "沿边"], "default": "标准"},
            "work_status": {"type": "string", "unit": "status", "enum": ["待机", "清扫中", "充电中", "暂停", "故障"], "default": "待机"},
            "dustbin_full": {"type": "boolean", "unit": "yes/no", "default": False}
        }),

        # 洗衣机设备型号 (3种)
        ("WASH001", "海尔智能洗衣机", "海尔", 7, {
            "power": {"type": "boolean", "unit": "on/off", "default": False},
            "work_status": {"type": "string", "unit": "status", "enum": ["待机", "洗涤中", "漂洗中", "脱水", "完成", "故障"], "default": "待机"},
            "wash_mode": {"type": "string", "unit": "mode", "enum": ["标准", "快洗", "强力", "轻柔", "羊毛", "羽绒"], "default": "标准"},
            "water_level": {"type": "string", "unit": "level", "enum": ["低", "中", "高", "自动"], "default": "自动"},
            "temperature": {"type": "int", "unit": "°C", "min": 20, "max": 90, "default": 40},
            "remaining_time": {"type": "int", "unit": "minutes", "min": 0, "max": 180, "default": 0}
        }),
        ("WASH002", "美的智能洗衣机", "美的", 7, {
            "power": {"type": "boolean", "unit": "on/off", "default": False},
            "work_status": {"type": "string", "unit": "status", "enum": ["待机", "洗涤中", "漂洗中", "脱水", "完成", "故障"], "default": "待机"},
            "wash_mode": {"type": "string", "unit": "mode", "enum": ["标准", "快洗", "强力", "轻柔", "羊毛", "羽绒"], "default": "标准"},
            "water_level": {"type": "string", "unit": "level", "enum": ["低", "中", "高", "自动"], "default": "自动"},
            "temperature": {"type": "int", "unit": "°C", "min": 20, "max": 90, "default": 40},
            "remaining_time": {"type": "int", "unit": "minutes", "min": 0, "max": 180, "default": 0}
        }),
        ("WASH003", "小天鹅智能洗衣机", "小天鹅", 7, {
            "power": {"type": "boolean", "unit": "on/off", "default": False},
            "work_status": {"type": "string", "unit": "status", "enum": ["待机", "洗涤中", "漂洗中", "脱水", "完成", "故障"], "default": "待机"},
            "wash_mode": {"type": "string", "unit": "mode", "enum": ["标准", "快洗", "强力", "轻柔", "羊毛", "羽绒"], "default": "标准"},
            "water_level": {"type": "string", "unit": "level", "enum": ["低", "中", "高", "自动"], "default": "自动"},
            "temperature": {"type": "int", "unit": "°C", "min": 20, "max": 90, "default": 40},
            "remaining_time": {"type": "int", "unit": "minutes", "min": 0, "max": 180, "default": 0}
        }),

        # 冰箱设备型号 (3种)
        ("FRIDGE001", "海尔智能冰箱", "海尔", 8, {
            "power": {"type": "boolean", "unit": "on/off", "default": True},
            "temperature_fresh": {"type": "int", "unit": "°C", "min": 0, "max": 10, "default": 4},
            "temperature_frozen": {"type": "int", "unit": "°C", "min": -25, "max": -10, "default": -18},
            "door_open": {"type": "boolean", "unit": "yes/no", "default": False},
            "ice_maker": {"type": "boolean", "unit": "on/off", "default": True},
            "energy_mode": {"type": "string", "unit": "mode", "enum": ["节能", "标准", "速冷"], "default": "标准"}
        }),
        ("FRIDGE002", "美的智能冰箱", "美的", 8, {
            "power": {"type": "boolean", "unit": "on/off", "default": True},
            "temperature_fresh": {"type": "int", "unit": "°C", "min": 0, "max": 10, "default": 4},
            "temperature_frozen": {"type": "int", "unit": "°C", "min": -25, "max": -10, "default": -18},
            "door_open": {"type": "boolean", "unit": "yes/no", "default": False},
            "ice_maker": {"type": "boolean", "unit": "on/off", "default": True},
            "energy_mode": {"type": "string", "unit": "mode", "enum": ["节能", "标准", "速冷"], "default": "标准"}
        }),
        ("FRIDGE003", "西门子智能冰箱", "西门子", 8, {
            "power": {"type": "boolean", "unit": "on/off", "default": True},
            "temperature_fresh": {"type": "int", "unit": "°C", "min": 0, "max": 10, "default": 4},
            "temperature_frozen": {"type": "int", "unit": "°C", "min": -25, "max": -10, "default": -18},
            "door_open": {"type": "boolean", "unit": "yes/no", "default": False},
            "ice_maker": {"type": "boolean", "unit": "on/off", "default": True},
            "energy_mode": {"type": "string", "unit": "mode", "enum": ["节能", "标准", "速冷"], "default": "标准"}
        }),

        # 智能音箱设备型号 (3种)
        ("SPEAKER001", "小米小爱音箱", "小米", 9, {
            "power": {"type": "boolean", "unit": "on/off", "default": True},
            "volume": {"type": "int", "unit": "%", "min": 0, "max": 100, "default": 30},
            "mute": {"type": "boolean", "unit": "on/off", "default": False},
            "playing": {"type": "boolean", "unit": "yes/no", "default": False},
            "wifi_connected": {"type": "boolean", "unit": "yes/no", "default": True},
            "voice_assistant": {"type": "boolean", "unit": "on/off", "default": True}
        }),
        ("SPEAKER002", "天猫精灵音箱", "天猫", 9, {
            "power": {"type": "boolean", "unit": "on/off", "default": True},
            "volume": {"type": "int", "unit": "%", "min": 0, "max": 100, "default": 30},
            "mute": {"type": "boolean", "unit": "on/off", "default": False},
            "playing": {"type": "boolean", "unit": "yes/no", "default": False},
            "wifi_connected": {"type": "boolean", "unit": "yes/no", "default": True},
            "voice_assistant": {"type": "boolean", "unit": "on/off", "default": True}
        }),
        ("SPEAKER003", "百度小度音箱", "百度", 9, {
            "power": {"type": "boolean", "unit": "on/off", "default": True},
            "volume": {"type": "int", "unit": "%", "min": 0, "max": 100, "default": 30},
            "mute": {"type": "boolean", "unit": "on/off", "default": False},
            "playing": {"type": "boolean", "unit": "yes/no", "default": False},
            "wifi_connected": {"type": "boolean", "unit": "yes/no", "default": True},
            "voice_assistant": {"type": "boolean", "unit": "on/off", "default": True}
        }),

        # 空气净化器设备型号 (3种)
        ("AIR001", "小米空气净化器", "小米", 10, {
            "power": {"type": "boolean", "unit": "on/off", "default": False},
            "fan_speed": {"type": "string", "unit": "speed", "enum": ["低", "中", "高", "自动", "睡眠"], "default": "自动"},
            "pm25_level": {"type": "float", "unit": "μg/m³", "min": 0, "max": 500, "precision": 1, "default": 50},
            "air_quality": {"type": "string", "unit": "level", "enum": ["优", "良", "轻度污染", "中度污染", "重度污染"], "default": "良"},
            "filter_life": {"type": "int", "unit": "%", "min": 0, "max": 100, "default": 80},
            "auto_mode": {"type": "boolean", "unit": "on/off", "default": True}
        }),
        ("AIR002", "飞利浦空气净化器", "飞利浦", 10, {
            "power": {"type": "boolean", "unit": "on/off", "default": False},
            "fan_speed": {"type": "string", "unit": "speed", "enum": ["低", "中", "高", "自动", "睡眠"], "default": "自动"},
            "pm25_level": {"type": "float", "unit": "μg/m³", "min": 0, "max": 500, "precision": 1, "default": 50},
            "air_quality": {"type": "string", "unit": "level", "enum": ["优", "良", "轻度污染", "中度污染", "重度污染"], "default": "良"},
            "filter_life": {"type": "int", "unit": "%", "min": 0, "max": 100, "default": 80},
            "auto_mode": {"type": "boolean", "unit": "on/off", "default": True}
        }),
        ("AIR003", "松下空气净化器", "松下", 10, {
            "power": {"type": "boolean", "unit": "on/off", "default": False},
            "fan_speed": {"type": "string", "unit": "speed", "enum": ["低", "中", "高", "自动", "睡眠"], "default": "自动"},
            "pm25_level": {"type": "float", "unit": "μg/m³", "min": 0, "max": 500, "precision": 1, "default": 50},
            "air_quality": {"type": "string", "unit": "level", "enum": ["优", "良", "轻度污染", "中度污染", "重度污染"], "default": "良"},
            "filter_life": {"type": "int", "unit": "%", "min": 0, "max": 100, "default": 80},
            "auto_mode": {"type": "boolean", "unit": "on/off", "default": True}
        })
    ]

    for model_code, name, vendor, thing_model_index, properties in models_data:
        services, events = get_device_services_events(thing_models[thing_model_index].name, model_code)
        device_model = DeviceModel(
            model_code=model_code,
            name=name,
            vendor=vendor,
            thing_model_id=thing_models[thing_model_index].id,
            properties=properties,
            services=services,
            events=events
        )
        session.add(device_model)
        device_models.append(device_model)

    await session.flush()
    return device_models

async def create_devices(session: AsyncSession, users, device_models):
    """创建设备"""
    print("创建设备...")
    devices = []
    
    # 用于跟踪每个型号的流水号
    model_serial_counters = {}

    # 创建一些未绑定的设备（user_id=None）
    unbound_count = 10
    for i in range(unbound_count):
        device_model = random.choice(device_models)
        model_code = device_model.model_code
        
        # 获取或初始化该型号的流水号计数器
        if model_code not in model_serial_counters:
            model_serial_counters[model_code] = 0
        model_serial_counters[model_code] += 1
        
        # 生成生产日期（随机生成2022-2024年的日期）
        production_date = f"{random.randint(22, 24):02d}{random.randint(1, 12):02d}{random.randint(1, 28):02d}"
        
        # 生成序列号：型号代码 + 生产日期 + 流水号
        sn = f"{model_code}-{production_date}-{model_serial_counters[model_code]:06d}"
        
        device = Device(
            user_id=None,
            model_id=device_model.id,
            name=f"未绑定设备{i+1}",
            sn=sn,
            status=random.choice(['unconfigured', 'unbound', 'offline', 'fault'])
        )
        session.add(device)
        devices.append(device)

    # 为每个用户创建设备，确保总数不少于50个
    device_count = 0
    target_count = 50

    for user in users:
        # 每个用户创建3-8个设备
        num_devices = random.randint(3, 8)
        for i in range(num_devices):
            if device_count >= target_count:
                break

            # 确保包含所有状态类型
            if device_count < 8:
                status = 'unconfigured'
            elif device_count < 15:
                status = 'configured'
            elif device_count < 22:
                status = 'unbound'
            elif device_count < 30:
                status = 'bound'
            elif device_count < 35:
                status = 'offline'
            elif device_count < 42:
                status = 'online'
            elif device_count < 45:
                status = 'fault'
            else:
                status = random.choice(['online', 'offline'])

            device_model = random.choice(device_models)
            model_code = device_model.model_code
            
            # 获取或初始化该型号的流水号计数器
            if model_code not in model_serial_counters:
                model_serial_counters[model_code] = 0
            model_serial_counters[model_code] += 1
            
            # 生成生产日期（随机生成2022-2024年的日期）
            production_date = f"{random.randint(22, 24):02d}{random.randint(1, 12):02d}{random.randint(1, 28):02d}"
            
            # 生成序列号：型号代码 + 生产日期 + 流水号
            sn = f"{model_code}-{production_date}-{model_serial_counters[model_code]:06d}"

            device = Device(
                user_id=user.id,
                model_id=device_model.id,
                name=f"设备{i+1}",
                sn=sn,
                status=status
            )
            session.add(device)
            devices.append(device)
            device_count += 1

        if device_count >= target_count:
            break

    # 如果还没达到目标数量，继续创建
    while device_count < target_count:
        user = random.choice(users)
        device_model = random.choice(device_models)
        model_code = device_model.model_code
        
        # 获取或初始化该型号的流水号计数器
        if model_code not in model_serial_counters:
            model_serial_counters[model_code] = 0
        model_serial_counters[model_code] += 1
        
        # 生成生产日期（随机生成2022-2024年的日期）
        production_date = f"{random.randint(22, 24):02d}{random.randint(1, 12):02d}{random.randint(1, 28):02d}"
        
        # 生成序列号：型号代码 + 生产日期 + 流水号
        sn = f"{model_code}-{production_date}-{model_serial_counters[model_code]:06d}"
        
        device = Device(
            user_id=user.id,
            model_id=device_model.id,
            name=f"额外设备{device_count+1}",
            sn=sn,
            status=random.choice(['unconfigured', 'configured', 'unbound', 'bound', 'offline', 'online', 'fault'])
        )
        session.add(device)
        devices.append(device)
        device_count += 1

    await session.flush()
    return devices

async def create_room_devices(session: AsyncSession, rooms, devices):
    """创建房间设备关联"""
    print("创建房间设备关联...")

    # 将设备随机分配到房间（只处理已绑定用户的设备）
    for device in devices:
        # 只处理已绑定用户的设备
        if device.user_id is not None:
            # 找到该用户的所有房间
            user_rooms = [room for room in rooms if room.user_id == device.user_id]
            if user_rooms:
                room = random.choice(user_rooms)
                room_device = RoomDevice(
                    room_id=room.id,
                    device_id=device.id,
                    sort_order=random.randint(0, 10)
                )
                session.add(room_device)

async def create_member_device_permissions(session: AsyncSession, members, devices):
    """创建成员设备权限"""
    print("创建成员设备权限...")

    for member in members:
        # 为每个成员随机分配一些设备的控制权限（只处理已绑定用户的设备）
        user_devices = [device for device in devices if device.user_id == member.user_id and device.user_id is not None]
        if user_devices:
            # 随机选择1-3个设备给成员权限
            num_devices = random.randint(1, min(3, len(user_devices)))
            selected_devices = random.sample(user_devices, num_devices)

            for device in selected_devices:
                # 仅为部分设备创建权限记录（存在即有权限，无字段）
                if random.choice([True, False]):
                    permission = MemberDevicePermission(
                        member_id=member.id,
                        device_id=device.id
                    )
                    session.add(permission)


async def create_device_logs(session: AsyncSession, devices):
    """创建设备日志"""
    print("创建设备日志...")

    types = ["properties", "services", "events"]

    for device in devices:
        # 为每个设备创建10-20条日志
        num_logs = random.randint(10, 20)
        for i in range(num_logs):
            type = random.choice(types)
            
            # 根据类型生成不同的参数
            if type == "properties":
                log_data = {
                    "property_name": random.choice(["temperature", "humidity", "power", "voltage"]),
                    "value": random.uniform(0, 100),
                    "unit": random.choice(["°C", "%", "W", "V"]),
                    "timestamp": (get_local_time() - timedelta(days=random.randint(0, 30))).isoformat()
                }
            elif type == "services":
                log_data = {
                    "service_name": random.choice(["power_on", "power_off", "set_temperature", "calibrate"]),
                    "status": random.choice(["success", "failed", "pending"]),
                    "duration": random.uniform(0.1, 5.0),
                    "timestamp": (get_local_time() - timedelta(days=random.randint(0, 30))).isoformat()
                }
            else:  # events
                log_data = {
                    "event_name": random.choice(["device_connected", "device_disconnected", "error_occurred", "maintenance_required"]),
                    "severity": random.choice(["low", "medium", "high"]),
                    "message": f"Device event occurred at {get_local_time().isoformat()}",
                    "timestamp": (get_local_time() - timedelta(days=random.randint(0, 30))).isoformat()
                }

            device_log = DeviceLog(
                device_id=device.id,
                type=type,
                params=log_data
            )
            session.add(device_log)

async def create_device_messages(session: AsyncSession, devices):
    """创建设备消息"""
    print("创建设备消息...")

    message_levels = ['normal', 'error', 'fatal']
    message_contents = [
        "设备离线",
        "温度异常",
        "湿度过高",
        "电量不足",
        "信号弱",
        "设备故障",
        "数据异常"
        ]
    
    # 为每个设备创建1-5条消息
    for device in devices:
        num_messages = random.randint(1, 5)
        for i in range(num_messages):
            level = random.choice(message_levels)
            message_content = random.choice(message_contents)
            
            # 根据级别生成不同的detail信息
            detail = None
            if level == 'error':
                detail = {
                    "error_code": f"ERR{random.randint(1000, 9999)}",
                    "component": random.choice(["CPU", "Memory", "Storage", "Network", "Sensor"]),
                    "severity": random.choice(["medium", "high"])
                }
            elif level == 'fatal':
                detail = {
                    "error_code": f"FATAL{random.randint(1000, 9999)}",
                    "component": random.choice(["System", "Hardware", "Critical"]),
                    "severity": "critical",
                    "requires_immediate_action": True
                }
            elif level == 'normal':
                detail = {
                    "status": "operational",
                    "component": random.choice(["All", "System", "Network"]),
                    "last_check": (get_local_time() - timedelta(minutes=random.randint(1, 60))).isoformat()
                }
            
            status = random.choice(['new', 'read'])
            updated_at = None
            # 如果状态是 'read'，随机设置 updated_at
            if status == 'read' and random.choice([True, False]):
                updated_at = get_local_time() - timedelta(minutes=random.randint(1, 1440))  # 1分钟到24小时前
            
            message = DeviceMessage(
                device_id=device.id,
                level=level,
                status=status,
                message=message_content,
                detail=detail,
                updated_at=updated_at
            )
            session.add(message)

async def create_device_networks(session: AsyncSession, devices):
    """创建设备网络信息（一对一：每个设备仅一条网络记录）"""
    print("创建设备网络信息...")

    network_types = ['wifi', 'ble', 'cellular', 'zigbee']
    connect_states = [0, 1, 2]  # 断开、连接中、已连接

    for device in devices:
        # 每个设备仅生成一条网络信息记录
        net_type = random.choice(network_types)
        # 根据网络类型生成不同的数据
        if net_type == 'wifi':
            network_data = {
                "name": f"WiFi_{random.randint(1, 100)}",
                "ip": f"192.168.{random.randint(1, 255)}.{random.randint(1, 255)}",
                "mac": f"{random.randint(0, 255):02x}:{random.randint(0, 255):02x}:{random.randint(0, 255):02x}:{random.randint(0, 255):02x}:{random.randint(0, 255):02x}:{random.randint(0, 255):02x}",
                "rssi": random.randint(-80, -20),
                "extra": {
                    "gateway": f"192.168.{random.randint(1, 255)}.1",
                    "frequency": random.choice(["2.4G", "5G"]),
                    "channel": random.randint(1, 13)
                }
            }
        elif net_type == 'ble':
            network_data = {
                "name": f"BLE_Device_{random.randint(1, 100)}",
                "mac": f"{random.randint(0, 255):02x}:{random.randint(0, 255):02x}:{random.randint(0, 255):02x}:{random.randint(0, 255):02x}:{random.randint(0, 255):02x}:{random.randint(0, 255):02x}",
                "rssi": random.randint(-100, -30),
                "extra": {
                    "firmware_version": f"v{random.randint(1, 5)}.{random.randint(0, 9)}.{random.randint(0, 9)}",
                    "battery_level": random.randint(10, 100),
                    "pairing_mode": random.choice([True, False])
                }
            }
        elif net_type == 'cellular':
            network_data = {
                "ip": f"{random.randint(10, 172)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}",
                "rssi": random.randint(-120, -50),
                "extra": {
                    "carrier": random.choice(["中国移动", "中国联通", "中国电信"]),
                    "signal_type": random.choice(["4G", "5G", "3G"]),
                    "data_usage": random.randint(100, 10000)  # MB
                }
            }
        else:  # zigbee
            network_data = {
                "name": f"Zigbee_Network_{random.randint(1, 10)}",
                "rssi": random.randint(-90, -20),
                "extra": {
                    "pan_id": f"0x{random.randint(1000, 9999):04x}",
                    "channel": random.randint(11, 26),
                    "coordinator": random.choice([True, False])
                }
            }

        device_network = DeviceNetwork(
            device_id=device.id,
            net_type=net_type,
            name=network_data.get("name"),
            ip=network_data.get("ip"),
            mac=network_data.get("mac"),
            rssi=network_data.get("rssi"),
            connect_state=random.choice(connect_states),
            extra=network_data.get("extra")
        )
        session.add(device_network)

async def create_check_ins(session: AsyncSession, accounts, devices):
    """创建签到记录"""
    print("创建签到记录...")
    
    from datetime import date, timedelta
    import random
    
    # 为每个账号创建签到记录
    for account in accounts:
        # 随机创建过去30天内的签到记录
        num_check_ins = random.randint(5, 25)  # 每个账号5-25次签到
        
        for i in range(num_check_ins):
            # 随机选择签到日期（过去30天内）
            days_ago = random.randint(0, 29)
            check_in_date = date.today() - timedelta(days=days_ago)
            
            # 随机选择签到时间（当天内）
            check_in_time = get_local_time() - timedelta(days=days_ago, hours=random.randint(0, 23), minutes=random.randint(0, 59))
            
            # 计算连续签到天数（简化逻辑）
            continuous_days = random.randint(1, min(30, num_check_ins - i + 1))
            
            # 根据连续签到天数计算积分
            if continuous_days >= 7:
                points_earned = 20  # 连续7天以上奖励20积分
            elif continuous_days >= 3:
                points_earned = 10  # 连续3-6天奖励10积分
            else:
                points_earned = 5   # 普通签到5积分
            
            # 随机选择签到类型
            check_in_type = random.choice(['normal', 'bonus', 'makeup'])
            if check_in_type == 'bonus':
                points_earned += 5  # 奖励签到额外5积分
            elif check_in_type == 'makeup':
                points_earned = max(1, points_earned - 2)  # 补签减少2积分
            
            check_in = CheckIn(
                account_id=account.id,
                check_in_date=check_in_date,
                check_in_time=check_in_time,
                points_earned=points_earned,
                continuous_days=continuous_days,
                check_in_type=check_in_type,
                created_at=check_in_time,  # 使用签到时间作为创建时间
                extra={
                    "ip_address": f"192.168.1.{random.randint(1, 254)}",
                    "user_agent": "FastIoT Mobile App 1.0.0",
                    "platform": random.choice(["iOS", "Android", "Web"])
                }
            )
            session.add(check_in)

async def create_points(session: AsyncSession, accounts):
    """创建积分记录"""
    print("创建积分记录...")
    
    from datetime import timedelta
    import random
    
    # 为每个账号创建积分记录
    for account in accounts:
        current_balance = 0
        
        # 创建一些历史积分记录
        num_points_records = random.randint(10, 50)
        
        for i in range(num_points_records):
            # 随机选择积分类型
            point_type = random.choice(['check_in', 'task', 'reward', 'exchange', 'penalty', 'admin_adjust'])
            
            # 根据类型设置积分变动
            if point_type == 'check_in':
                points_change = random.randint(5, 20)
                description = "每日签到奖励"
            elif point_type == 'task':
                points_change = random.randint(10, 50)
                description = "完成任务奖励"
            elif point_type == 'reward':
                points_change = random.randint(20, 100)
                description = "活动奖励"
            elif point_type == 'exchange':
                points_change = -random.randint(10, 100)  # 负数为消耗
                description = "积分兑换"
            elif point_type == 'penalty':
                points_change = -random.randint(5, 30)  # 负数为扣除
                description = "违规扣除"
            else:  # admin_adjust
                points_change = random.randint(-50, 100)  # 管理员调整
                description = "管理员调整"
            
            # 确保余额不为负数
            if current_balance + points_change < 0:
                points_change = -current_balance  # 最多扣到0
            
            current_balance += points_change
            
            # 随机选择时间（过去90天内）
            days_ago = random.randint(0, 89)
            created_at = get_local_time() - timedelta(days=days_ago, hours=random.randint(0, 23), minutes=random.randint(0, 59))
            
            points_record = Points(
                account_id=account.id,
                points=points_change,
                balance=current_balance,
                type=point_type,
                description=description,
                created_at=created_at,  # 提供创建时间
                extra={
                    "operator": "system" if point_type != 'admin_adjust' else "admin",
                    "reason": f"积分{point_type}操作",
                    "timestamp": created_at.isoformat()
                }
            )
            session.add(points_record)

async def create_system_messages(session: AsyncSession):
    """创建系统消息"""
    print("创建系统消息...")
    
    from app.models.system_message import Platform, SystemMessageType, SystemMessagePriority
    
    system_messages_data = [
        {
            "title": "欢迎使用FastIoT平台",
            "content": "欢迎使用FastIoT智能物联网平台！我们为您提供完整的设备管理和监控解决方案。",
            "type": SystemMessageType.ANNOUNCEMENT,
            "priority": SystemMessagePriority.NORMAL,
            "platforms": [Platform.ANDROID, Platform.IOS, Platform.WEB]
        },
        {
            "title": "系统维护通知",
            "content": "系统将于本周日凌晨2:00-4:00进行例行维护，期间服务可能短暂中断，请提前做好准备。",
            "type": SystemMessageType.MAINTENANCE,
            "priority": SystemMessagePriority.HIGH,
            "platforms": [Platform.ANDROID, Platform.IOS, Platform.WEB, Platform.DESKTOP]
        },
        {
            "title": "新功能上线",
            "content": "我们新增了设备分组功能，现在您可以更方便地管理多个设备了！",
            "type": SystemMessageType.UPDATE,
            "priority": SystemMessagePriority.NORMAL,
            "platforms": [Platform.ANDROID, Platform.IOS, Platform.WEB]
        },
        {
            "title": "安全提醒",
            "content": "请定期更新您的设备密码，确保账户安全。建议使用强密码并启用双重验证。",
            "type": SystemMessageType.ALERT,
            "priority": SystemMessagePriority.URGENT,
            "platforms": [Platform.ANDROID, Platform.IOS, Platform.WEB]
        },
        {
            "title": "移动端优化",
            "content": "我们优化了移动端应用的用户界面，现在操作更加流畅便捷！",
            "type": SystemMessageType.UPDATE,
            "priority": SystemMessagePriority.NORMAL,
            "platforms": [Platform.ANDROID, Platform.IOS]
        },
        {
            "title": "API接口更新",
            "content": "我们更新了部分API接口，请开发者查看最新的API文档。",
            "type": SystemMessageType.UPDATE,
            "priority": SystemMessagePriority.NORMAL,
            "platforms": [Platform.WEB, Platform.DESKTOP]
        },
        {
            "title": "节日祝福",
            "content": "感谢您对FastIoT的支持！祝您节日快乐，工作顺利！",
            "type": SystemMessageType.NOTIFICATION,
            "priority": SystemMessagePriority.LOW,
            "platforms": [Platform.ANDROID, Platform.IOS, Platform.WEB]
        },
        {
            "title": "数据备份提醒",
            "content": "建议您定期备份重要数据，我们提供自动备份功能，可在设置中开启。",
            "type": SystemMessageType.NOTIFICATION,
            "priority": SystemMessagePriority.NORMAL,
            "platforms": [Platform.ANDROID, Platform.IOS, Platform.WEB, Platform.DESKTOP]
        }
    ]
    
    for message_data in system_messages_data:
        system_message = SystemMessage(
            title=message_data["title"],
            content=message_data["content"],
            type=message_data["type"],
            priority=message_data["priority"],
            platforms=message_data["platforms"],
            extra={
                "created_by": "system",
                "version": "1.0.0"
            }
        )
        session.add(system_message)

async def create_version_infos(session: AsyncSession):
    """创建版本信息"""
    print("创建版本信息...")
    
    version_infos_data = [
        {
            "version_code": "1.0.0",
            "version_name": "FastIoT v1.0.0",
            "platform": "all",
            "title": "FastIoT 正式版发布",
            "description": "FastIoT智能物联网平台正式版发布，提供完整的设备管理和监控功能。",
            "download_url": "https://download.fastiot.com/v1.0.0/fastiot-v1.0.0.apk",
            "file_size": 25600000,  # 25.6MB
            "md5_hash": "a1b2c3d4e5f6789012345678901234ab",
            "is_force_update": False,
            "min_supported_version": "0.9.0"
        },
        {
            "version_code": "1.1.0",
            "version_name": "FastIoT v1.1.0",
            "platform": "android",
            "title": "Android版本更新",
            "description": "优化Android端用户体验，修复已知问题，新增设备分组功能。",
            "download_url": "https://download.fastiot.com/v1.1.0/fastiot-v1.1.0-android.apk",
            "file_size": 26800000,  # 26.8MB
            "md5_hash": "b2c3d4e5f6789012345678901234abcd",
            "is_force_update": False,
            "min_supported_version": "1.0.0"
        },
        {
            "version_code": "1.1.0",
            "version_name": "FastIoT v1.1.0",
            "platform": "ios",
            "title": "iOS版本更新",
            "description": "优化iOS端用户体验，修复已知问题，新增设备分组功能。",
            "download_url": "https://apps.apple.com/app/fastiot/id123456789",
            "file_size": 24500000,  # 24.5MB
            "md5_hash": "c3d4e5f6789012345678901234abcdef",
            "is_force_update": False,
            "min_supported_version": "1.0.0"
        },
        {
            "version_code": "1.2.0",
            "version_name": "FastIoT Web v1.2.0",
            "platform": "web",
            "title": "Web版本重大更新",
            "description": "Web端重大更新，新增实时监控面板，优化设备控制界面，提升用户体验。",
            "download_url": "https://web.fastiot.com",
            "file_size": None,
            "md5_hash": None,
            "is_force_update": False,
            "min_supported_version": "1.0.0"
        },
        {
            "version_code": "1.2.1",
            "version_name": "FastIoT Web v1.2.1",
            "platform": "web",
            "title": "Web版本修复更新",
            "description": "修复Web端设备列表加载缓慢问题，优化数据刷新机制，提升页面响应速度。",
            "download_url": "https://web.fastiot.com",
            "file_size": None,
            "md5_hash": None,
            "is_force_update": False,
            "min_supported_version": "1.2.0"
        },
        {
            "version_code": "1.3.0",
            "version_name": "FastIoT Web v1.3.0",
            "platform": "web",
            "title": "Web版本功能增强",
            "description": "新增设备分组管理、批量操作功能，优化数据可视化图表，增强用户权限管理。",
            "download_url": "https://web.fastiot.com",
            "file_size": None,
            "md5_hash": None,
            "is_force_update": False,
            "min_supported_version": "1.2.0"
        },
        {
            "version_code": "1.3.1",
            "version_name": "FastIoT Web v1.3.1",
            "platform": "web",
            "title": "Web版本安全更新",
            "description": "修复安全漏洞，增强数据加密，优化登录验证机制，提升系统安全性。",
            "download_url": "https://web.fastiot.com",
            "file_size": None,
            "md5_hash": None,
            "is_force_update": True,
            "min_supported_version": "1.3.0"
        },
        {
            "version_code": "1.4.0",
            "version_name": "FastIoT Web v1.4.0",
            "platform": "web",
            "title": "Web版本界面优化",
            "description": "全新UI设计，响应式布局优化，新增暗黑模式，支持多语言切换，提升用户体验。",
            "download_url": "https://web.fastiot.com",
            "file_size": None,
            "md5_hash": None,
            "is_force_update": False,
            "min_supported_version": "1.3.0"
        },
        {
            "version_code": "1.4.1",
            "version_name": "FastIoT Web v1.4.1",
            "platform": "web",
            "title": "Web版本性能优化",
            "description": "优化页面加载速度，减少内存占用，修复浏览器兼容性问题，提升整体性能。",
            "download_url": "https://web.fastiot.com",
            "file_size": None,
            "md5_hash": None,
            "is_force_update": False,
            "min_supported_version": "1.4.0"
        },
        {
            "version_code": "1.5.0",
            "version_name": "FastIoT Web v1.5.0",
            "platform": "web",
            "title": "Web版本数据分析",
            "description": "新增数据分析和报表功能，支持自定义仪表板，增强数据导出功能，提供更深入的数据洞察。",
            "download_url": "https://web.fastiot.com",
            "file_size": None,
            "md5_hash": None,
            "is_force_update": False,
            "min_supported_version": "1.4.0"
        },
        {
            "version_code": "1.5.1",
            "version_name": "FastIoT Web v1.5.1",
            "platform": "web",
            "title": "Web版本API优化",
            "description": "优化API接口性能，新增WebSocket实时通信，修复数据同步延迟问题，提升实时性。",
            "download_url": "https://web.fastiot.com",
            "file_size": None,
            "md5_hash": None,
            "is_force_update": False,
            "min_supported_version": "1.5.0"
        },
        {
            "version_code": "1.6.0",
            "version_name": "FastIoT Web v1.6.0",
            "platform": "web",
            "title": "Web版本协作功能",
            "description": "新增团队协作功能，支持多用户同时操作，新增评论和标注功能，提升团队工作效率。",
            "download_url": "https://web.fastiot.com",
            "file_size": None,
            "md5_hash": None,
            "is_force_update": False,
            "min_supported_version": "1.5.0"
        },
        {
            "version_code": "1.6.1",
            "version_name": "FastIoT Web v1.6.1",
            "platform": "web",
            "title": "Web版本移动适配",
            "description": "优化移动端显示效果，新增触摸手势支持，修复移动端操作问题，提升移动端体验。",
            "download_url": "https://web.fastiot.com",
            "file_size": None,
            "md5_hash": None,
            "is_force_update": False,
            "min_supported_version": "1.6.0"
        },
        {
            "version_code": "1.0.1",
            "version_name": "FastIoT v1.0.1",
            "platform": "all",
            "title": "紧急修复版本",
            "description": "修复登录异常和设备连接问题，建议立即更新。",
            "download_url": "https://download.fastiot.com/v1.0.1/fastiot-v1.0.1-hotfix.apk",
            "file_size": 25800000,  # 25.8MB
            "md5_hash": "d4e5f6789012345678901234abcdef12",
            "is_force_update": True,
            "min_supported_version": "1.0.0"
        }
    ]
    
    for version_data in version_infos_data:
        version_info = VersionInfo(
            version_code=version_data["version_code"],
            version_name=version_data["version_name"],
            platform=version_data["platform"],
            title=version_data["title"],
            description=version_data["description"],
            download_url=version_data["download_url"],
            file_size=version_data["file_size"],
            md5_hash=version_data["md5_hash"],
            is_force_update=version_data["is_force_update"],
            min_supported_version=version_data["min_supported_version"],
            extra={
                "release_notes": [
                    "修复已知问题",
                    "优化用户体验",
                    "新增功能特性"
                ],
                "compatibility": {
                    "android": "5.0+",
                    "ios": "12.0+",
                    "web": "Chrome 80+, Firefox 75+, Safari 13+"
                }
            }
        )
        session.add(version_info)

async def create_feedbacks(session: AsyncSession, accounts):
    """创建意见反馈"""
    print("创建意见反馈...")
    
    feedback_types = ['bug', 'feature', 'improvement', 'complaint', 'praise', 'other']
    feedback_statuses = ['pending', 'processing', 'resolved', 'rejected', 'closed']
    feedback_sources = ['app', 'web', 'email', 'phone', 'wechat', 'other']
    feedback_priorities = ['low', 'normal', 'high', 'urgent']
    
    feedback_titles = [
        "应用启动速度慢",
        "设备连接不稳定",
        "希望增加设备分组功能",
        "界面设计不够美观",
        "功能很实用，点赞！",
        "数据同步有问题",
        "希望支持更多设备类型",
        "推送通知不及时",
        "用户界面需要优化",
        "系统运行很稳定",
        "登录验证码收不到",
        "希望增加离线模式",
        "设备控制响应慢",
        "数据统计功能很好",
        "希望支持多语言",
        "系统偶尔会崩溃",
        "希望增加设备分享功能",
        "界面操作不够直观",
        "功能很全面，推荐！",
        "希望增加自定义主题",
        # Web相关反馈
        "Web端页面加载太慢",
        "希望Web端支持暗黑模式",
        "Web端移动端适配不好",
        "Web端数据图表显示异常",
        "Web端批量操作功能很好用",
        "Web端实时数据更新延迟",
        "希望Web端支持快捷键操作",
        "Web端文件上传功能有问题",
        "Web端界面布局可以更合理",
        "Web端搜索功能不够强大",
        "Web端导出数据格式太少",
        "Web端多标签页切换卡顿",
        "Web端权限管理功能完善",
        "Web端API文档很详细",
        "Web端响应式设计不错",
        "Web端浏览器兼容性问题",
        "Web端数据可视化很直观",
        "Web端操作流程可以简化",
        "Web端性能监控功能有用",
        "Web端用户体验持续改善"
    ]
    
    feedback_contents = [
        "应用启动时间过长，希望能优化启动速度。",
        "设备经常掉线，连接不稳定，影响使用体验。",
        "建议增加设备分组功能，方便管理多个设备。",
        "界面设计可以更现代化一些，提升视觉效果。",
        "这个应用功能很实用，界面也很友好，非常满意！",
        "数据同步经常失败，希望能修复这个问题。",
        "希望支持更多品牌的智能设备，扩大兼容性。",
        "推送通知经常延迟，希望能及时推送重要信息。",
        "用户界面布局可以更合理，操作更便捷。",
        "系统运行很稳定，很少出现故障，值得信赖。",
        "登录时验证码经常收不到，影响正常使用。",
        "希望增加离线模式，在网络不好时也能使用。",
        "设备控制响应比较慢，希望能提升响应速度。",
        "数据统计功能很详细，对分析很有帮助。",
        "希望支持多语言，方便不同地区用户使用。",
        "系统偶尔会崩溃，希望能提高稳定性。",
        "希望增加设备分享功能，方便家庭成员使用。",
        "界面操作不够直观，新手用户上手困难。",
        "功能很全面，界面也很美观，强烈推荐！",
        "希望增加自定义主题功能，个性化设置。",
        # Web相关反馈内容
        "Web端页面加载速度比较慢，特别是数据量大的时候，希望能优化加载性能。",
        "希望Web端能支持暗黑模式，在夜间使用时更护眼，提升用户体验。",
        "Web端在移动设备上显示效果不好，按钮太小，操作不方便，希望能优化移动端适配。",
        "Web端的数据图表有时候显示异常，数据不准确，希望能修复这个问题。",
        "Web端的批量操作功能很实用，可以同时管理多个设备，大大提高了工作效率。",
        "Web端实时数据更新有延迟，不能及时反映设备状态变化，希望能提升实时性。",
        "希望Web端能支持更多快捷键操作，提高操作效率，特别是对于专业用户。",
        "Web端文件上传功能有问题，有时候上传失败，希望能修复这个功能。",
        "Web端界面布局可以更合理一些，信息密度可以适当调整，提升可读性。",
        "Web端搜索功能不够强大，希望能支持更复杂的搜索条件和模糊搜索。",
        "Web端导出数据格式太少，希望能支持更多格式，如Excel、PDF等。",
        "Web端多标签页切换时会有卡顿现象，希望能优化性能。",
        "Web端权限管理功能很完善，可以精确控制用户权限，安全性很好。",
        "Web端API文档很详细，接口设计也很规范，对开发者很友好。",
        "Web端响应式设计做得不错，在不同屏幕尺寸下都能正常显示。",
        "Web端在某些浏览器上兼容性有问题，希望能提高浏览器兼容性。",
        "Web端数据可视化功能很直观，图表类型丰富，数据分析很方便。",
        "Web端操作流程可以进一步简化，减少不必要的步骤，提升用户体验。",
        "Web端性能监控功能很有用，可以实时了解系统运行状态，便于运维管理。",
        "Web端用户体验在持续改善，每次更新都有新的优化，期待更多功能。"
    ]
    
    # 为每个账号创建1-3条反馈
    for account in accounts:
        num_feedbacks = random.randint(1, 3)
        for i in range(num_feedbacks):
            feedback_type = random.choice(feedback_types)
            status = random.choice(feedback_statuses)
            # 增加Web来源的权重
            source_weights = {
                'web': 0.4,  # 40%概率选择Web
                'app': 0.3,  # 30%概率选择App
                'email': 0.1,  # 10%概率选择Email
                'phone': 0.1,  # 10%概率选择Phone
                'wechat': 0.05,  # 5%概率选择WeChat
                'other': 0.05  # 5%概率选择Other
            }
            source = random.choices(list(source_weights.keys()), weights=list(source_weights.values()))[0]
            priority = random.choice(feedback_priorities)
            title = random.choice(feedback_titles)
            content = random.choice(feedback_contents)
            
            # 根据状态设置处理时间
            processed_at = None
            replay = None
            if status in ['resolved', 'rejected', 'closed']:
                processed_at = get_local_time() - timedelta(days=random.randint(1, 30))
                if random.choice([True, False]):  # 50%概率有回复
                    replay = "感谢您的反馈，我们已经处理了您的问题。如有其他疑问，请随时联系我们。"
            
            feedback = Feedback(
                account_id=account.id,
                type=feedback_type,
                title=title,
                content=content,
                priority=priority,
                status=status,
                source=source,
                contact_info=f"{account.email}" if account.email else f"{account.phone}",
                replay=replay,
                processed_at=processed_at,
                extra={
                    "device_info": {
                        "platform": random.choice(["Android", "iOS", "Web"]),
                        "version": f"{random.randint(1, 2)}.{random.randint(0, 2)}.{random.randint(0, 5)}",
                        "model": random.choice(["iPhone 12", "Samsung Galaxy S21", "Chrome Browser"])
                    },
                    "user_agent": "FastIoT Mobile App 1.0.0",
                    "ip_address": f"192.168.1.{random.randint(1, 254)}"
                }
            )
            session.add(feedback)

async def reset_database():
    """重置数据库"""
    try:
        await init_db(reset=True)
    except Exception as e:
        print(f"数据库重置失败: {e}")
        sys.exit(1)

async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='数据库初始化工具')
    parser.add_argument('--reset', action='store_true', help='重置数据库（删除所有表后重新创建）')
    args = parser.parse_args()

    try:
        if args.reset:
            await reset_database()
        else:
            await init_db()
    except KeyboardInterrupt:
        print("\n操作被用户中断")
    except Exception as e:
        print(f"操作失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
