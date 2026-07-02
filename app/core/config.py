"""
Configuration module for the Fraud Analytics Platform.
Handles environment variables and application settings.
"""
from pydantic_settings import BaseSettings
from typing import Optional, List
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application Settings
    environment: str = os.getenv("ENVIRONMENT", "development")
    debug: bool = os.getenv("DEBUG", "True").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Server Configuration
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    reload: bool = os.getenv("RELOAD", "True").lower() == "true"
    
    # API Configuration
    api_title: str = "Fraud Analytics Platform"
    api_description: str = "Real-time fraud detection and analytics platform"
    api_version: str = "1.0.0"

    # Database Configuration - PostgreSQL
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = int(os.getenv("DB_PORT", "5432"))
    db_name: str = os.getenv("DB_NAME", "fraud_analytics")
    db_user: str = os.getenv("DB_USER", "fraud_admin")
    db_password: str = os.getenv("DB_PASSWORD", "")
    
    @property
    def database_url(self) -> str:
        """Generate PostgreSQL database URL."""
        return (
            f"postgresql://{self.db_user}:{self.db_password}@"
            f"{self.db_host}:{self.db_port}/{self.db_name}"
        )

    # Snowflake Configuration
    snowflake_account: str = os.getenv("SNOWFLAKE_ACCOUNT", "")
    snowflake_user: str = os.getenv("SNOWFLAKE_USER", "")
    snowflake_password: str = os.getenv("SNOWFLAKE_PASSWORD", "")
    snowflake_database: str = os.getenv("SNOWFLAKE_DATABASE", "fraud_analytics")
    snowflake_schema: str = os.getenv("SNOWFLAKE_SCHEMA", "public")
    snowflake_warehouse: str = os.getenv("SNOWFLAKE_WAREHOUSE", "compute_wh")

    # Kafka Configuration
    kafka_broker: str = os.getenv("KAFKA_BROKER", "localhost:9092")
    kafka_topic_transactions: str = os.getenv("KAFKA_TOPIC_TRANSACTIONS", "transactions")
    kafka_topic_alerts: str = os.getenv("KAFKA_TOPIC_ALERTS", "alerts")
    kafka_consumer_group: str = os.getenv("KAFKA_CONSUMER_GROUP", "fraud-detector-group")
    kafka_client_id: str = os.getenv("KAFKA_CLIENT_ID", "fraud-analytics-backend")
    kafka_topic_partitions: int = int(os.getenv("KAFKA_TOPIC_PARTITIONS", "3"))
    kafka_topic_replication_factor: int = int(os.getenv("KAFKA_TOPIC_REPLICATION_FACTOR", "1"))

    # Kafka Producer tuning
    kafka_producer_acks: str = os.getenv("KAFKA_PRODUCER_ACKS", "all")
    kafka_producer_retries: int = int(os.getenv("KAFKA_PRODUCER_RETRIES", "5"))
    kafka_producer_batch_size: int = int(os.getenv("KAFKA_PRODUCER_BATCH_SIZE", "16384"))
    kafka_producer_linger_ms: int = int(os.getenv("KAFKA_PRODUCER_LINGER_MS", "10"))
    kafka_producer_compression_type: str = os.getenv("KAFKA_PRODUCER_COMPRESSION_TYPE", "gzip")

    # Kafka Consumer tuning
    kafka_auto_offset_reset: str = os.getenv("KAFKA_AUTO_OFFSET_RESET", "earliest")
    kafka_enable_auto_commit: bool = os.getenv("KAFKA_ENABLE_AUTO_COMMIT", "True").lower() == "true"
    kafka_auto_commit_interval_ms: int = int(os.getenv("KAFKA_AUTO_COMMIT_INTERVAL_MS", "5000"))
    kafka_max_poll_records: int = int(os.getenv("KAFKA_MAX_POLL_RECORDS", "500"))

    @property
    def kafka_topics(self) -> List[str]:
        """List of Kafka topics that must exist for the platform."""
        return [self.kafka_topic_transactions, self.kafka_topic_alerts]

    # AWS Configuration
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    aws_access_key_id: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    aws_secret_access_key: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    aws_s3_bucket: str = os.getenv("AWS_S3_BUCKET", "fraud-analytics-bucket")

    # Security
    secret_key: str = os.getenv("SECRET_KEY", "your-super-secret-key-change-in-production")
    algorithm: str = os.getenv("ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

    # Logging
    log_format: str = os.getenv("LOG_FORMAT", "json")
    log_file_path: str = os.getenv("LOG_FILE_PATH", "logs/app.log")

    # Email/Alerts
    alert_email_enabled: bool = os.getenv("ALERT_EMAIL_ENABLED", "False").lower() == "true"
    alert_email_from: str = os.getenv("ALERT_EMAIL_FROM", "noreply@frauddetection.com")
    alert_smtp_server: str = os.getenv("ALERT_SMTP_SERVER", "smtp.gmail.com")
    alert_smtp_port: int = int(os.getenv("ALERT_SMTP_PORT", "587"))

    class Config:
        """Pydantic config class."""
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
