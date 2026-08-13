"""Provision the platform's S3 and CloudWatch resources."""
from app.core.aws import S3StorageService
from monitoring.cloudwatch_metrics import provision_monitoring


def main() -> None:
    storage = S3StorageService()
    storage.ensure_bucket()
    monitoring = provision_monitoring()
    print({"bucket": storage.bucket, **monitoring})


if __name__ == "__main__":
    main()
