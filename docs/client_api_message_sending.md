# Client API 发送信息功能文档

## 概述

本文档详细说明了 `app/api/client/` 目录下所有API文件中的消息发送功能。系统通过 MQTT 服务实现实时消息推送，支持家庭通知、设备通知、系统通知和个人通知四种类型。

---

## 一、消息发送工具函数

**文件位置**: `app/api/utils.py`

系统提供了5个核心的消息发送工具函数，所有API接口都通过这些函数来发送消息。

### 1.1 send_family_notice - 发送家庭通知

**函数签名**:
```python
async def send_family_notice(
    family_id: int,
    payload: Dict[str, Any],
    raise_on_error: bool = False
) -> None
```

**功能说明**: 向指定家庭的所有成员发送家庭通知消息

**参数说明**:
- `family_id`: 家庭ID
- `payload`: 消息内容字典
- `raise_on_error`: 是否在发送失败时抛出异常，默认为 False

**实现方式**: 调用 `mqtt_service.publish_home_notice(str(family_id), payload)`

**示例**:
```python
await send_family_notice(
    family_id=1,
    payload={
        "type": "member_added",
        "message": "有新成员加入家庭",
        "member_id": 123
    }
)
```

---

### 1.2 send_device_notice - 发送设备通知

**函数签名**:
```python
async def send_device_notice(
    device_sn: str,
    payload: Dict[str, Any],
    raise_on_error: bool = False
) -> None
```

**功能说明**: 向指定设备发送设备通知消息

**参数说明**:
- `device_sn`: 设备序列号
- `payload`: 消息内容字典
- `raise_on_error`: 是否在发送失败时抛出异常，默认为 False

**实现方式**: 调用 `mqtt_service.publish_device_notice(device_sn, payload)`

**示例**:
```python
await send_device_notice(
    device_sn="M701001",
    payload={
        "type": "status_change",
        "message": "设备状态已更新",
        "status": "online"
    }
)
```

---

### 1.3 send_system_notice - 发送系统通知

**函数签名**:
```python
async def send_system_notice(
    payload: Dict[str, Any],
    raise_on_error: bool = False
) -> None
```

**功能说明**: 向所有用户发送系统通知消息

**参数说明**:
- `payload`: 消息内容字典
- `raise_on_error`: 是否在发送失败时抛出异常，默认为 False

**实现方式**: 调用 `mqtt_service.publish_system_notice(payload)`

**示例**:
```python
await send_system_notice({
    "type": "maintenance",
    "message": "系统将在今晚进行维护",
    "start_time": "2024-01-01 00:00:00"
})
```

---

### 1.4 send_personal_notice - 发送个人通知

**函数签名**:
```python
async def send_personal_notice(
    account_id: int,
    payload: Dict[str, Any],
    raise_on_error: bool = False
) -> None
```

**功能说明**: 向指定账户发送个人通知消息

**参数说明**:
- `account_id`: 账户ID
- `payload`: 消息内容字典
- `raise_on_error`: 是否在发送失败时抛出异常，默认为 False

**实现方式**: 调用 `mqtt_service.publish_client_notice(account_id, payload)`

**示例**:
```python
await send_personal_notice(
    account_id=123,
    payload={
        "type": "points_awarded",
        "message": "您获得了积分奖励",
        "points": 100
    }
)
```

---

### 1.5 send_families_notice_by_account - 向账户下所有家庭发送通知

**函数签名**:
```python
async def send_families_notice_by_account(
    db: AsyncSession,
    account_id: int,
    payload: Dict[str, Any],
    raise_on_error: bool = False
) -> Dict[str, int]
```

**功能说明**: 向指定账户下的所有家庭发送家庭通知消息

**参数说明**:
- `db`: 数据库会话
- `account_id`: 账户ID
- `payload`: 消息内容字典
- `raise_on_error`: 是否在发送失败时抛出异常，默认为 False

**返回值**: 包含发送统计信息的字典，格式为 `{"total": 总家庭数, "success": 成功数, "failed": 失败数}`

