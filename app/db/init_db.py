import asyncio
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

async def init_db() -> None:
    """初始化数据库"""
    async with engine.begin() as conn:
        # 创建所有表
        await conn.run_sync(Base.metadata.create_all)
    
    # 插入初始数据
    async with AsyncSession(engine) as session:
        await insert_initial_data(session)

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
    
    # 创建1个管理员账号
    admin_account = Account(
        account="admin",
        password_hash=get_password_hash("admin123"),
        name="管理员",
        gender='other',
        phone="13700000000",
            email="admin@fastiot.com",
        role='admin'
    )
    session.add(admin_account)
    accounts.append(admin_account)

    # 创建5个主账号
    for i in range(5):
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
    
    # 创建10个子账号
    for i in range(10):
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
    
    # 为前5个账号（owner角色）创建用户
    for i, account in enumerate(accounts[:5]):
        user = User(account_id=account.id)
        session.add(user)
        users.append(user)
    
    await session.flush()
    return users

async def create_members(session: AsyncSession, users, accounts):
    """创建成员"""
    print("创建成员...")
    members = []
    
    # 为后10个账号（member角色）创建成员
    member_accounts = accounts[6:]  # 后10个账号
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
        ("温度传感器物模型", "基础温度传感器功能定义", 
         {"temperature": {"type": "float", "unit": "°C", "min": -40, "max": 85}},
         ["read_temperature", "calibrate"],
         ["temperature_alert", "sensor_fault"]),
        ("湿度传感器物模型", "基础湿度传感器功能定义",
         {"humidity": {"type": "float", "unit": "%", "min": 0, "max": 100}},
         ["read_humidity", "calibrate"],
         ["humidity_alert", "sensor_fault"]),
        ("智能开关物模型", "智能开关功能定义",
         {"power": {"type": "boolean", "unit": "on/off"}},
         ["toggle", "reset"],
         ["power_fault", "overload"]),
        ("智能灯泡物模型", "智能灯泡功能定义",
         {"brightness": {"type": "int", "unit": "%", "min": 0, "max": 100}, "color": {"type": "string", "unit": "hex"}},
         ["set_brightness", "set_color", "toggle"],
         ["bulb_fault", "overheating"]),
        ("烟雾报警器物模型", "烟雾报警器功能定义",
         {"smoke_level": {"type": "float", "unit": "ppm", "min": 0, "max": 1000}},
         ["test_alarm", "reset"],
         ["smoke_detected", "low_battery", "sensor_fault"]),
        ("门锁物模型", "智能门锁功能定义",
         {"locked": {"type": "boolean", "unit": "locked/unlocked"}},
         ["lock", "unlock", "reset"],
         ["lock_fault", "low_battery", "tamper_detected"]),
        ("摄像头物模型", "智能摄像头功能定义",
         {"recording": {"type": "boolean", "unit": "on/off"}, "motion_detected": {"type": "boolean", "unit": "yes/no"}},
         ["start_recording", "stop_recording", "take_photo"],
         ["motion_detected", "storage_full", "camera_fault"]),
        ("空气质量监测器物模型", "空气质量监测器功能定义",
         {"pm25": {"type": "float", "unit": "μg/m³", "min": 0, "max": 500}, "co2": {"type": "float", "unit": "ppm", "min": 300, "max": 5000}},
         ["read_air_quality", "calibrate"],
         ["air_quality_alert", "sensor_fault", "data_anomaly"])
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
        ("TEMP001", "温度传感器", "IoT Corp", 0, {
            "temperature": {"type": "float", "unit": "°C", "min": -40, "max": 85, "precision": 1, "default": 20}
        }),
        ("HUM001", "湿度传感器", "IoT Corp", 1, {
            "humidity": {"type": "float", "unit": "%", "min": 0, "max": 100, "precision": 1, "default": 50}
        }),
        ("SWITCH001", "智能开关", "SmartHome Inc", 2, {
            "power": {"type": "boolean", "unit": "on/off", "default": False},
            "voltage": {"type": "float", "unit": "V", "min": 0, "max": 250, "precision": 1},
            "current": {"type": "float", "unit": "A", "min": 0, "max": 16, "precision": 2}
        }),
        ("BULB001", "智能灯泡", "LightTech", 3, {
            "brightness": {"type": "int", "unit": "%", "min": 0, "max": 100, "default": 50},
            "color": {"type": "string", "unit": "hex", "default": "#FFFFFF"},
            "color_temp": {"type": "int", "unit": "K", "min": 2700, "max": 6500, "default": 4000}
        }),
        ("SMOKE001", "烟雾报警器", "SafetyFirst", 4, {
            "smoke_level": {"type": "float", "unit": "ppm", "min": 0, "max": 1000, "precision": 1},
            "battery_level": {"type": "int", "unit": "%", "min": 0, "max": 100},
            "test_mode": {"type": "boolean", "unit": "on/off", "default": False}
        }),
        ("LOCK001", "智能门锁", "SecureLock", 5, {
            "locked": {"type": "boolean", "unit": "locked/unlocked", "default": True},
            "battery_level": {"type": "int", "unit": "%", "min": 0, "max": 100},
            "auto_lock": {"type": "boolean", "unit": "enabled/disabled", "default": True},
            "auto_lock_delay": {"type": "int", "unit": "seconds", "min": 30, "max": 300, "default": 60}
        }),
        ("CAM001", "智能摄像头", "VisionCam", 6, {
            "recording": {"type": "boolean", "unit": "on/off", "default": False},
            "motion_detected": {"type": "boolean", "unit": "yes/no", "default": False},
            "night_vision": {"type": "boolean", "unit": "on/off", "default": True},
            "resolution": {"type": "string", "unit": "pixels", "default": "1920x1080"},
            "storage_used": {"type": "float", "unit": "GB", "min": 0, "max": 1000, "precision": 2}
        }),
        ("AIR001", "空气质量监测器", "AirQuality", 7, {
            "pm25": {"type": "float", "unit": "μg/m³", "min": 0, "max": 500, "precision": 1},
            "co2": {"type": "float", "unit": "ppm", "min": 300, "max": 5000, "precision": 0},
            "tvoc": {"type": "float", "unit": "ppb", "min": 0, "max": 1000, "precision": 1},
            "temperature": {"type": "float", "unit": "°C", "min": -10, "max": 60, "precision": 1},
            "humidity": {"type": "float", "unit": "%", "min": 0, "max": 100, "precision": 1}
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
    
    # 创建一些未绑定的设备（user_id=None）
    unbound_count = 5
    for i in range(unbound_count):
        device = Device(
            user_id=None,
            model_id=random.choice(device_models).id,
            name=f"未绑定设备{i+1}",
            sn=f"UNBOUND{i+1:03d}",
            status=random.choice(['unconfigured', 'unbound'])
        )
        session.add(device)
        devices.append(device)
    
    # 为每个用户创建设备
    for user in users:
        # 每个用户创建3-5个设备
        num_devices = random.randint(3, 5)
        for i in range(num_devices):
            device = Device(
                user_id=user.id,
                model_id=random.choice(device_models).id,
                name=f"设备{i+1}",
                sn=f"SN{user.id:03d}{i+1:03d}",
                status=random.choice(['bound', 'online', 'offline', 'upgrading', 'fault'])
            )
            session.add(device)
            devices.append(device)
    
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
        
        for device in devices:
        # 为每个设备创建1-5条告警
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

if __name__ == "__main__":
    asyncio.run(init_db())
