# App端接口文档

## 概述

App端接口位于 `app/api/app/` 目录下，提供移动应用所需的所有API接口。

## 接口列表

### 1. 认证接口 (auth.py)
- `GET /api/v1/app/auth/rsa_public_key` - 获取RSA公钥
- `POST /api/v1/app/auth/register` - 用户注册（注册成功后自动登录）
- `POST /api/v1/app/auth/login` - 用户登录
- `POST /api/v1/app/auth/logout` - 用户登出
- `GET /api/v1/app/auth/profile` - 获取当前用户信息
- `GET /api/v1/app/auth/current-family` - 获取当前家庭信息
- `DELETE /api/v1/app/auth/account` - 删除当前账户

### 2. 设备管理接口 (devices.py)
- `GET /api/v1/app/devices/` - 获取设备列表（支持分页和状态筛选）
- `POST /api/v1/app/devices/bind-by-sn/` - 通过序列号绑定设备
- `DELETE /api/v1/app/devices/unbind-by-sn/{sn}` - 通过序列号解绑设备
- `PATCH /api/v1/app/devices/{id}/name` - 修改设备名称

### 3. 家庭管理接口 (families.py)
- `GET /api/v1/app/families/` - 获取家庭列表
- `POST /api/v1/app/families/` - 创建家庭
- `DELETE /api/v1/app/families/{id}` - 删除家庭（仅创建者）
- `POST /api/v1/app/families/{family_id}/devices/{device_id}` - 添加设备到家庭
- `DELETE /api/v1/app/families/{family_id}/devices/{device_id}` - 从家庭移除设备

### 4. 家庭成员接口 (family_members.py)
- `GET /api/v1/app/family-members/family/{family_id}` - 获取家庭成员列表
- `POST /api/v1/app/family-members/join-by-invite-code` - 通过邀请码加入家庭
- `PATCH /api/v1/app/family-members/{id}` - 更新成员信息
- `DELETE /api/v1/app/family-members/{id}` - 移除家庭成员

### 5. 设备消息接口 (device_messages.py)
- `GET /api/v1/app/device-messages/` - 获取设备消息列表（支持分页和筛选）
- `PATCH /api/v1/app/device-messages/{id}/make-read` - 标记消息为已读
- `PATCH /api/v1/app/device-messages/mark-all-read` - 标记所有消息为已读
- `GET /api/v1/app/device-messages/unread-count` - 获取未读消息数量

### 6. 系统消息接口 (system_message.py)
- `GET /api/v1/app/system-messages/` - 获取系统消息列表（支持分页和筛选）

### 7. 签到积分接口 (check_in.py)
- `POST /api/v1/app/check-in/` - 用户签到
- `GET /api/v1/app/check-in/calendar` - 获取签到日历
- `GET /api/v1/app/check-in/stats` - 获取签到统计
- `GET /api/v1/app/check-in/history` - 获取签到历史

### 8. 积分接口 (points.py)
- `GET /api/v1/app/points/balance` - 获取积分余额
- `GET /api/v1/app/points/history` - 获取积分历史

### 9. 反馈接口 (feedback.py)
- `POST /api/v1/app/feedback/` - 提交用户反馈

### 10. 版本信息接口 (version_info.py)
- `GET /api/v1/app/version-info/` - 获取最新版本信息（无需认证）

## 特点

1. **平台标识**: 所有app端接口在生成token时会标记 `platform: "app"`，便于区分不同平台的请求

2. **认证机制**: 
   - 使用RSA加密传输密码
   - 基于JWT的Token认证
   - 除了注册、登录和版本信息接口外，其他接口都需要Token认证

3. **注册即登录**: 注册接口直接返回Token和用户信息，无需再次登录

4. **操作日志**: 所有重要操作都会记录操作日志，便于追踪和审计

5. **MQTT通知**: 家庭相关的操作会通过MQTT实时推送通知给家庭成员

## 与Web端的区别

1. **注册流程**: App端注册成功后直接返回Token和用户信息，而Web端只返回用户信息
2. **平台标识**: Token中的platform字段为"app"
3. **操作日志**: 日志中会标记platform为"app"，便于区分不同平台的操作
4. **版本检查**: App端有专门的版本信息接口，用于检查更新

## 响应格式

### 成功响应 (HTTP 200/201)
直接返回数据对象或数组

### 错误响应 (HTTP 4xx/5xx)
```json
{
  "message": "错误信息描述"
}
```

## HTTP状态码说明
- `200 OK`: 请求成功
- `201 Created`: 创建成功
- `400 Bad Request`: 请求参数错误
- `401 Unauthorized`: 未授权，Token无效或过期
- `403 Forbidden`: 无权限访问
- `404 Not Found`: 资源不存在
- `409 Conflict`: 资源冲突（如重复创建）
- `500 Internal Server Error`: 服务器内部错误

