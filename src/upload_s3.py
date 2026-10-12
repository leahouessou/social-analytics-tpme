# ============================================================
# upload_s3.py — Upload des données nettoyées vers AWS S3
# ============================================================
# Ce script fait 3 choses :
#   1. Se connecte à AWS S3 avec tes credentials
#   2. Organise les fichiers par date (structure data lake)
#   3. Uploade les données nettoyées dans le bucket
#
# Structure data lake dans S3 :
#   social-analytics-tpme-lea/
#   └── youtube/
#       └── clean/
#           └── year=2026/
#               └── month=05/
#                   └── youtube_tpme_clean.csv
# ============================================================

import boto3          # SDK AWS pour Python
import logging
import os
from pathlib import Path
from datetime import datetime  # Pour organiser les fichiers par date
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger(__name__)

# --- Chemins locaux ---
CLEAN_PATH = Path(__file__).parent.parent / "data" / "clean"

# --- Config AWS ---
# Ces valeurs viennent du fichier .env
BUCKET_NAME = "social-analytics-tpme-lea-296122126872-eu-north-1-an"# ← mets ton vrai nom de bucket
AWS_REGION = os.getenv("AWS_REGION", "eu-north-1")

def get_s3_client():
    """
    Crée et retourne un client boto3 connecté à S3.

    boto3 lit automatiquement les variables d'environnement :
    AWS_ACCESS_KEY_ID et AWS_SECRET_ACCESS_KEY
    Pas besoin de les passer manuellement.

    Retourne : un objet client S3 prêt à uploader
    """
    return boto3.client(
        "s3",
        region_name=AWS_REGION,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
    )


def build_s3_key(filename: str) -> str:
    """
    Construit le chemin S3 du fichier avec partitionnement par date.

    Pourquoi partitionner par date ?
    → C'est la bonne pratique data lake : chaque exécution
      crée un nouveau fichier daté, on garde l'historique complet.
    → Athena et Glue peuvent lire ces partitions efficacement.

    Exemple de résultat :
    youtube/clean/year=2026/month=05/day=07/youtube_tpme_clean.csv

    Paramètre : filename = nom du fichier local
    Retourne  : chemin S3 complet (appelé "key" dans AWS)
    """
    now = datetime.now()
    return (
        f"youtube/clean/"
        f"year={now.year}/"
        f"month={now.month:02d}/"   # :02d = toujours 2 chiffres (05 pas 5)
        f"day={now.day:02d}/"
        f"{filename}"
    )


def upload_file(local_path: Path, s3_key: str) -> bool:
    """
    Uploade un fichier local vers S3.

    Paramètres :
        local_path : chemin du fichier sur ton ordinateur
        s3_key     : chemin de destination dans le bucket S3

    Retourne : True si succès, False si erreur
    """
    s3 = get_s3_client()

    try:
        log.info(f"Upload : {local_path.name} → s3://{BUCKET_NAME}/{s3_key}")

        # upload_file() = méthode boto3 pour envoyer un fichier
        # ExtraArgs = métadonnées supplémentaires sur le fichier
        s3.upload_file(
            Filename=str(local_path),   # Chemin local (doit être une string)
            Bucket=BUCKET_NAME,         # Nom du bucket
            Key=s3_key,                 # Chemin dans le bucket
            ExtraArgs={
                "ContentType": "text/csv",  # Type MIME du fichier
                "Metadata": {               # Métadonnées custom
                    "source":    "youtube-api",
                    "project":   "social-analytics-tpme",
                    "uploaded":  datetime.now().isoformat(),
                }
            }
        )

        log.info(f"✓ Upload réussi !")
        log.info(f"  URL : s3://{BUCKET_NAME}/{s3_key}")
        return True

    except Exception as e:
        # On capture toutes les erreurs AWS (credentials, bucket inexistant, etc.)
        log.error(f"✗ Erreur upload : {e}")
        return False


def verify_upload(s3_key: str) -> None:
    """
    Vérifie que le fichier est bien arrivé dans S3.
    Affiche la taille et la date de dernière modification.

    Paramètre : s3_key = chemin S3 du fichier uploadé
    """
    s3 = get_s3_client()

    try:
        # head_object() = récupère les métadonnées sans télécharger le fichier
        response = s3.head_object(Bucket=BUCKET_NAME, Key=s3_key)

        taille = response["ContentLength"]  # Taille en octets
        date   = response["LastModified"]   # Date de dernière modification

        log.info(f"✓ Vérification S3 :")
        log.info(f"  Taille : {taille:,} octets ({taille/1024:.1f} KB)")
        log.info(f"  Date   : {date}")

    except Exception as e:
        log.error(f"✗ Fichier introuvable dans S3 : {e}")


def list_bucket() -> None:
    """
    Liste tous les fichiers dans le bucket S3.
    Utile pour voir la structure data lake qu'on a créée.
    """
    s3 = get_s3_client()

    try:
        # list_objects_v2() = liste les fichiers dans un bucket
        # Prefix="youtube/" = filtre sur le dossier youtube/
        response = s3.list_objects_v2(
            Bucket=BUCKET_NAME,
            Prefix="youtube/"
        )

        objects = response.get("Contents", [])

        if not objects:
            log.info("Bucket vide pour le moment.")
            return

        log.info(f"\n📦 Contenu du bucket s3://{BUCKET_NAME}/")
        for obj in objects:
            taille = obj["Size"]
            date   = obj["LastModified"].strftime("%Y-%m-%d %H:%M")
            key    = obj["Key"]
            log.info(f"  {date} | {taille:>8,} octets | {key}")

    except Exception as e:
        log.error(f"✗ Erreur listage bucket : {e}")


# --- Point d'entrée ---
if __name__ == "__main__":

    # Fichier à uploader
    local_file = CLEAN_PATH / "youtube_tpme_clean.csv"

    # Vérifie que le fichier existe
    if not local_file.exists():
        log.error(f"Fichier introuvable : {local_file}")
        log.error("Lance d'abord : python src/transform.py")
        exit(1)

    # Construit le chemin S3 avec partitionnement par date
    s3_key = build_s3_key(local_file.name)

    # Upload
    success = upload_file(local_file, s3_key)

    if success:
        # Vérifie que le fichier est bien arrivé
        verify_upload(s3_key)

        # Affiche la structure du bucket
        list_bucket()