"""
Custom exceptions for the Fraud Analytics Platform.
"""


class FraudAnalyticsException(Exception):
    """Base exception for Fraud Analytics Platform."""

    def __init__(self, message: str, code: str = "FRAUD_ANALYTICS_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class DatabaseException(FraudAnalyticsException):
    """Exception raised for database operation errors."""

    def __init__(self, message: str, code: str = "DATABASE_ERROR"):
        super().__init__(message, code)


class ConfigurationException(FraudAnalyticsException):
    """Exception raised for configuration errors."""

    def __init__(self, message: str, code: str = "CONFIG_ERROR"):
        super().__init__(message, code)


class AuthenticationException(FraudAnalyticsException):
    """Exception raised for authentication errors."""

    def __init__(self, message: str, code: str = "AUTH_ERROR"):
        super().__init__(message, code)


class AuthorizationException(FraudAnalyticsException):
    """Exception raised for authorization errors."""

    def __init__(self, message: str, code: str = "AUTHZ_ERROR"):
        super().__init__(message, code)


class ValidationException(FraudAnalyticsException):
    """Exception raised for validation errors."""

    def __init__(self, message: str, code: str = "VALIDATION_ERROR"):
        super().__init__(message, code)


class KafkaException(FraudAnalyticsException):
    """Exception raised for Kafka operation errors."""

    def __init__(self, message: str, code: str = "KAFKA_ERROR"):
        super().__init__(message, code)


class ExternalServiceException(FraudAnalyticsException):
    """Exception raised for external service errors."""

    def __init__(self, message: str, code: str = "EXTERNAL_SERVICE_ERROR"):
        super().__init__(message, code)


class DataNotFoundError(FraudAnalyticsException):
    """Exception raised when requested data is not found."""

    def __init__(self, message: str, code: str = "NOT_FOUND"):
        super().__init__(message, code)


class DuplicateDataError(FraudAnalyticsException):
    """Exception raised when attempting to create duplicate data."""

    def __init__(self, message: str, code: str = "DUPLICATE_ERROR"):
        super().__init__(message, code)