**实现方式**: 
1. 获取该账户下的所有家庭
2. 遍历所有家庭，调用 `send_family_notice` 发送消息

**示例**:
```python
result = await send_families_notice_by_account(
    db=db,
    account_id=123,
    payload={
        "type": "system_update",
        "message": "系统即将更新",
        "update_time": "2024-01-01 00:00:00"
    }
)
# result: {"total": 3, "success": 3, "failed": 0}
```

---

## 二、各模块消息发送详情

### 2.1 设备消息模块 (device_messages.py)

#### 2.1.1 标记设备消息为已读

**接口**: `PATCH /device-messages/{message_id}/make-read`

**发送时机**: 当用户标记某条设备消息为已读时

**消息类型**: 设备通知 (`send_device_notice`)

**消息内容**:
```python
{
    "type": "message_read",
    "message": "设备消息已标记为已读",
    "message_id": message_id,
    "device_id": updated.device_id,
    "device_name": device.name,
    "level": updated.level.value if updated.level else None,
}
```

**代码位置**: `device_messages.py:118-128`

---

#### 2.1.2 标记所有设备消息为已读

**接口**: `PATCH /device-messages/mark-all-read`

**发送时机**: 当用户标记所有设备消息为已读时

**消息类型**: 设备通知 (`send_device_notice`)

**消息内容**:
```python
{
    "type": "all_messages_read",
    "message": f"设备{device.name}的所有消息已标记为已读",
    "account_id": account_id,
    "device_id": device.id,
    "sn": device.sn,
}
```

**发送范围**: 向用户的所有相关设备发送通知

**代码位置**: `device_messages.py:158-167`

---

### 2.2 家庭成员管理模块 (family_members.py)

#### 2.2.1 加入家庭通知

**接口**: `POST /family-members/join-by-invite-code`

**发送时机**: 当用户通过邀请码加入家庭时

**消息类型**: 家庭通知 (`send_family_notice`)

**消息内容**:
```python
{
    "type": "family_member_added",
    "message": f"家庭成员 {nickname} 已加入家庭 {family.name}",
    "family_id": family.id,
    "family_name": family.name
}
```

**代码位置**: `family_members.py:103-111`

---

#### 2.2.2 更新成员昵称通知

**接口**: `PATCH /family-members/{family_member_id}`

**发送时机**: 当家庭成员昵称被更新时

**消息类型**: 家庭通知 (`send_family_notice`)

**消息内容**:
```python
{
    "type": "family_member_updated",
    "message": f"家庭成员昵称已更新：{old_nickname or '未设置'} -> {family_member.nickname or '未设置'}",
    "family_id": db_family_member.family_id,
    "family_name": family_name
}
```

**代码位置**: `family_members.py:207-215`

---

#### 2.2.3 删除家庭通知

**接口**: `DELETE /family-members/{family_member_id}`

**发送时机**: 当移除家庭成员时，如果被移除的是创建者，则删除整个家庭并发送通知

**消息类型**: 家庭通知 (`send_family_notice`)

**消息内容**:
```python
{
    "type": "family_deleted",
    "message": f"家庭 {family_name} 已被删除",
    "family_id": family_id,
    "family_name": family_name
}
```

**代码位置**: `family_members.py:295-303`

---

#### 2.2.4 移除成员通知

**接口**: `DELETE /family-members/{family_member_id}`

**发送时机**: 当普通成员被从家庭中移除时

**消息类型**: 家庭通知 (`send_family_notice`)

**消息内容**:
```python
{
    "type": "family_member_removed",
    "message": f"家庭成员 {removed_member_name} 已从家庭 {family_name} 中移除",
    "family_id": family_id,
    "family_name": family_name
}
```

**代码位置**: `family_members.py:336-344`

---

### 2.3 家庭管理模块 (families.py)

#### 2.3.1 删除家庭通知

**接口**: `DELETE /families/{family_id}`

**发送时机**: 当家庭创建者删除家庭时（在删除操作之前发送）

