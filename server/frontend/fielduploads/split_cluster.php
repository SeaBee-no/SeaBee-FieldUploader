<?php
require '/var/www/authenticate.php';
authenticate("SeaBee fielduploads");
// split_cluster.php
require '/var/www/vultrdbconfig.php';
$dbname = 'fielduploads';
header('Content-Type: application/json');

$in = json_decode(file_get_contents('php://input'), true);
if (empty($in['cluster_id']) || empty($in['polygon'])) {
    echo json_encode(['success'=>false,'error'=>'Missing cluster_id or polygon']);
    exit;
}
$cid     = (int)$in['cluster_id'];
$polyGeo = json_encode($in['polygon']);

try {
    $pdo = new PDO(
      "pgsql:host=$host;dbname=$dbname",
      $dbuser, $dbpassword,
      [PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]
    );
    $pdo->beginTransaction();

    // 1) new cluster ID
    $newId = (int)$pdo
      ->query("SELECT COALESCE(MAX(id),0)+1 FROM clusters")
      ->fetchColumn();

    // 2) move points INSIDE polygon to new cluster
    $pdo->exec("
      UPDATE files
         SET cluster_id = $newId
       WHERE cluster_id = $cid
         AND ST_Within(
               geom,
               ST_SetSRID(
                 ST_GeomFromGeoJSON('$polyGeo')::geometry,
                 4326
               )
             );
    ");

    // 3) clone metadata
    $pdo->exec("
      INSERT INTO clusters (
        id, grouping, area, \"datetime\", nfiles,
        organisation, mosaic, classify, publish, theme,
        spectrum_type, elevation, creator_name, project, vehicle, sensor,
        licence, licence_link,
        odm_dsm, odm_dtm, odm_cog,
        odm_orthophoto_compression, odm_orthophoto_resolution,
        odm_dem_resolution, odm_max_concurrency,
        odm_auto_boundary, odm_use_3dmesh, odm_fast_orthophoto,
        odm_pc_rectify, odm_split, odm_split_overlap,
        odm_crop, odm_pc_quality, odm_feature_quality,
        odm_radiometric_calibration,
        ml_task, ml_model,
        centroid_lon, centroid_lat, min_datetime,
        readyforsigma, senttosigma
      )
      SELECT
        $newId, grouping, area, \"datetime\", nfiles,
        organisation, mosaic, classify, publish, theme,
        spectrum_type, elevation, creator_name, project, vehicle, sensor,
        licence, licence_link,
        odm_dsm, odm_dtm, odm_cog,
        odm_orthophoto_compression, odm_orthophoto_resolution,
        odm_dem_resolution, odm_max_concurrency,
        odm_auto_boundary, odm_use_3dmesh, odm_fast_orthophoto,
        odm_pc_rectify, odm_split, odm_split_overlap,
        odm_crop, odm_pc_quality, odm_feature_quality,
        odm_radiometric_calibration,
        ml_task, ml_model,
        centroid_lon, centroid_lat, min_datetime,
        readyforsigma, senttosigma
      FROM clusters
      WHERE id = $cid;
    ");

    // 4) recompute stats for new cluster
    $newStats = $pdo->query("
      SELECT COUNT(*) AS cnt, MIN(datetimetaken) AS mindt
        FROM files
       WHERE cluster_id = $newId
    ")->fetch(PDO::FETCH_ASSOC);
    $newCount = (int)$newStats['cnt'];
    $newMinDt = $newStats['mindt'];
    $newDtStr = $newMinDt ? date('YmdHi', strtotime($newMinDt)) : null;
    $pdo->prepare("
      UPDATE clusters
         SET nfiles       = :cnt,
             \"datetime\" = :dtstr,
             min_datetime = :mindt
       WHERE id = :nid
    ")->execute([
      ':cnt'   => $newCount,
      ':dtstr' => $newDtStr,
      ':mindt' => $newMinDt,
      ':nid'   => $newId
    ]);

    // 5) recompute stats for original cluster
    $origStats = $pdo->query("
      SELECT COUNT(*) AS cnt, MIN(datetimetaken) AS mindt
        FROM files
       WHERE cluster_id = $cid
    ")->fetch(PDO::FETCH_ASSOC);
    $origCount = (int)$origStats['cnt'];
    $origMinDt = $origStats['mindt'];
    $origDtStr = $origMinDt ? date('YmdHi', strtotime($origMinDt)) : null;
    $pdo->prepare("
      UPDATE clusters
         SET nfiles       = :cnt,
             \"datetime\" = :dtstr,
             min_datetime = :mindt
       WHERE id = :cid
    ")->execute([
      ':cnt'   => $origCount,
      ':dtstr' => $origDtStr,
      ':mindt' => $origMinDt,
      ':cid'   => $cid
    ]);

    $pdo->commit();

    // 6) fetch bounds
    $b1 = $pdo->query("
      SELECT MIN(ST_X(geom)) AS minx, MIN(ST_Y(geom)) AS miny,
             MAX(ST_X(geom)) AS maxx, MAX(ST_Y(geom)) AS maxy
        FROM files WHERE cluster_id = $cid
    ")->fetch(PDO::FETCH_ASSOC);
    $b2 = $pdo->query("
      SELECT MIN(ST_X(geom)) AS minx, MIN(ST_Y(geom)) AS miny,
             MAX(ST_X(geom)) AS maxx, MAX(ST_Y(geom)) AS maxy
        FROM files WHERE cluster_id = $newId
    ")->fetch(PDO::FETCH_ASSOC);

    echo json_encode([
      'success' => true,
      'new_id'  => $newId,
      'bounds1' => [
        'minX'=> (float)$b1['minx'], 'minY'=> (float)$b1['miny'],
        'maxX'=> (float)$b1['maxx'], 'maxY'=> (float)$b1['maxy']
      ],
      'bounds2' => [
        'minX'=> (float)$b2['minx'], 'minY'=> (float)$b2['miny'],
        'maxX'=> (float)$b2['maxx'], 'maxY'=> (float)$b2['maxy']
      ],
    ]);
} catch (Exception $e) {
    if (isset($pdo)) $pdo->rollBack();
    echo json_encode(['success'=>false,'error'=>$e->getMessage()]);
}
?>