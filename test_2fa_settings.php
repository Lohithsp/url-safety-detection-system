<?php
require_once 'php/db_config.php';

// Query current 2FA settings
$sql = "SELECT role, owner_key, setting_key, setting_value FROM settings_store WHERE (setting_key = 'two_factor_admin' OR setting_key = 'two_factor_user') ORDER BY role, owner_key, setting_key";
$result = $conn->query($sql);

echo "Current 2FA Settings:\n";
echo "====================\n";

if ($result->num_rows > 0) {
    while ($row = $result->fetch_assoc()) {
        echo "Role: {$row['role']}, Owner: {$row['owner_key']}, Setting: {$row['setting_key']}, Value: {$row['setting_value']}\n";
    }
} else {
    echo "No 2FA settings found in database.\n";
}

$conn->close();
?>
