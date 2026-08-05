<?php
header('Content-Type: application/json');
require_once 'db_config.php';

// If user is logged in, clear their url_scans; otherwise return success for local-only mode
if (isset($_SESSION['role']) && isset($_SESSION['email'])) {
    if ($_SESSION['role'] === 'admin') {
        echo json_encode(['success' => false, 'message' => 'Admin cannot clear all history via this endpoint']);
        $conn->close();
        exit;
    }

    // Ensure users table has id
    $stmt = $conn->prepare("SELECT id FROM users WHERE email = ? LIMIT 1");
    $stmt->bind_param('s', $_SESSION['email']);
    $stmt->execute();
    $res = $stmt->get_result();
    if ($res && $res->num_rows === 1) {
        $row = $res->fetch_assoc();
        $uid = (int)$row['id'];
        $stmt->close();

        $del = $conn->prepare("DELETE FROM url_scans WHERE user_id = ?");
        $del->bind_param('i', $uid);
        $del->execute();
        $del->close();

        echo json_encode(['success' => true, 'message' => 'Scan history cleared for user']);
        $conn->close();
        exit;
    }
    $stmt->close();
}

// If reached here, we're either anonymous/local or user record not found — return success
echo json_encode(['success' => true, 'message' => 'No server-side history to clear (local-only mode)']);
$conn->close();
exit;
?>