-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS `iot` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE `iot`;

-- 账号表：所有能登录的用户
CREATE TABLE IF NOT EXISTS `account` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '账号ID',
    `password` VARCHAR(128) NULL COMMENT '密码',
    `nickname` VARCHAR(64) NULL COMMENT '昵称/显示名',
    `unionid` VARCHAR(128) UNIQUE NULL COMMENT '微信UnionID',
    `gender` ENUM('male','female','other') DEFAULT 'other' COMMENT '性别',
    `phone` VARCHAR(32) NOT NULL UNIQUE COMMENT '手机号',
    `email` VARCHAR(128) UNIQUE COMMENT '邮箱',
    `avatar` VARCHAR(255) NULL COMMENT '头像URL',
    `role` ENUM('user','admin') NOT NULL DEFAULT 'user' COMMENT '角色: 普通用户/管理员',
    `current_family_id` BIGINT NULL COMMENT '当前使用的家庭ID，个人使用则为NULL',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (`current_family_id`) REFERENCES `family`(`id`) ON DELETE SET NULL,
    INDEX `idx_unionid` (`unionid`),
    INDEX `idx_account_current_family` (`current_family_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='账号表';

-- 家庭表：家庭/组织容器
CREATE TABLE IF NOT EXISTS `family` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '家庭ID',
    `name` VARCHAR(100) NOT NULL COMMENT '家庭名称',
    `avatar` VARCHAR(255) NULL COMMENT '家庭头像',
    `description` VARCHAR(500) NULL COMMENT '家庭描述',
    `invite_code` VARCHAR(32) UNIQUE NULL COMMENT '家庭邀请码',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX `idx_family_invite_code` (`invite_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='家庭表';

-- 家庭成员关联表：账号与家庭的多对多关系
CREATE TABLE IF NOT EXISTS `family_member` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '关联ID',
    `family_id` BIGINT NOT NULL COMMENT '家庭ID',
    `account_id` BIGINT NOT NULL COMMENT '账号ID',
    `role` ENUM('creator','member') NOT NULL DEFAULT 'member' COMMENT '在家庭中的角色：创建者/成员',
    `nickname` VARCHAR(64) NULL COMMENT '在家庭中的昵称（可选，覆盖账号默认昵称）',
    `joined_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '加入时间',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (`family_id`) REFERENCES `family`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`account_id`) REFERENCES `account`(`id`) ON DELETE CASCADE,
    UNIQUE KEY `uq_family_account` (`family_id`, `account_id`) COMMENT '同一账号在同一家庭中只能有一条记录',
    INDEX `idx_family_member_family` (`family_id`),
    INDEX `idx_family_member_account` (`account_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='家庭成员关联表';

-- 物模型表：定义设备功能能力（属性/服务/事件）
CREATE TABLE IF NOT EXISTS `device_thing_model` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '物模型ID',
    `name` VARCHAR(100) NOT NULL COMMENT '物模型名称',
    `description` VARCHAR(500) COMMENT '物模型描述',
    `properties` JSON NOT NULL COMMENT '属性定义JSON',
    `services` JSON NOT NULL COMMENT '服务定义JSON',
    `events` JSON NOT NULL COMMENT '事件定义JSON',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='物模型表';

-- 设备型号表：具体型号，关联物模型
CREATE TABLE IF NOT EXISTS `device_model` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '设备型号ID',
    `model_code` VARCHAR(50) NOT NULL UNIQUE COMMENT '型号代码',
    `name` VARCHAR(100) NOT NULL COMMENT '型号名称',
    `vendor` VARCHAR(100) COMMENT '厂商',
    `thing_model_id` BIGINT NOT NULL COMMENT '物模型ID',
    `properties` JSON NOT NULL COMMENT '属性定义JSON（扩展自物模型）',
    `services` JSON NOT NULL COMMENT '服务定义JSON（扩展自物模型）',
    `events` JSON NOT NULL COMMENT '事件定义JSON（扩展自物模型）',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (`thing_model_id`) REFERENCES `device_thing_model`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='设备型号表';

-- 设备表：具体的物联网设备实例
CREATE TABLE IF NOT EXISTS `device` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '设备ID',
    `account_id` BIGINT NULL COMMENT '所属账号ID（个人设备）',
    `model_id` BIGINT NOT NULL COMMENT '设备型号ID',
    `name` VARCHAR(100) NOT NULL COMMENT '设备名称',
    `sn` VARCHAR(100) UNIQUE NOT NULL COMMENT '设备序列号',
    `status` ENUM('unconfigured','configured','unbound','bound','offline','online','fault') DEFAULT 'unconfigured' COMMENT '设备状态',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (`account_id`) REFERENCES `account`(`id`) ON DELETE SET NULL,
    FOREIGN KEY (`model_id`) REFERENCES `device_model`(`id`),
    INDEX `idx_device_account` (`account_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='设备表';

-- 家庭设备关联表：设备与家庭的多对多关系（一个设备可以属于多个家庭）
CREATE TABLE IF NOT EXISTS `family_device` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '关联ID',
    `family_id` BIGINT NOT NULL COMMENT '家庭ID',
    `device_id` BIGINT NOT NULL COMMENT '设备ID',
    `added_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '添加到家庭的时间',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (`family_id`) REFERENCES `family`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`device_id`) REFERENCES `device`(`id`) ON DELETE CASCADE,
    UNIQUE KEY `uq_family_device` (`family_id`, `device_id`) COMMENT '同一设备在同一家庭中只能有一条记录',
    INDEX `idx_family_device_family` (`family_id`),
    INDEX `idx_family_device_device` (`device_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='家庭设备关联表';


-- 设备消息表：记录设备产生的消息信息
CREATE TABLE IF NOT EXISTS `device_message` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '消息ID',
    `device_id` BIGINT NOT NULL COMMENT '设备ID',
    `level` ENUM('low','normal','error','fatal') NOT NULL DEFAULT 'low' COMMENT '消息级别',
    `status` ENUM('new','read') DEFAULT 'new' COMMENT '消息状态',
    `message` VARCHAR(255) COMMENT '消息内容',
    `detail` JSON NULL COMMENT '消息详细参数',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NULL COMMENT '更新时间',
    FOREIGN KEY (`device_id`) REFERENCES `device`(`id`) ON DELETE CASCADE,
    INDEX `idx_device_message_created_at` (`created_at`),
    INDEX `idx_device_message_updated_at` (`updated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='设备消息表';

-- 设备网络信息表：存储设备的实时网络状态
CREATE TABLE IF NOT EXISTS `device_network` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '自增主键',
    `device_id` BIGINT NOT NULL COMMENT '关联设备表 device 的 ID，标识具体设备实例',
    `net_type` VARCHAR(20) NOT NULL COMMENT '网络类型：wifi/ble/cellular/zigbee 等',
    `name` VARCHAR(128) NULL COMMENT '网络名称：蓝牙信息：存蓝牙广播名称（如 "Xiaomi Light 01"）；Wi-Fi 信息：存 Wi-Fi SSID',
    `ip` VARCHAR(64) NULL COMMENT '设备 IP 地址，仅 Wi-Fi 或蜂窝网络使用',
    `mac` VARCHAR(64) NULL COMMENT '设备网络接口 MAC 地址：蓝牙：蓝牙唯一标识；Wi-Fi：设备 Wi-Fi 网卡 MAC',
    `rssi` INT NULL COMMENT '信号强度：蓝牙：接收信号强度；Wi-Fi：RSSI',
    `connect_state` TINYINT DEFAULT 0 COMMENT '连接状态：0=断开, 1=连接中, 2=已连接',
    `extra` JSON NULL COMMENT '扩展字段，用于存储其他网络相关信息：蓝牙：配网模式、固件版本等；Wi-Fi：网关信息、是否 2.4G/5G 等',
    `last_update` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录最后一次更新时间',
    FOREIGN KEY (`device_id`) REFERENCES `device`(`id`) ON DELETE CASCADE,
    UNIQUE KEY `uq_device_network_device` (`device_id`) COMMENT '保证每个设备仅有一条网络记录'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='设备网络信息表，存储设备的实时网络状态，可支持 Wi-Fi / 蓝牙 / 蜂窝 / Zigbee 等类型';

-- 签到表：记录用户的签到记录
CREATE TABLE IF NOT EXISTS `check_in` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '签到记录ID',
    `account_id` BIGINT NOT NULL COMMENT '签到用户账号ID',
    `check_in_date` DATE NOT NULL COMMENT '签到日期',
    `check_in_time` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '签到时间',
    `points_earned` INT DEFAULT 0 COMMENT '本次签到获得积分',
    `continuous_days` INT DEFAULT 1 COMMENT '连续签到天数',
    `check_in_type` ENUM('normal','bonus','makeup') DEFAULT 'normal' COMMENT '签到类型：正常/奖励/补签',
    `extra` JSON NULL COMMENT '扩展信息',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (`account_id`) REFERENCES `account`(`id`) ON DELETE CASCADE,
    UNIQUE KEY `uq_check_in_account_date` (`account_id`, `check_in_date`) COMMENT '每个用户每天只能签到一次',
    INDEX `idx_check_in_date` (`check_in_date`),
    INDEX `idx_check_in_account` (`account_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户签到记录表';

-- 积分表：记录用户的积分变动历史
CREATE TABLE IF NOT EXISTS `points` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '积分记录ID',
    `account_id` BIGINT NOT NULL COMMENT '用户账号ID',
    `points` INT NOT NULL COMMENT '积分变动数量（正数为增加，负数为减少）',
    `balance` INT NOT NULL COMMENT '变动后积分余额',
    `type` ENUM('check_in','task','reward','exchange','penalty','admin_adjust') NOT NULL COMMENT '积分类型：签到/任务/奖励/兑换/惩罚/管理员调整',
    `description` VARCHAR(255) NULL COMMENT '积分变动描述',
    `extra` JSON NULL COMMENT '扩展信息',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (`account_id`) REFERENCES `account`(`id`) ON DELETE CASCADE,
    INDEX `idx_points_account` (`account_id`),
    INDEX `idx_points_type` (`type`),
    INDEX `idx_points_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户积分变动记录表';

-- 系统消息表：记录系统发送的消息
CREATE TABLE IF NOT EXISTS `system_message` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '消息ID',
    `title` VARCHAR(255) NOT NULL COMMENT '消息标题',
    `content` TEXT NOT NULL COMMENT '消息内容',
    `type` ENUM('notification','announcement','alert','maintenance','update') NOT NULL DEFAULT 'notification' COMMENT '消息类型：通知/公告/警告/维护/更新',
    `priority` ENUM('low','normal','high','urgent') NOT NULL DEFAULT 'normal' COMMENT '优先级：低/普通/高/紧急',
    `platforms` JSON NOT NULL COMMENT '目标平台：android/ios/web等，可多选',
    `extra` JSON NULL COMMENT '扩展信息',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX `idx_system_message_type` (`type`),
    INDEX `idx_system_message_priority` (`priority`),
    INDEX `idx_system_message_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统消息表';

-- 版本信息表：记录系统版本更新信息
CREATE TABLE IF NOT EXISTS `version_info` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '版本ID',
    `version_code` VARCHAR(20) NOT NULL COMMENT '版本号（如：1.0.0）',
    `version_name` VARCHAR(50) NOT NULL COMMENT '版本名称（如：FastIoT v1.0.0）',
    `platform` ENUM('web','app') NOT NULL DEFAULT 'web' COMMENT '目标平台：web或app',
    `title` VARCHAR(255) NOT NULL COMMENT '版本标题',
    `description` TEXT NOT NULL COMMENT '版本描述',
    `download_url` VARCHAR(500) NULL COMMENT '下载链接',
    `file_size` BIGINT NULL COMMENT '文件大小（字节）',
    `is_force_update` BOOLEAN DEFAULT FALSE COMMENT '是否强制更新',
    `min_supported_version` VARCHAR(20) NULL COMMENT '最低支持版本',
    `extra` JSON NULL COMMENT '扩展信息',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX `idx_version_info_platform` (`platform`),
    INDEX `idx_version_info_created_at` (`created_at`),
    UNIQUE KEY `uq_version_code_platform` (`version_code`, `platform`) COMMENT '同一平台版本号唯一'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='版本信息表';

-- 意见反馈表：记录用户反馈和建议
CREATE TABLE IF NOT EXISTS `feedback` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '反馈ID',
    `account_id` BIGINT NOT NULL COMMENT '反馈用户账号ID',
    `name` VARCHAR(100) NULL COMMENT '反馈人姓名（可选）',
    `type` ENUM('bug','feature','improvement','complaint','praise','other') NOT NULL DEFAULT 'other' COMMENT '反馈类型：bug/功能建议/改进建议/投诉/表扬/其他',
    `content` TEXT NOT NULL COMMENT '反馈内容',
    `status` ENUM('pending','processing','resolved','rejected','closed') NOT NULL DEFAULT 'pending' COMMENT '处理状态：待处理/处理中/已解决/已拒绝/已关闭',
    `source` ENUM('web','app') NOT NULL DEFAULT 'web' COMMENT '来源：web或app',
    `contact_info` VARCHAR(255) NULL COMMENT '联系方式',
    `replay` TEXT NULL COMMENT '回复内容',
    `processed_at` TIMESTAMP NULL COMMENT '处理时间',
    `extra` JSON NULL COMMENT '扩展信息',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (`account_id`) REFERENCES `account`(`id`) ON DELETE CASCADE,
    INDEX `idx_feedback_account` (`account_id`),
    INDEX `idx_feedback_type` (`type`),
    INDEX `idx_feedback_status` (`status`),
    INDEX `idx_feedback_source` (`source`),
    INDEX `idx_feedback_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='意见反馈表';

-- 插入默认账号（密码: admin123）
INSERT INTO `account` (`password`, `nickname`, `email`, `role`, `phone`) 
VALUES ('admin123', '管理员', 'admin@fastiot.com', 'admin', '13800000000')
ON DUPLICATE KEY UPDATE `nickname` = VALUES(`nickname`);

-- 数据迁移：将 account.role 中的 'owner' 和 'member' 改为 'user'
UPDATE `account` SET `role` = 'user' WHERE `role` IN ('owner', 'member');

-- 插入示例物模型
INSERT INTO `device_thing_model` (`name`, `description`, `properties`, `services`, `events`) 
VALUES 
('温度传感器物模型', '基础温度传感器功能定义', 
 '{"temperature": {"type": "float", "unit": "°C", "min": -40, "max": 85}}',
 '["read_temperature", "calibrate"]',
 '["temperature_alert", "sensor_fault"]'),
('湿度传感器物模型', '基础湿度传感器功能定义',
 '{"humidity": {"type": "float", "unit": "%", "min": 0, "max": 100}}',
 '["read_humidity", "calibrate"]',
 '["humidity_alert", "sensor_fault"]'),
('环境监测器物模型', '多功能环境监测设备功能定义',
 '{"temperature": {"type": "float", "unit": "°C"}, "humidity": {"type": "float", "unit": "%"}, "pressure": {"type": "float", "unit": "hPa"}}',
 '["read_all", "calibrate", "reset"]',
 '["environment_alert", "sensor_fault", "data_anomaly"]'),
('室内空气质量监测器物模型', '室内空气质量综合监测设备功能定义',
 '{"co2": {"type": "float", "unit": "ppm", "min": 0, "max": 5000}, "hcho": {"type": "float", "unit": "μg/m³", "min": 0, "max": 1000}, "tvoc": {"type": "float", "unit": "μg/m³", "min": 0, "max": 10000}, "pm25": {"type": "float", "unit": "μg/m³", "min": 0, "max": 1000}, "pm10": {"type": "float", "unit": "μg/m³", "min": 0, "max": 1000}, "temp": {"type": "float", "unit": "°C", "min": -40, "max": 85}, "humi": {"type": "float", "unit": "%", "min": 0, "max": 100}}',
 '["read_all", "calibrate", "reset", "set_alarm_threshold", "export_data"]',
 '["air_quality_alert", "sensor_fault", "data_anomaly", "calibration_complete", "low_battery", "data_exported"]')
ON DUPLICATE KEY UPDATE `name` = VALUES(`name`);

-- 插入示例设备型号
INSERT INTO `device_model` (`model_code`, `name`, `vendor`, `thing_model_id`, `properties`, `services`, `events`) 
VALUES 
('TEMP001', '温度传感器', 'IoT Corp', 1, 
 '{"temperature": {"type": "float", "unit": "°C", "min": -40, "max": 85, "precision": 1, "default": 20, "readable": true, "writable": false}}',
 '["read_temperature", "calibrate", "set_precision", "reset_calibration"]',
 '["temperature_alert", "sensor_fault", "calibration_complete", "low_battery"]'),
('HUM001', '湿度传感器', 'IoT Corp', 2, 
 '{"humidity": {"type": "float", "unit": "%", "min": 0, "max": 100, "precision": 1, "default": 50, "readable": true, "writable": false}}',
 '["read_humidity", "calibrate", "set_precision", "reset_calibration"]',
 '["humidity_alert", "sensor_fault", "calibration_complete", "low_battery"]'),
('ENV001', '环境监测器', 'Smart Devices', 3, 
 '{"temperature": {"type": "float", "unit": "°C", "min": -40, "max": 85, "precision": 1, "readable": true, "writable": false}, "humidity": {"type": "float", "unit": "%", "min": 0, "max": 100, "precision": 1, "readable": true, "writable": false}, "pressure": {"type": "float", "unit": "hPa", "min": 800, "max": 1200, "precision": 1, "readable": true, "writable": false}}',
 '["read_all", "calibrate", "reset", "set_sampling_rate", "export_data"]',
 '["environment_alert", "sensor_fault", "data_anomaly", "calibration_complete", "low_battery", "data_exported"]'),
('M701001', '室内空气质量监测器', 'Smart Devices', 4, 
 '{"co2": {"type": "float", "unit": "ppm", "min": 0, "max": 5000, "precision": 0, "readable": true, "writable": false}, "hcho": {"type": "float", "unit": "μg/m³", "min": 0, "max": 1000, "precision": 1, "readable": true, "writable": false}, "tvoc": {"type": "float", "unit": "μg/m³", "min": 0, "max": 10000, "precision": 1, "readable": true, "writable": false}, "pm25": {"type": "float", "unit": "μg/m³", "min": 0, "max": 1000, "precision": 1, "readable": true, "writable": false}, "pm10": {"type": "float", "unit": "μg/m³", "min": 0, "max": 1000, "precision": 1, "readable": true, "writable": false}, "temp": {"type": "float", "unit": "°C", "min": -40, "max": 85, "precision": 1, "readable": true, "writable": false}, "humi": {"type": "float", "unit": "%", "min": 0, "max": 100, "precision": 1, "readable": true, "writable": false}}',
 '["read_all", "calibrate", "reset", "set_alarm_threshold", "export_data", "set_sampling_rate"]',
 '["air_quality_alert", "sensor_fault", "data_anomaly", "calibration_complete", "low_battery", "data_exported", "threshold_exceeded"]')
ON DUPLICATE KEY UPDATE `name` = VALUES(`name`);

-- 注意：示例设备插入已移除，因为需要 account_id 或 family_id
-- 实际使用时，设备应该通过 account_id 或 family_id 绑定

-- 用户操作记录表：记录用户的重要操作行为
CREATE TABLE IF NOT EXISTS `user_operation_log` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '操作记录ID',
    `account_id` BIGINT NOT NULL COMMENT '操作用户账号ID',
    `operation_type` ENUM('login','logout','register','account_delete','account_update','device_bind','device_unbind','device_name_update','device_add_to_family','device_remove_from_family','family_create','family_delete','family_member_add','family_member_remove','family_member_update','permission_update','quick_control','feedback_create') NOT NULL COMMENT '操作类型',
    `description` VARCHAR(500) NOT NULL COMMENT '操作描述',
    `extra` JSON NULL COMMENT '扩展信息（如快捷控制的具体操作、设备排序详情等）',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
    FOREIGN KEY (`account_id`) REFERENCES `account`(`id`) ON DELETE CASCADE,
    INDEX `idx_user_operation_account` (`account_id`),
    INDEX `idx_user_operation_type` (`operation_type`),
    INDEX `idx_user_operation_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户操作记录表';
