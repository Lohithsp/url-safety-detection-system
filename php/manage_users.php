<?php
header('Content-Type: application/json');
require_once 'db_config.php';

// Check if user is admin
if (!isset($_SESSION['role']) || $_SESSION['role'] !== 'admin') {
    http_response_code(403);
    die(json_encode(['success' => false, 'message' => 'Unauthorized']));
}

$action = $_GET['action'] ?? '';
$user_id = $_GET['user_id'] ?? '';

// Keep schema compatible with older databases
$conn->query("ALTER TABLE users ADD COLUMN IF NOT EXISTS role ENUM('user','admin') DEFAULT 'user' AFTER password");
$conn->query("UPDATE users SET role = 'user' WHERE role IS NULL OR role = ''");

if ($_SERVER['REQUEST_METHOD'] === 'GET' && $action === 'list') {
    // Get pending users
    $stmt = $conn->prepare("SELECT id, name, email, role, registration_date, last_login, status FROM users ORDER BY registration_date DESC");
    $stmt->execute();
    $result = $stmt->get_result();
    $users = [];

    while ($row = $result->fetch_assoc()) {
        $users[] = $row;
    }

    echo json_encode([
        'success' => true,
        'users' => $users
    ]);
    $stmt->close();
} else if ($_SERVER['REQUEST_METHOD'] === 'POST' && $action === 'approve') {
    if (!$user_id) {
        http_response_code(400);
        die(json_encode(['success' => false, 'message' => 'User ID required']));
    }

    $approvedRole = $_GET['role'] ?? 'user';
    if (!in_array($approvedRole, ['user', 'admin'], true)) {
        http_response_code(400);
        die(json_encode(['success' => false, 'message' => 'Invalid role']));
    }

    $stmt = $conn->prepare("UPDATE users SET status = 'approved', role = ?, approved_date = NOW() WHERE id = ?");
    $stmt->bind_param("si", $approvedRole, $user_id);

    if ($stmt->execute()) {
        echo json_encode(['success' => true, 'message' => 'User approved as ' . $approvedRole]);
    } else {
        http_response_code(500);
        echo json_encode(['success' => false, 'message' => 'Failed to approve user']);
    }
    $stmt->close();
} else if ($_SERVER['REQUEST_METHOD'] === 'POST' && $action === 'reject') {
    if (!$user_id) {
        http_response_code(400);
        die(json_encode(['success' => false, 'message' => 'User ID required']));
    }

    $stmt = $conn->prepare("DELETE FROM users WHERE id = ?");
    $stmt->bind_param("i", $user_id);

    if ($stmt->execute()) {
        echo json_encode(['success' => true, 'message' => 'User rejected']);
    } else {
        http_response_code(500);
        echo json_encode(['success' => false, 'message' => 'Failed to reject user']);
    }
    $stmt->close();
} else if ($_SERVER['REQUEST_METHOD'] === 'POST' && $action === 'update_role') {
    if (!$user_id) {
        http_response_code(400);
        die(json_encode(['success' => false, 'message' => 'User ID required']));
    }

    $newRole = $_GET['role'] ?? 'user';
    if (!in_array($newRole, ['user', 'admin'], true)) {
        http_response_code(400);
        die(json_encode(['success' => false, 'message' => 'Invalid role']));
    }

    $stmt = $conn->prepare("UPDATE users SET role = ?, status = 'approved' WHERE id = ?");
    $stmt->bind_param('si', $newRole, $user_id);

    if ($stmt->execute()) {
        echo json_encode(['success' => true, 'message' => 'User role updated to ' . $newRole]);
    } else {
        http_response_code(500);
        echo json_encode(['success' => false, 'message' => 'Failed to update user role']);
    }
    $stmt->close();
} else if ($_SERVER['REQUEST_METHOD'] === 'POST' && $action === 'delete') {
    if (!$user_id) {
        http_response_code(400);
        die(json_encode(['success' => false, 'message' => 'User ID required']));
    }

    // Only the main admin (as defined by ADMIN_EMAIL) can delete users
    if (!isset($_SESSION['email']) || $_SESSION['email'] !== ADMIN_EMAIL) {
        http_response_code(403);
        die(json_encode(['success' => false, 'message' => 'Only the main admin can delete users']));
    }

    if (isset($_SESSION['role'], $_SESSION['user_id']) && $_SESSION['role'] === 'admin' && (string)$_SESSION['user_id'] === (string)$user_id) {
        http_response_code(403);
        die(json_encode(['success' => false, 'message' => 'You cannot delete your own admin account']));
    }

    $stmt = $conn->prepare("DELETE FROM users WHERE id = ?");
    $stmt->bind_param("i", $user_id);

    if ($stmt->execute()) {
        echo json_encode(['success' => true, 'message' => 'User deleted successfully']);
    } else {
        http_response_code(500);
        echo json_encode(['success' => false, 'message' => 'Failed to delete user']);
    }
    $stmt->close();
} else {
    http_response_code(400);
    echo json_encode(['success' => false, 'message' => 'Invalid request']);
}

$conn->close();
?>
