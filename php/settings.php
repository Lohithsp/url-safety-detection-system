<?php
header('Content-Type: application/json');
require_once 'db_config.php';

// Allow anonymous/local settings in development with env flag
$allowAnon = false;
$envAllow = getenv('ALLOW_ANON_SETTINGS');
if ($envAllow !== false && (strtolower($envAllow) === '1' || strtolower($envAllow) === 'true')) {
    $allowAnon = true;
}

if (!isset($_SESSION['role']) || !isset($_SESSION['email'])) {
    if (!$allowAnon) {
        http_response_code(401);
        die(json_encode(['success' => false, 'message' => 'Unauthorized']));
    }
    // fallback to a local owner when anonymous access is allowed
    $_SESSION['role'] = 'user';
    $_SESSION['email'] = 'local@local';
    // note: do not persist these sentinel values anywhere sensitive
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

$action = isset($input['action']) ? trim($input['action']) : '';
$role = $_SESSION['role'];
$ownerKey = ($role === 'admin') ? 'admin' : $_SESSION['email'];

$createTableSql = "CREATE TABLE IF NOT EXISTS settings_store (
    id INT AUTO_INCREMENT PRIMARY KEY,
    role ENUM('admin', 'user') NOT NULL,
    owner_key VARCHAR(120) NOT NULL,
    setting_key VARCHAR(120) NOT NULL,
    setting_value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_owner_setting (role, owner_key, setting_key),
    INDEX idx_owner (role, owner_key)
)";

if (!$conn->query($createTableSql)) {
    http_response_code(500);
    die(json_encode(['success' => false, 'message' => 'Failed to initialize settings storage']));
}

if ($action === 'get') {
    $stmt = $conn->prepare("SELECT setting_key, setting_value FROM settings_store WHERE role = ? AND owner_key = ?");
    $stmt->bind_param('ss', $role, $ownerKey);
    $stmt->execute();
    $result = $stmt->get_result();

    $settings = [];
    while ($row = $result->fetch_assoc()) {
        $settings[$row['setting_key']] = $row['setting_value'];
    }

    $stmt->close();
    echo json_encode(['success' => true, 'settings' => $settings, 'role' => $role]);
    $conn->close();
    exit;
}

if ($action === 'save') {
    if (!isset($input['settings']) || !is_array($input['settings'])) {
        http_response_code(400);
        die(json_encode(['success' => false, 'message' => 'Settings payload is required']));
    }

    $settings = $input['settings'];
    $stmt = $conn->prepare("INSERT INTO settings_store (role, owner_key, setting_key, setting_value) VALUES (?, ?, ?, ?) ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)");

    foreach ($settings as $key => $value) {
        $cleanKey = preg_replace('/[^a-zA-Z0-9_\-\.]/', '', (string)$key);
        if ($cleanKey === '') {
            continue;
        }
        $cleanValue = is_bool($value) ? ($value ? '1' : '0') : trim((string)$value);
        $stmt->bind_param('ssss', $role, $ownerKey, $cleanKey, $cleanValue);
        $stmt->execute();
    }

    $stmt->close();
    echo json_encode(['success' => true, 'message' => 'Settings saved successfully']);
    $conn->close();
    exit;
}

http_response_code(400);
echo json_encode(['success' => false, 'message' => 'Invalid action']);
$conn->close();
?>
