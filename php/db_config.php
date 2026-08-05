<?php
function load_env_file($filePath)
{
    if (!file_exists($filePath)) {
        return;
    }

    $lines = file($filePath, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
    foreach ($lines as $line) {
        $trimmed = trim($line);
        if ($trimmed === '' || strpos($trimmed, '#') === 0) {
            continue;
        }

        $parts = explode('=', $trimmed, 2);
        if (count($parts) !== 2) {
            continue;
        }

        $key = trim($parts[0]);
        $value = trim($parts[1]);
        $value = trim($value, "\"'");

        if ($key !== '' && getenv($key) === false) {
            putenv($key . '=' . $value);
            $_ENV[$key] = $value;
        }
    }
}

function env_value($key, $defaultValue = '')
{
    $value = getenv($key);
    if ($value === false || $value === '') {
        return $defaultValue;
    }
    return $value;
}

load_env_file(dirname(__DIR__) . DIRECTORY_SEPARATOR . '.env');

// Database Configuration
define('DB_HOST', env_value('DB_HOST', 'localhost'));
define('DB_USER', env_value('DB_USER', 'root'));
define('DB_PASSWORD', env_value('DB_PASSWORD', ''));
define('DB_NAME', env_value('DB_NAME', 'url_safety'));

// Mailer/app configuration
define('APP_NAME', env_value('APP_NAME', 'URL safety'));
define('ADMIN_EMAIL', env_value('ADMIN_EMAIL', 'youremail@gmail.com'));
define('ADMIN_PASSWORD', env_value('ADMIN_PASSWORD', 'yourpassword'));
define('MAIL_FROM_EMAIL', env_value('MAIL_FROM_EMAIL', 'youremail@gmail.com'));
define('MAIL_FROM_NAME', env_value('MAIL_FROM_NAME', 'URL safety'));
define('MAIL_APP_PASSWORD', env_value('MAIL_APP_PASSWORD', 'yourpassword'));
define('SESSION_TIMEOUT', (int)env_value('SESSION_TIMEOUT', '7200'));

// Create connection and ensure the database exists
$conn = @new mysqli(DB_HOST, DB_USER, DB_PASSWORD, DB_NAME);
if ($conn->connect_error) {
    // Try connecting without selecting a database so we can create it
    $tmp = @new mysqli(DB_HOST, DB_USER, DB_PASSWORD);
    if ($tmp && !$tmp->connect_error) {
        $safeDbName = str_replace('`', '', DB_NAME);
        $createSql = "CREATE DATABASE IF NOT EXISTS `" . $safeDbName . "` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci";
        $tmp->query($createSql);
        $tmp->close();

        // Try connecting again to the newly created (or existing) database
        $conn = @new mysqli(DB_HOST, DB_USER, DB_PASSWORD, DB_NAME);
        if ($conn->connect_error) {
            die(json_encode(['success' => false, 'message' => 'Database connection failed: ' . $conn->connect_error]));
        }
    } else {
        die(json_encode(['success' => false, 'message' => 'Database connection failed: ' . $conn->connect_error]));
    }
}

// Set charset to utf8
$conn->set_charset("utf8mb4");

// Session configuration
ini_set('session.gc_maxlifetime', SESSION_TIMEOUT);
session_set_cookie_params([
    'lifetime' => SESSION_TIMEOUT,
    'path' => '/',
    'httponly' => true,
    'secure' => false, // Set to true if using HTTPS
    'samesite' => 'Lax'
]);

if (!session_id()) {
    session_start();
}
?>
