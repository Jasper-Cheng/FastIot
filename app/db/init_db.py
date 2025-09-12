import asyncio
from datetime import datetime, timedelta
import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.base import Base
from app.db.session import engine
from app.db.models.user import User
from app.db.models.member import Member
from app.db.models.room import Room
from app.db.models.device import Device
from app.db.models.device_model import DeviceModel
from app.db.models.device_param import DeviceParam
from app.db.models.device_log import DeviceLog
from app.db.models.alert import Alert
from app.db.models.room_device import RoomDevice
from app.db.models.member_device_permission import MemberDevicePermission
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
    result = await session.execute(text("SELECT COUNT(*) FROM user"))
    count = result.scalar()
    
    if count == 0:
        print("开始创建测试数据...")
        
        # 1. 创建用户
        users = await create_users(session)
        
        # 2. 创建成员
        members = await create_members(session, users)
        
        # 3. 创建房间
        rooms = await create_rooms(session, users)
        
        # 4. 创建设备型号
        device_models = await create_device_models(session)
        
        # 5. 创建设备
        devices = await create_devices(session, users, device_models)
        
        # 6. 创建房间设备关联
        await create_room_devices(session, rooms, devices)
        
        # 7. 创建成员设备权限
        await create_member_device_permissions(session, members, devices)
        
        # 8. 创建设备参数
        await create_device_params(session, devices)
        
        # 9. 创建设备日志
        await create_device_logs(session, devices)
        
        # 10. 创建告警
        await create_alerts(session, devices)
        
        await session.commit()
        print("✅ 数据库初始化完成！创建了丰富的测试数据")
    else:
        print("数据库已存在数据，跳过初始化")

async def create_users(session: AsyncSession):
    """创建用户"""
    users_data = [
        {"username": "admin", "email": "admin@fastiot.com", "phone": "13800138000"},
        {"username": "user1", "email": "user1@example.com", "phone": "13800138001"},
        {"username": "user2", "email": "user2@example.com", "phone": "13800138002"},
        {"username": "user3", "email": "user3@example.com", "phone": "13800138003"},
        {"username": "user4", "email": "user4@example.com", "phone": "13800138004"},
    ]
    
    users = []
    for user_data in users_data:
        user = User(
            username=user_data["username"],
            email=user_data["email"],
            phone=user_data["phone"],
            password=get_password_hash("123456"),
            avatar=f"https://api.dicebear.com/7.x/avataaars/svg?seed={user_data['username']}"
        )
        session.add(user)
        users.append(user)
    
    await session.flush()
    return users

async def create_members(session: AsyncSession, users):
    """创建成员"""
    members_data = [
        {"name": "张三", "gender": "male", "account": "zhangsan", "phone": "13900139001", "email": "zhangsan@example.com"},
        {"name": "李四", "gender": "female", "account": "lisi", "phone": "13900139002", "email": "lisi@example.com"},
        {"name": "王五", "gender": "male", "account": "wangwu", "phone": "13900139003", "email": "wangwu@example.com"},
        {"name": "赵六", "gender": "female", "account": "zhaoliu", "phone": "13900139004", "email": "zhaoliu@example.com"},
        {"name": "钱七", "gender": "male", "account": "qianqi", "phone": "13900139005", "email": "qianqi@example.com"},
    ]
    
    members = []
    for i, member_data in enumerate(members_data):
        member = Member(
            user_id=users[i % len(users)].id,
            name=member_data["name"],
            gender=member_data["gender"],
            account=member_data["account"],
            password=get_password_hash("123456"),
            phone=member_data["phone"],
            email=member_data["email"],
            avatar=f"https://api.dicebear.com/7.x/avataaars/svg?seed={member_data['account']}"
        )
        session.add(member)
        members.append(member)
    
    await session.flush()
    return members

async def create_rooms(session: AsyncSession, users):
    """创建房间"""
    rooms_data = [
        {"name": "客厅", "user_id": 0},
        {"name": "卧室", "user_id": 0},
        {"name": "厨房", "user_id": 0},
        {"name": "办公室", "user_id": 1},
        {"name": "实验室", "user_id": 1},
        {"name": "仓库", "user_id": 2},
        {"name": "车库", "user_id": 2},
        {"name": "花园", "user_id": 3},
    ]
    
    rooms = []
    for room_data in rooms_data:
        room = Room(
            user_id=users[room_data["user_id"]].id,
            name=room_data["name"]
        )
        session.add(room)
        rooms.append(room)
    
    await session.flush()
    return rooms

