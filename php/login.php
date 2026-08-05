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

// determine action early so we validate appropriate fields
$action = isset($input['action']) ? trim($input['action']) : '';

if ($action === 'verify_2fa' || $action === 'resend_2fa') {
    // these actions require at least `email` and `role` (otp/otp_id validated later)
    if (!isset($input['email']) || !isset($input['role'])) {
        http_response_code(400);
        die(json_encode(['success' => false, 'message' => 'Missing required fields']));
    }
    $email = trim($input['email']);
    $role = trim($input['role']);
    $password = '';
    $remember = false;
} else {
    if (!isset($input['email']) || !isset($input['password']) || !isset($input['role'])) {
        http_response_code(400);
        die(json_encode(['success' => false, 'message' => 'Missing required fields']));
    }
    $email = trim($input['email']);
    $password = (string)$input['password'];
    $role = trim($input['role']);
    $remember = !empty($input['remember']);
}

if (!in_array($role, ['admin', 'user'], true)) {
    http_response_code(400);
    die(json_encode(['success' => false, 'message' => 'Invalid role']));
}

$createAttemptsTableSql = "CREATE TABLE IF NOT EXISTS auth_attempts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    role ENUM('admin', 'user') NOT NULL,
    email VARCHAR(120) NOT NULL,
    failed_count INT DEFAULT 0,
    blocked_until DATETIME NULL,
    last_failed_at DATETIME NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_role_email (role, email),
    INDEX idx_blocked_until (blocked_until)
)";

if (!$conn->query($createAttemptsTableSql)) {
    http_response_code(500);
    die(json_encode(['success' => false, 'message' => 'Failed to initialize login security']));
}

$createLoginOtpsSql = "CREATE TABLE IF NOT EXISTS login_otps (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(120) NOT NULL,
    role ENUM('admin', 'user') NOT NULL,
    user_id INT NULL,
    otp_hash VARCHAR(255) NOT NULL,
    expires_at DATETIME NOT NULL,
    used TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_email_role (email, role),
    INDEX idx_expires_at (expires_at)
)";

if (!$conn->query($createLoginOtpsSql)) {
    http_response_code(500);
    die(json_encode(['success' => false, 'message' => 'Failed to initialize OTP storage']));
}

$conn->query("ALTER TABLE users ADD COLUMN IF NOT EXISTS role ENUM('user','admin') DEFAULT 'user' AFTER password");
$conn->query("UPDATE users SET role = 'user' WHERE role IS NULL OR role = ''");

$createLoginActivitySql = "CREATE TABLE IF NOT EXISTS login_activity (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(120) NOT NULL,
    ip_address VARCHAR(45) NOT NULL,
    user_agent TEXT,
    login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4";

if (!$conn->query($createLoginActivitySql)) {
    http_response_code(500);
    die(json_encode(['success' => false, 'message' => 'Failed to initialize login activity tracking']));
}

function log_login_activity_php($conn, $userId) {
    $ipAddress = isset($_SERVER['HTTP_X_FORWARDED_FOR']) ? $_SERVER['HTTP_X_FORWARDED_FOR'] : (isset($_SERVER['REMOTE_ADDR']) ? $_SERVER['REMOTE_ADDR'] : '');
    $userAgent = isset($_SERVER['HTTP_USER_AGENT']) ? $_SERVER['HTTP_USER_AGENT'] : '';
    $stmt = $conn->prepare("INSERT INTO login_activity (user_id, ip_address, user_agent) VALUES (?, ?, ?)");
    if ($stmt) {
        $userIdStr = (string)$userId;
        $stmt->bind_param('sss', $userIdStr, $ipAddress, $userAgent);
        $stmt->execute();
        $stmt->close();
    }
}

