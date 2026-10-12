"""Chargement : dépôt des données nettoyées dans le data lake S3.

Les fichiers sont partitionnés par date d'exécution (format Hive), ce qui garde
l'historique de chaque run et permet à Athena / Glue de filtrer par partition :

    s3://<bucket>/youtube/clean/year=2026/month=05/day=07/youtube_tpme_clean.csv
"""

import logging
import sys
from datetime import datetime, timezone

import boto3
import pandas as pd

from src import config

log = logging.getLogger(__name__)


def get_s3_client():
    """Retourne un client S3.

    Les credentials sont résolus par boto3 (variables d'environnement, profil AWS
    ou rôle IAM de la Lambda) : aucune clé n'est écrite dans le code.
    """
    return boto3.client("s3", region_name=config.AWS_REGION)


def get_bucket() -> str:
    if not config.S3_BUCKET:
        raise ValueError("S3_BUCKET manquant (fichier .env ou variable d'environnement)")
    return config.S3_BUCKET


def build_s3_key(filename: str, run_date: datetime | None = None,
                 prefix: str = config.S3_PREFIX) -> str:
    """Construit la clé S3 partitionnée par date (UTC par défaut)."""
    d = run_date or datetime.now(timezone.utc)
    return f"{prefix}/year={d.year}/month={d.month:02d}/day={d.day:02d}/{filename}"


def upload_dataframe(df: pd.DataFrame, s3_key: str, bucket: str | None = None, s3=None) -> str:
    """Écrit un DataFrame en CSV directement dans S3, sans fichier local.

    Retourne l'URI S3 du fichier créé.
    """
    bucket = bucket or get_bucket()
    s3 = s3 or get_s3_client()

    body = df.to_csv(index=False).encode("utf-8")
    s3.put_object(
        Bucket=bucket,
        Key=s3_key,
        Body=body,
        ContentType="text/csv",
        Metadata={"source": "youtube-api", "project": "social-analytics-tpme"},
    )
    uri = f"s3://{bucket}/{s3_key}"
    log.info("Upload réussi : %s (%d lignes, %.1f KB)", uri, len(df), len(body) / 1024)
    return uri


def list_objects(prefix: str = config.S3_PREFIX, bucket: str | None = None, s3=None) -> list[dict]:
    """Liste les fichiers du data lake sous `prefix` (pagination incluse)."""
    bucket = bucket or get_bucket()
    s3 = s3 or get_s3_client()

    objects = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        objects.extend(page.get("Contents", []))
    return objects


if __name__ == "__main__":
    config.setup_logging()

    local_file = config.CLEAN_PATH / config.CLEAN_FILENAME
    if not local_file.exists():
        log.error("Fichier introuvable : %s — lance d'abord `python -m src.transform`", local_file)
        sys.exit(1)

    upload_dataframe(pd.read_csv(local_file), build_s3_key(local_file.name))

    for obj in list_objects():
        log.info("%s | %8d octets | %s",
                 obj["LastModified"].strftime("%Y-%m-%d %H:%M"), obj["Size"], obj["Key"])
