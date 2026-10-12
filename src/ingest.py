"""Extraction : recherche de vidéos YouTube et récupération de leurs statistiques."""

import logging

import pandas as pd
from googleapiclient.discovery import build

from src import config

log = logging.getLogger(__name__)

API_PAGE_SIZE = 50  # Maximum autorisé par l'API YouTube Data v3


def get_youtube_client(api_key: str | None = None):
    """Retourne un client YouTube Data v3 authentifié par clé API."""
    api_key = api_key or config.YOUTUBE_API_KEY
    if not api_key:
        raise ValueError("YOUTUBE_API_KEY manquante (fichier .env ou variable d'environnement)")
    # cache_discovery=False évite un warning et un accès disque inutile (Lambda)
    return build("youtube", "v3", developerKey=api_key, cache_discovery=False)


def search_videos(youtube, query: str, max_results: int = 50) -> pd.DataFrame:
    """Recherche les vidéos francophones correspondant à `query`.

    Gère la pagination : `max_results` peut dépasser 50.
    """
    log.info("Recherche YouTube : '%s' (%d résultats max)", query, max_results)

    videos = []
    page_token = None
    while len(videos) < max_results:
        response = youtube.search().list(
            q=query,
            part="snippet",
            type="video",
            maxResults=min(API_PAGE_SIZE, max_results - len(videos)),
            relevanceLanguage="fr",
            regionCode="FR",
            pageToken=page_token,
        ).execute()

        for item in response.get("items", []):
            snippet = item["snippet"]
            videos.append({
                "video_id": item["id"]["videoId"],
                "titre": snippet["title"],
                "description": snippet["description"][:200],
                "chaine": snippet["channelTitle"],
                "chaine_id": snippet["channelId"],
                "date_publi": snippet["publishedAt"],
                "query": query,
            })

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    log.info("%d vidéos récupérées pour '%s'", len(videos), query)
    return pd.DataFrame(videos)


def get_video_stats(youtube, video_ids: list[str]) -> pd.DataFrame:
    """Récupère vues, likes et commentaires par lots de 50 IDs (limite de l'API)."""
    log.info("Récupération des stats pour %d vidéos", len(video_ids))

    stats = []
    for i in range(0, len(video_ids), API_PAGE_SIZE):
        batch = video_ids[i:i + API_PAGE_SIZE]
        response = youtube.videos().list(part="statistics", id=",".join(batch)).execute()

        for item in response.get("items", []):
            s = item.get("statistics", {})
            # Une stat absente signifie qu'elle est masquée par le créateur
            stats.append({
                "video_id": item["id"],
                "vues": int(s.get("viewCount", 0)),
                "likes": int(s.get("likeCount", 0)),
                "commentaires": int(s.get("commentCount", 0)),
            })

    return pd.DataFrame(stats, columns=["video_id", "vues", "likes", "commentaires"])


def extract(queries: list[str] = config.QUERIES,
            max_results: int = config.MAX_RESULTS_PER_QUERY) -> pd.DataFrame:
    """Extrait les vidéos de chaque thématique et y joint leurs statistiques."""
    youtube = get_youtube_client()

    df_videos = pd.concat(
        [search_videos(youtube, q, max_results) for q in queries],
        ignore_index=True,
    )
    if df_videos.empty:
        log.warning("Aucune vidéo trouvée")
        return df_videos

    df_stats = get_video_stats(youtube, df_videos["video_id"].unique().tolist())
    return df_videos.merge(df_stats, on="video_id", how="left")


if __name__ == "__main__":
    config.setup_logging()
    df = extract()

    config.RAW_PATH.mkdir(parents=True, exist_ok=True)
    output = config.RAW_PATH / config.RAW_FILENAME
    # utf-8-sig : lisible correctement dans Excel
    df.to_csv(output, index=False, encoding="utf-8-sig")
    log.info("Données brutes sauvegardées : %s %s", output, df.shape)
