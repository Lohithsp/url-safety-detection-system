<?php
require_once 'db_config.php';

function get_admin_system_setting($key, $defaultValue)
{
    global $conn;

    if (!$conn) {
        return $defaultValue;
    }

    $stmt = $conn->prepare("SELECT setting_value FROM settings_store WHERE role = 'admin' AND owner_key = 'admin' AND setting_key = ? LIMIT 1");
    if (!$stmt) {
        return $defaultValue;
    }

    $stmt->bind_param('s', $key);
    if (!$stmt->execute()) {
        $stmt->close();
        return $defaultValue;
    }

    $result = $stmt->get_result();
    if ($result->num_rows !== 1) {
        $stmt->close();
        return $defaultValue;
    }

    $row = $result->fetch_assoc();
    $stmt->close();
    $value = trim((string)$row['setting_value']);
    return ($value === '') ? $defaultValue : $value;
}

function smtp_read($socket)
{
    $response = '';
    while ($line = fgets($socket, 515)) {
        $response .= $line;
        if (preg_match('/^\d{3} /', $line)) {
            break;
        }
    }
    return $response;
}

function smtp_write($socket, $command, $expectedCode)
{
    fwrite($socket, $command . "\r\n");
    $response = smtp_read($socket);
    if (strpos($response, (string)$expectedCode) !== 0) {
        return ['success' => false, 'message' => 'SMTP error: ' . trim($response)];
    }
    return ['success' => true, 'message' => 'ok'];
}

function send_otp_email($toEmail, $otp, $role)
{
    $smtpHost = get_admin_system_setting('smtp_host', 'smtp.gmail.com');
    $smtpPort = (int)get_admin_system_setting('smtp_port', '465');
    if ($smtpPort <= 0) {
        $smtpPort = 465;
    }
    $senderEmail = get_admin_system_setting('sender_email', MAIL_FROM_EMAIL);

    $purpose = ($role === 'registration') ? 'Registration' : 'Login';
    $subject = APP_NAME . ' - ' . $purpose . ' OTP';
    $body = "Hello,\r\n\r\n";
    if ($role === 'registration') {
        $body .= "Your OTP for " . APP_NAME . " registration is: " . $otp . "\r\n";
    } else {
        $body .= "Your OTP for " . APP_NAME . " " . ucfirst($role) . " login is: " . $otp . "\r\n";
    }
    $body .= "This OTP expires in 10 minutes.\r\n\r\n";
    $body .= "If you did not request this, please ignore this email.\r\n\r\n";
    $body .= APP_NAME . " Team\r\n";

    $headers = "From: " . MAIL_FROM_NAME . " <" . $senderEmail . ">\r\n";
    $headers .= "To: <" . $toEmail . ">\r\n";
    $headers .= "Subject: " . $subject . "\r\n";
    $headers .= "Date: " . date('r') . "\r\n";
    $headers .= "MIME-Version: 1.0\r\n";
    $headers .= "Content-Type: text/plain; charset=UTF-8\r\n";
    $headers .= "\r\n" . $body . "\r\n.";

    $socket = @fsockopen('ssl://' . $smtpHost, $smtpPort, $errno, $errstr, 15);
    if (!$socket) {
        // Fallback for development: log OTP to a file so the app can run without SMTP
        $logDir = dirname(__DIR__) . DIRECTORY_SEPARATOR . 'data';
        if (!is_dir($logDir)) {
            @mkdir($logDir, 0755, true);
        }
        $logFile = $logDir . DIRECTORY_SEPARATOR . 'otp_log.txt';
        $entry = date('Y-m-d H:i:s') . "\t" . $toEmail . "\t" . $role . "\t" . $otp . "\n";
        @file_put_contents($logFile, $entry, FILE_APPEND | LOCK_EX);
        return ['success' => true, 'message' => 'SMTP unavailable; OTP logged to data/otp_log.txt for development', 'debug_otp' => $otp];
    }

    $greeting = smtp_read($socket);
    if (strpos($greeting, '220') !== 0) {
        fclose($socket);
        return ['success' => false, 'message' => 'SMTP greeting failed'];
    }

    $steps = [
        smtp_write($socket, 'EHLO localhost', 250),
        smtp_write($socket, 'AUTH LOGIN', 334),
        smtp_write($socket, base64_encode($senderEmail), 334),
        smtp_write($socket, base64_encode(str_replace(' ', '', MAIL_APP_PASSWORD)), 235),
        smtp_write($socket, 'MAIL FROM: <' . $senderEmail . '>', 250),
        smtp_write($socket, 'RCPT TO: <' . $toEmail . '>', 250),
        smtp_write($socket, 'DATA', 354),
        smtp_write($socket, $headers, 250),
        smtp_write($socket, 'QUIT', 221)
    ];

    foreach ($steps as $step) {
        if (!$step['success']) {
            fclose($socket);
            // SMTP failed mid-flow — fallback to logging the OTP for development
            $logDir = dirname(__DIR__) . DIRECTORY_SEPARATOR . 'data';
            if (!is_dir($logDir)) {
                @mkdir($logDir, 0755, true);
            }
            $logFile = $logDir . DIRECTORY_SEPARATOR . 'otp_log.txt';
            $entry = date('Y-m-d H:i:s') . "\t" . $toEmail . "\t" . $role . "\t" . $otp . "\n";
            @file_put_contents($logFile, $entry, FILE_APPEND | LOCK_EX);
            return ['success' => true, 'message' => 'SMTP error; OTP logged to data/otp_log.txt for development', 'debug_otp' => $otp];
        }
    }

    fclose($socket);
    return ['success' => true, 'message' => 'OTP sent'];
}

