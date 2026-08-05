CREATE TABLE IF NOT EXISTS scan_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    url VARCHAR(2048) NOT NULL,
    prediction VARCHAR(20) NOT NULL,
    confidence DOUBLE NOT NULL,
    risk_level VARCHAR(20) NOT NULL,
    explanation TEXT NOT NULL,
    scan_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_scan_history_user_id (user_id),
    INDEX idx_scan_history_prediction (prediction),
    INDEX idx_scan_history_scan_time (scan_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
