import pandas as pd
import pytest

from src.transform import clean, compute_insights


@pytest.fixture
def raw_df():
    return pd.DataFrame({
        "video_id": ["a", "b", "b", "c"],
        "titre": ["L&#39;astuce &amp; co", "Compta", "Compta", None],
        "description": ["desc", None, None, "x"],
        "chaine": ["Chaine1", "Chaine2", "Chaine2", "Chaine1"],
        "chaine_id": ["c1", "c2", "c2", "c1"],
        "date_publi": ["2023-09-07T06:51:22Z", "2024-01-15T10:00:00Z",
                       "2024-01-15T10:00:00Z", "2025-03-01T00:00:00Z"],
        "query": ["gestion", "compta", "marketing", "gestion"],
        "vues": [2_000, 150_000, 150_000, 0],
        "likes": [100, 3_000, 3_000, 0],
        "commentaires": [20, 0, 0, 0],
    })


def test_clean_decodes_html(raw_df):
    df = clean(raw_df)
    assert df.loc[df.video_id == "a", "titre"].item() == "L'astuce & co"
    assert df.loc[df.video_id == "c", "titre"].item() == ""


def test_clean_removes_duplicates(raw_df):
    df = clean(raw_df)
    assert df["video_id"].tolist() == ["a", "b", "c"]


def test_clean_extracts_dates(raw_df):
    df = clean(raw_df)
    assert df.loc[df.video_id == "a", ["annee", "mois"]].values.tolist() == [[2023, 9]]


def test_engagement_rate(raw_df):
    df = clean(raw_df).set_index("video_id")
    assert df.loc["a", "taux_engagement"] == 6.0   # (100 + 20) / 2000 * 100
    assert df.loc["b", "taux_engagement"] == 2.0
    assert pd.isna(df.loc["c", "taux_engagement"])  # 0 vue : pas de taux


def test_performance_categories(raw_df):
    df = clean(raw_df).set_index("video_id")
    assert df.loc["a", "performance"] == "moyen"
    assert df.loc["b", "performance"] == "viral"
    assert df.loc["c", "performance"] == "faible"  # 0 vue reste classée


def test_clean_does_not_mutate_input(raw_df):
    before = raw_df.copy()
    clean(raw_df)
    pd.testing.assert_frame_equal(raw_df, before)


def test_compute_insights(raw_df):
    insights = compute_insights(clean(raw_df))
    assert insights["nb_videos"] == 3
    assert insights["vues_totales"] == 152_000
    assert insights["sujet_plus_vu"] == "compta"
    assert insights["sujet_plus_engageant"] == "gestion"