**消息类型**: 家庭通知 (`send_family_notice`)

**消息内容**:
```python
{
    "type": "family_deleted",
    "message": f"家庭 {family_name} 已被删除",
    "family_id": family_id,
    "family_name": family_name,
    "deleted_by_account_id": account_id,
    "platform": platform
}
```

**注意**: 在删除家庭之前发送，以便所有家庭成员都能收到通知

**代码位置**: `families.py:100-110`

---

#### 2.3.2 添加设备到家庭通知

**接口**: `POST /families/{family_id}/devices/{device_id}`

**发送时机**: 当设备被添加到家庭时

**消息类型**: 家庭通知 (`send_family_notice`)

**消息内容**:
```python
{
    "type": "device_added_to_family",
    "message": f"设备 {device.name} 已添加到家庭 {family_name or family_id}",
    "device_id": device.id,
    "device_name": device.name,
    "device_sn": device.sn
}
```

**代码位置**: `families.py:183-192`

---

#### 2.3.3 从家庭移除设备通知

**接口**: `DELETE /families/{family_id}/devices/{device_id}`

**发送时机**: 当设备从家庭中移除时

**消息类型**: 家庭通知 (`send_family_notice`)

**消息内容**:
```python
{
    "type": "device_removed_from_family",
    "message": f"设备 {device.name} 已从家庭 {family_name or family_id} 中移除",
    "device_id": device.id,
    "device_name": device.name,
    "device_sn": device.sn
}
```

**代码位置**: `families.py:247-256`

---

### 2.4 设备管理模块 (devices.py)

#### 2.4.1 更新设备名称通知

**接口**: `PATCH /devices/{device_id}/name`

**发送时机**: 当设备名称被更新时

**消息类型**: 设备通知 (`send_device_notice`)

**消息内容**:
```python
{
    "type": "device_name_updated",
    "message": f"设备名称已更新：{old_name} -> {payload.name}",
    "device_id": updated.id,
    "device_name": payload.name,
    "old_name": old_name,
    "device_sn": updated.sn,
    "account_id": account_id,
    "family_id": family_id,
}
```

**代码位置**: `devices.py:123-135`

---

#### 2.4.2 解绑设备通知

**接口**: `DELETE /devices/unbind-by-sn/{sn}`

**发送时机**: 当设备被解绑时

**消息类型**: 设备通知 (`send_device_notice`)

**消息内容**:
```python
{
    "type": "device_unbind",
    "message": f"设备已解绑：{device_name}（SN: {sn}）",
    "device_id": device.id,
    "device_name": device_name,
    "device_sn": sn,
}
```

**代码位置**: `devices.py:256-265`

---

### 2.5 反馈模块 (feedback.py)

#### 2.5.1 创建反馈通知

**接口**: `POST /feedback/`

**发送时机**: 当用户创建意见反馈时

**消息类型**: 个人通知 (`send_personal_notice`)

**消息内容**:
```python
{
    "type": "feedback_created",
    "message": f"创建意见反馈：{feedback_type}",
    "feedback_id": created_feedback.id,
    "feedback_type": feedback_type,
    "feedback_name": feedback_in.name if hasattr(feedback_in, 'name') else None,
    "source": source.value
}
```

**代码位置**: `feedback.py:83-93`

---

### 2.6 签到模块 (check_in.py)

#### 2.6.1 签到成功通知

**接口**: `POST /check-in/`

**发送时机**: 当用户成功签到时

**消息类型**: 个人通知 (`send_personal_notice`)

**消息内容**:
```python
{
    "type": "check_in_success",
    "message": f"签到成功！获得 {points_earned} 积分，连续签到 {continuous_days} 天",
    "check_in_id": check_in_record.id,
    "points_earned": points_earned,
    "continuous_days": continuous_days,
    "check_in_type": check_in_type,
    "check_in_date": today.isoformat(),
}
```

**代码位置**: `check_in.py:79-90`

---

### 2.7 认证模块 (auth.py)

