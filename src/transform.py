# ============================================================
# transform.py — Nettoyage et analyse des données YouTube
# ============================================================
# Ce script fait 3 choses :
#   1. Charge le CSV brut produit par ingest.py
#   2. Nettoie et enrichit les données (pandas)
#   3. Affiche des insights business pour les TPE/PME
# ============================================================

import pandas as pd  # Manipulation de données en tableaux
import logging       # Messages structurés dans le terminal
import html          # Décodage des caractères HTML (&amp; &#39; etc.)
from pathlib import Path  # Gestion des chemins de fichiers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger(__name__)

# --- Chemins des dossiers ---
# RAW_PATH   = là où ingest.py a sauvegardé les données brutes
# CLEAN_PATH = là où on va sauvegarder les données nettoyées
RAW_PATH   = Path(__file__).parent.parent / "data" / "raw"
CLEAN_PATH = Path(__file__).parent.parent / "data" / "clean"
CLEAN_PATH.mkdir(parents=True, exist_ok=True)  # Crée le dossier si absent


def load_raw() -> pd.DataFrame:
    """
    Charge le fichier CSV brut produit par ingest.py.
    Retourne un DataFrame pandas.
    """
    path = RAW_PATH / "youtube_tpme.csv"
    df = pd.read_csv(path)
    log.info(f"Données brutes chargées : {df.shape}")
    # df.shape retourne (nb_lignes, nb_colonnes)
    # ex: (60, 10) = 60 vidéos, 10 colonnes
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """
    Nettoie et enrichit le DataFrame brut.

    Les transformations appliquées :
    1. Décodage HTML
    2. Conversion des dates
    3. Suppression des doublons
    4. Calcul du taux d'engagement
    5. Catégorisation de la performance

    Retourne le DataFrame nettoyé et enrichi.
    """

    # --- 1. Décodage des caractères HTML ---
    # YouTube encode certains caractères dans les titres :
    # &#39; → '    &amp; → &    &quot; → "
    # fillna("") = remplace les valeurs manquantes (NaN) par une chaîne vide
    # astype(str) = force la conversion en texte (évite l'erreur TypeError)
    # .apply(html.unescape) = applique le décodage sur chaque cellule
    df["titre"]       = df["titre"].fillna("").astype(str).apply(html.unescape)
    df["description"] = df["description"].fillna("").astype(str).apply(html.unescape)
    log.info("✓ Caractères HTML décodés")

    # --- 2. Conversion des dates ---
    # La date arrive en texte ISO 8601 : "2023-09-07T06:51:22Z"
    # pd.to_datetime() la convertit en vrai objet datetime
    # Ça permet ensuite d'extraire l'année, le mois, etc.
    df["date_publi"] = pd.to_datetime(df["date_publi"])
    df["annee"]      = df["date_publi"].dt.year   # Extrait l'année (2023)
    df["mois"]       = df["date_publi"].dt.month  # Extrait le mois (9)
    log.info("✓ Dates converties")

    # --- 3. Suppression des doublons ---
    # Une même vidéo peut apparaître dans plusieurs queries
    # ex: une vidéo sur "gestion TPE" ET "marketing PME"
    # drop_duplicates(subset="video_id") = garde une seule ligne par video_id
    avant = len(df)
    df    = df.drop_duplicates(subset="video_id")
    apres = len(df)
    df    = df.copy()
    log.info(f"✓ Doublons supprimés : {avant - apres} lignes retirées")

    # --- 4. Calcul du taux d'engagement ---
    # Formule : (likes + commentaires) / vues × 100
    # Un taux élevé = la vidéo génère des interactions
    # C'est plus utile que les vues seules pour les TPE/PME
    # .replace(0, 1) = évite la division par zéro si vues = 0
    # .round(2) = arrondit à 2 décimales (ex: 3.47%)
    df["taux_engagement"] = (
        (df["likes"] + df["commentaires"]) / df["vues"].replace(0, 1) * 100
    ).round(2)
    log.info("✓ Taux d'engagement calculé")

    # --- 5. Catégorisation de la performance ---
    # pd.cut() découpe une colonne numérique en catégories
    # bins = les seuils : 0, 1k, 10k, 100k, infini
    # labels = le nom de chaque catégorie
    # Résultat : chaque vidéo reçoit une étiquette de performance
    df["performance"] = pd.cut(
        df["vues"],
        bins=[0, 1000, 10000, 100000, float("inf")],
        labels=["faible", "moyen", "bon", "viral"]
    )
    log.info("✓ Catégories de performance assignées")

    return df


