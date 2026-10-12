"""Transformation : nettoyage, enrichissement et insights business."""

import html
import logging

import numpy as np
import pandas as pd

from src import config

log = logging.getLogger(__name__)

PERFORMANCE_BINS = [0, 1_000, 10_000, 100_000, float("inf")]
PERFORMANCE_LABELS = ["faible", "moyen", "bon", "viral"]


def load_raw() -> pd.DataFrame:
    """Charge le CSV brut produit par ingest.py."""
    df = pd.read_csv(config.RAW_PATH / config.RAW_FILENAME)
    log.info("Données brutes chargées : %s", df.shape)
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Nettoie et enrichit les données brutes.

    - décode les entités HTML des titres et descriptions (&#39; → ')
    - convertit la date de publication et en extrait l'année et le mois
    - supprime les doublons (une vidéo peut sortir sur plusieurs thématiques)
    - calcule le taux d'engagement : (likes + commentaires) / vues × 100
    - classe chaque vidéo par niveau de performance selon ses vues
    """
    df = df.copy()

    for col in ("titre", "description"):
        df[col] = df[col].fillna("").astype(str).map(html.unescape)

    df["date_publi"] = pd.to_datetime(df["date_publi"], utc=True)
    df["annee"] = df["date_publi"].dt.year
    df["mois"] = df["date_publi"].dt.month

    avant = len(df)
    df = df.drop_duplicates(subset="video_id").reset_index(drop=True)
    log.info("Doublons supprimés : %d", avant - len(df))

    for col in ("vues", "likes", "commentaires"):
        df[col] = df[col].fillna(0).astype(int)

    # Sans vues, le taux d'engagement n'est pas défini (NaN plutôt qu'un chiffre faux)
    df["taux_engagement"] = (
        (df["likes"] + df["commentaires"]) / df["vues"].replace(0, np.nan) * 100
    ).round(2)

    # include_lowest=True : une vidéo à 0 vue est classée « faible » et non NaN
    df["performance"] = pd.cut(
        df["vues"],
        bins=PERFORMANCE_BINS,
        labels=PERFORMANCE_LABELS,
        include_lowest=True,
    )

    log.info("Données nettoyées : %s", df.shape)
    return df


def compute_insights(df: pd.DataFrame) -> dict:
    """Calcule les indicateurs clés pour orienter la stratégie de contenu des TPE/PME."""
    par_sujet = df.groupby("query").agg(
        vues_moyennes=("vues", "mean"),
        engagement_moyen=("taux_engagement", "mean"),
        nb_videos=("video_id", "count"),
    ).round(2)

    return {
        "nb_videos": len(df),
        "vues_totales": int(df["vues"].sum()),
        "likes_totaux": int(df["likes"].sum()),
        "commentaires_totaux": int(df["commentaires"].sum()),
        "top_videos": df.nlargest(5, "vues")[["titre", "chaine", "vues", "taux_engagement"]],
        "top_chaines": df.groupby("chaine")["vues"].sum().nlargest(5),
        "par_sujet": par_sujet,
        "repartition_performance": df["performance"].value_counts().reindex(PERFORMANCE_LABELS),
        "sujet_plus_vu": par_sujet["vues_moyennes"].idxmax(),
        "sujet_plus_engageant": par_sujet["engagement_moyen"].idxmax(),
    }


def print_insights(insights: dict) -> None:
    """Affiche les insights dans le terminal."""
    print(f"\n{'=' * 55}\n  INSIGHTS — Contenu TPE/PME sur YouTube\n{'=' * 55}")

    print("\nVOLUME")
    print(f"   Vidéos analysées    : {insights['nb_videos']}")
    print(f"   Vues totales        : {insights['vues_totales']:,}")
    print(f"   Likes totaux        : {insights['likes_totaux']:,}")
    print(f"   Commentaires totaux : {insights['commentaires_totaux']:,}")

    print("\nTOP 5 VIDÉOS (par vues)")
    for _, row in insights["top_videos"].iterrows():
        print(f"   {row['vues']:>10,} vues | {row['taux_engagement']:>5.2f}% | {row['titre'][:50]}")

    print("\nTOP 5 CHAÎNES (par vues totales)")
    for chaine, vues in insights["top_chaines"].items():
        print(f"   {vues:>10,} vues | {chaine}")

    print("\nPERFORMANCE PAR SUJET")
    print(insights["par_sujet"].to_string())

    print("\nRÉPARTITION PAR PERFORMANCE")
    print(insights["repartition_performance"].to_string())

    print("\nINSIGHT CLÉ POUR TPE/PME")
    print(f"   Sujet le plus vu        : '{insights['sujet_plus_vu']}'")
    print(f"   Sujet le plus engageant : '{insights['sujet_plus_engageant']}'")


if __name__ == "__main__":
    config.setup_logging()
    df_clean = clean(load_raw())
    print_insights(compute_insights(df_clean))

    config.CLEAN_PATH.mkdir(parents=True, exist_ok=True)
    output = config.CLEAN_PATH / config.CLEAN_FILENAME
    df_clean.to_csv(output, index=False, encoding="utf-8-sig")
    log.info("Données nettoyées sauvegardées : %s", output)
