#!/usr/bin/env python3
import os
import logging
import datetime
import yaml
import re

import boto3
import botocore
import psycopg2
from psycopg2.extras import DictCursor

from credentials import *

# ─── Setup logging & S3 client ────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
s3 = boto3.client(
    "s3",
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def sanitize_folder_name(name: str) -> str:
    """Lowercase and replace æ→ae, ø→oe, å→aa, non-alnum → underscore."""
    name = name.lower().replace("æ", "ae").replace("ø", "oe").replace("å", "aa")
    return re.sub(r'[^a-z0-9_\-]', '_', name)

def list_extra_files_in_dir(prefix: str):
    """List .nav/.bin/.obs/.mrk under prefix/ in S3."""
    extras = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=prefix.rstrip("/") + "/"):
        for obj in page.get("Contents", []):
            ext = obj["Key"].rsplit(".", 1)[-1].lower()
            if ext in ("nav", "bin", "obs", "mrk", "rtk"):
                extras.append(obj["Key"])
    return extras

# ─── Database helpers ──────────────────────────────────────────────────────────

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        dbname=DB_NAME, user=DB_USER,
        password=DB_PASSWORD
    )

def fetch_pending_clusters(conn):
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute("""
            SELECT * FROM clusters
             WHERE readyforsigma = TRUE
               AND senttosigma IS NULL;
        """)
        return cur.fetchall()

def fetch_cluster_files(conn, cluster_id):
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute("""
            SELECT filename, directory
              FROM files
             WHERE cluster_id = %s;
        """, (cluster_id,))
        return cur.fetchall()

def mark_sent_to_sigma(conn, cluster_id):
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE clusters SET senttosigma = %s WHERE id = %s;
        """, (datetime.datetime.utcnow(), cluster_id))
    conn.commit()

def update_nfiles(conn, cluster_id, count):
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE clusters SET nfiles = %s WHERE id = %s;
        """, (count, cluster_id))
    conn.commit()

# ─── Main delivery logic ───────────────────────────────────────────────────────

def deliver_clusters():
    conn = get_db_connection()
    try:
        pending = fetch_pending_clusters(conn)
        if not pending:
            logging.info("No clusters ready for Sigma.")
            return

        for cluster in pending:
            cid        = cluster["id"]
            grouping   = cluster["grouping"]
            area       = cluster["area"]
            dt_str     = cluster["datetime"]

            # sanitized folder path
            foldername = sanitize_folder_name(f"{grouping}_{area}_{dt_str}")
            base_key   = f"{DEST_PREFIX}/{foldername}"
            images_key = f"{base_key}/images/"

            # 1) Copy image files
            files = fetch_cluster_files(conn, cid)
            logging.info(f"[Cluster {cid}] Copying {len(files)} image files...")
            copied_keys = set()
            for row in files:
                src_key = f"{row['directory'].rstrip('/')}/{row['filename']}"
                dst_key = f"{images_key}{row['filename']}"
                s3.copy_object(
                    Bucket=BUCKET_NAME,
                    CopySource={"Bucket": BUCKET_NAME, "Key": src_key},
                    Key=dst_key
                )
                copied_keys.add(dst_key)

            # 2) Copy extra files (.nav/.bin/.obs/.mrk)
            dirs = {r["directory"].rstrip("/") for r in files}
            extra_count = 0
            for d in dirs:
                for src_key in list_extra_files_in_dir(d):
                    filename = src_key.split("/")[-1]
                    dst_key = f"{images_key}{filename}"
                    if dst_key in copied_keys:
                        continue
                    s3.copy_object(
                        Bucket=BUCKET_NAME,
                        CopySource={"Bucket": BUCKET_NAME, "Key": src_key},
                        Key=dst_key
                    )
                    copied_keys.add(dst_key)
                    extra_count += 1
            logging.info(f"[Cluster {cid}] Copied {extra_count} extra files")

            # 3) Count total and update DB.nfiles
            total = 0
            paginator = s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=images_key):
                total += len(page.get("Contents", []))
            logging.info(f"[Cluster {cid}] Total files in images/: {total}")
            update_nfiles(conn, cid, total)
            cluster["nfiles"] = total  # update local copy

            # 4) Build & upload config YAML last
            config_key = f"{base_key}/config.seabee.yaml"
            omit = {"id", "centroid_lon", "centroid_lat", "min_datetime",
                    "skip", "readyforsigma"}
            cfg = {}
            for k, v in cluster.items():
                if k in omit or v in (None, ""):
                    continue
                cfg[k] = v
            yaml_body = yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True)
            logging.info(f"[Cluster {cid}] Uploading config to {config_key}")
            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=config_key,
                Body=yaml_body.encode("utf-8")
            )

            # 5) Mark sent
            mark_sent_to_sigma(conn, cid)
            logging.info(f"[Cluster {cid}] Delivered and marked senttosigma.")

    finally:
        conn.close()

if __name__ == "__main__":
    deliver_clusters()
