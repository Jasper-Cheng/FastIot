import asyncio
import sys
from datetime import datetime, timedelta
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
from app.db.models.thing_model import ThingModel
from app.db.models.device_model import DeviceModel
from app.db.models.device_param import DeviceParam
from app.db.models.device_log import DeviceLog
from app.db.models.alert import Alert
from app.db.models.room_device import RoomDevice
from app.db.models.member_device_permission import MemberDevicePermission
from app.db.models.device_network import DeviceNetwork
from app.core.security import get_password_hash

async def init_db(reset=False) -> None:
    """初始化数据库"""
    try:
        if reset:
            print("🔄 开始重置数据库...")
            # 删除所有表
            async with engine.begin() as conn:
                print("🗑️  删除现有表...")
                await conn.run_sync(lambda sync_conn: sync_conn.execute(text("SET FOREIGN_KEY_CHECKS = 0")))
                
                # 获取所有表名
                result = await conn.execute(text("SHOW TABLES"))
                tables = [row[0] for row in result.fetchall()]
                
                # 删除所有表
                for table in tables:
                    await conn.execute(text(f"DROP TABLE IF EXISTS `{table}`"))
                    print(f"   ✅ 删除表: {table}")
                
                await conn.run_sync(lambda sync_conn: sync_conn.execute(text("SET FOREIGN_KEY_CHECKS = 1")))
                print("✅ 所有表已删除")
        
        # 创建所有表
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # 插入初始数据
        async with AsyncSession(engine) as session:
            await insert_initial_data(session)
        
        if reset:
            print("🎉 数据库重置完成！")
            print("\n📊 创建的测试数据包括:")
            print("   👤 3个管理员账号")
            print("   👤 15个主账号")
            print("   👤 35个成员账号")
            print("   🏠 多个房间")
            print("   📱 11种物模型类型")
            print("   🔧 33种设备型号")
            print("   🔧 50+个设备")
            print("   🔗 房间设备关联")
            print("   🔐 成员设备权限")
            print("   📊 设备参数数据")
            print("   📝 设备日志记录")
            print("   ⚠️  告警记录")
            print("\n📋 数据库结构说明：")
            print("   • account 表：统一管理所有登录账号（管理员、主账号和子账号）")
            print("   • admin 表：管理员，与 account 一一对应")
            print("   • user 表：主账号，与 account 一一对应")
            print("   • member 表：子账号，与 account 一一对应，属于某个 user")
            print("   • thing_model 表：物模型定义")
            print("   • device_model 表：设备型号定义")
            print("   • device 表：具体设备实例")
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
        
        # 10. 创建设备参数
        await create_device_params(session, devices)
        
        # 11. 创建设备日志
        await create_device_logs(session, devices)
        
        # 12. 创建告警
        await create_alerts(session, devices)
        
        # 13. 创建设备网络信息
        await create_device_networks(session, devices)
        
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
        thing_model = ThingModel(
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

    for model_code, name, vendor, thing_model_index, params in models_data:
        device_model = DeviceModel(
            model_code=model_code,
            name=name,
            vendor=vendor,
            thing_model_id=thing_models[thing_model_index].id,
            params=params
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
            status=random.choice(['unconfigured', 'unbound'])
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
            if device_count < 10:
                status = 'unconfigured'
            elif device_count < 20:
                status = 'unbound'
            elif device_count < 30:
                status = 'bound'
            elif device_count < 40:
                status = 'online'
            elif device_count < 45:
                status = 'offline'
            elif device_count < 48:
                status = 'upgrading'
            else:
                status = 'fault'

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
            status=random.choice(['bound', 'online', 'offline', 'upgrading', 'fault'])
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

async def create_device_params(session: AsyncSession, devices):
    """创建设备参数"""
    print("创建设备参数...")

    for device in devices:
        # 为每个设备创建参数记录
        param_data = {
            "timestamp": datetime.now().isoformat(),
            "status": device.status,
            "battery": random.randint(20, 100) if device.status == 'online' else 0,
            "signal_strength": random.randint(60, 100) if device.status == 'online' else 0
        }

        device_param = DeviceParam(
            device_id=device.id,
            params=param_data
        )
        session.add(device_param)

async def create_device_logs(session: AsyncSession, devices):
    """创建设备日志"""
    print("创建设备日志...")

    event_types = ["power_on", "power_off", "data_update", "error", "maintenance", "status_change"]

    for device in devices:
        # 为每个设备创建10-20条日志
        num_logs = random.randint(10, 20)
        for i in range(num_logs):
            log_data = {
                "event": random.choice(event_types),
                "value": random.uniform(0, 100),
                "timestamp": (datetime.now() - timedelta(days=random.randint(0, 30))).isoformat()
            }

            device_log = DeviceLog(
                device_id=device.id,
                event_type=random.choice(event_types),
                params=log_data
            )
            session.add(device_log)

async def create_alerts(session: AsyncSession, devices):
    """创建告警"""
    print("创建告警...")

    alert_levels = ['low', 'medium', 'high']
    alert_messages = [
        "设备离线",
        "温度异常",
        "湿度过高",
        "电量不足",
        "信号弱",
        "设备故障",
        "数据异常"
        ]
    # 为每个设备创建1-5条告警
    for device in devices:
        num_alerts = random.randint(1, 5)
        for i in range(num_alerts):
            alert = Alert(
                device_id=device.id,
                level=random.choice(alert_levels),
                status=random.choice(['new', 'read', 'resolved']),
                message=random.choice(alert_messages)
            )
            session.add(alert)

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

async def reset_database():
    """重置数据库"""
    try:
        await init_db(reset=True)
    except Exception as e:
        print(f"❌ 数据库重置失败: {e}")
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
        print("\n⚠️  操作被用户中断")
    except Exception as e:
        print(f"❌ 操作失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
