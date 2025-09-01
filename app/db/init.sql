-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS `iot` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE `iot`;

-- 用户表
CREATE TABLE IF NOT EXISTS `User` (
    `id` INT PRIMARY KEY AUTO_INCREMENT,
    `username` VARCHAR(50) UNIQUE NOT NULL,
    `email` VARCHAR(100) UNIQUE NOT NULL,
    `password` VARCHAR(255) NOT NULL,
    `role` ENUM('user','admin') DEFAULT 'user',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 设备表
CREATE TABLE IF NOT EXISTS `Device` (
    `id` INT PRIMARY KEY AUTO_INCREMENT,
    `name` VARCHAR(50) NOT NULL,
    `serial_number` VARCHAR(100) UNIQUE NOT NULL,
    `owner_id` INT,
    `status` ENUM('online','offline') DEFAULT 'offline',
    `last_active` TIMESTAMP NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`owner_id`) REFERENCES `User`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 设备数据表
CREATE TABLE IF NOT EXISTS `DeviceData` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `device_id` INT NOT NULL,
    `data` JSON NOT NULL,
    `timestamp` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`device_id`) REFERENCES `Device`(`id`),
    INDEX `idx_device_id` (`device_id`),
    INDEX `idx_timestamp` (`timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 告警表
CREATE TABLE IF NOT EXISTS `Alert` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `device_id` INT NOT NULL,
    `alert_type` VARCHAR(50),
    `message` TEXT,
    `status` ENUM('new','read','resolved') DEFAULT 'new',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`device_id`) REFERENCES `Device`(`id`),
    INDEX `idx_device_id` (`device_id`),
    INDEX `idx_status` (`status`),
    INDEX `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 插入默认管理员用户（密码: admin123）
INSERT INTO `User` (`username`, `email`, `password`, `role`) 
VALUES ('admin', 'admin@fastiot.com', 'admin123', 'admin')
ON DUPLICATE KEY UPDATE `username` = `username`;

-- 插入示例设备
INSERT INTO `Device` (`name`, `serial_number`, `owner_id`, `status`) 
VALUES 
('温度传感器-01', 'TEMP001', 1, 'offline'),
('湿度传感器-01', 'HUM001', 1, 'offline'),
('环境监测器-01', 'ENV001', 1, 'offline')
ON DUPLICATE KEY UPDATE `name` = VALUES(`name`);
