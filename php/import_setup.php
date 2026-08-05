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

$host = env_value('DB_HOST', 'localhost');
$user = env_value('DB_USER', 'root');
$pass = env_value('DB_PASSWORD', '');
$dbname = env_value('DB_NAME', 'url_safety');

echo "Using DB host={$host}, user={$user}, db={$dbname}\n";

$mysqli = new mysqli($host, $user, $pass);
if ($mysqli->connect_error) {
    fwrite(STDERR, "Connection failed: " . $mysqli->connect_error . "\n");
    exit(1);
}

$sqlFile = __DIR__ . DIRECTORY_SEPARATOR . 'setup.sql';
if (!file_exists($sqlFile)) {
    fwrite(STDERR, "SQL file not found: {$sqlFile}\n");
    exit(1);
}

$sql = file_get_contents($sqlFile);
if ($sql === false) {
    fwrite(STDERR, "Failed to read SQL file\n");
    exit(1);
}

// Ensure database exists
if (!$mysqli->query("CREATE DATABASE IF NOT EXISTS `" . $mysqli->real_escape_string($dbname) . "` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")) {
    fwrite(STDERR, "Failed to create database: " . $mysqli->error . "\n");
    exit(1);
}

// Select the database
if (!$mysqli->select_db($dbname)) {
    fwrite(STDERR, "Failed to select database: " . $mysqli->error . "\n");
    exit(1);
}

// Execute SQL file (may contain multiple statements)
if ($mysqli->multi_query($sql)) {
    do {
        if ($res = $mysqli->store_result()) {
            $res->free();
        }
    } while ($mysqli->more_results() && $mysqli->next_result());
    echo "Imported SQL into {$dbname}\n";
} else {
    fwrite(STDERR, "Failed to import SQL: " . $mysqli->error . "\n");
    exit(1);
}

echo "Done.\n";

$mysqli->close();

?>
