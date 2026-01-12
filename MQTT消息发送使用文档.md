# MQTT 消息发送使用文档

本文档详细记录了 `client` 和 `admin` 目录中所有使用 MQTT 发送消息的地方。

## 目录

1. [工具函数概览](#工具函数概览)
2. [MQTT Topic 结构](#mqtt-topic-结构)
3. [Client API 使用场景](#client-api-使用场景)
4. [Admin API 使用场景](#admin-api-使用场景)
5. [消息类型与Payload结构](#消息类型与payload结构)

---

## 工具函数概览

所有 MQTT 消息发送都通过 `app/api/utils.py` 中的工具函数实现，这些函数封装了对 `mqtt_service` 的调用。

### 1. `send_personal_notice(account_id, payload)`

**功能**：向指定用户发送个人通知消息

**MQTT Topic**：`client/{account_id}/notice`

**底层调用**：`mqtt_service.publish_client_notice(account_id, payload)`

**使用场景**：
- 用户签到成功通知
- 反馈创建/回复通知
- 积分调整通知

---

### 2. `send_device_notice(device_sn, payload)`

**功能**：发送设备相关通知消息

**MQTT Topic**：`device/{sn}/notice`

**底层调用**：`mqtt_service.publish_device_notice(device_sn, payload)`

**使用场景**：
- 设备名称更新通知
- 设备解绑通知
- 设备消息状态变更通知

---

### 3. `send_system_notice(payload)`

**功能**：发送系统级别的通知消息（广播给所有客户端）

**MQTT Topic**：`system/notice`

**底层调用**：`mqtt_service.publish_system_notice(payload)`

**使用场景**：
- 系统消息创建通知
- 系统维护通知
- 系统公告通知

---

### 4. `send_family_notice(family_id, payload)`

**功能**：向指定家庭发送通知消息

**MQTT Topic**：`home/{home_id}/notice`

**底层调用**：`mqtt_service.publish_home_notice(str(family_id), payload)`

**使用场景**：
- 家庭成员变更通知
- 家庭设备变更通知
- 家庭相关事件通知

**注意**：当前代码中，该函数在 client/admin API 中暂未使用，但已实现。

---

### 5. `send_families_notice_by_account(db, account_id, payload)`

**功能**：向指定账户下的所有家庭发送通知消息

**底层实现**：遍历账户的所有家庭，调用 `send_family_notice` 发送

**使用场景**：
- 需要向用户的所有家庭发送通知的场景

**注意**：当前代码中，该函数在 client/admin API 中暂未使用，但已实现。

---

## MQTT Topic 结构

系统使用以下 Topic 结构：

| Topic 类型 | Topic 格式 | 说明 |
|-----------|-----------|------|
| 个人通知 | `client/{account_id}/notice` | 后台 → 客户端（个人通知） |
| 设备通知 | `device/{sn}/notice` | 后台 → 客户端（设备消息） |
| 系统通知 | `system/notice` | 后台 → 客户端（系统消息） |
| 家庭通知 | `home/{home_id}/notice` | 后台 → 客户端（家庭消息） |

---

## Client API 使用场景

### 1. 用户反馈模块 (`app/api/client/feedback.py`)

#### 接口：`POST /feedback/`

**功能**：创建意见反馈

**MQTT 调用**：
```python
await send_personal_notice(
    account_id=account_id,
    payload={
        "type": "feedback_created",
        "message": f"创建意见反馈：{feedback_type}",
        "feedback_id": created_feedback.id,
        "feedback_type": feedback_type,
        "feedback_name": feedback_in.name if hasattr(feedback_in, 'name') else None,
        "source": source.value
    }
)
```

**消息类型**：`feedback_created`

**Topic**：`client/{account_id}/notice`

---

### 2. 签到功能模块 (`app/api/client/check_in.py`)

#### 接口：`POST /check_in/`

**功能**：用户签到

**MQTT 调用**：
```python
await send_personal_notice(
    account_id=account_id,
    payload={
        "type": "check_in_success",
        "message": f"签到成功！获得 {points_earned} 积分，连续签到 {continuous_days} 天",
        "check_in_id": check_in_record.id,
        "points_earned": points_earned,
        "continuous_days": continuous_days,
        "check_in_type": check_in_type,
        "check_in_date": today.isoformat(),
    }
)
```

**消息类型**：`check_in_success`

**Topic**：`client/{account_id}/notice`

**Payload 字段说明**：
- `check_in_id`：签到记录ID
- `points_earned`：获得的积分
- `continuous_days`：连续签到天数
- `check_in_type`：签到类型（normal/bonus）
- `check_in_date`：签到日期

---

### 3. 设备消息管理模块 (`app/api/client/device_messages.py`)

#### 接口：`PATCH /device-messages/{message_id}/make-read`

**功能**：标记设备消息为已读状态

**MQTT 调用**：
```python
await send_device_notice(
    device_sn=device.sn,
    payload={
        "type": "message_read",
        "message": "设备消息已标记为已读",
        "message_id": message_id,
        "device_id": updated.device_id,
        "device_name": device.name,
        "level": updated.level.value if updated.level else None,
    }
)
```

**消息类型**：`message_read`

**Topic**：`device/{sn}/notice`

---

#### 接口：`PATCH /device-messages/mark-all-read`

**功能**：标记所有设备消息为已读

**MQTT 调用**：
```python
# 遍历用户的所有设备，为每个设备发送通知
await send_device_notice(
    device_sn=device.sn,
    payload={
        "type": "all_messages_read",
        "message": f"设备{device.name}的所有消息已标记为已读",
        "account_id": account_id,
        "device_id": device.id,
        "sn": device.sn,
    }
)
```

**消息类型**：`all_messages_read`

**Topic**：`device/{sn}/notice`

**说明**：此接口会遍历用户的所有设备（可指定家庭），为每个设备发送一条通知。

---

### 4. 设备管理模块 (`app/api/client/devices.py`)

#### 接口：`PATCH /devices/{device_id}/name`

**功能**：修改设备名称

**MQTT 调用**：
```python
await send_device_notice(
    device_sn=updated.sn,
    payload={
        "type": "device_name_updated",
        "message": f"设备名称已更新：{old_name} -> {payload.name}",
        "device_id": updated.id,
        "device_name": payload.name,
        "old_name": old_name,
        "device_sn": updated.sn,
        "account_id": account_id,
        "family_id": family_id,
    }
)
```

**消息类型**：`device_name_updated`

**Topic**：`device/{sn}/notice`

---

#### 接口：`DELETE /devices/unbind-by-sn/{sn}`

**功能**：解绑设备

**MQTT 调用**：
```python
await send_device_notice(
    device_sn=sn,
    payload={
        "type": "device_unbind",
        "message": f"设备已解绑：{device_name}（SN: {sn}）",
        "device_id": device.id,
        "device_name": device_name,
        "device_sn": sn,
    }
)
```

**消息类型**：`device_unbind`

**Topic**：`device/{sn}/notice`

---

## Admin API 使用场景

### 1. 系统消息管理模块 (`app/api/admin/notice.py`)

#### 接口：`POST /admin/notice`

**功能**：创建系统消息

**MQTT 调用**：
```python
await send_system_notice(
    payload={
        "type": message_type,
        "message": message_content,
        "id": message_id,
        "title": message_title,
        "priority": message_priority,
        "platforms": message_platforms,
        "extra": message_extra
    }
)
```

**消息类型**：系统消息类型（如 notification、announcement、alert、maintenance、update）

**Topic**：`system/notice`

**说明**：
- 这是系统级别的广播消息，所有订阅了 `system/notice` 的客户端都会收到
- Payload 中的 `type` 字段出现了两次（代码中有重复，建议修复）
- `platforms` 字段用于指定目标平台（app/web）

---

### 2. 积分管理模块 (`app/api/admin/points.py`)

#### 接口：`POST /admin/points/{accountId}/adjust`

**功能**：积分奖励/扣除（管理员调整用户积分）

**MQTT 调用**：
```python
await send_personal_notice(
    account_id=accountId,
    payload={
        "type": "points_adjusted",
        "message": f"{'奖励' if points > 0 else '扣除'}用户 {account.nickname or account.phone} {abs(points)} 积分",
        "points": points,
        "old_balance": int(current_balance),
        "new_balance": int(new_balance),
        "type": points_type,
        "description": description
    }
)
```

**消息类型**：`points_adjusted`

**Topic**：`client/{account_id}/notice`

**Payload 字段说明**：
- `points`：积分变动数量（正数为奖励，负数为扣除）
- `old_balance`：调整前的积分余额
- `new_balance`：调整后的积分余额
- `type`：积分类型（check_in/task/reward/exchange/penalty/admin_adjust）
- `description`：操作描述

**注意**：Payload 中的 `type` 字段出现了两次（代码中有重复，建议修复）

---

### 3. 反馈管理模块 (`app/api/admin/feedback.py`)

#### 接口：`PUT /admin/feedback/{id}/reply`

**功能**：回复用户反馈

**MQTT 调用**：
```python
await send_personal_notice(
    account_id=updated_fb.account_id,
    payload={
        "type": "feedback_replied",
        "message": f"回复反馈：{updated_fb.name} - {old_status} -> {updated_fb.status}",
        "feedback_id": updated_fb.id,
        "feedback_name": updated_fb.name,
    }
)
```

**消息类型**：`feedback_replied`

**Topic**：`client/{account_id}/notice`

**说明**：当管理员回复用户的反馈时，向反馈创建者发送通知。

---

## 消息类型与Payload结构

### 个人通知消息类型 (`client/{account_id}/notice`)

| 消息类型 | 来源接口 | Payload 关键字段 |
|---------|---------|-----------------|
| `feedback_created` | `POST /feedback/` | feedback_id, feedback_type, feedback_name, source |
| `check_in_success` | `POST /check_in/` | check_in_id, points_earned, continuous_days, check_in_type, check_in_date |
| `points_adjusted` | `POST /admin/points/{accountId}/adjust` | points, old_balance, new_balance, type, description |
| `feedback_replied` | `PUT /admin/feedback/{id}/reply` | feedback_id, feedback_name |

---

### 设备通知消息类型 (`device/{sn}/notice`)

| 消息类型 | 来源接口 | Payload 关键字段 |
|---------|---------|-----------------|
| `message_read` | `PATCH /device-messages/{message_id}/make-read` | message_id, device_id, device_name, level |
| `all_messages_read` | `PATCH /device-messages/mark-all-read` | account_id, device_id, sn |
| `device_name_updated` | `PATCH /devices/{device_id}/name` | device_id, device_name, old_name, device_sn, account_id, family_id |
| `device_unbind` | `DELETE /devices/unbind-by-sn/{sn}` | device_id, device_name, device_sn |

---

### 系统通知消息类型 (`system/notice`)

| 消息类型 | 来源接口 | Payload 关键字段 |
|---------|---------|-----------------|
| 系统消息类型（动态） | `POST /admin/notice` | id, title, type, message, priority, platforms, extra |

**系统消息类型包括**：
- `notification`：普通通知
- `announcement`：公告
- `alert`：警报
- `maintenance`：维护通知
- `update`：更新通知

---

## 代码质量问题

在代码审查过程中，发现以下问题：

### 1. Payload 中重复的 `type` 字段

**位置1**：`app/api/admin/notice.py` 第 121-131 行
```python
payload={
    "type": message_type,  # 第一次
    "message": message_content,
    "id": message_id,
    "title": message_title,
    "type": message_type,  # 第二次（重复）
    "priority": message_priority,
    ...
}
```

**位置2**：`app/api/admin/points.py` 第 229-239 行
```python
payload={
    "type": "points_adjusted",  # 第一次
    "message": ...,
    "points": points,
    ...
    "type": points_type,  # 第二次（重复，且值不同）
    "description": description
}
```

**建议**：
- 第一个 `type` 应该保留，表示消息类型
- 第二个 `type` 应该重命名为更具体的字段名，如 `points_type`、`message_category` 等

---

## 实现细节

### 错误处理

所有工具函数都包含异常处理：

```python
try:
    from app.services.mqtt_service import mqtt_service
    await mqtt_service.publish_xxx(...)
except Exception as e:
    print(f"发送xxx通知失败: {e}")
    if raise_on_error:
        raise
```

- 默认情况下，发送失败不会中断业务流程（`raise_on_error=False`）
- 错误信息会打印到控制台
- 可以通过 `raise_on_error=True` 参数控制是否抛出异常

---

### 连接状态检查

MQTT 服务在发送消息前会检查连接状态：

```python
if not self.client or not self.running:
    print("❌ [MQTT] 客户端未连接，无法发送消息")
    return
```

如果 MQTT 客户端未连接或未运行，消息发送会被跳过，但不会抛出异常。

---

## 总结

- **个人通知**：4 个使用场景（Client: 2个，Admin: 2个）
- **设备通知**：4 个使用场景（全部在 Client API）
- **系统通知**：1 个使用场景（Admin API）
- **家庭通知**：0 个使用场景（已实现但未使用）

所有 MQTT 消息发送都通过统一的工具函数封装，便于维护和扩展。建议修复代码中发现的 Payload 字段重复问题。
