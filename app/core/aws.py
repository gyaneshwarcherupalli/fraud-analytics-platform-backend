"""AWS session, S3 storage, and resource provisioning helpers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, BinaryIO, Dict, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings
from app.utils.exceptions import ExternalServiceException


def aws_client(service_name: str):
    """Create an AWS client using the standard credential provider chain.

    Explicit credentials are passed only when configured, allowing ECS/EC2 IAM
    roles, AWS profiles, and web identity credentials to work normally.
    """
    kwargs: Dict[str, Any] = {"region_name": settings.aws_region}
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        kwargs.update(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
        if settings.aws_session_token:
            kwargs["aws_session_token"] = settings.aws_session_token
    if settings.aws_endpoint_url:
        kwargs["endpoint_url"] = settings.aws_endpoint_url
    return boto3.client(service_name, **kwargs)


class S3StorageService:
    """Encrypted object storage for reports, exports, and model artifacts."""

    def __init__(self, bucket: Optional[str] = None, client=None) -> None:
        self.bucket = bucket or settings.aws_s3_bucket
        self.client = client or aws_client("s3")

    def ensure_bucket(self) -> None:
        """Idempotently create and secure the configured bucket."""
        try:
            try:
                self.client.head_bucket(Bucket=self.bucket)
            except ClientError as exc:
                code = str(exc.response.get("Error", {}).get("Code", ""))
                if code not in {"404", "NoSuchBucket", "NotFound"}:
                    raise
                args: Dict[str, Any] = {"Bucket": self.bucket}
                if settings.aws_region != "us-east-1":
                    args["CreateBucketConfiguration"] = {"LocationConstraint": settings.aws_region}
                self.client.create_bucket(**args)

            encryption = {"SSEAlgorithm": "AES256"}
            if settings.aws_s3_kms_key_id:
                encryption = {
                    "SSEAlgorithm": "aws:kms",
                    "KMSMasterKeyID": settings.aws_s3_kms_key_id,
                }
            encryption_rule: Dict[str, Any] = {
                "ApplyServerSideEncryptionByDefault": encryption,
            }
            if settings.aws_s3_kms_key_id:
                encryption_rule["BucketKeyEnabled"] = True
            self.client.put_bucket_encryption(
                Bucket=self.bucket,
                ServerSideEncryptionConfiguration={"Rules": [encryption_rule]},
            )
            self.client.put_public_access_block(Bucket=self.bucket, PublicAccessBlockConfiguration={
                "BlockPublicAcls": True, "IgnorePublicAcls": True,
                "BlockPublicPolicy": True, "RestrictPublicBuckets": True,
            })
            self.client.put_bucket_versioning(
                Bucket=self.bucket, VersioningConfiguration={"Status": "Enabled"}
            )
            self.client.put_bucket_lifecycle_configuration(Bucket=self.bucket, LifecycleConfiguration={
                "Rules": [{
                    "ID": "archive-and-expire",
                    "Status": "Enabled",
                    "Filter": {"Prefix": settings.aws_s3_prefix},
                    "Transitions": [{"Days": 30, "StorageClass": "STANDARD_IA"}],
                    "NoncurrentVersionExpiration": {"NoncurrentDays": 90},
                    "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7},
                }]
            })
        except (BotoCoreError, ClientError) as exc:
            raise ExternalServiceException(f"Unable to configure S3 bucket: {exc}") from exc

    def upload_file(self, local_path: str | Path, key: str, content_type: Optional[str] = None) -> str:
        extra = {"ContentType": content_type} if content_type else {}
        try:
            self.client.upload_file(str(local_path), self.bucket, self._key(key), ExtraArgs=extra or None)
            return self.uri(key)
        except (BotoCoreError, ClientError, OSError) as exc:
            raise ExternalServiceException(f"S3 upload failed: {exc}") from exc

    def upload_bytes(self, data: bytes | BinaryIO, key: str, content_type: str = "application/octet-stream") -> str:
        body = data.read() if hasattr(data, "read") else data
        try:
            self.client.put_object(Bucket=self.bucket, Key=self._key(key), Body=body, ContentType=content_type)
            return self.uri(key)
        except (BotoCoreError, ClientError) as exc:
            raise ExternalServiceException(f"S3 upload failed: {exc}") from exc

    def upload_json(self, payload: Any, key: str) -> str:
        return self.upload_bytes(json.dumps(payload, default=str).encode("utf-8"), key, "application/json")

    def download_file(self, key: str, local_path: str | Path) -> Path:
        destination = Path(local_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.client.download_file(self.bucket, self._key(key), str(destination))
            return destination
        except (BotoCoreError, ClientError, OSError) as exc:
            raise ExternalServiceException(f"S3 download failed: {exc}") from exc

    def presigned_download_url(self, key: str, expires_in: int = 900) -> str:
        try:
            return self.client.generate_presigned_url(
                "get_object", Params={"Bucket": self.bucket, "Key": self._key(key)},
                ExpiresIn=expires_in,
            )
        except (BotoCoreError, ClientError) as exc:
            raise ExternalServiceException(f"Unable to create presigned URL: {exc}") from exc

    def uri(self, key: str) -> str:
        return f"s3://{self.bucket}/{self._key(key)}"

    @staticmethod
    def _key(key: str) -> str:
        clean = key.lstrip("/")
        prefix = settings.aws_s3_prefix.strip("/")
        return f"{prefix}/{clean}" if prefix else clean