def analyse(df: pd.DataFrame) -> None:
    """
    Affiche les insights clés dans le terminal.
    C'est ce qu'on présentera aux TPE/PME :
    quels sujets marchent, quelles chaînes dominent, etc.
    """
    print(f"\n{'='*55}")
    print("  INSIGHTS — Contenu TPE/PME sur YouTube")
    print(f"{'='*55}")

    # --- Volume global ---
    print(f"\n📊 VOLUME")
    print(f"   Vidéos analysées    : {len(df)}")
    print(f"   Vues totales        : {df['vues'].sum():,}")
    # :, = format avec séparateur milliers (1,234,567)
    print(f"   Likes totaux        : {df['likes'].sum():,}")
    print(f"   Commentaires totaux : {df['commentaires'].sum():,}")

    # --- Top 5 vidéos ---
    # nlargest(5, "vues") = les 5 lignes avec les plus grandes valeurs de "vues"
    print(f"\n🏆 TOP 5 VIDÉOS (par vues)")
    top5 = df.nlargest(5, "vues")[["titre", "chaine", "vues", "taux_engagement"]]
    for _, row in top5.iterrows():
        # iterrows() = parcourt le DataFrame ligne par ligne
        # _ = index (on ne l'utilise pas)
        # row = la ligne courante (comme un dictionnaire)
        print(f"   {row['vues']:>10,} vues | {row['taux_engagement']:>5.2f}% | {row['titre'][:50]}")
        # :>10, = aligné à droite sur 10 caractères avec séparateur milliers
        # :>5.2f = aligné à droite sur 5 caractères, 2 décimales

    # --- Top chaînes ---
    # groupby("chaine") = regroupe les lignes par chaîne
    # ["vues"].sum() = additionne les vues pour chaque chaîne
    # .nlargest(5) = garde les 5 chaînes avec le plus de vues
    print(f"\n📺 TOP 5 CHAÎNES (par vues totales)")
    top_chaines = df.groupby("chaine")["vues"].sum().nlargest(5)
    for chaine, vues in top_chaines.items():
        print(f"   {vues:>10,} vues | {chaine}")

    # --- Performance par sujet ---
    # .agg() = applique plusieurs fonctions d'agrégation en même temps
    # mean() = moyenne, count() = nombre de lignes
    print(f"\n🔍 PERFORMANCE PAR SUJET")
    perf_query = df.groupby("query").agg(
        vues_moyennes    =("vues", "mean"),
        engagement_moyen =("taux_engagement", "mean"),
        nb_videos        =("video_id", "count")
    ).round(0)
    print(perf_query.to_string())

    # --- Répartition performance ---
    # value_counts() = compte le nombre de vidéos dans chaque catégorie
    print(f"\n📅 RÉPARTITION PAR PERFORMANCE")
    print(df["performance"].value_counts().to_string())

    # --- Insight clé ---
    # idxmax() = retourne l'index (ici le nom du sujet) avec la valeur max
    print(f"\n💡 INSIGHT CLÉ POUR TPE/PME")
    meilleur_sujet      = df.groupby("query")["vues"].mean().idxmax()
    meilleur_engagement = df.groupby("query")["taux_engagement"].mean().idxmax()
    print(f"   Sujet le plus vu        : '{meilleur_sujet}'")
    print(f"   Sujet le plus engageant : '{meilleur_engagement}'")


# --- Point d'entrée ---
if __name__ == "__main__":
    df_raw   = load_raw()       # Charge les données brutes
    df_clean = clean(df_raw)    # Nettoie et enrichit
    analyse(df_clean)           # Affiche les insights

    # Sauvegarde les données nettoyées pour la suite (S3, Snowflake...)
    output = CLEAN_PATH / "youtube_tpme_clean.csv"
    df_clean.to_csv(output, index=False, encoding="utf-8-sig")
    log.info(f"✓ Données nettoyées sauvegardées : {output}")