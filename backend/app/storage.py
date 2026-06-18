"""Object storage for uploads and sliced outputs.

Two interchangeable backends behind one tiny API:
  * **Spaces/S3** (boto3) when ``SPACES_*`` is configured — what production uses.
  * **Local disk** under ``DATA_DIR/objects`` otherwise — so dev/test and a
    single small host need no external bucket.

Keys mirror the old on-disk layout: ``uploads/<job_id>/<file>`` and
``outputs/<job_id>.gcode.3mf``. The bucket's lifecycle rule (infra) expires both.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import BinaryIO, Optional

from . import config

_LOCAL_ROOT = config.DATA_DIR / "objects"


def is_remote() -> bool:
    """True when a Spaces/S3 bucket is configured."""
    return bool(config.SPACES_BUCKET and config.SPACES_ENDPOINT)


_client = None


def _s3():
    global _client
    if _client is None:
        import boto3  # imported lazily so local/dev needs no boto3 at import time

        _client = boto3.client(
            "s3",
            endpoint_url=config.SPACES_ENDPOINT,
            region_name=config.SPACES_REGION,
            aws_access_key_id=config.SPACES_ACCESS_ID,
            aws_secret_access_key=config.SPACES_SECRET_KEY,
        )
    return _client


def _local(key: str) -> Path:
    p = _LOCAL_ROOT / key
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def upload_fileobj(key: str, fileobj: BinaryIO) -> None:
    if is_remote():
        _s3().upload_fileobj(fileobj, config.SPACES_BUCKET, key)
    else:
        with open(_local(key), "wb") as out:
            shutil.copyfileobj(fileobj, out)


def upload_file(key: str, local_path: Path) -> None:
    if is_remote():
        _s3().upload_file(str(local_path), config.SPACES_BUCKET, key)
    else:
        dest = _local(key)
        if Path(local_path) != dest:
            shutil.copyfile(local_path, dest)


def download_to(key: str, local_path: Path) -> Path:
    local_path = Path(local_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    if is_remote():
        _s3().download_file(config.SPACES_BUCKET, key, str(local_path))
    else:
        shutil.copyfile(_local(key), local_path)
    return local_path


def presigned_get_url(key: str, *, filename: Optional[str] = None, expires: int = 3600) -> Optional[str]:
    """A time-limited GET URL for remote storage, or ``None`` for local disk.

    Callers serve local files directly (``local_path``) and redirect remote ones.
    """
    if not is_remote():
        return None
    params = {"Bucket": config.SPACES_BUCKET, "Key": key}
    if filename:
        params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
    return _s3().generate_presigned_url("get_object", Params=params, ExpiresIn=expires)


def local_path(key: str) -> Path:
    """Filesystem path for a local-backend object (only valid when not remote)."""
    return _local(key)


def delete(key: str) -> None:
    if is_remote():
        _s3().delete_object(Bucket=config.SPACES_BUCKET, Key=key)
    else:
        _local(key).unlink(missing_ok=True)
