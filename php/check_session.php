<?php
header('Content-Type: application/json');
require_once 'db_config.php';

$response = [
    'logged_in' => false,
    'user' => null
];

function get_admin_setting_value($conn, $key, $default)
{
    $stmt = $conn->prepare("SELECT setting_value FROM settings_store WHERE role = 'admin' AND owner_key = 'admin' AND setting_key = ? LIMIT 1");
    if (!$stmt) {
        return $default;
    }

    $stmt->bind_param('s', $key);
    if (!$stmt->execute()) {
        $stmt->close();
        return $default;
    }

    $result = $stmt->get_result();
    if ($result->num_rows !== 1) {
        $stmt->close();
        return $default;
    }

    $row = $result->fetch_assoc();
    $stmt->close();
    $value = trim((string)$row['setting_value']);
    return ($value === '') ? $default : $value;
}

// Check if user is logged in
if (isset($_SESSION['user_id']) && isset($_SESSION['role'])) {
    $response['logged_in'] = true;
    $response['user'] = [
        'id' => $_SESSION['user_id'],
        'name' => $_SESSION['name'] ?? 'User',
        'email' => $_SESSION['email'],
        'role' => $_SESSION['role'],
        'is_main_admin' => (isset($_SESSION['email']) && $_SESSION['email'] === ADMIN_EMAIL) ? true : false
    ];

    // Check session expiry
    if (isset($_SESSION['login_time'])) {
        $session_duration = time() - $_SESSION['login_time'];
        $sessionTimeout = isset($_SESSION['session_timeout']) ? (int)$_SESSION['session_timeout'] : 0;

        if ($sessionTimeout <= 0) {
            $sessionTimeoutMinutes = (int)get_admin_setting_value($conn, 'session_timeout_minutes', (string)max(1, (int)floor(SESSION_TIMEOUT / 60)));
            if ($sessionTimeoutMinutes < 1) {
                $sessionTimeoutMinutes = max(1, (int)floor(SESSION_TIMEOUT / 60));
            }
            $sessionTimeout = $sessionTimeoutMinutes * 60;
        }

        if ($session_duration > $sessionTimeout) {
            session_destroy();
            $response['logged_in'] = false;
            $response['message'] = 'Session expired';
        }
    }
} else {
    http_response_code(401);
}

echo json_encode($response);
?>
