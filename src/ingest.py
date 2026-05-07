# ============================================================
# ingest.py — Récupération des données YouTube via l'API
# ============================================================
# Ce script fait 3 choses :
#   1. Se connecte à l'API YouTube avec ta clé
#   2. Cherche des vidéos sur des sujets TPE/PME
#   3. Récupère les statistiques (vues, likes, commentaires)
# ============================================================

import os          # Pour lire les variables d'environnement (.env)
import pandas as pd  # Pour manipuler les données en tableaux (DataFrames)
import logging     # Pour afficher des messages structurés dans le terminal
from pathlib import Path  # Pour gérer les chemins de fichiers (Windows/Mac/Linux)
from dotenv import load_dotenv  # Pour charger les variables du fichier .env
from googleapiclient.discovery import build  # Client officiel YouTube API

# --- Chargement du fichier .env ---
# Sans ça, os.getenv("YOUTUBE_API_KEY") retournerait None
load_dotenv()

# --- Configuration du logging ---
# format : "2026-05-06 10:00:00 | INFO | Mon message"
# Permet de suivre ce que fait le script en temps réel
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger(__name__)  # Logger propre à ce fichier

# --- Chemin vers le dossier de sauvegarde ---
# Path(__file__) = chemin du fichier ingest.py
# .parent.parent = remonte 2 niveaux → racine du projet
# / "data" / "raw" = descend dans data/raw
RAW_PATH = Path(__file__).parent.parent / "data" / "raw"
RAW_PATH.mkdir(parents=True, exist_ok=True)  # Crée le dossier s'il n'existe pas


def get_youtube_client():
    """
    Crée et retourne un client YouTube API authentifié.

    Pourquoi une fonction séparée ?
    → Principe DRY (Don't Repeat Yourself) : on crée le client
      une seule fois et on le réutilise partout.

    Retourne : un objet client YouTube prêt à faire des requêtes
    """
    # Lit la clé API depuis le fichier .env
    api_key = os.getenv("YOUTUBE_API_KEY")

    # Sécurité : on arrête tout si la clé est absente
    if not api_key:
        raise ValueError("YOUTUBE_API_KEY manquante dans le fichier .env")

    # build() = constructeur du client Google API
    # "youtube" = nom du service, "v3" = version de l'API
    return build("youtube", "v3", developerKey=api_key)


def search_videos(query: str, max_results: int = 50) -> pd.DataFrame:
    """
    Recherche des vidéos YouTube sur un sujet donné.

    Paramètres :
        query       : le mot-clé de recherche (ex: "gestion TPE PME")
        max_results : nombre max de vidéos à récupérer (défaut: 50)

    Retourne : un DataFrame avec les métadonnées des vidéos
               (titre, chaîne, date, description...)

    Note : max_results est limité à 50 par l'API YouTube gratuite
    """
    log.info(f"Recherche YouTube : '{query}' ({max_results} résultats)")

    youtube = get_youtube_client()

    # Construction de la requête API
    # part="snippet" = on veut les métadonnées (titre, description, date...)
    # type="video" = on ne veut que des vidéos (pas des chaînes ou playlists)
    # relevanceLanguage="fr" = vidéos en français en priorité
    # regionCode="FR" = résultats pour la France
    request = youtube.search().list(
        q=query,
        part="snippet",
        type="video",
        maxResults=max_results,
        relevanceLanguage="fr",
        regionCode="FR"
    )

    # execute() envoie la vraie requête HTTP à YouTube
    # et retourne un dictionnaire JSON avec les résultats
    response = request.execute()

    # On transforme le JSON brut en liste de dictionnaires plats
    # plus faciles à mettre dans un DataFrame
    videos = []
    for item in response.get("items", []):
        snippet = item["snippet"]  # Sous-dictionnaire avec les métadonnées
        videos.append({
            "video_id":    item["id"]["videoId"],       # ID unique de la vidéo
            "titre":       snippet["title"],             # Titre
            "description": snippet["description"][:200], # 200 premiers caractères
            "chaine":      snippet["channelTitle"],      # Nom de la chaîne
            "chaine_id":   snippet["channelId"],         # ID unique de la chaîne
            "date_publi":  snippet["publishedAt"],       # Date de publication (ISO 8601)
            "query":       query,                        # Mot-clé utilisé (pour traçabilité)
        })

    df = pd.DataFrame(videos)  # Conversion liste → DataFrame pandas
    log.info(f"{len(df)} vidéos récupérées")
    return df


