<?php
require '/var/www/authenticate.php';
authenticate("SeaBee fielduploads");
// merge_clusters.php
require '/var/www/vultrdbconfig.php';
$dbname = 'fielduploads';
header('Content-Type: application/json');

$in = json_decode(file_get_contents('php://input'), true);
if (empty($in['clusters']) || count($in['clusters']) < 2) {
    echo json_encode(['success'=>false,'error'=>'Need at least two cluster IDs']);
    exit;
}
$ids = array_map('intval', $in['clusters']);
sort($ids);
$keep = array_shift($ids);

try {
    $pdo = new PDO("pgsql:host=$host;dbname=$dbname", $dbuser, $dbpassword);
    $pdo->beginTransaction();

    // Reassign files
    $inList = implode(',', $ids);
    $pdo->exec("UPDATE files SET cluster_id = $keep WHERE cluster_id IN ($inList)");

    // Delete old clusters
    $pdo->exec("DELETE FROM clusters WHERE id IN ($inList)");

    $pdo->commit();
    echo json_encode(['success'=>true,'new_id'=>$keep]);
} catch (Exception $e) {
    $pdo->rollBack();
    echo json_encode(['success'=>false,'error'=>$e->getMessage()]);
}
?>