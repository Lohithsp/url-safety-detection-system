<?php
header('Content-Type: application/json');
require_once 'db_config.php';

// Clear session
$_SESSION = [];
session_destroy();

// Clear cookies
setcookie('admin_token', '', time() - 3600, '/');
setcookie('user_token', '', time() - 3600, '/');

echo json_encode([
    'success' => true,
    'message' => 'Logged out successfully',
    'redirect' => '../index.html'
]);
?>
