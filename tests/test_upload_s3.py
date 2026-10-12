from datetime import datetime

import boto3
import pandas as pd
import pytest
from moto import mock_aws

from src.upload_s3 import build_s3_key, list_objects, upload_dataframe

BUCKET = "test-bucket"


def test_build_s3_key_is_partitioned_by_date():
    key = build_s3_key("file.csv", datetime(2026, 5, 7))
    assert key == "youtube/clean/year=2026/month=05/day=07/file.csv"


def test_build_s3_key_custom_prefix():
    key = build_s3_key("file.csv", datetime(2026, 12, 25), prefix="youtube/raw")
    assert key == "youtube/raw/year=2026/month=12/day=25/file.csv"


@pytest.fixture
def s3(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    with mock_aws():
        client = boto3.client("s3", region_name="eu-north-1")
        client.create_bucket(
            Bucket=BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "eu-north-1"},
        )
        yield client


def test_upload_dataframe_and_list(s3):
    df = pd.DataFrame({"video_id": ["a", "b"], "vues": [10, 20]})
    key = build_s3_key("clean.csv", datetime(2026, 5, 7))

    uri = upload_dataframe(df, key, bucket=BUCKET, s3=s3)

    assert uri == f"s3://{BUCKET}/{key}"
    body = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read().decode()
    assert body.splitlines() == ["video_id,vues", "a,10", "b,20"]
    assert [o["Key"] for o in list_objects(bucket=BUCKET, s3=s3)] == [key]
