-- URL Safety Detection System - Database Setup
-- Create database
CREATE DATABASE IF NOT EXISTS url_safety;
USE url_safety;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    role ENUM('user', 'admin') DEFAULT 'user',
    status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
    registration_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    approved_date DATETIME NULL,
    last_login DATETIME NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_email (email),
    INDEX idx_status (status)
);

-- Admin Users table (optional - for multi-admin support)
CREATE TABLE IF NOT EXISTS admin_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(120) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    name VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME NULL,
    active BOOLEAN DEFAULT TRUE,
    INDEX idx_email (email)
);

-- URL Scan History
CREATE TABLE IF NOT EXISTS url_scans (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    url VARCHAR(2048) NOT NULL,
    status ENUM('safe', 'suspicious', 'malicious') NOT NULL,
    detection_details JSON,
    scan_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_user_id (user_id),
    INDEX idx_scan_date (scan_date)
);

-- Approval Logs
CREATE TABLE IF NOT EXISTS approval_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    admin_id VARCHAR(100),
    action ENUM('approved', 'rejected', 'pending') DEFAULT 'pending',
    reason TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id)
);

-- Login OTP storage
CREATE TABLE IF NOT EXISTS login_otps (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(120) NOT NULL,
    role ENUM('admin', 'user') NOT NULL,
    user_id INT NULL,
    otp_hash VARCHAR(255) NOT NULL,
    expires_at DATETIME NOT NULL,
    used TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_email_role (email, role),
    INDEX idx_expires_at (expires_at)
);

-- Shared settings (admin + user)
CREATE TABLE IF NOT EXISTS settings_store (
    id INT AUTO_INCREMENT PRIMARY KEY,
    role ENUM('admin', 'user') NOT NULL,
    owner_key VARCHAR(120) NOT NULL,
    setting_key VARCHAR(120) NOT NULL,
    setting_value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_owner_setting (role, owner_key, setting_key),
    INDEX idx_owner (role, owner_key)
);

-- Login attempt tracking for lockout
CREATE TABLE IF NOT EXISTS auth_attempts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    role ENUM('admin', 'user') NOT NULL,
    email VARCHAR(120) NOT NULL,
    failed_count INT DEFAULT 0,
    blocked_until DATETIME NULL,
    last_failed_at DATETIME NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_role_email (role, email),
    INDEX idx_blocked_until (blocked_until)
);

-- Insert default admin user (email: youremail@gmail.com)
-- Note: The login will use the credentials from login.php directly
-- If you want to store admin in DB, uncomment and modify:
-- INSERT INTO admin_users (email, name, active) VALUES ('youremail@gmail.com', 'System Admin', TRUE);