def get_video_stats(video_ids: list) -> pd.DataFrame:
    """
    Récupère les statistiques des vidéos (vues, likes, commentaires).

    Paramètre :
        video_ids : liste des IDs YouTube à interroger

    Retourne : DataFrame avec video_id + vues + likes + commentaires

    Contrainte API : YouTube accepte max 50 IDs par requête.
    Solution : on découpe la liste en "batches" de 50.
    """
    log.info(f"Récupération des stats pour {len(video_ids)} vidéos")

    youtube = get_youtube_client()
    stats = []  # Liste qui va accumuler les résultats de chaque batch

    # range(0, len(video_ids), 50) génère : 0, 50, 100, 150...
    # Ça permet de découper la liste en tranches de 50
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]  # Tranche courante (max 50 IDs)
        log.info(f"Batch {i//50 + 1} : {len(batch)} vidéos")

        # part="statistics" = on veut uniquement les chiffres
        # id=",".join(batch) = on passe les IDs séparés par des virgules
        request = youtube.videos().list(
            part="statistics",
            id=",".join(batch)
        )
        response = request.execute()

        # Pour chaque vidéo retournée, on extrait les stats
        # .get("viewCount", 0) = retourne 0 si la stat est absente
        # (certaines vidéos ont les stats désactivées)
        for item in response.get("items", []):
            s = item.get("statistics", {})
            stats.append({
                "video_id":     item["id"],
                "vues":         int(s.get("viewCount", 0)),
                "likes":        int(s.get("likeCount", 0)),
                "commentaires": int(s.get("commentCount", 0)),
            })

    return pd.DataFrame(stats)


def inspect(df: pd.DataFrame, name: str) -> None:
    """
    Affiche un résumé lisible d'un DataFrame dans le terminal.
    Utile pour vérifier rapidement que les données sont correctes.

    Paramètres :
        df   : le DataFrame à inspecter
        name : label affiché dans le titre (pour s'y retrouver)
    """
    print(f"\n{'='*50}")
    print(f"INSPECTION : {name}")
    print(f"{'='*50}")
    print(f"Lignes   : {len(df):,}")       # :, = formatage avec séparateur milliers
    print(f"Colonnes : {list(df.columns)}")
    print(f"\nAperçu :")
    print(df.head(3).to_string())          # head(3) = 3 premières lignes
    print(f"\nTypes :")
    print(df.dtypes)                       # Type de chaque colonne (int, str, datetime...)


# --- Point d'entrée du script ---
# Ce bloc ne s'exécute QUE si on lance ce fichier directement
# (pas si on l'importe depuis un autre fichier)
if __name__ == "__main__":

    # Sujets pertinents pour des TPE/PME
    # On cherche 3 thématiques différentes pour avoir de la diversité
    QUERIES = [
        "conseils gestion TPE PME",
        "marketing digital petite entreprise",
        "comptabilité auto entrepreneur",
    ]

    all_videos = []  # Liste qui va accumuler les DataFrames de chaque query

    for query in QUERIES:
        df_videos = search_videos(query, max_results=20)
        all_videos.append(df_videos)

    # pd.concat = fusionne une liste de DataFrames en un seul
    # ignore_index=True = réinitialise les index (0, 1, 2, 3...)
    df_all = pd.concat(all_videos, ignore_index=True)
    inspect(df_all, "Vidéos YouTube")

    # Récupère les stats pour toutes les vidéos trouvées
    video_ids = df_all["video_id"].tolist()  # Convertit la colonne en liste Python
    df_stats = get_video_stats(video_ids)
    inspect(df_stats, "Statistiques vidéos")

    # Merge = jointure entre les deux DataFrames sur la colonne commune "video_id"
    # how="left" = on garde toutes les vidéos, même sans stats
    df_final = df_all.merge(df_stats, on="video_id", how="left")

    # Sauvegarde en CSV
    # encoding="utf-8-sig" = UTF-8 avec BOM, lisible correctement par Excel
    output_path = RAW_PATH / "youtube_tpme.csv"
    df_final.to_csv(output_path, index=False, encoding="utf-8-sig")
    log.info(f"Données sauvegardées : {output_path}")
    log.info(f"Shape finale : {df_final.shape}")  # Shape = (lignes, colonnes)