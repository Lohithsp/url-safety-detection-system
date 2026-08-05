<?php
require_once __DIR__ . '/db_config.php';

$email = $argv[1] ?? 'testuser@example.com';
$name = $argv[2] ?? 'Test User';
$password = $argv[3] ?? 'TestPass123';

if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
    fwrite(STDERR, "Invalid email\n");
    exit(1);
}

$passwordHash = password_hash($password, PASSWORD_BCRYPT);

$stmt = $conn->prepare("INSERT INTO users (name, email, password, role, status, registration_date, approved_date) VALUES (?, ?, ?, 'user', 'approved', NOW(), NOW()) ON DUPLICATE KEY UPDATE name = VALUES(name), password = VALUES(password), status = 'approved', approved_date = NOW(), role = 'user'");
$stmt->bind_param('sss', $name, $email, $passwordHash);

if ($stmt->execute()) {
    echo "User ensured: {$email}\n";
    exit(0);
} else {
    fwrite(STDERR, "Failed to create user: " . $stmt->error . "\n");
    exit(1);
}

$stmt->close();
$conn->close();

?>
