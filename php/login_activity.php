<?php
header('Content-Type: application/json');
require_once 'db_config.php';

if (!isset($_SESSION['user_id'])) {
    http_response_code(401);
    die(json_encode(['success' => false, 'message' => 'Access denied. Please log in.']));
}

$userId = $_SESSION['user_id'];

$stmt = $conn->prepare("SELECT ip_address, user_agent, login_time FROM login_activity WHERE user_id = ? ORDER BY id DESC LIMIT 50");
if (!$stmt) {
    http_response_code(500);
    die(json_encode(['success' => false, 'message' => 'Database query preparation failed.']));
}

$userIdStr = (string)$userId;
$stmt->bind_param('s', $userIdStr);
if (!$stmt->execute()) {
    $stmt->close();
    http_response_code(500);
    die(json_encode(['success' => false, 'message' => 'Failed to fetch login activity.']));
}

$result = $stmt->get_result();
$activities = [];
while ($row = $result->fetch_assoc()) {
    $activities[] = [
        'ip_address' => $row['ip_address'],
        'user_agent' => $row['user_agent'],
        'login_time' => $row['login_time']
    ];
}

$stmt->close();
$conn->close();

echo json_encode(['success' => true, 'activities' => $activities]);
?>
