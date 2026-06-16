#!/usr/bin/env python3
"""Create the Spaces bucket that holds Terraform remote state (run once).

The S3 backend in backend.tf can't create its own bucket, so this bootstraps it
and enables versioning (so a bad apply can be rolled back).

Env:
  AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY  -> your DO Spaces keys
  SLICER2_STATE_REGION (default: nyc3)        -> must match backend.tf endpoint
  SLICER2_STATE_BUCKET (default: slicer2-tfstate)

Usage:
  pip install boto3
  python infra/bootstrap_state.py
"""
from __future__ import annotations

import os
import sys

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    sys.exit("boto3 is required: pip install boto3")

region = os.getenv("SLICER2_STATE_REGION", "nyc3")
bucket = os.getenv("SLICER2_STATE_BUCKET", "slicer2-tfstate")
key = os.getenv("AWS_ACCESS_KEY_ID")
secret = os.getenv("AWS_SECRET_ACCESS_KEY")

if not (key and secret):
    sys.exit("Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY to your Spaces keys.")

s3 = boto3.client(
    "s3",
    region_name=region,
    endpoint_url=f"https://{region}.digitaloceanspaces.com",
    aws_access_key_id=key,
    aws_secret_access_key=secret,
)

try:
    s3.head_bucket(Bucket=bucket)
    print(f"State bucket '{bucket}' already exists in {region}.")
except ClientError:
    print(f"Creating state bucket '{bucket}' in {region}…")
    s3.create_bucket(Bucket=bucket)

s3.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})
print(f"Done. Versioning enabled on '{bucket}'. backend.tf is ready to init.")