async def create_device_models(session: AsyncSession):
    """创建设备型号"""
    device_models_data = [
        {
            "model_name": "温度传感器",
            "vendor": "IoT Corp",
            "params": {"temperature": {"type": "float", "unit": "°C", "min": -40, "max": 85}}
        },
        {
            "model_name": "湿度传感器",
            "vendor": "IoT Corp",
            "params": {"humidity": {"type": "float", "unit": "%", "min": 0, "max": 100}}
        },
        {
            "model_name": "环境监测器",
            "vendor": "Smart Devices",
            "params": {
                "temperature": {"type": "float", "unit": "°C", "min": -40, "max": 85},
                "humidity": {"type": "float", "unit": "%", "min": 0, "max": 100},
                "pressure": {"type": "float", "unit": "hPa", "min": 300, "max": 1100}
            }
        },
        {
            "model_name": "智能开关",
            "vendor": "Smart Home",
            "params": {"power": {"type": "boolean", "unit": "on/off"}}
        },
        {
            "model_name": "烟雾报警器",
            "vendor": "Safety First",
            "params": {"smoke_level": {"type": "float", "unit": "ppm", "min": 0, "max": 1000}}
        },
        {
            "model_name": "摄像头",
            "vendor": "Vision Tech",
            "params": {"motion_detected": {"type": "boolean", "unit": "true/false"}}
        },
        {
            "model_name": "空气质量监测器",
            "vendor": "Air Quality Inc",
            "params": {
                "pm25": {"type": "float", "unit": "μg/m³", "min": 0, "max": 500},
                "pm10": {"type": "float", "unit": "μg/m³", "min": 0, "max": 500},
                "co2": {"type": "float", "unit": "ppm", "min": 300, "max": 5000}
            }
        },
        {
            "model_name": "智能门锁",
            "vendor": "Secure Lock",
            "params": {"locked": {"type": "boolean", "unit": "locked/unlocked"}}
        }
    ]
    
    device_models = []
    for model_data in device_models_data:
        model = DeviceModel(
            model_name=model_data["model_name"],
            vendor=model_data["vendor"],
            params=model_data["params"]
        )
        session.add(model)
        device_models.append(model)
    
    await session.flush()
    return device_models

async def create_devices(session: AsyncSession, users, device_models):
    """创建设备"""
    devices_data = [
        # 用户1的设备
        {"name": "客厅温度传感器", "sn": "TEMP001", "user_id": 0, "model_id": 0, "status": "online"},
        {"name": "客厅湿度传感器", "sn": "HUM001", "user_id": 0, "model_id": 1, "status": "online"},
        {"name": "客厅环境监测器", "sn": "ENV001", "user_id": 0, "model_id": 2, "status": "online"},
        {"name": "卧室智能开关", "sn": "SW001", "user_id": 0, "model_id": 3, "status": "offline"},
        {"name": "厨房烟雾报警器", "sn": "SMOKE001", "user_id": 0, "model_id": 4, "status": "online"},
        
        # 用户2的设备
        {"name": "办公室摄像头", "sn": "CAM001", "user_id": 1, "model_id": 5, "status": "online"},
        {"name": "实验室空气质量监测器", "sn": "AIR001", "user_id": 1, "model_id": 6, "status": "online"},
        {"name": "实验室温度传感器", "sn": "TEMP002", "user_id": 1, "model_id": 0, "status": "offline"},
        
        # 用户3的设备
        {"name": "仓库智能门锁", "sn": "LOCK001", "user_id": 2, "model_id": 7, "status": "online"},
        {"name": "车库环境监测器", "sn": "ENV002", "user_id": 2, "model_id": 2, "status": "offline"},
        {"name": "仓库湿度传感器", "sn": "HUM002", "user_id": 2, "model_id": 1, "status": "online"},
        
        # 用户4的设备
        {"name": "花园温度传感器", "sn": "TEMP003", "user_id": 3, "model_id": 0, "status": "online"},
        {"name": "花园环境监测器", "sn": "ENV003", "user_id": 3, "model_id": 2, "status": "online"},
        {"name": "花园摄像头", "sn": "CAM002", "user_id": 3, "model_id": 5, "status": "offline"},
        
        # 用户5的设备
        {"name": "智能开关组", "sn": "SW002", "user_id": 4, "model_id": 3, "status": "online"},
        {"name": "烟雾报警器组", "sn": "SMOKE002", "user_id": 4, "model_id": 4, "status": "online"},
    ]
    
    devices = []
    for device_data in devices_data:
        device = Device(
            name=device_data["name"],
            sn=device_data["sn"],
            user_id=users[device_data["user_id"]].id,
            model_id=device_models[device_data["model_id"]].id,
            status=device_data["status"]
        )
        session.add(device)
        devices.append(device)
    
    await session.flush()
    return devices

