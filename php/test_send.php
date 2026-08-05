<?php
require_once __DIR__ . '/db_config.php';
require_once __DIR__ . '/mailer.php';

$to = 'chandanlohith76@gmail.com';
$otp = (string)random_int(100000, 999999);
$res = send_otp_email($to, $otp, 'registration');
var_export($res);
echo "\n";
?>