#### 2.7.1 更新个人信息通知

**接口**: `PATCH /account/`

**发送时机**: 当用户更新个人信息时

**消息类型**: 家庭通知 (`send_families_notice_by_account`)

**消息内容**:
```python
{
    "type": "member_info_updated",
    "message": f"{updated_account.nickname or updated_account.phone} 更新了个人信息",
    "account_id": current_account.id,
    "updated_fields": list(update_data.keys()),
    "platform": platform
}
```

**发送范围**: 向该用户下的所有家庭发送通知

**代码位置**: `auth.py:465-475`

---

#### 2.7.2 注销账号通知

**接口**: `DELETE /account/`

**发送时机**: 当用户注销账号时（在删除账号之前发送）

**消息类型**: 家庭通知 (`send_families_notice_by_account`)

**消息内容**:
```python
{
    "type": "account_deleted",
    "message": f"{current_account.nickname or current_account.phone} 已注销账号",
    "account_id": account_id,
    "reason": "account_deletion",
    "platform": platform
}
```

**发送范围**: 向该用户下的所有家庭发送通知

**注意**: 在删除账号之前发送，此时还能查询到所有家庭

**代码位置**: `auth.py:1006-1016`

---

### 2.8 WebSocket 模块 (websocket.py)

**状态**: ⚠️ **已废弃** - 改用 MQTT 实现

**说明**: 该文件中的 WebSocket 功能已废弃，所有消息发送功能已迁移到 MQTT 实现。文件中包含的注释代码展示了之前通过 WebSocket 发送强制退出消息的实现方式。

**历史实现** (已注释):
- 当检测到同一账户的新连接时，向旧连接发送强制退出消息
- 消息格式包含 `method: "family.message"` 和 `type: "force.logout"`

**代码位置**: `websocket.py:66-90` (已注释)

---

## 三、消息类型总结

### 3.1 家庭通知类型 (family_notice)

| 类型 | 触发场景 | 消息字段 |
|------|---------|---------|
| `family_member_added` | 新成员加入家庭 | family_id, family_name |
| `family_member_updated` | 成员昵称更新 | family_id, family_name |
| `family_member_removed` | 成员被移除 | family_id, family_name |
| `family_deleted` | 家庭被删除 | family_id, family_name |
| `device_added_to_family` | 设备添加到家庭 | device_id, device_name, device_sn |
| `device_removed_from_family` | 设备从家庭移除 | device_id, device_name, device_sn |
| `member_info_updated` | 成员信息更新 | account_id, updated_fields, platform |
| `account_deleted` | 账号注销 | account_id, reason, platform |

---

### 3.2 设备通知类型 (device_notice)

| 类型 | 触发场景 | 消息字段 |
|------|---------|---------|
| `message_read` | 设备消息标记为已读 | message_id, device_id, device_name, level |
| `all_messages_read` | 所有设备消息标记为已读 | account_id, device_id, sn |
| `device_name_updated` | 设备名称更新 | device_id, device_name, old_name, device_sn, account_id, family_id |
| `device_unbind` | 设备解绑 | device_id, device_name, device_sn |

---

### 3.3 个人通知类型 (personal_notice)

| 类型 | 触发场景 | 消息字段 |
|------|---------|---------|
| `feedback_created` | 创建反馈 | feedback_id, feedback_type, feedback_name, source |
| `check_in_success` | 签到成功 | check_in_id, points_earned, continuous_days, check_in_type, check_in_date |

---

## 四、消息发送流程

### 4.1 标准发送流程

```
API接口调用
    ↓
执行业务逻辑（数据库操作等）
    ↓
调用消息发送工具函数（send_xxx_notice）
    ↓
工具函数内部调用 mqtt_service.publish_xxx_notice
    ↓
MQTT服务发布消息到对应主题
    ↓
客户端通过MQTT订阅接收消息
```

### 4.2 错误处理

