"""Orchestration du pipeline complet : YouTube API → pandas → S3.

Utilisable en local (`python -m src.pipeline`) ou comme handler AWS Lambda
(`src.pipeline.lambda_handler`). Tout se fait en mémoire : aucun fichier
local n'est nécessaire, ce qui convient à l'environnement Lambda.
"""

import logging
from datetime import datetime, timezone

from src import config
from src.ingest import extract
from src.transform import clean, compute_insights, print_insights
from src.upload_s3 import build_s3_key, upload_dataframe

log = logging.getLogger(__name__)


def run() -> dict:
    """Exécute le pipeline et retourne un résumé du run."""
    run_date = datetime.now(timezone.utc)

    df_raw = extract()
    if df_raw.empty:
        return {"status": "no_data", "rows": 0}

    df_clean = clean(df_raw)
    insights = compute_insights(df_clean)

    raw_uri = upload_dataframe(df_raw, build_s3_key(config.RAW_FILENAME, run_date, "youtube/raw"))
    clean_uri = upload_dataframe(df_clean, build_s3_key(config.CLEAN_FILENAME, run_date))

    return {
        "status": "success",
        "rows": len(df_clean),
        "raw_uri": raw_uri,
        "clean_uri": clean_uri,
        "sujet_plus_vu": insights["sujet_plus_vu"],
        "sujet_plus_engageant": insights["sujet_plus_engageant"],
        "insights": insights,
    }


def lambda_handler(event, context):
    """Point d'entrée AWS Lambda (déclenchable par une règle EventBridge planifiée).

    Les logs sont envoyés automatiquement dans CloudWatch Logs.
    """
    logging.getLogger().setLevel(logging.INFO)
    result = run()
    result.pop("insights", None)  # DataFrames non sérialisables en JSON
    log.info("Résultat du run : %s", result)
    return result


if __name__ == "__main__":
    config.setup_logging()
    result = run()
    if result["status"] == "success":
        print_insights(result["insights"])
        log.info("Données brutes    : %s", result["raw_uri"])
        log.info("Données nettoyées : %s", result["clean_uri"])
