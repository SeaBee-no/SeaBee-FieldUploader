<?php
require '/var/www/authenticate.php';
authenticate("SeaBee fielduploads");
// Returns cluster polygons with settings
require '/var/www/vultrdbconfig.php';
$dbname = 'fielduploads';
$conn = new PDO("pgsql:host=$host;dbname=$dbname", $dbuser, $dbpassword);
$conn->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
header('Access-Control-Allow-Origin: *');

$sql = "
    SELECT c.id as cluster_id,
           c.grouping,
           c.area,
           c.datetime,
           c.nfiles,
           c.organisation,
           c.mosaic,
           c.classify,
           c.publish,
           c.theme,
           c.creator_name,
           c.project,
           c.readyforsigma,
           c.skip,
           ST_AsGeoJSON(ST_ConvexHull(ST_Collect(f.geom))) AS geom
    FROM clusters c
    JOIN files f ON f.cluster_id = c.id
    WHERE f.geom IS NOT NULL
    GROUP BY c.id
    ORDER BY c.id;
";
$stmt = $conn->prepare($sql);
$stmt->execute();
$rows = $stmt->fetchAll(PDO::FETCH_ASSOC);
$features = [];
foreach ($rows as $r) {
    $geom = json_decode($r['geom'], true);
    unset($r['geom']);
    $features[] = [
        'type' => 'Feature',
        'properties' => $r,
        'geometry' => $geom
    ];
}
echo json_encode(['type'=>'FeatureCollection','features'=>$features]);
?>