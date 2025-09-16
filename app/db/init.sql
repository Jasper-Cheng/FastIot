-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS `iot` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE `iot`;

-- 账号表：所有能登录的用户（包含主账号和子账号）
CREATE TABLE IF NOT EXISTS `account` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '账号ID',
    `account` VARCHAR(64) NOT NULL UNIQUE COMMENT '登录名',
    `password_hash` VARCHAR(128) NOT NULL COMMENT '密码哈希',
    `name` VARCHAR(64) NULL COMMENT '昵称/显示名',
    `gender` ENUM('male','female','other') DEFAULT 'other' COMMENT '性别',
    `phone` VARCHAR(32) NOT NULL UNIQUE COMMENT '手机号',
    `email` VARCHAR(128) UNIQUE COMMENT '邮箱',
    `avatar` VARCHAR(255) NULL COMMENT '头像URL',
    `role` ENUM('owner','member') NOT NULL DEFAULT 'member' COMMENT '角色: 主账号/子账号',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='账号表';

-- 用户表：主账号（家庭/组织的拥有者），和 account 一一对应
CREATE TABLE IF NOT EXISTS `user` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '用户ID',
    `account_id` BIGINT NOT NULL UNIQUE COMMENT '对应 account.id',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (`account_id`) REFERENCES `account`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- 成员表：子账号，同样和 account 一一对应，并且属于某个 user
CREATE TABLE IF NOT EXISTS `member` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '成员ID',
    `user_id` BIGINT NOT NULL COMMENT '归属主账号',
    `account_id` BIGINT NOT NULL UNIQUE COMMENT '对应 account.id',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (`user_id`) REFERENCES `user`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`account_id`) REFERENCES `account`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='成员表';

-- 房间表：用于组织和管理设备的空间
CREATE TABLE IF NOT EXISTS `room` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '房间ID',
    `user_id` BIGINT NOT NULL COMMENT '所属用户ID',
    `name` VARCHAR(50) NOT NULL COMMENT '房间名称',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (`user_id`) REFERENCES `user`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='房间表';

-- 设备型号表：定义设备类型和参数规范
CREATE TABLE IF NOT EXISTS `device_model` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '设备型号ID',
    `model_name` VARCHAR(100) NOT NULL COMMENT '型号名称',
    `vendor` VARCHAR(100) COMMENT '厂商',
    `params` JSON NOT NULL COMMENT '参数定义JSON',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='设备型号表';

-- 设备表：具体的物联网设备实例
CREATE TABLE IF NOT EXISTS `device` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '设备ID',
    `user_id` BIGINT NULL COMMENT '所属用户ID',
    `model_id` BIGINT NOT NULL COMMENT '设备型号ID',
    `name` VARCHAR(100) NOT NULL COMMENT '设备名称',
    `sn` VARCHAR(100) UNIQUE NOT NULL COMMENT '设备序列号',
    `status` ENUM('unconfigured','unbound','bound','online','offline','upgrading','fault') DEFAULT 'unconfigured' COMMENT '设备状态',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (`user_id`) REFERENCES `user`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`model_id`) REFERENCES `device_model`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='设备表';

-- 房间设备关联表：设备与房间的多对多关系
CREATE TABLE IF NOT EXISTS `room_device` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '关联ID',
    `room_id` BIGINT NOT NULL COMMENT '房间ID',
    `device_id` BIGINT NOT NULL COMMENT '设备ID',
    `sort_order` INT DEFAULT 0 COMMENT '排序顺序',
    FOREIGN KEY (`room_id`) REFERENCES `room`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`device_id`) REFERENCES `device`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='房间设备关联表';

-- 设备参数表：存储设备的实时参数数据
CREATE TABLE IF NOT EXISTS `device_param` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '参数记录ID',
    `device_id` BIGINT NOT NULL COMMENT '设备ID',
    `params` JSON NOT NULL COMMENT '参数数据JSON',
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (`device_id`) REFERENCES `device`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='设备参数表';

-- 设备日志表：记录设备运行历史记录和事件
CREATE TABLE IF NOT EXISTS `device_log` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '日志ID',
    `device_id` BIGINT NOT NULL COMMENT '设备ID',
    `event_type` VARCHAR(50) COMMENT '事件类型',
    `params` JSON COMMENT '事件参数JSON',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (`device_id`) REFERENCES `device`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='设备日志表';

-- 成员设备权限表：控制成员对设备的访问权限
CREATE TABLE IF NOT EXISTS `member_device_permission` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '权限ID',
    `member_id` BIGINT NOT NULL COMMENT '成员ID',
    `device_id` BIGINT NOT NULL COMMENT '设备ID',
    `can_control` TINYINT(1) DEFAULT 0 COMMENT '是否可控制设备(0=否,1=是)',
    FOREIGN KEY (`member_id`) REFERENCES `member`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`device_id`) REFERENCES `device`(`id`) ON DELETE CASCADE,
    UNIQUE(`member_id`, `device_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='成员设备权限表';

-- 告警表：记录设备产生的告警信息
CREATE TABLE IF NOT EXISTS `alert` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '告警ID',
    `device_id` BIGINT NOT NULL COMMENT '设备ID',
    `level` ENUM('low','medium','high') NOT NULL COMMENT '告警级别',
    `status` ENUM('new','read','resolved') DEFAULT 'new' COMMENT '告警状态',
    `message` VARCHAR(255) COMMENT '告警消息',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (`device_id`) REFERENCES `device`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='告警表';

-- 插入默认账号和用户（密码: admin123）
INSERT INTO `account` (`account`, `password_hash`, `name`, `email`, `role`) 
VALUES ('admin', 'admin123', '管理员', 'admin@fastiot.com', 'owner')
ON DUPLICATE KEY UPDATE `account` = `account`;

-- 为默认账号创建对应的用户记录
INSERT INTO `user` (`account_id`) 
SELECT `id` FROM `account` WHERE `account` = 'admin' AND `role` = 'owner'
ON DUPLICATE KEY UPDATE `account_id` = `account_id`;

-- 插入示例设备型号
INSERT INTO `device_model` (`model_name`, `vendor`, `params`) 
VALUES 
('温度传感器', 'IoT Corp', '{"temperature": {"type": "float", "unit": "°C", "min": -40, "max": 85}}'),
('湿度传感器', 'IoT Corp', '{"humidity": {"type": "float", "unit": "%", "min": 0, "max": 100}}'),
('环境监测器', 'Smart Devices', '{"temperature": {"type": "float", "unit": "°C"}, "humidity": {"type": "float", "unit": "%"}, "pressure": {"type": "float", "unit": "hPa"}}')
ON DUPLICATE KEY UPDATE `model_name` = VALUES(`model_name`);

-- 插入示例设备
INSERT INTO `device` (`user_id`, `model_id`, `name`, `sn`, `status`) 
VALUES 
(1, 1, '温度传感器-01', 'TEMP001', 'offline'),
(1, 2, '湿度传感器-01', 'HUM001', 'offline'),
(1, 3, '环境监测器-01', 'ENV001', 'offline')
ON DUPLICATE KEY UPDATE `name` = VALUES(`name`);
