#!/usr/bin/env python3
import os
import logging
import datetime
import math
import requests
import yaml
import boto3
import botocore
from urllib.parse import urlparse

import psycopg2
from psycopg2 import sql
from psycopg2.extras import DictCursor
from shapely import wkb

from credentials import *

# ─── Configuration ─────────────────────────────────────────────────────────────

TIME_THRESHOLD    = datetime.timedelta(hours=1)
SPATIAL_THRESHOLD = 100.0       # meters
ER                = 6_371_000.0 # Earth radius in meters

# ─── Helpers ────────────────────────────────────────────────────────────────────

s3_client = boto3.client(
    's3',
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

def load_yaml_meta_from_s3(s3_uri):
    """
    Given s3://bucket/prefix, fetch prefix/fielduploads.seabee.yaml
    using the pre-configured s3_client.
    """
    parsed = urlparse(s3_uri)
    bucket = parsed.netloc
    prefix = parsed.path.lstrip('/')
    key    = prefix.rstrip('/') + '/fielduploads.seabee.yaml'

    try:
        obj  = s3_client.get_object(Bucket=bucket, Key=key)
        body = obj['Body'].read().decode('utf-8')
        meta = yaml.safe_load(body) or {}
        logging.info(f"Loaded YAML from s3://{bucket}/{key}")
        return meta

    except botocore.exceptions.ClientError as e:
        code = e.response.get('Error', {}).get('Code','')
        if code in ('NoSuchKey','404'):
            logging.info(f"No YAML at s3://{bucket}/{key}")
            return {}
        logging.warning(f"S3 error reading s3://{bucket}/{key}: {e}")
        return {}

    except Exception as e:
        logging.warning(f"Failed parsing YAML s3://{bucket}/{key}: {e}")
        return {}
    

def haversine(pt1, pt2):
    """Great-circle distance in meters between (lon,lat) points."""
    lon1, lat1 = pt1
    lon2, lat2 = pt2
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ     = math.radians(lat2 - lat1)
    dλ     = math.radians(lon2 - lon1)
    a      = math.sin(dφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(dλ/2)**2
    return 2 * ER * math.asin(math.sqrt(a))

def get_place_name(lat, lon):
    """Nearest natural place via Kartverket."""
    url = (
      "https://ws.geonorge.no/stedsnavn/v1/punkt"
      f"?nord={lat}&ost={lon}&koordsys=4326"
      "&radius=500&treffPerSide=50"
    )
    natural_features = {
        "Annen terrengdetalj", "Annen vanndetalj", "Bakke", "Bakke (Veg)", 
        "Bakke i sjø", "Bakketopp i sjø", "Banke", "Banke i sjø", "Basseng i sjø", 
        "Bekk", "Berg", "Botn", "Båe", "Båe i sjø", "Dal", "Dalføre", 
        "Del av innsjø", "Egg i sjø", "Eid", "Eid i sjø", "Elv", "Elvemel", 
        "Elvesving", "Eng", "Fjell", "Fjell i dagen", "Fjellkant", 
        "Fjellkjede i sjø", "Fjellområde", "Fjellside", "Fjelltopp i sjø", 
        "Fjord", "Fjordmunning", "Fonn", "Foss", "Grotte", "Grunne", 
        "Grunne i sjø", "Gruppe av tjern", "Gruppe av vann", "Halvøy", 
        "Halvøy i sjø", "Haug", "Havdyp", "Havområde", "Hei", "Heller", 
        "Holme", "Holme i sjø", "Holmegruppe i sjø", "Hylle", "Hylle i sjø", 
        "Høl", "Høyde", "Innsjø", "Isbre", "Iskuppel", "Juv", "Kanal", 
        "Kilde", "Klakk i sjø", "Klopp", "Krater", "Landskapsområde", "Li", 
        "Lon", "Mo", "Molo", "Myr", "Nes", "Nes i sjø", "Nes ved elver", 
        "Os", "Park", "Platå i sjø", "Pytt", "Ras i sjø", "Renne/Kløft i sjø", 
        "Rev i sjø", "Rygg", "Rygg i sjø", "Sadel i sjø", "Sand", "Senkning", 
        "Sjødetalj", "Sjømerke", "Sjøstykke", "Skar", "Skjær", 
        "Skjær i sjø", "Skog", "Skogholt", "Skogområde", "Skredområde", 
        "Slette", "Sokkel i sjø", "Stein", "Sti", "Strand", 
        "Strand i sjø", "Stryk", "Stup", "Stø", "Sund", "Sund i sjø", 
        "Søkk", "Søkk i sjø", "Tjern", "Topp", "Undersjøisk vegg", "Ur", 
        "Utmark", "Vann", "Verneområde", "Vidde", "Vik", "Vik i sjø", 
        "Vulkan i sjø", "Våg i sjø", "Øy", "Øy i sjø", "Øygruppe", 
        "Øygruppe i sjø", "Øyr", "Ås", "Våtmarksområde", "Friluftsområde", 
        "Egg", "Fjellvegg", "Del av vann", "Hammar", "Sva"
    }
    resp = requests.get(url)
    if resp.status_code != 200:
        return None
    names = resp.json().get("navn", [])
    cand  = [p for p in names if p.get("navneobjekttype") in natural_features]
    if not cand:
        return None
    best = min(cand, key=lambda p: p["meterFraPunkt"])
    place_name = best["stedsnavn"][0]["skrivemåte"].replace(" ", "-")
    return place_name

def get_municipality_and_county(lat, lon):
    """County & municipality via Kartverket."""
    url = (
      "https://ws.geonorge.no/kommuneinfo/v1/punkt"
      f"?nord={lat}&ost={lon}&koordsys=4326"
    )
    resp = requests.get(url)
    if resp.status_code != 200:
        return "Unknown", "Unknown"
    data = resp.json()
    municipality = data.get("kommunenavn", "Unknown").replace(" ", "-")
    county       = data.get("fylkesnavn",    "Unknown").replace(" ", "-")
    return county, municipality

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST","localhost"),
        port=os.getenv("DB_PORT","5432"),
        dbname=os.getenv("DB_NAME","fielduploads"),
        user=os.getenv("DB_USER","postgres"),
        password=os.getenv("DB_PASSWORD","tijJmjNbZG%yjcZE$C4mAPZ@b")
    )

# ─── Schema Initialization ─────────────────────────────────────────────────────

def init_cluster_schema(conn):
    cur = conn.cursor()
    cur.execute("ALTER TABLE files ADD COLUMN IF NOT EXISTS cluster_id INTEGER;")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS clusters (
        id SERIAL PRIMARY KEY,
        grouping TEXT,
        area TEXT,
        "datetime" TEXT,
        nfiles INTEGER,
        organisation TEXT,
        mosaic BOOLEAN DEFAULT TRUE,
        publish BOOLEAN DEFAULT TRUE,
        classify BOOLEAN DEFAULT TRUE,
        theme TEXT,
        spectrum_type TEXT,
        elevation INTEGER,
        creator_name TEXT,
        project TEXT,
        vehicle TEXT,
        sensor TEXT,
        licence TEXT,
        licence_link TEXT,
        odm_dsm BOOLEAN,
        odm_dtm BOOLEAN,
        odm_cog BOOLEAN,
        odm_orthophoto_compression TEXT,
        odm_orthophoto_resolution DOUBLE PRECISION,
        odm_dem_resolution DOUBLE PRECISION,
        odm_max_concurrency INTEGER,
        odm_auto_boundary BOOLEAN,
        odm_use_3dmesh BOOLEAN,
        odm_fast_orthophoto BOOLEAN,
        odm_pc_rectify BOOLEAN,
        odm_split INTEGER,
        odm_split_overlap INTEGER,
        odm_crop DOUBLE PRECISION,
        odm_pc_quality TEXT,
        odm_feature_quality TEXT,
        odm_radiometric_calibration TEXT,
        ml_task TEXT,
        ml_model TEXT,
        centroid_lon DOUBLE PRECISION,
        centroid_lat DOUBLE PRECISION,
        min_datetime TIMESTAMP,
        skip BOOLEAN DEFAULT FALSE,
        readyforsigma BOOLEAN DEFAULT FALSE,
        senttosigma TIMESTAMP
    );
    """)
    # Add missing extras
    extras = [
        "classify BOOLEAN DEFAULT TRUE",
        "skip BOOLEAN DEFAULT FALSE",
        "readyforsigma BOOLEAN DEFAULT FALSE",
        "senttosigma TIMESTAMP",
        "centroid_lon DOUBLE PRECISION",
        "centroid_lat DOUBLE PRECISION",
        "min_datetime TIMESTAMP"
    ]
    for col in extras:
        cur.execute(sql.SQL("ALTER TABLE clusters ADD COLUMN IF NOT EXISTS {};").format(sql.SQL(col)))
    conn.commit()
    cur.close()

# ─── Fetch new files ────────────────────────────────────────────────────────────

def fetch_new_points(conn):
    cur = conn.cursor(cursor_factory=DictCursor)
    cur.execute("""
        SELECT id, directory, datetimetaken, geom
          FROM files
         WHERE cluster_id IS NULL
           AND geom IS NOT NULL
           AND datetimetaken IS NOT NULL;
    """)
    rows = cur.fetchall(); cur.close()
    pts = []
    for r in rows:
        geom = wkb.loads(r["geom"], hex=False)
        pts.append({
            "file_id":      r["id"],
            "directory":    r["directory"],
            "datetime":     r["datetimetaken"],
            "coord":        (geom.x, geom.y)
        })
    return pts

# ─── Incremental clustering ────────────────────────────────────────────────────

def assign_incremental(conn):
    """
    Assign unclustered files into existing clusters (or brand-new ones),
    pulling metadata from S3 when available.
    """
    cur = conn.cursor(cursor_factory=DictCursor)
    cur.execute("""
      SELECT id, centroid_lon, centroid_lat, min_datetime, nfiles
        FROM clusters
       WHERE readyforsigma = FALSE
         AND centroid_lon IS NOT NULL
         AND centroid_lat IS NOT NULL
         AND min_datetime IS NOT NULL;
    """)
    existing = cur.fetchall()
    cur.close()

    new_pts = fetch_new_points(conn)
    if not new_pts:
        logging.info("No new files to cluster.")
        return

    # In‐memory snapshot of existing clusters
    clusters = [
        {
            'id':           r['id'],
            'centroid':     (r['centroid_lon'], r['centroid_lat']),
            'min_datetime': r['min_datetime'],
            'nfiles':       r['nfiles']
        }
        for r in existing
    ]

    cur = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(id),0) FROM clusters;")
    next_cid = cur.fetchone()[0] + 1

    for pt in new_pts:
        # 1) Try to fit into an existing cluster…
        best, best_dist = None, None
        for cl in clusters:
            dt = abs(pt['datetime'] - cl['min_datetime'])
            if dt > TIME_THRESHOLD:
                continue
            dist = haversine(pt['coord'], cl['centroid'])
            if dist > SPATIAL_THRESHOLD:
                continue
            if best is None or dist < best_dist:
                best, best_dist = cl, dist

        if best:
            # assign to existing
            cur.execute(
                "UPDATE files SET cluster_id = %s WHERE id = %s;",
                (best['id'], pt['file_id'])
            )
            old_n = best['nfiles']
            new_n = old_n + 1
            lon0, lat0 = best['centroid']
            lon1, lat1 = pt['coord']
            avg_lon = (lon0*old_n + lon1) / new_n
            avg_lat = (lat0*old_n + lat1) / new_n
            new_min = min(best['min_datetime'], pt['datetime'])
            dt_txt  = new_min.strftime('%Y%m%d%H%M')

            cur.execute("""
                UPDATE clusters
                   SET centroid_lon = %s,
                       centroid_lat = %s,
                       min_datetime = %s,
                       nfiles       = %s,
                       "datetime"   = %s
                 WHERE id = %s;
            """, (avg_lon, avg_lat, new_min, new_n, dt_txt, best['id']))

            # update in‐memory
            best.update({
                'centroid':     (avg_lon, avg_lat),
                'min_datetime': new_min,
                'nfiles':       new_n
            })

        else:
            # Create a brand-new cluster
            cid = next_cid
            next_cid += 1
            lon, lat = pt["coord"]
            dt0       = pt["datetime"]
            dt_txt    = dt0.strftime("%Y%m%d%H%M")

            # derive area & grouping
            area = get_place_name(lat, lon) or os.path.basename(pt["directory"])
            county, muni = get_municipality_and_county(lat, lon)
            grouping     = f"{county}-{muni}"

            # ─── LOAD YAML META ────────────────────────────────────
            # Always build an S3 URI from the known bucket + the directory path:
            s3_uri = f"s3://{BUCKET_NAME}/{pt['directory']}"
            meta = load_yaml_meta_from_s3(s3_uri)

            # fallback to local FS only if you want:
            if not meta:
                local_yaml = os.path.join(pt["directory"], "fielduploads.seabee.yaml")
                if os.path.exists(local_yaml):
                    try:
                        with open(local_yaml, "r", encoding="utf-8") as yf:
                            meta = yaml.safe_load(yf) or {}
                    except Exception as e:
                        logging.warning(f"Failed to parse {local_yaml}: {e}")

            org      = meta.get("organisation")
            creator  = meta.get("creator_name")
            proj     = meta.get("project")
            theme    = meta.get("theme")

            # defaults
            mosaic   = True
            publish  = True
            classify = True

            # insert the new cluster
            cur.execute("""
                INSERT INTO clusters (
                id, grouping, area, "datetime", nfiles,
                organisation, creator_name, project, theme,
                mosaic, publish, classify,
                centroid_lon, centroid_lat, min_datetime
                ) VALUES (
                %s, %s, %s, %s, 1,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s
                );
            """, (
                cid, grouping, area, dt_txt,
                org, creator, proj, theme,
                mosaic, publish, classify,
                lon, lat, dt0
            ))

            # assign the file to this new cluster
            cur.execute(
                "UPDATE files SET cluster_id = %s WHERE id = %s;",
                (cid, pt["file_id"])
            )

            clusters.append({
                "id":           cid,
                "centroid":     (lon, lat),
                "min_datetime": dt0,
                "nfiles":       1
            })

    conn.commit()
    cur.close()
    logging.info(f"Assigned {len(new_pts)} new file(s) into clusters.")

# ─── True Spatial Merge ────────────────────────────────────────────────────────

def merge_clusters(conn):
    """Merge clusters whose files overlap within thresholds."""
    cur = conn.cursor()
    cur.execute("""
    SELECT DISTINCT f1.cluster_id AS cid1, f2.cluster_id AS cid2
      FROM files f1
      JOIN files f2
        ON f1.cluster_id < f2.cluster_id
       AND f1.cluster_id IN (SELECT id FROM clusters WHERE readyforsigma = FALSE)
       AND f2.cluster_id IN (SELECT id FROM clusters WHERE readyforsigma = FALSE)
       AND f1.datetimetaken BETWEEN
           f2.datetimetaken - INTERVAL '1 hour' AND f2.datetimetaken + INTERVAL '1 hour'
       AND ST_DWithin(
            f1.geom::geography,
            f2.geom::geography,
            %s
       );
    """, (SPATIAL_THRESHOLD,))
    pairs = cur.fetchall()
    cur.close()

    if not pairs:
        logging.info("No overlapping clusters to merge.")
        return

    parent = {}
    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for a, b in pairs:
        union(a, b)

    comps = {}
    for a, b in pairs:
        r = find(a)
        comps.setdefault(r, set()).update([a, b])

    cur = conn.cursor()
    for comp in comps.values():
        if len(comp) < 2:
            continue
        keep = min(comp)
        to_del = [c for c in comp if c != keep]

        cur.execute(sql.SQL("""
        SELECT 
          ST_X(c.geomc) AS lon,
          ST_Y(c.geomc) AS lat,
          c.min_dt,
          c.nf
        FROM (
          SELECT 
            ST_Centroid(ST_Collect(f.geom::geometry)) AS geomc,
            MIN(f.datetimetaken) AS min_dt,
            COUNT(*) AS nf
          FROM files f
          WHERE f.cluster_id = ANY(%s)
        ) c;
        """), (list(comp),))
        lon, lat, min_dt, nf = cur.fetchone()
        dt_txt = min_dt.strftime('%Y%m%d%H%M')
        area = get_place_name(lat, lon) or ""
        county, municipality = get_municipality_and_county(lat, lon)
        grouping = f"{county}-{municipality}"

        cur.execute(sql.SQL("""
        UPDATE clusters
           SET centroid_lon = %s,
               centroid_lat = %s,
               min_datetime = %s,
               nfiles       = %s,
               "datetime"   = %s,
               area         = %s,
               grouping     = %s
         WHERE id = %s;
        """), (lon, lat, min_dt, nf, dt_txt, area, grouping, keep))

        cur.execute(sql.SQL("""
        UPDATE files
           SET cluster_id = %s
         WHERE cluster_id = ANY(%s);
        """), (keep, list(comp)))

        cur.execute(sql.SQL("""
        DELETE FROM clusters
              WHERE id = ANY(%s)
                AND id <> %s;
        """), (list(comp), keep))

    conn.commit()
    cur.close()
    logging.info("Merged overlapping clusters.")

# ─── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.info("Starting clustering run…")
    conn = get_db_connection()
    init_cluster_schema(conn)
    assign_incremental(conn)
    merge_clusters(conn)
    conn.close()
    logging.info("Clustering run complete.")
