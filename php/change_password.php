<?php
header('Content-Type: application/json');
require_once 'db_config.php';

// Verify session
if (!isset($_SESSION['email']) || !isset($_SESSION['role'])) {
    http_response_code(401);
    die(json_encode(['success' => false, 'message' => 'Unauthorized. Please log in.']));
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    die(json_encode(['success' => false, 'message' => 'Method not allowed']));
}

$input = json_decode(file_get_contents('php://input'), true);
if (!is_array($input)) {
    http_response_code(400);
    die(json_encode(['success' => false, 'message' => 'Invalid JSON body']));
}

$currentPw = isset($input['current_password']) ? (string)$input['current_password'] : '';
$newPw = isset($input['new_password']) ? (string)$input['new_password'] : '';

if ($currentPw === '' || $newPw === '') {
    http_response_code(400);
    die(json_encode(['success' => false, 'message' => 'All password fields are required.']));
}

$role = $_SESSION['role'];
$email = $_SESSION['email'];

if ($role === 'admin') {
    $stmt = $conn->prepare("SELECT id, password FROM users WHERE role = 'admin' OR email = ? LIMIT 1");
    $stmt->bind_param('s', $email);
    $stmt->execute();
    $result = $stmt->get_result();
    $dbAdmin = $result->fetch_assoc();
    $stmt->close();

    if ($dbAdmin) {
        if (!password_verify($currentPw, $dbAdmin['password'])) {
            http_response_code(400);
            die(json_encode(['success' => false, 'message' => 'Incorrect current password.']));
        }
        $newHash = password_hash($newPw, PASSWORD_BCRYPT);
        $stmt = $conn->prepare("UPDATE users SET password = ? WHERE id = ?");
        $stmt->bind_param('si', $newHash, $dbAdmin['id']);
        $stmt->execute();
        $stmt->close();
        echo json_encode(['success' => true, 'message' => 'Admin password changed successfully.']);
    } else {
        if ($currentPw !== ADMIN_PASSWORD) {
            http_response_code(400);
            die(json_encode(['success' => false, 'message' => 'Incorrect current password.']));
        }
        $newHash = password_hash($newPw, PASSWORD_BCRYPT);
        $stmt = $conn->prepare("INSERT INTO users (name, email, password, role, status) VALUES ('Admin', ?, ?, 'admin', 'approved')");
        $stmt->bind_param('ss', $email, $newHash);
        $stmt->execute();
        $stmt->close();
        echo json_encode(['success' => true, 'message' => 'Admin password changed successfully.']);
    }
    $conn->close();
    exit;
}

// Regular user password change
$stmt = $conn->prepare("SELECT id, password FROM users WHERE email = ? LIMIT 1");
$stmt->bind_param('s', $email);
$stmt->execute();
$result = $stmt->get_result();
$dbUser = $result->fetch_assoc();
$stmt->close();

if (!$dbUser) {
    http_response_code(404);
    die(json_encode(['success' => false, 'message' => 'User account not found.']));
}

if (!password_verify($currentPw, $dbUser['password'])) {
    http_response_code(400);
    die(json_encode(['success' => false, 'message' => 'Incorrect current password.']));
}

$newHash = password_hash($newPw, PASSWORD_BCRYPT);
$stmt = $conn->prepare("UPDATE users SET password = ? WHERE id = ?");
$stmt->bind_param('si', $newHash, $dbUser['id']);
$stmt->execute();
$stmt->close();

echo json_encode(['success' => true, 'message' => 'Password changed successfully.']);
$conn->close();
?>