// Helper function to get admin settings
function get_admin_setting_value($conn, $key, $default) {
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

// Calculate session timeout early so it's available for all action handlers
$sessionTimeoutMinutes = (int)get_admin_setting_value($conn, 'session_timeout_minutes', (string)max(1, (int)floor(SESSION_TIMEOUT / 60)));
if ($sessionTimeoutMinutes < 1) {
    $sessionTimeoutMinutes = max(1, (int)floor(SESSION_TIMEOUT / 60));
}
$sessionTimeoutSeconds = $sessionTimeoutMinutes * 60;

// Support explicit actions like verify_2fa
if ($action === 'verify_2fa') {
    if (!isset($input['otp_id']) || !isset($input['otp']) || !isset($input['role']) || !isset($input['email'])) {
        http_response_code(400);
        die(json_encode(['success' => false, 'message' => 'Missing fields for 2FA verification']));
    }

    $otpId = (int)$input['otp_id'];
    $otpPlain = trim($input['otp']);
    $vRole = trim($input['role']);
    $vEmail = trim($input['email']);

    $findStmt = $conn->prepare("SELECT id, email, role, user_id, otp_hash, expires_at, used FROM login_otps WHERE id = ? AND role = ? AND email = ? LIMIT 1");
    $findStmt->bind_param('iss', $otpId, $vRole, $vEmail);
    $findStmt->execute();
    $res = $findStmt->get_result();
    if ($res->num_rows !== 1) {
        $findStmt->close();
        http_response_code(401);
        echo json_encode(['success' => false, 'message' => 'OTP record not found.']);
        $conn->close();
        exit;
    }

    $otpRow = $res->fetch_assoc();
    $findStmt->close();

    if ($otpRow['used']) {
        http_response_code(401);
        echo json_encode(['success' => false, 'message' => 'OTP already used']);
        $conn->close();
        exit;
    }

    if (strtotime($otpRow['expires_at']) < time()) {
        http_response_code(401);
        echo json_encode(['success' => false, 'message' => 'OTP expired. Request a new login OTP.']);
        $conn->close();
        exit;
    }

    if (!password_verify($otpPlain, $otpRow['otp_hash'])) {
        http_response_code(401);
        echo json_encode(['success' => false, 'message' => 'Invalid OTP']);
        $conn->close();
        exit;
    }

    // mark used
    $markStmt = $conn->prepare("UPDATE login_otps SET used = 1 WHERE id = ?");
    $markStmt->bind_param('i', $otpRow['id']);
    $markStmt->execute();
    $markStmt->close();

    // finalize login session
    if ($vRole === 'admin') {
        $_SESSION['user_id'] = 'admin_' . time();
        $_SESSION['email'] = $vEmail;
        $_SESSION['name'] = 'Admin';
        $_SESSION['role'] = 'admin';
        $_SESSION['login_time'] = time();
        $_SESSION['session_timeout'] = $sessionTimeoutSeconds;

        log_login_activity_php($conn, 'admin');
        echo json_encode(['success' => true, 'message' => 'Admin login successful (2FA) ', 'redirect' => '../admin/scan.html']);
        $conn->close();
        exit;
    }

    // user: fetch user record and set session
    $uStmt = $conn->prepare("SELECT id, name, email FROM users WHERE email = ? LIMIT 1");
    $uStmt->bind_param('s', $vEmail);
    $uStmt->execute();
    $uRes = $uStmt->get_result();
    if ($uRes->num_rows !== 1) {
        $uStmt->close();
        http_response_code(401);
        echo json_encode(['success' => false, 'message' => 'User not found']);
        $conn->close();
        exit;
    }
    $u = $uRes->fetch_assoc();
    $uStmt->close();

    $_SESSION['user_id'] = $u['id'];
    $_SESSION['email'] = $u['email'];
    $_SESSION['name'] = $u['name'];
    $_SESSION['role'] = 'user';
    $_SESSION['login_time'] = time();
    $_SESSION['session_timeout'] = $sessionTimeoutSeconds;

    $updateStmt = $conn->prepare("UPDATE users SET last_login = NOW() WHERE id = ?");
    $updateStmt->bind_param('i', $u['id']);
    $updateStmt->execute();
    $updateStmt->close();

    log_login_activity_php($conn, $u['id']);
    echo json_encode(['success' => true, 'message' => 'User login successful (2FA)', 'redirect' => '../user/index.html']);
    $conn->close();
    exit;
}

if ($action === 'resend_2fa') {
    if (!isset($input['role']) || !isset($input['email'])) {
        http_response_code(400);
        die(json_encode(['success' => false, 'message' => 'Missing fields for resend']));
    }
    $rRole = trim($input['role']);
    $rEmail = trim($input['email']);

    // cooldown: check latest unused OTP created recently
    $cooldownSeconds = 5; // 5s between resends for testing, adjust to 60 for production
    $checkStmt = $conn->prepare("SELECT id, created_at, expires_at, used FROM login_otps WHERE role = ? AND email = ? ORDER BY id DESC LIMIT 1");
    $checkStmt->bind_param('ss', $rRole, $rEmail);
    $checkStmt->execute();
    $checkRes = $checkStmt->get_result();
    $last = null;
    if ($checkRes->num_rows === 1) {
        $last = $checkRes->fetch_assoc();
    }
    $checkStmt->close();

    if ($last && !$last['used']) {
        $createdAt = strtotime($last['created_at']);
        if ((time() - $createdAt) < $cooldownSeconds) {
            $secondsLeft = $cooldownSeconds - (time() - $createdAt);
            http_response_code(429);
            echo json_encode(['success' => false, 'message' => 'Please wait ' . $secondsLeft . ' seconds before requesting a new OTP.']);
            $conn->close();
            exit;
        }
    }

    // mark previous unused as used to avoid confusion
    if ($last && !$last['used']) {
        $markPrev = $conn->prepare("UPDATE login_otps SET used = 1 WHERE id = ?");
        $markPrev->bind_param('i', $last['id']);
        $markPrev->execute();
        $markPrev->close();
    }

    $plainOtp = (string)random_int(100000, 999999);
    $otpHash = password_hash($plainOtp, PASSWORD_DEFAULT);
    $expiresAt = date('Y-m-d H:i:s', strtotime('+10 minutes'));

    $insertStmt = $conn->prepare("INSERT INTO login_otps (email, role, user_id, otp_hash, expires_at, used) VALUES (?, ?, NULL, ?, ?, 0)");
    $insertStmt->bind_param('ssss', $rEmail, $rRole, $otpHash, $expiresAt);
    if (!$insertStmt->execute()) {
        $insertStmt->close();
        http_response_code(500);
        echo json_encode(['success' => false, 'message' => 'Failed to create OTP']);
        $conn->close();
        exit;
    }
    $newOtpId = $insertStmt->insert_id;
    $insertStmt->close();

    require_once 'mailer.php';
    $mailResult = send_otp_email($rEmail, $plainOtp, $rRole === 'admin' ? 'admin' : 'user');
    if (!$mailResult['success']) {
        $del = $conn->prepare("DELETE FROM login_otps WHERE id = ?");
        $del->bind_param('i', $newOtpId);
        $del->execute();
        $del->close();
        http_response_code(500);
        echo json_encode(['success' => false, 'message' => $mailResult['message']]);
        $conn->close();
        exit;
    }

    echo json_encode(['success' => true, 'otp_id' => $newOtpId, 'message' => 'OTP resent to email']);
    $conn->close();
    exit;
}

function get_lockout_status($conn, $role, $email)
{
    $stmt = $conn->prepare("SELECT failed_count, blocked_until FROM auth_attempts WHERE role = ? AND email = ? LIMIT 1");
    $stmt->bind_param('ss', $role, $email);
    $stmt->execute();
    $result = $stmt->get_result();

    if ($result->num_rows !== 1) {
        $stmt->close();
        return ['failed_count' => 0, 'blocked_until' => null];
    }

    $row = $result->fetch_assoc();
    $stmt->close();
    return $row;
}

function register_failed_login($conn, $role, $email, $maxAttempts, $lockoutMinutes)
{
    $status = get_lockout_status($conn, $role, $email);
    $failedCount = (int)$status['failed_count'] + 1;
    $blockedUntil = null;

    if ($failedCount >= $maxAttempts) {
        $blockedUntil = date('Y-m-d H:i:s', strtotime('+' . $lockoutMinutes . ' minutes'));
    }

    $stmt = $conn->prepare("INSERT INTO auth_attempts (role, email, failed_count, blocked_until, last_failed_at) VALUES (?, ?, ?, ?, NOW()) ON DUPLICATE KEY UPDATE failed_count = VALUES(failed_count), blocked_until = VALUES(blocked_until), last_failed_at = VALUES(last_failed_at)");
    $stmt->bind_param('ssis', $role, $email, $failedCount, $blockedUntil);
    $stmt->execute();
    $stmt->close();

    return ['failed_count' => $failedCount, 'blocked_until' => $blockedUntil];
}

function clear_failed_logins($conn, $role, $email)
{
    $stmt = $conn->prepare("DELETE FROM auth_attempts WHERE role = ? AND email = ?");
    $stmt->bind_param('ss', $role, $email);
    $stmt->execute();
    $stmt->close();
}

$maxAttempts = (int)get_admin_setting_value($conn, 'login_attempts_limit', '5');
if ($maxAttempts < 1) {
    $maxAttempts = 5;
}

$sessionTimeoutMinutes = (int)get_admin_setting_value($conn, 'session_timeout_minutes', (string)max(1, (int)floor(SESSION_TIMEOUT / 60)));
if ($sessionTimeoutMinutes < 1) {
    $sessionTimeoutMinutes = max(1, (int)floor(SESSION_TIMEOUT / 60));
}
$sessionTimeoutSeconds = $sessionTimeoutMinutes * 60;
$lockoutMinutes = 15;

$attemptStatus = get_lockout_status($conn, $role, $email);
if (!empty($attemptStatus['blocked_until']) && strtotime($attemptStatus['blocked_until']) > time()) {
    http_response_code(429);
    echo json_encode([
        'success' => false,
        'message' => 'Too many failed attempts. Try again after lockout period.'
    ]);
    $conn->close();
    exit;
}

if ($role === 'admin') {
    $isDefaultAdmin = ($email === ADMIN_EMAIL && $password === ADMIN_PASSWORD);

    if (!$isDefaultAdmin) {
        $adminUserStmt = $conn->prepare("SELECT id, name, email, password, status, role FROM users WHERE email = ? LIMIT 1");
        $adminUserStmt->bind_param('s', $email);
        $adminUserStmt->execute();
        $adminUserRes = $adminUserStmt->get_result();

        if ($adminUserRes->num_rows !== 1) {
            $adminUserStmt->close();
            $failed = register_failed_login($conn, $role, $email, $maxAttempts, $lockoutMinutes);
            if (!empty($failed['blocked_until'])) {
                http_response_code(429);
                echo json_encode(['success' => false, 'message' => 'Account locked due to too many failed attempts.']);
            } else {
                http_response_code(401);
                echo json_encode(['success' => false, 'message' => 'Invalid admin credentials']);
            }
            $conn->close();
            exit;
        }

        $adminUser = $adminUserRes->fetch_assoc();
        $adminUserStmt->close();

        if ($adminUser['status'] !== 'approved') {
            http_response_code(403);
            echo json_encode(['success' => false, 'message' => 'Admin account is pending approval']);
            $conn->close();
            exit;
        }

        if (($adminUser['role'] ?? 'user') !== 'admin') {
            http_response_code(403);
            echo json_encode(['success' => false, 'message' => 'No admin access. Login as user.']);
            $conn->close();
            exit;
        }

        if (!password_verify($password, $adminUser['password'])) {
            $failed = register_failed_login($conn, $role, $email, $maxAttempts, $lockoutMinutes);
            if (!empty($failed['blocked_until'])) {
                http_response_code(429);
                echo json_encode(['success' => false, 'message' => 'Account locked due to too many failed attempts.']);
            } else {
                http_response_code(401);
                echo json_encode(['success' => false, 'message' => 'Invalid admin credentials']);
            }
            $conn->close();
            exit;
        }
    }
    // Admins bypass 2FA and login directly
    clear_failed_logins($conn, $role, $email);

    $_SESSION['user_id'] = isset($adminUser['id']) ? $adminUser['id'] : ('admin_' . time());
    $_SESSION['email'] = $email;
    $_SESSION['name'] = isset($adminUser['name']) ? $adminUser['name'] : 'Admin';
    $_SESSION['role'] = 'admin';
    $_SESSION['login_time'] = time();
    $_SESSION['session_timeout'] = $sessionTimeoutSeconds;

    if (isset($adminUser['id'])) {
        $adminLastLoginStmt = $conn->prepare("UPDATE users SET last_login = NOW() WHERE id = ?");
        $adminLastLoginStmt->bind_param('i', $adminUser['id']);
        $adminLastLoginStmt->execute();
        $adminLastLoginStmt->close();
    }

    if ($remember) {
        setcookie('admin_token', bin2hex(random_bytes(32)), time() + 30 * 24 * 60 * 60, '/');
    }

    log_login_activity_php($conn, 'admin');
    echo json_encode([
        'success' => true,
        'message' => 'Admin login successful',
        'redirect' => '../admin/scan.html'
    ]);
    $conn->close();
    exit;
}

$stmt = $conn->prepare("SELECT id, name, email, password, role, status FROM users WHERE email = ? LIMIT 1");
$stmt->bind_param('s', $email);
$stmt->execute();
$result = $stmt->get_result();

if ($result->num_rows !== 1) {
    $stmt->close();
    register_failed_login($conn, $role, $email, $maxAttempts, $lockoutMinutes);
    http_response_code(401);
    echo json_encode(['success' => false, 'message' => 'User not found']);
    $conn->close();
    exit;
}

$user = $result->fetch_assoc();
$stmt->close();

if ($user['status'] !== 'approved') {
    http_response_code(403);
    echo json_encode(['success' => false, 'message' => 'Your account is pending admin approval']);
    $conn->close();
    exit;
}

if (($user['role'] ?? 'user') !== 'user') {
    http_response_code(403);
    echo json_encode(['success' => false, 'message' => 'This account has admin role. Use Admin login.']);
    $conn->close();
    exit;
}

if (!password_verify($password, $user['password'])) {
    $failed = register_failed_login($conn, $role, $email, $maxAttempts, $lockoutMinutes);

    if (!empty($failed['blocked_until'])) {
        // Automatically enable 2-Factor Authentication (2FA) for this user
        $stmt2fa = $conn->prepare("INSERT INTO settings_store (role, owner_key, setting_key, setting_value) VALUES ('user', ?, 'two_factor_user', '1') ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)");
        $stmt2fa->bind_param('s', $email);
        $stmt2fa->execute();
        $stmt2fa->close();

        // Send security alert email
        require_once 'mailer.php';
        send_security_alert_email($email);

        http_response_code(429);
        echo json_encode(['success' => false, 'message' => 'Account locked due to too many failed attempts.']);
    } else {
        http_response_code(401);
        echo json_encode(['success' => false, 'message' => 'Invalid password']);
    }

    $conn->close();
    exit;
}
// check if user two-factor is enabled
$stmt2fa = $conn->prepare("SELECT setting_value FROM settings_store WHERE role = 'user' AND owner_key = ? AND setting_key = 'two_factor_user' LIMIT 1");
$stmt2fa->bind_param('s', $email);
$stmt2fa->execute();
$res2fa = $stmt2fa->get_result();
$user2fa = '0';
if ($res2fa->num_rows === 1) {
    $row2fa = $res2fa->fetch_assoc();
    $user2fa = trim((string)$row2fa['setting_value']);
}
$stmt2fa->close();

if ($user2fa === '1' || $user2fa === 'true') {
    $plainOtp = (string)random_int(100000, 999999);
    $otpHash = password_hash($plainOtp, PASSWORD_DEFAULT);
    $expiresAt = date('Y-m-d H:i:s', strtotime('+10 minutes'));

    $insertStmt = $conn->prepare("INSERT INTO login_otps (email, role, user_id, otp_hash, expires_at, used) VALUES (?, 'user', ?, ?, ?, 0)");
    $insertStmt->bind_param('siss', $email, $user['id'], $otpHash, $expiresAt);
    if (!$insertStmt->execute()) {
        $insertStmt->close();
        http_response_code(500);
        echo json_encode(['success' => false, 'message' => 'Failed to create 2FA OTP']);
        $conn->close();
        exit;
    }
    $otpId = $insertStmt->insert_id;
    $insertStmt->close();

    require_once 'mailer.php';
    $mailResult = send_otp_email($email, $plainOtp, 'user');
    if (!$mailResult['success']) {
        $deleteStmt = $conn->prepare("DELETE FROM login_otps WHERE id = ?");
        $deleteStmt->bind_param('i', $otpId);
        $deleteStmt->execute();
        $deleteStmt->close();

        http_response_code(500);
        echo json_encode(['success' => false, 'message' => $mailResult['message']]);
        $conn->close();
        exit;
    }

    echo json_encode(['success' => true, 'two_factor' => true, 'otp_id' => $otpId, 'message' => '2FA OTP sent to your email']);
    $conn->close();
    exit;
}

clear_failed_logins($conn, $role, $email);

$_SESSION['user_id'] = $user['id'];
$_SESSION['email'] = $user['email'];
$_SESSION['name'] = $user['name'];
$_SESSION['role'] = 'user';
$_SESSION['login_time'] = time();
$_SESSION['session_timeout'] = $sessionTimeoutSeconds;

$updateStmt = $conn->prepare("UPDATE users SET last_login = NOW() WHERE id = ?");
$updateStmt->bind_param('i', $user['id']);
$updateStmt->execute();
$updateStmt->close();

if ($remember) {
    setcookie('user_token', bin2hex(random_bytes(32)), time() + 30 * 24 * 60 * 60, '/');
}

log_login_activity_php($conn, $user['id']);

echo json_encode([
    'success' => true,
    'message' => 'User login successful',
    'redirect' => '../user/index.html'
]);

$conn->close();
?>
