<?php
require '/var/www/authenticate.php';
authenticate("SeaBee fielduploads");
// Returns per‐cluster summary + individual image points
require '/var/www/vultrdbconfig.php';
$dbname = 'fielduploads';
$conn = new PDO(
    "pgsql:host=$host;dbname=$dbname",
    $dbuser,
    $dbpassword,
    [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]
);
header('Access-Control-Allow-Origin: *');
header('Content-Type: application/json');

// Must pass cluster_id
if (empty($_GET['cluster_id'])) {
    http_response_code(400);
    echo json_encode(['error' => 'Missing cluster_id']);
    exit;
}
$cid = (int)$_GET['cluster_id'];

// 1) Summary stats
$sqlSummary = "
    SELECT
      COUNT(*)           AS nfiles,
      MIN(datetimetaken) AS first_timestamp,
      MAX(datetimetaken) AS last_timestamp
    FROM files
    WHERE cluster_id = :cid
      AND datetimetaken IS NOT NULL;
";
$stmt = $conn->prepare($sqlSummary);
$stmt->bindValue(':cid', $cid, PDO::PARAM_INT);
$stmt->execute();
$sum = $stmt->fetch(PDO::FETCH_ASSOC) ?: [
    'nfiles'=>0, 'first_timestamp'=>null, 'last_timestamp'=>null
];

// 2) Unique directories
$sqlDirs = "
    SELECT DISTINCT directory
    FROM files
    WHERE cluster_id = :cid;
";
$stmt = $conn->prepare($sqlDirs);
$stmt->bindValue(':cid', $cid, PDO::PARAM_INT);
$stmt->execute();
$dirs = $stmt->fetchAll(PDO::FETCH_COLUMN);

// 3) Point features
$sqlPts = "
    SELECT
      id         AS file_id,
      filename,
      datetimetaken,
      directory,
      cluster_id,
      ST_X(geom) AS lon,
      ST_Y(geom) AS lat
    FROM files
    WHERE geom IS NOT NULL
      AND cluster_id = :cid;
";
$stmt = $conn->prepare($sqlPts);
$stmt->bindValue(':cid', $cid, PDO::PARAM_INT);
$stmt->execute();
$rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

// Build geoJSON
$features = [];
foreach ($rows as $r) {
    $features[] = [
        'type'       => 'Feature',
        'properties' => $r,
        'geometry'   => [
            'type'        => 'Point',
            'coordinates' => [
                (float)$r['lon'],
                (float)$r['lat']
            ]
        ]
    ];
}

echo json_encode([
  'type'     => 'FeatureCollection',
  'summary'  => [
    'cluster_id'      => $cid,
    'nfiles'          => (int)$sum['nfiles'],
    'first_timestamp'=> $sum['first_timestamp'],
    'last_timestamp' => $sum['last_timestamp'],
    'directories'    => $dirs
  ],
  'features' => $features
]);
?>