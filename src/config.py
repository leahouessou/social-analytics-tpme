"""Configuration centralisée du pipeline (chemins locaux et variables d'environnement)."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_PATH = PROJECT_ROOT / "data" / "raw"
CLEAN_PATH = PROJECT_ROOT / "data" / "clean"

RAW_FILENAME = "youtube_tpme.csv"
CLEAN_FILENAME = "youtube_tpme_clean.csv"

# Thématiques recherchées sur YouTube pour les TPE/PME
QUERIES = [
    "conseils gestion TPE PME",
    "marketing digital petite entreprise",
    "comptabilité auto entrepreneur",
]
MAX_RESULTS_PER_QUERY = int(os.getenv("MAX_RESULTS_PER_QUERY", "20"))

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
S3_BUCKET = os.getenv("S3_BUCKET")
S3_PREFIX = os.getenv("S3_PREFIX", "youtube/clean")
AWS_REGION = os.getenv("AWS_REGION", "eu-north-1")


def setup_logging() -> None:
    """Configure le logging (format lisible en local et dans CloudWatch)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
