# social-analytics-tpme
Social Analytics Pipeline — YouTube Insights for TPE/PME

Ce projet analyse l'engagement autour de vidéos YouTube sur des thématiques ciblées pour les TPE/PME.
Objectif:
Identifier les sujets les plus performants sur YouTube pour aider les TPE/PME à orienter leur stratégie de contenu.

Pipeline:
1- Extraction: Récupération de vidéos et métadonnées via l'API YouTube Data v3
2- Transformation: Nettoyage et enrichissement des données en Python (pandas)
3- Chargement: Ingestion dans AWS S3 (data lake partitionné)
4- Analyse: Production d'insights business : taux d'engagement, sujets performants, tendances

Stack technique
Python pandas boto3 AWS S3 AWS Lambda CloudWatch YouTube API v3

Résultats:
--> Pipeline serverless AWS fonctionnel end-to-end
--> Insights actionnables sur les contenus à fort engagement pour les TPE/PME
