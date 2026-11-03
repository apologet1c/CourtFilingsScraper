"""S3 layout helpers.

  {RAW_PREFIX}/{db}/judge={id}/{YYYY}/{MM}/{YYYY-MM-DD}.html   raw docket pages
  {CASE_PREFIX}/{db}/{casemasterid}.html                         raw case pages (only if VERIFY_FED)
  {REPORT_PREFIX}/{db}/{year}/...csv|json                        generated reports
"""
from __future__ import annotations

import os
from datetime import date

import boto3
from botocore.exceptions import ClientError

BUCKET = os.environ.get("S3_BUCKET", "")
RAW_PREFIX = os.environ.get("RAW_PREFIX", "raw/dockets").strip("/")
CASE_PREFIX = os.environ.get("CASE_PREFIX", "raw/cases").strip("/")
REPORT_PREFIX = os.environ.get("REPORT_PREFIX", "reports/dockets").strip("/")

_s3 = boto3.client("s3")


def docket_key(db: str, judge_id: str, day: date) -> str:
    return f"{RAW_PREFIX}/{db}/judge={judge_id}/{day:%Y}/{day:%m}/{day.isoformat()}.html"


def case_key(db: str, casemasterid: str) -> str:
    return f"{CASE_PREFIX}/{db}/{casemasterid}.html"


def exists(key: str) -> bool:
    try:
        _s3.head_object(Bucket=BUCKET, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


def put_text(key: str, body: str, content_type: str = "text/html; charset=ISO-8859-1",
             metadata: dict | None = None) -> None:
    enc = "ISO-8859-1" if "8859" in content_type else "utf-8"
    _s3.put_object(Bucket=BUCKET, Key=key, Body=body.encode(enc, errors="replace"),
                   ContentType=content_type, Metadata=metadata or {})


def get_text(key: str) -> str:
    obj = _s3.get_object(Bucket=BUCKET, Key=key)
    return obj["Body"].read().decode("ISO-8859-1")


def list_keys(prefix: str):
    paginator = _s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for o in page.get("Contents", []):
            yield o["Key"]


def get_text_or_none(key: str) -> str | None:
    try:
        return get_text(key)
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            return None
        raise
