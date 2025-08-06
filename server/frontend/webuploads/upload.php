<?php

error_reporting(E_ALL);
ini_set('display_errors', 1);

require '/var/www/authenticate.php';
authenticate("SeaBee webuploads");

require '/var/www/vendor/autoload.php';
use Aws\S3\S3Client;
use Symfony\Component\Yaml\Yaml;

date_default_timezone_set('Europe/Oslo');

// reuse the client-side timestamp if present
$timestamp = $_POST['upload_timestamp'] ?? date('YmdHis');
$folder    = "webuploader_uploads_{$timestamp}/";

// prepare a per‐upload staging dir
$tmpdir = sys_get_temp_dir() . "/webupload_{$timestamp}";
if (!is_dir($tmpdir)) {
    mkdir($tmpdir, 0777, true);
}

// write metadata
$meta = [
    'theme'        => $_POST['theme']        ?? '',
    'organisation' => $_POST['organisation'] ?? '',
    'creator_name' => $_POST['creator_name'] ?? '',
    'project'      => $_POST['project']      ?? '',
];
file_put_contents("$tmpdir/fielduploads.seabee.yaml", Yaml::dump($meta, 2, 2));

// move only allowed files into staging
$allowed = ['jpg','jpeg','mrk','rtk','nav','obs','bin'];
if (empty($_FILES['files']['tmp_name']) || !is_array($_FILES['files']['tmp_name'])) {
    echo "<p class='error'>❌ No files received — check your PHP limits!</p>";
    exit;
}
foreach ($_FILES['files']['tmp_name'] as $i => $tmp) {
    $name = $_FILES['files']['name'][$i];
    $ext  = strtolower(pathinfo($name, PATHINFO_EXTENSION));
    if (in_array($ext, $allowed)) {
        move_uploaded_file($tmp, "$tmpdir/$name");
    }
}

// S3 client
$s3 = new S3Client([
    'region'   => 'us-east-1',
    'version'  => 'latest',
    'endpoint' => 'https://storage.seabee.sigma2.no',
    'credentials' => [
        'key'    => $S3KEY,
        'secret' => $S3SECRET,
    ],
    'use_path_style_endpoint' => true,
]);
$bucket = 'seabirds';
$prefix = 'fielduploads2025/';

// upload every file in staging to the *same* S3 folder
foreach (scandir($tmpdir) as $file) {
    if ($file === '.' || $file === '..') continue;
    $local = "$tmpdir/$file";
    $key   = $prefix . $folder . $file;
    try {
        $s3->putObject([
            'Bucket'     => $bucket,
            'Key'        => $key,
            'SourceFile' => $local,
            'ACL'        => 'private',
        ]);
    } catch (Exception $e) {
        echo "<p class='error'>❌ Upload error for {$file}: {$e->getMessage()}</p>";
        exit;
    }
}

// cleanup staging (only if this is the final batch you want to remove)
array_map('unlink', glob("$tmpdir/*"));
rmdir($tmpdir);

// success
echo "<p class='success'>✅ Batch complete!</p>";
echo "<p>All files are in folder: <strong>{$prefix}{$folder}</strong></p>";
?>