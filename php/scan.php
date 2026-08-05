<?php
header('Content-Type: application/json');
require_once 'db_config.php';

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['success' => false, 'message' => 'Method not allowed']);
    exit;
}

$input = json_decode(file_get_contents('php://input'), true);
if (!is_array($input)) {
    http_response_code(400);
    echo json_encode(['success' => false, 'message' => 'Invalid JSON body']);
    exit;
}

$url = isset($input['url']) ? trim((string)$input['url']) : '';
if ($url === '') {
    http_response_code(400);
    echo json_encode(['success' => false, 'message' => 'URL is required']);
    exit;
}

if (!preg_match('~^https?://~i', $url)) {
    $url = 'https://' . $url;
}

if (!filter_var($url, FILTER_VALIDATE_URL)) {
    http_response_code(400);
    echo json_encode(['success' => false, 'message' => 'Enter a valid URL']);
    exit;
}

function add_signal(array &$signals, string $label, string $value, int $points): void
{
    $signals[] = [
        'label' => $label,
        'value' => $value,
        'points' => $points,
    ];
}

function classify_score(int $score): array
{
    if ($score >= 6) {
        return ['status' => 'malicious', 'title' => 'Malicious', 'pillClass' => 'status-malicious'];
    }

    if ($score >= 3) {
        return ['status' => 'suspicious', 'title' => 'Suspicious', 'pillClass' => 'status-suspicious'];
    }

    return ['status' => 'safe', 'title' => 'Safe', 'pillClass' => 'status-safe'];
}

$parts = parse_url($url);
$host = strtolower($parts['host'] ?? '');
$path = (string)($parts['path'] ?? '');
$query = (string)($parts['query'] ?? '');
$signals = [];
$score = 0;

if ($host === '') {
    add_signal($signals, 'Host', 'Missing host component', 3);
    $score += 3;
}

if (filter_var($host, FILTER_VALIDATE_IP)) {
    add_signal($signals, 'Host type', 'IP address used instead of domain', 3);
    $score += 3;
}

$hostLabels = array_values(array_filter(explode('.', $host)));
if (count($hostLabels) >= 4) {
    add_signal($signals, 'Subdomains', 'Deep subdomain chain detected', 2);
    $score += 2;
}

if (strlen($url) > 120) {
    add_signal($signals, 'Length', 'URL is unusually long', 1);
    $score += 1;
}

if (preg_match('~(login|secure|verify|account|update|reset|signin|auth|bank|wallet|bonus|claim|free|gift|reward|prize)~i', $url)) {
    add_signal($signals, 'Keywords', 'Credential or urgency-related wording detected', 2);
    $score += 2;
}

if (preg_match('~(login|signin|verify|secure)~i', $host) && preg_match('~(login|signin|verify|secure)~i', $path . '?' . $query)) {
    add_signal($signals, 'Brand trust', 'Security/login wording appears in more than one part of the URL', 1);
    $score += 1;
}

if (preg_match('~verify-user|secure-login|account-login|signin-secure|login-secure~i', $host)) {
    add_signal($signals, 'Brand trust', 'Compound login/verify wording detected in the host', 2);
    $score += 2;
}

if (preg_match('~(bit\.ly|tinyurl|t\.co|goo\.gl|ow\.ly|is\.gd|buff\.ly|cutt\.ly|rebrand\.ly)~i', $host)) {
    add_signal($signals, 'Redirects', 'URL shortener detected', 3);
    $score += 3;
}

if (preg_match('~xn--~i', $host)) {
    add_signal($signals, 'Domain encoding', 'Punycode / IDN encoding detected', 2);
    $score += 2;
}

if (preg_match('~[^a-z0-9\-.]~i', $host)) {
    add_signal($signals, 'Host characters', 'Unusual characters found in host', 2);
    $score += 2;
}

if (preg_match('~@~', $url)) {
    add_signal($signals, 'Credentials trick', 'At-sign used in URL pattern', 3);
    $score += 3;
}

if (preg_match('~https?://[^/]+/.*[\?&](redirect|url|next|goto|dest)=~i', $url)) {
    add_signal($signals, 'Redirect parameters', 'Redirect-style query parameter detected', 2);
    $score += 2;
}

if (preg_match('~(\.|-){2,}~', $host)) {
    add_signal($signals, 'Structure', 'Repeated separators in domain', 1);
    $score += 1;
}

if (substr_count($host, '-') >= 2) {
    add_signal($signals, 'Structure', 'Multiple hyphens found in host name', 1);
    $score += 1;
}

if ($score === 0) {
    add_signal($signals, 'Structure', 'No obvious high-risk patterns detected', 0);
}

$classification = classify_score($score);
$label = $classification['title'];
$pillClass = $classification['pillClass'];

if ($classification['status'] === 'safe') {
    $explanation = 'The URL looks consistent with a normal destination and no strong phishing indicators were found in the backend rules.';
} elseif ($classification['status'] === 'suspicious') {
    $explanation = 'The backend found patterns that deserve review, such as login-style wording, structure issues, or redirection cues.';
} else {
    $explanation = 'The backend matched multiple high-risk indicators that are commonly used in phishing or deceptive redirect URLs.';
}

$featureMap = [
    ['label' => 'URL structure', 'value' => $host === '' ? 'Invalid host' : $host],
    ['label' => 'Risk score', 'value' => (string)$score],
    ['label' => 'Backend verdict', 'value' => $label],
];

$userId = null;
if (isset($_SESSION['user_id']) && is_numeric($_SESSION['user_id'])) {
    $userId = (int)$_SESSION['user_id'];
}

$details = [
    'url' => $url,
    'host' => $host,
    'score' => $score,
    'status' => $classification['status'],
    'signals' => $signals,
    'checked_at' => date('c'),
];

$conn->query("CREATE TABLE IF NOT EXISTS url_scans (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    url VARCHAR(2048) NOT NULL,
    status ENUM('safe', 'suspicious', 'malicious') NOT NULL,
    detection_details JSON,
    scan_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_user_id (user_id),
    INDEX idx_scan_date (scan_date)
)");

if ($userId !== null) {
    $status = $classification['status'];
    $detailsJson = json_encode($details);
    $insertStmt = $conn->prepare('INSERT INTO url_scans (user_id, url, status, detection_details) VALUES (?, ?, ?, ?)');
    if ($insertStmt) {
        $insertStmt->bind_param('isss', $userId, $url, $status, $detailsJson);
        $insertStmt->execute();
        $insertStmt->close();
    }
}

echo json_encode([
    'success' => true,
    'status' => $classification['status'],
    'status_label' => $label,
    'pillClass' => $pillClass,
    'explanation' => $explanation,
    'features' => $featureMap,
    'signals' => $signals,
    'score' => $score,
    'url' => $url,
    'details' => $details,
]);
$conn->close();
?>