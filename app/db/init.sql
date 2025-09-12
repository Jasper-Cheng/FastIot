-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS `iot` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE `iot`;

-- 用户表
CREATE TABLE IF NOT EXISTS `user` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `username` VARCHAR(50) NOT NULL UNIQUE,
    `password` VARCHAR(255) NOT NULL,
    `phone` VARCHAR(20),
    `email` VARCHAR(100),
    `avatar` VARCHAR(255),
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 成员表
CREATE TABLE IF NOT EXISTS `member` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `user_id` BIGINT NOT NULL,
    `name` VARCHAR(50) NOT NULL,
    `gender` ENUM('male','female','other'),
    `account` VARCHAR(50) UNIQUE,
    `password` VARCHAR(255),
    `phone` VARCHAR(20),
    `email` VARCHAR(100),
    `avatar` VARCHAR(255),
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`user_id`) REFERENCES `user`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 房间表
CREATE TABLE IF NOT EXISTS `room` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `user_id` BIGINT NOT NULL,
    `name` VARCHAR(50) NOT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`user_id`) REFERENCES `user`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 设备型号表
CREATE TABLE IF NOT EXISTS `device_model` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `model_name` VARCHAR(100) NOT NULL,
    `vendor` VARCHAR(100),
    `params` JSON NOT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 设备表
CREATE TABLE IF NOT EXISTS `device` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `user_id` BIGINT NOT NULL,
    `model_id` BIGINT NOT NULL,
    `name` VARCHAR(100) NOT NULL,
    `sn` VARCHAR(100) UNIQUE NOT NULL,
    `status` ENUM('online','offline') DEFAULT 'offline',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`user_id`) REFERENCES `user`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`model_id`) REFERENCES `device_model`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 房间设备关联表
CREATE TABLE IF NOT EXISTS `room_device` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `room_id` BIGINT NOT NULL,
    `device_id` BIGINT NOT NULL,
    `sort_order` INT DEFAULT 0,
    FOREIGN KEY (`room_id`) REFERENCES `room`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`device_id`) REFERENCES `device`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 设备参数表
CREATE TABLE IF NOT EXISTS `device_param` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `device_id` BIGINT NOT NULL,
    `params` JSON NOT NULL,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`device_id`) REFERENCES `device`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 设备日志表
CREATE TABLE IF NOT EXISTS `device_log` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `device_id` BIGINT NOT NULL,
    `event_type` VARCHAR(50),
    `params` JSON,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`device_id`) REFERENCES `device`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 成员设备权限表
CREATE TABLE IF NOT EXISTS `member_device_permission` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `member_id` BIGINT NOT NULL,
    `device_id` BIGINT NOT NULL,
    `can_control` TINYINT(1) DEFAULT 0,
    FOREIGN KEY (`member_id`) REFERENCES `member`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`device_id`) REFERENCES `device`(`id`) ON DELETE CASCADE,
    UNIQUE(`member_id`, `device_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 告警表
CREATE TABLE IF NOT EXISTS `alert` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `device_id` BIGINT NOT NULL,
    `level` ENUM('low','medium','high') NOT NULL,
    `status` ENUM('new','read','resolved') DEFAULT 'new',
    `message` VARCHAR(255),
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`device_id`) REFERENCES `device`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 插入默认用户（密码: admin123）
INSERT INTO `user` (`username`, `password`, `email`) 
VALUES ('admin', 'admin123', 'admin@fastiot.com')
ON DUPLICATE KEY UPDATE `username` = `username`;

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
