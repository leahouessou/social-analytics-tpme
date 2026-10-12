import boto3
import pytest
from moto import mock_aws

from src import config, ingest, pipeline


class FakeRequest:
    def __init__(self, response):
        self.response = response

    def execute(self):
        return self.response


class FakeYouTube:
    """Simule l'API YouTube : 2 pages de recherche par thématique, puis les stats."""

    def __init__(self):
        self.search_calls = []

    def search(self):
        return self

    def videos(self):
        return _FakeVideos()

    def list(self, q, pageToken=None, maxResults=50, **kwargs):
        self.search_calls.append((q, pageToken, maxResults))
        page = 2 if pageToken else 1
        items = [{
            "id": {"videoId": f"{q}-{page}-{i}"},
            "snippet": {
                "title": f"Vidéo {i} &amp; co", "description": "d" * 300,
                "channelTitle": "Chaine", "channelId": "c1",
                "publishedAt": "2024-01-15T10:00:00Z",
            },
        } for i in range(maxResults)]
        return FakeRequest({"items": items, "nextPageToken": None if page == 2 else "p2"})


class _FakeVideos:
    def list(self, part, id):
        return FakeRequest({"items": [
            {"id": vid, "statistics": {"viewCount": "5000", "likeCount": "100"}}
            for vid in id.split(",")
        ]})


def test_search_videos_paginates():
    yt = FakeYouTube()
    df = ingest.search_videos(yt, "compta", max_results=70)

    assert len(df) == 70
    assert [c[2] for c in yt.search_calls] == [50, 20]
    assert df["description"].str.len().max() == 200


def test_get_video_stats_batches_and_defaults():
    df = ingest.get_video_stats(FakeYouTube(), [f"v{i}" for i in range(120)])
    assert len(df) == 120
    assert df["commentaires"].eq(0).all()  # stat masquée → 0


@pytest.fixture
def aws(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setattr(config, "S3_BUCKET", "test-bucket")
    with mock_aws():
        s3 = boto3.client("s3", region_name=config.AWS_REGION)
        s3.create_bucket(
            Bucket="test-bucket",
            CreateBucketConfiguration={"LocationConstraint": config.AWS_REGION},
        )
        yield s3


def test_lambda_handler_end_to_end(aws, monkeypatch):
    monkeypatch.setattr(ingest, "get_youtube_client", lambda: FakeYouTube())

    result = pipeline.lambda_handler({}, None)

    assert result["status"] == "success"
    assert result["rows"] == 3 * config.MAX_RESULTS_PER_QUERY
    keys = [o["Key"] for o in aws.list_objects_v2(Bucket="test-bucket")["Contents"]]
    assert any(k.startswith("youtube/raw/year=") for k in keys)
    assert any(k.startswith("youtube/clean/year=") for k in keys)
