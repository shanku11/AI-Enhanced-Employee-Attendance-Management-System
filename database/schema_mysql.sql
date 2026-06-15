CREATE DATABASE IF NOT EXISTS ai_attendance_system;
USE ai_attendance_system;

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(50) NOT NULL UNIQUE,
  email VARCHAR(100) NOT NULL UNIQUE,
  password_hash VARCHAR(100) NOT NULL,
  role VARCHAR(20) DEFAULT 'employee',
  name VARCHAR(100) NOT NULL,
  department VARCHAR(100) DEFAULT 'General',
  is_active BOOLEAN DEFAULT TRUE,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS attendance (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  date DATE NOT NULL,
  clock_in DATETIME NOT NULL,
  clock_out DATETIME NULL,
  status VARCHAR(20) NOT NULL,
  working_hours FLOAT DEFAULT 0,
  INDEX idx_attendance_user_date (user_id, date),
  CONSTRAINT fk_attendance_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS prediction_cache (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  prediction_type VARCHAR(50) NOT NULL,
  prediction_value VARCHAR(100) NOT NULL,
  confidence_score FLOAT NOT NULL,
  features JSON NULL,
  model_version VARCHAR(50) DEFAULT '1.0',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  expires_at DATETIME NOT NULL,
  INDEX idx_prediction_user (user_id),
  CONSTRAINT fk_prediction_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS employee_insight (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  insight_type VARCHAR(50) NOT NULL,
  insight_title VARCHAR(200) NOT NULL,
  insight_content TEXT NOT NULL,
  severity VARCHAR(20) DEFAULT 'info',
  is_read BOOLEAN DEFAULT FALSE,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_insight_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chat_message (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  sender VARCHAR(20) NOT NULL,
  message_text TEXT NOT NULL,
  context_employee_id INT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_chat_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alerts (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  type VARCHAR(50) NOT NULL,
  message TEXT NOT NULL,
  severity VARCHAR(20) DEFAULT 'info',
  occurrences INT DEFAULT 1,
  is_acknowledged BOOLEAN DEFAULT FALSE,
  acknowledged_by INT NULL,
  acknowledged_at DATETIME NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_alert_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

INSERT IGNORE INTO users (id, username, email, password_hash, role, name, department)
VALUES
  (1, 'admin', 'hr@company.com', 'ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f', 'admin', 'HR Administrator', 'Human Resources'),
  (2, 'alice', 'alice@company.com', 'ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f', 'employee', 'Alice Johnson', 'Engineering'),
  (3, 'bob', 'bob@company.com', 'ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f', 'employee', 'Bob Smith', 'Marketing'),
  (4, 'charlie', 'charlie@company.com', 'ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f', 'employee', 'Charlie Davis', 'Sales');
