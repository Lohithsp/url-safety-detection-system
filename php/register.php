<?php
header('Content-Type: application/json');
require_once 'db_config.php';

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    die(json_encode(['success' => false, 'message' => 'Method not allowed']));
}

$input = json_decode(file_get_contents('php://input'), true);
if (!is_array($input)) {
    http_response_code(400);
    die(json_encode(['success' => false, 'message' => 'Invalid JSON body']));
}

$action = isset($input['action']) ? trim($input['action']) : 'register';
$name = isset($input['name']) ? trim($input['name']) : '';
$email = isset($input['email']) ? trim($input['email']) : '';
$password = isset($input['password']) ? (string)$input['password'] : '';

if ($action !== 'register') {
    http_response_code(400);
    die(json_encode(['success' => false, 'message' => 'Invalid action']));
}

if ($name === '' || $email === '' || $password === '') {
    http_response_code(400);
    die(json_encode(['success' => false, 'message' => 'Missing required fields']));
}

if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
    http_response_code(400);
    die(json_encode(['success' => false, 'message' => 'Invalid email format']));
}

if (strlen($password) < 8) {
    http_response_code(400);
    die(json_encode(['success' => false, 'message' => 'Password must be at least 8 characters']));
}

$createUsersTableSql = "CREATE TABLE IF NOT EXISTS users (
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
)";

if (!$conn->query($createUsersTableSql)) {
    http_response_code(500);
    die(json_encode(['success' => false, 'message' => 'Failed to initialize users table']));
}

$checkUserStmt = $conn->prepare("SELECT id FROM users WHERE email = ? LIMIT 1");
if ($checkUserStmt === false) {
    http_response_code(500);
    die(json_encode(['success' => false, 'message' => 'Database schema error: users table not ready. Please run php/setup.sql.']));
}

$checkUserStmt->bind_param('s', $email);
$checkUserStmt->execute();
$checkUserResult = $checkUserStmt->get_result();
if ($checkUserResult->num_rows > 0) {
    $checkUserStmt->close();
    http_response_code(409);
    die(json_encode(['success' => false, 'message' => 'This email is already used. Please login or use another email.']));
}
$checkUserStmt->close();

$passwordHash = password_hash($password, PASSWORD_BCRYPT);
$insertStmt = $conn->prepare("INSERT INTO users (name, email, password, role, status, registration_date, approved_date) VALUES (?, ?, ?, 'user', 'approved', NOW(), NOW())");
if ($insertStmt === false) {
    http_response_code(500);
    die(json_encode(['success' => false, 'message' => 'Registration failed']));
}

$insertStmt->bind_param('sss', $name, $email, $passwordHash);

if (!$insertStmt->execute()) {
    $insertErrno = (int)$insertStmt->errno;
    $insertStmt->close();
    if ($insertErrno === 1062) {
        http_response_code(409);
        echo json_encode(['success' => false, 'message' => 'This email is already used. Please login or use another email.']);
    } else {
        http_response_code(500);
        echo json_encode(['success' => false, 'message' => 'Registration failed']);
    }
    $conn->close();
    exit;
}

$insertStmt->close();
echo json_encode(['success' => true, 'message' => 'Registration completed. You can now log in.']);
$conn->close();
?>