所有消息发送函数都支持 `raise_on_error` 参数：
- 默认值为 `False`，表示发送失败时不会抛出异常，只打印错误日志
- 设置为 `True` 时，发送失败会抛出异常，中断业务流程

**推荐做法**: 
- 对于关键业务操作后的通知，可以使用默认值 `False`，确保通知失败不影响主业务流程
- 对于必须发送成功的通知，设置 `raise_on_error=True`，并在外层进行异常处理

---

## 五、消息数据结构规范

### 5.1 通用字段

所有消息payload必须包含以下字段：
- `type` (str): 消息类型，用于客户端区分不同的业务场景
- `message` (str): 消息内容，用户可见的提示信息

### 5.2 扩展字段

根据不同的消息类型，可以包含以下扩展字段：
- `family_id` / `family_name`: 家庭相关信息
- `device_id` / `device_name` / `device_sn`: 设备相关信息
- `account_id`: 账户相关信息
- `platform`: 平台标识（app/web）
- 其他业务相关字段（如 `points_earned`, `feedback_type` 等）

### 5.3 时间戳

时间戳由 MQTT 服务自动添加，不需要在 payload 中手动指定。

---

## 六、最佳实践

### 6.1 消息发送时机

1. **在数据库操作成功后发送**: 确保业务逻辑执行成功后再发送通知
2. **在关键操作前发送**: 对于删除操作（如删除家庭、注销账号），应在删除前发送，确保所有相关成员都能收到通知
3. **批量操作**: 对于批量操作（如标记所有消息为已读），应遍历所有相关对象并逐一发送通知

### 6.2 消息内容设计

1. **message 字段**: 应包含清晰、友好的用户提示信息，可以直接展示给用户
2. **type 字段**: 应使用统一的命名规范，便于客户端进行消息分类和处理
3. **扩展字段**: 根据业务需要包含足够的上下文信息，方便客户端进行后续操作

### 6.3 错误处理

1. **默认不抛出异常**: 消息发送失败不应影响主业务流程
2. **日志记录**: 所有发送失败的情况都应记录日志，便于排查问题
3. **重试机制**: 可在 MQTT 服务层实现消息发送的重试机制

---

## 七、相关文件清单

### 核心工具文件
- `app/api/utils.py` - 消息发送工具函数

### API接口文件
- `app/api/client/device_messages.py` - 设备消息管理
- `app/api/client/family_members.py` - 家庭成员管理
- `app/api/client/families.py` - 家庭管理
- `app/api/client/devices.py` - 设备管理
- `app/api/client/feedback.py` - 反馈功能
- `app/api/client/check_in.py` - 签到功能
- `app/api/client/auth.py` - 认证相关
- `app/api/client/websocket.py` - WebSocket（已废弃）

### 服务层文件
- `app/services/mqtt_service.py` - MQTT服务实现

---

## 八、注意事项

1. **WebSocket 已废弃**: `websocket.py` 文件中的功能已废弃，所有消息发送都通过 MQTT 实现
2. **平台兼容性**: 所有消息发送功能都支持 App 和 Web 平台，平台信息通过 token.platform 字段自动识别
3. **家庭通知范围**: 家庭通知会发送给家庭的所有成员，个人通知只发送给指定账户
4. **设备通知**: 设备通知通过设备序列号（SN）发送，确保消息能准确到达目标设备
5. **消息持久化**: MQTT 消息的持久化和可靠性由 MQTT 服务层处理，API 层不需要关心

---

## 九、未来扩展建议

1. **消息模板**: 可以引入消息模板机制，统一管理消息格式
2. **消息优先级**: 可以为不同类型的消息设置优先级，确保重要消息优先发送
3. **消息推送历史**: 可以记录消息发送历史，支持消息重发和查询
4. **消息过滤**: 可以为用户提供消息过滤配置，允许用户自定义接收哪些类型的消息
5. **消息统计**: 可以添加消息发送统计功能，监控消息发送的成功率和延迟

---

**文档版本**: v1.0  
**最后更新**: 2024年  
**维护者**: FastIoT 开发团队