async def create_room_devices(session: AsyncSession, rooms, devices):
    """创建房间设备关联"""
    # 将设备分配到不同房间
    room_device_mappings = [
        (0, [0, 1, 2, 3]),  # 客厅：温度、湿度、环境监测器、智能开关
        (1, [4]),           # 卧室：烟雾报警器
        (2, [5, 6]),        # 厨房：摄像头、空气质量监测器
        (3, [7, 8]),        # 办公室：温度传感器、环境监测器
        (4, [9, 10]),       # 实验室：智能门锁、湿度传感器
        (5, [11, 12]),      # 仓库：温度传感器、环境监测器
        (6, [13, 14]),      # 车库：花园温度传感器、摄像头
        (7, [15, 16]),      # 花园：智能开关组、烟雾报警器组
    ]
    
    for room_idx, device_indices in room_device_mappings:
        if room_idx < len(rooms):
            for i, device_idx in enumerate(device_indices):
                if device_idx < len(devices):
                    from app.db.models.room_device import RoomDevice
                    room_device = RoomDevice(
                        room_id=rooms[room_idx].id,
                        device_id=devices[device_idx].id,
                        sort_order=i
                    )
                    session.add(room_device)

async def create_member_device_permissions(session: AsyncSession, members, devices):
    """创建成员设备权限"""
    # 为每个成员分配一些设备的控制权限
    permissions = [
        (0, [0, 1, 2]),     # 成员0可以控制设备0,1,2
        (1, [3, 4]),        # 成员1可以控制设备3,4
        (2, [5, 6, 7]),     # 成员2可以控制设备5,6,7
        (3, [8, 9]),        # 成员3可以控制设备8,9
        (4, [10, 11, 12]),  # 成员4可以控制设备10,11,12
    ]
    
    for member_idx, device_indices in permissions:
        if member_idx < len(members):
            for device_idx in device_indices:
                if device_idx < len(devices):
                    permission = MemberDevicePermission(
                        member_id=members[member_idx].id,
                        device_id=devices[device_idx].id,
                        can_control=True
                    )
                    session.add(permission)

async def create_device_params(session: AsyncSession, devices):
    """创建设备参数"""
    for device in devices:
        # 根据设备型号生成相应的参数数据
        if "温度" in device.name:
            params = {"temperature": round(random.uniform(15, 30), 1)}
        elif "湿度" in device.name:
            params = {"humidity": round(random.uniform(30, 80), 1)}
        elif "环境监测器" in device.name:
            params = {
                "temperature": round(random.uniform(15, 30), 1),
                "humidity": round(random.uniform(30, 80), 1),
                "pressure": round(random.uniform(950, 1050), 1)
            }
        elif "智能开关" in device.name:
            params = {"power": random.choice([True, False])}
        elif "烟雾报警器" in device.name:
            params = {"smoke_level": round(random.uniform(0, 50), 1)}
        elif "摄像头" in device.name:
            params = {"motion_detected": random.choice([True, False])}
        elif "空气质量" in device.name:
            params = {
                "pm25": round(random.uniform(10, 100), 1),
                "pm10": round(random.uniform(20, 150), 1),
                "co2": round(random.uniform(400, 1000), 1)
            }
        elif "智能门锁" in device.name:
            params = {"locked": random.choice([True, False])}
        else:
            params = {"status": "unknown"}
        
        device_param = DeviceParam(
            device_id=device.id,
            params=params
        )
        session.add(device_param)

async def create_device_logs(session: AsyncSession, devices):
    """创建设备日志"""
    event_types = ["online", "offline", "data_update", "alert", "maintenance", "error"]
    
    for device in devices:
        # 为每个设备创建10-20条日志记录
        log_count = random.randint(10, 20)
        for i in range(log_count):
            created_at = datetime.now() - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))
            
            event_type = random.choice(event_types)
            if event_type == "data_update":
                params = {"temperature": round(random.uniform(15, 30), 1)}
            elif event_type == "alert":
                params = {"message": "设备异常", "level": random.choice(["low", "medium", "high"])}
            elif event_type == "error":
                params = {"error_code": random.randint(1000, 9999), "message": "连接超时"}
            else:
                params = {"status": event_type}
            
            device_log = DeviceLog(
                device_id=device.id,
                event_type=event_type,
                params=params,
                created_at=created_at
            )
            session.add(device_log)

async def create_alerts(session: AsyncSession, devices):
    """创建告警"""
    alert_messages = [
        "温度过高", "温度过低", "湿度异常", "烟雾检测", "设备离线", 
        "连接超时", "数据异常", "维护提醒", "电量不足", "信号弱"
    ]
    
    for device in devices:
        # 为每个设备创建1-5条告警记录
        alert_count = random.randint(1, 5)
        for i in range(alert_count):
            created_at = datetime.now() - timedelta(days=random.randint(0, 7), hours=random.randint(0, 23))
            
            alert = Alert(
                device_id=device.id,
                level=random.choice(["low", "medium", "high"]),
                status=random.choice(["new", "read", "resolved"]),
                message=random.choice(alert_messages),
                created_at=created_at
            )
            session.add(alert)

if __name__ == "__main__":
    asyncio.run(init_db())