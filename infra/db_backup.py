#!/usr/bin/env python3
"""Park/retrieve a Postgres dump in the Terraform state bucket.

The freeze/thaw workflow tears the managed database down with the rest of the
infra, so the only safe place to keep a dump is somewhere that *isn't* managed
by Terraform. The state bucket (created by bootstrap_state.py, not by `apply`)
fits perfectly and is already versioned, so we stash dumps there under a
`db-backups/` prefix.

Env (same conventions as bootstrap_state.py):
  AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY  -> your DO Spaces keys
  SLICER2_STATE_REGION (default: nyc3)        -> must match the state bucket
  SLICER2_STATE_BUCKET (default: slicer2-tfstate)

Usage:
  python infra/db_backup.py upload <local-dump.sql.gz>
  python infra/db_backup.py download-latest <dest.sql.gz>
"""
from __future__ import annotations

import os
import sys

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    sys.exit("boto3 is required: pip install boto3")

PREFIX = "db-backups/"


def _client():
    region = os.getenv("SLICER2_STATE_REGION", "nyc3")
    key = os.getenv("AWS_ACCESS_KEY_ID")
    secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    if not (key and secret):
        sys.exit("Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY to your Spaces keys.")
    bucket = os.getenv("SLICER2_STATE_BUCKET", "slicer2-tfstate")
    s3 = boto3.client(
        "s3",
        region_name=region,
        endpoint_url=f"https://{region}.digitaloceanspaces.com",
        aws_access_key_id=key,
        aws_secret_access_key=secret,
    )
    return s3, bucket


def upload(path: str) -> None:
    if not os.path.isfile(path):
        sys.exit(f"No such file: {path}")
    s3, bucket = _client()
    import datetime

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    key = f"{PREFIX}{stamp}.sql.gz"
    s3.upload_file(path, bucket, key)
    print(key)


def download_latest(dest: str) -> None:
    s3, bucket = _client()
    keys: list[str] = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=PREFIX):
        keys.extend(obj["Key"] for obj in page.get("Contents", []))
    if not keys:
        sys.exit(f"No backups found under s3://{bucket}/{PREFIX}")
    latest = max(keys)  # timestamp naming sorts lexicographically
    try:
        s3.download_file(bucket, latest, dest)
    except ClientError as e:
        sys.exit(f"Download failed: {e}")
    print(latest)


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    cmd, arg = sys.argv[1], sys.argv[2]
    if cmd == "upload":
        upload(arg)
    elif cmd == "download-latest":
        download_latest(arg)
    else:
        sys.exit(f"Unknown command: {cmd}\n{__doc__}")


if __name__ == "__main__":
    main()
