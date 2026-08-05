<?php
require_once __DIR__ . '/../php/db_config.php';
$k = 'two_factor_user';
$v = '1';
$stmt = $conn->prepare('INSERT INTO settings_store (role, owner_key, setting_key, setting_value) VALUES (?, ?, ?, ?) ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)');
$role = 'admin';
$owner = 'admin';
$stmt->bind_param('ssss', $role, $owner, $k, $v);
$stmt->execute();
echo "two_factor_user enabled\n";
?>