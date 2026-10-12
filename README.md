# Social Analytics Pipeline — YouTube Insights pour TPE/PME

Pipeline de données qui analyse l'engagement des vidéos YouTube sur des thématiques
utiles aux TPE/PME (gestion, marketing digital, comptabilité), afin d'identifier
les sujets les plus performants et d'orienter leur stratégie de contenu.

## Architecture

```
 EventBridge (planifié)
        │
        ▼
 ┌──────────────┐   extract    ┌──────────────┐   clean / enrich   ┌──────────────────────────┐
 │  AWS Lambda  │ ───────────▶ │ YouTube Data │ ─────────────────▶ │  S3 data lake (Hive)     │
 │ src.pipeline │              │    API v3    │      pandas        │  youtube/raw/year=…/     │
 └──────────────┘              └──────────────┘                    │  youtube/clean/year=…/   │
        │                                                          └──────────────────────────┘
        ▼
  CloudWatch Logs
```

| Étape | Module | Rôle |
|---|---|---|
| Extraction | `src/ingest.py` | Recherche des vidéos par thématique (pagination) et récupération des statistiques par lots de 50 |
| Transformation | `src/transform.py` | Décodage HTML, dates, dédoublonnage, taux d'engagement, catégorie de performance |
| Chargement | `src/upload_s3.py` | Écriture CSV dans S3, partitionnée par date (`year=/month=/day=`) |
| Orchestration | `src/pipeline.py` | Enchaîne les 3 étapes ; utilisable en local ou comme handler Lambda |

### Indicateurs produits

- **Taux d'engagement** = (likes + commentaires) / vues × 100
- **Performance** : `faible` (< 1k vues), `moyen` (< 10k), `bon` (< 100k), `viral` (≥ 100k)
- Top vidéos, top chaînes, vues et engagement moyens par thématique
- Sujet le plus vu et sujet le plus engageant

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # puis renseigner YOUTUBE_API_KEY et S3_BUCKET
```

Les credentials AWS ne sont jamais écrits dans le code : ils sont lus par boto3
(`aws configure` en local, rôle IAM en Lambda).

## Utilisation

Pipeline complet (YouTube → S3) :

```bash
python -m src.pipeline
```

Étape par étape, avec fichiers intermédiaires dans `data/` :

```bash
python -m src.ingest      # → data/raw/youtube_tpme.csv
python -m src.transform   # → data/clean/youtube_tpme_clean.csv + insights dans le terminal
python -m src.upload_s3   # → s3://<bucket>/youtube/clean/year=…/month=…/day=…/
```

## Déploiement AWS Lambda

- **Handler** : `src.pipeline.lambda_handler`
- **Variables d'environnement** : `YOUTUBE_API_KEY`, `S3_BUCKET` (et `AWS_REGION` si besoin)
- **Rôle IAM** : `s3:PutObject` et `s3:ListBucket` sur le bucket
- **Dépendances** : pandas via la layer publique *AWSSDKPandas*, `google-api-python-client`
  et `python-dotenv` dans le package de déploiement
- **Planification** : règle EventBridge (ex. `rate(1 day)`)
- **Timeout** recommandé : 1 à 2 minutes

## Tests

```bash
pytest
```

Les tests n'appellent ni YouTube ni AWS : l'API YouTube est simulée et S3 est
mocké avec [moto](https://github.com/getmoto/moto), y compris un run complet du
`lambda_handler`.

## Stack

Python · pandas · boto3 · AWS S3 · AWS Lambda · CloudWatch · YouTube Data API v3 · pytest · moto

## Structure

```
.
├── src/
│   ├── config.py       # chemins, variables d'environnement, logging
│   ├── ingest.py       # extraction YouTube API
│   ├── transform.py    # nettoyage + insights
│   ├── upload_s3.py    # chargement S3 partitionné
│   └── pipeline.py     # orchestration + handler Lambda
├── tests/
├── .env.example
├── requirements.txt
└── requirements-dev.txt
```
