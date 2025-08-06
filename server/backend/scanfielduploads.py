import os
import logging
import io
import datetime

import boto3
from botocore.client import Config
import exifread
import psycopg2
from psycopg2 import sql

from credentials import *

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# Connect to S3 (MinIO)
s3 = boto3.resource(
    's3',
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    config=Config(signature_version='s3v4'),
    region_name='us-east-1'
)

# PostgreSQL helpers
def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )


def init_db():
    """
    Ensure database and 'files' table with PostGIS extension exist, renaming 'filepath' column to 'directory'.
    """
    # Create database if needed
    try:
        admin_conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, dbname='postgres', user=DB_USER, password=DB_PASSWORD
        )
        admin_conn.autocommit = True
        cur = admin_conn.cursor()
        cur.execute(sql.SQL("CREATE DATABASE {};").format(sql.Identifier(DB_NAME)))
        cur.close()
        admin_conn.close()
        logger.info(f"Database '{DB_NAME}' created.")
    except psycopg2.errors.DuplicateDatabase:
        logger.info(f"Database '{DB_NAME}' already exists.")
    except Exception as e:
        logger.warning(f"Could not create database '{DB_NAME}': {e}")

    # Create table and extension
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS files (
            id SERIAL PRIMARY KEY,
            directory TEXT NOT NULL,
            filename TEXT NOT NULL,
            filetype TEXT,
            geom geometry(Point, 4326),
            datetimetaken TIMESTAMP,
            datetimemodified TIMESTAMP,
            CONSTRAINT files_unique UNIQUE (directory, filename)
        );
        """
    )
    conn.commit()
    cur.close()
    conn.close()
    logger.info("Table 'files' ensured with 'directory' and 'filename' uniqueness.")


def parse_exif_gps(tags):
    """
    Convert EXIF GPS tags to decimal coordinates.
    """
    def to_degrees(vals):
        d = float(vals.values[0].num) / vals.values[0].den
        m = float(vals.values[1].num) / vals.values[1].den
        s = float(vals.values[2].num) / vals.values[2].den
        return d + m/60.0 + s/3600.0

    lat_tag = tags.get('GPS GPSLatitude')
    lon_tag = tags.get('GPS GPSLongitude')
    lat_ref = tags.get('GPS GPSLatitudeRef')
    lon_ref = tags.get('GPS GPSLongitudeRef')

    if lat_tag and lon_tag and lat_ref and lon_ref:
        lat = to_degrees(lat_tag)
        lon = to_degrees(lon_tag)
        if lat_ref.values[0] != 'N': lat = -lat
        if lon_ref.values[0] != 'E': lon = -lon
        return lon, lat
    return None, None


def process_object(obj_summary, conn):
    key = obj_summary.key
    logger.info(f"Processing {key}")

    # Compute directory and filename
    directory = os.path.dirname(key)
    filename = os.path.basename(key)

    # Skip if in the $RECYCLE.BIN folder
    if '$RECYCLE.BIN' in directory:
        logger.info(f"Skipping $RECYCLE.BIN folder: {directory}")
        return

    # Skip if already in DB
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM files WHERE directory = %s AND filename = %s;",
            (directory, filename)
        )
        if cur.fetchone():
            logger.info(f"Skipping existing file: {directory}/{filename}")
            return

    ext = os.path.splitext(key)[1].lower().lstrip('.')
    geom_wkt = None
    dt_taken = None
    dt_mod = obj_summary.last_modified

    # If image, extract EXIF
    if ext in ('jpg', 'jpeg', 'png', 'tiff', 'tif'):
        obj = s3.Object(BUCKET_NAME, key)
        data = obj.get()['Body'].read()
        tags = exifread.process_file(io.BytesIO(data), details=False)
        lon, lat = parse_exif_gps(tags)
        if lon is not None and lat is not None:
            geom_wkt = f"SRID=4326;POINT({lon} {lat})"
        dt_tag = tags.get('EXIF DateTimeOriginal') or tags.get('Image DateTime')
        if dt_tag:
            raw = dt_tag.values
            try:
                dt_taken = datetime.datetime.strptime(raw, '%Y:%m:%d %H:%M:%S')
            except ValueError:
                logger.warning(f"Invalid EXIF datetime for {key}: {raw}")

    # Insert new record
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL(
                "INSERT INTO files "
                "(directory, filename, filetype, geom, datetimetaken, datetimemodified) "
                "VALUES (%s, %s, %s, %s, %s, %s);"
            ),
            [
                directory,
                filename,
                ext,
                geom_wkt,
                dt_taken,
                dt_mod
            ]
        )
    conn.commit()
    logger.info(f"Inserted {directory}/{filename}")


def main():
    init_db()
    conn = get_db_connection()
    bucket = s3.Bucket(BUCKET_NAME)
    for obj in bucket.objects.filter(Prefix=PREFIX):
        process_object(obj, conn)
    conn.close()
    logger.info("Completed scan.")

if __name__ == '__main__':
    main()
