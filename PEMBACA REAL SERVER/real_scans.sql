USE Dashboard;

CREATE TABLE IF NOT EXISTS real_scans (
    id INT AUTO_INCREMENT PRIMARY KEY,
    folder_name VARCHAR(100) NOT NULL,
    folder_path VARCHAR(255) NOT NULL UNIQUE,
    main_image VARCHAR(255),
    icon_image VARCHAR(255),
    camera_images TEXT,
    scan_date DATE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_scan_date (scan_date),
    INDEX idx_folder_name (folder_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;