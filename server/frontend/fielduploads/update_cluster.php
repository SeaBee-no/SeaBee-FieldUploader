<?php
require '/var/www/authenticate.php';
authenticate("SeaBee fielduploads");
// Minimal endpoint to persist edits from the left‐pane form
require '/var/www/vultrdbconfig.php';
$dbname = 'fielduploads';
try {
    $conn = new PDO(
      "pgsql:host=$host;dbname=$dbname",
      $dbuser,
      $dbpassword,
      [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]
    );
} catch (Exception $e) {
    http_response_code(500);
    echo json_encode(['success' => false, 'error' => 'DB connection failed']);
    exit;
}

header('Content-Type: application/json');
$input = json_decode(file_get_contents('php://input'), true);
if (empty($input['cluster_id'])) {
    echo json_encode(['success' => false, 'error' => 'Missing cluster_id']);
    exit;
}

// Fields we allow updating:
$allowed = [
    'grouping',
    'area',
    'datetime',
    'creator_name',
    'project',
    'theme',
    'organisation',
    'mosaic',
    'classify',
    'skip',
    'publish',
    'readyforsigma'
];

$sets   = [];
$params = [':id' => (int)$input['cluster_id']];

foreach ($allowed as $f) {
    if (isset($input[$f])) {
        // Build SET clause
        $sets[] = "\"$f\" = :$f";
        // Cast booleans for the three flag fields
        if (in_array($f, ['mosaic','classify','publish','readyforsigma','skip'], true)) {
            $params[":$f"] = filter_var($input[$f], FILTER_VALIDATE_BOOLEAN) ? 'TRUE' : 'FALSE';
        } else {
            $params[":$f"] = $input[$f];
        }
    }
}

if (empty($sets)) {
    echo json_encode(['success' => false, 'error' => 'No updatable fields']);
    exit;
}

$sql = "UPDATE clusters SET " . implode(', ', $sets) . " WHERE id = :id;";
$stmt = $conn->prepare($sql);

try {
    $stmt->execute($params);
    echo json_encode(['success' => true]);
} catch (Exception $e) {
    echo json_encode(['success' => false, 'error' => $e->getMessage()]);
}
?>