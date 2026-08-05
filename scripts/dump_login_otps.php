<?php
require_once __DIR__ . '/../php/db_config.php';
$res = $conn->query('SELECT id,email,role,expires_at,used,created_at FROM login_otps ORDER BY id DESC LIMIT 10');
while($r = $res->fetch_assoc()) {
    echo json_encode($r) . PHP_EOL;
}
?>