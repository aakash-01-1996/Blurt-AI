from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class StorageProvider(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def playback_url(self, key: str, *, expires_in: int = 3600) -> str: ...


class LocalDiskStorage:
    def __init__(self, base_dir: str) -> None:
        self._base = Path(base_dir).resolve()

    def _resolve(self, key: str) -> Path:
        """Resolve `key` to a path under the base directory."""
        path = (self._base / key).resolve()
        if path != self._base and self._base not in path.parents:
            raise ValueError(f"invalid storage key: {key!r}")
        return path

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._resolve(key)
        self._base.mkdir(parents=True, exist_ok=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.exists():
            path.unlink()

    def playback_url(self, key: str, *, expires_in: int = 3600) -> str:
        # The API streams local files — return a path the API can resolve
        return f"/api/v1/audio/{key}"


class S3Storage:
    def __init__(
        self,
        endpoint_url: str,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
    ) -> None:
        import boto3

        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    def get(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        return response["Body"].read()

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def playback_url(self, key: str, *, expires_in: int = 3600) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )


class FakeStorage:
    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._store[key] = data

    def get(self, key: str) -> bytes:
        return self._store[key]

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def playback_url(self, key: str, *, expires_in: int = 3600) -> str:
        return f"/fake/{key}"


def build_storage_provider(settings: object) -> LocalDiskStorage | S3Storage:
    """Build the storage provider singleton from settings."""
    from blurt_core.config import Settings

    assert isinstance(settings, Settings)
    if settings.storage_backend == "s3":
        return S3Storage(
            endpoint_url=settings.s3_endpoint_url,
            bucket=settings.s3_bucket,
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key,
        )
    return LocalDiskStorage(settings.audio_dir)