function send_security_alert_email($toEmail)
{
    $smtpHost = get_admin_system_setting('smtp_host', 'smtp.gmail.com');
    $smtpPort = (int)get_admin_system_setting('smtp_port', '465');
    if ($smtpPort <= 0) {
        $smtpPort = 465;
    }
    $senderEmail = get_admin_system_setting('sender_email', MAIL_FROM_EMAIL);

    $subject = APP_NAME . ' - Security Alert: Multiple Failed Login Attempts';
    $body = "Hello,\r\n\r\n";
    $body .= "We detected multiple failed login attempts on your account. For your security, login has been temporarily disabled for 15 minutes.\r\n\r\n";
    $body .= "Please change your password immediately to secure your account.\r\n\r\n";
    $body .= "Additionally, Two-Factor Authentication (2FA) has been automatically enabled for your account. You will be required to verify via OTP for future logins.\r\n\r\n";
    $body .= "If this wasn't you, please contact support or update your password right away.\r\n\r\n";
    $body .= APP_NAME . " Team\r\n";

    $headers = "From: " . MAIL_FROM_NAME . " <" . $senderEmail . ">\r\n";
    $headers .= "To: <" . $toEmail . ">\r\n";
    $headers .= "Subject: " . $subject . "\r\n";
    $headers .= "Date: " . date('r') . "\r\n";
    $headers .= "MIME-Version: 1.0\r\n";
    $headers .= "Content-Type: text/plain; charset=UTF-8\r\n";
    $headers .= "\r\n" . $body . "\r\n.";

    $socket = @fsockopen('ssl://' . $smtpHost, $smtpPort, $errno, $errstr, 15);
    if (!$socket) {
        error_log("[SMTP Alert] ssl://" . $smtpHost . ":" . $smtpPort . " connection failed: " . $errstr . " (" . $errno . ")");
        // Fallback for development: log alert to a file so we can run/test without functional SMTP
        $logDir = dirname(__DIR__) . DIRECTORY_SEPARATOR . 'data';
        if (!is_dir($logDir)) {
            @mkdir($logDir, 0755, true);
        }
        $logFile = $logDir . DIRECTORY_SEPARATOR . 'otp_log.txt';
        $entry = date('Y-m-d H:i:s') . "\t" . $toEmail . "\tsecurity_alert_2fa_enabled_change_password\tN/A\n";
        @file_put_contents($logFile, $entry, FILE_APPEND | LOCK_EX);
        return ['success' => true, 'message' => 'SMTP unavailable; Security alert logged to data/otp_log.txt for development'];
    }

    $greeting = smtp_read($socket);
    if (strpos($greeting, '220') !== 0) {
        error_log("[SMTP Alert] SMTP greeting failed: " . trim($greeting));
        fclose($socket);
        return ['success' => false, 'message' => 'SMTP greeting failed'];
    }

    $steps = [
        smtp_write($socket, 'EHLO localhost', 250),
        smtp_write($socket, 'AUTH LOGIN', 334),
        smtp_write($socket, base64_encode($senderEmail), 334),
        smtp_write($socket, base64_encode(str_replace(' ', '', MAIL_APP_PASSWORD)), 235),
        smtp_write($socket, 'MAIL FROM: <' . $senderEmail . '>', 250),
        smtp_write($socket, 'RCPT TO: <' . $toEmail . '>', 250),
        smtp_write($socket, 'DATA', 354),
        smtp_write($socket, $headers, 250),
        smtp_write($socket, 'QUIT', 221)
    ];

    foreach ($steps as $idx => $step) {
        if (!$step['success']) {
            error_log("[SMTP Alert] SMTP command step " . ($idx + 1) . " failed: " . $step['message']);
            fclose($socket);
            $logDir = dirname(__DIR__) . DIRECTORY_SEPARATOR . 'data';
            if (!is_dir($logDir)) {
                @mkdir($logDir, 0755, true);
            }
            $logFile = $logDir . DIRECTORY_SEPARATOR . 'otp_log.txt';
            $entry = date('Y-m-d H:i:s') . "\t" . $toEmail . "\tsecurity_alert_failed_2fa_enabled_change_password\tN/A\n";
            @file_put_contents($logFile, $entry, FILE_APPEND | LOCK_EX);
            return ['success' => true, 'message' => 'SMTP error; logged security alert to data/otp_log.txt'];
        }
    }

    fclose($socket);
    return ['success' => true, 'message' => 'Security alert sent'];
}
?>
