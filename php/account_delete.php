<?php
header('Content-Type: application/json');
require_once 'db_config.php';

// Only proceed if user is logged in
if (!isset($_SESSION['role']) || !isset($_SESSION['email'])) {
    echo json_encode(['success' => false, 'message' => 'Not logged in — cannot delete account on server']);
    $conn->close();
    exit;
}

// find user id
$stmt = $conn->prepare("SELECT id, role FROM users WHERE email = ? LIMIT 1");
$stmt->bind_param('s', $_SESSION['email']);
$stmt->execute();
$res = $stmt->get_result();
if (!$res || $res->num_rows !== 1) {
    $stmt->close();
    echo json_encode(['success' => false, 'message' => 'User record not found']);
    $conn->close();
    exit;
}
$row = $res->fetch_assoc();
$uid = (int)$row['id'];
$userRole = $row['role'] ?? 'user';
$stmt->close();

// Prevent deleting main admin
if (isset($_SESSION['email']) && $_SESSION['email'] === ADMIN_EMAIL) {
    echo json_encode(['success' => false, 'message' => 'Main admin account cannot be deleted via this endpoint']);
    $conn->close();
    exit;
}

// Remove user-related data
$del1 = $conn->prepare("DELETE FROM url_scans WHERE user_id = ?");
$del1->bind_param('i', $uid);
$del1->execute();
$del1->close();

$del2 = $conn->prepare("DELETE FROM settings_store WHERE role = 'user' AND owner_key = ?");
$ownerKey = $_SESSION['email'];
$del2->bind_param('s', $ownerKey);
$del2->execute();
$del2->close();

$del3 = $conn->prepare("DELETE FROM users WHERE id = ?");
$del3->bind_param('i', $uid);
$del3->execute();
$del3->close();

// Destroy session
session_unset();
session_destroy();

echo json_encode(['success' => true, 'message' => 'Account deleted']);
$conn->close();
exit;
?>