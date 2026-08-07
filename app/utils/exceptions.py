"""
Custom exceptions for the Fraud Analytics Platform.
"""


class FraudAnalyticsException(Exception):
    """Base exception for Fraud Analytics Platform."""

    status_code = 500

    def __init__(self, message: str, code: str = "FRAUD_ANALYTICS_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class DatabaseException(FraudAnalyticsException):
    """Exception raised for database operation errors."""

    status_code = 500

    def __init__(self, message: str, code: str = "DATABASE_ERROR"):
        super().__init__(message, code)


class ConfigurationException(FraudAnalyticsException):
    """Exception raised for configuration errors."""

    def __init__(self, message: str, code: str = "CONFIG_ERROR"):
        super().__init__(message, code)


class AuthenticationException(FraudAnalyticsException):
    """Exception raised for authentication errors."""

    status_code = 401

    def __init__(self, message: str, code: str = "AUTH_ERROR"):
        super().__init__(message, code)


class AuthorizationException(FraudAnalyticsException):
    """Exception raised for authorization errors."""

    status_code = 403

    def __init__(self, message: str, code: str = "AUTHZ_ERROR"):
        super().__init__(message, code)


class ValidationException(FraudAnalyticsException):
    """Exception raised for validation errors."""

    status_code = 422

    def __init__(self, message: str, code: str = "VALIDATION_ERROR"):
        super().__init__(message, code)


class KafkaException(FraudAnalyticsException):
    """Exception raised for Kafka operation errors."""

    status_code = 503

    def __init__(self, message: str, code: str = "KAFKA_ERROR"):
        super().__init__(message, code)


class ExternalServiceException(FraudAnalyticsException):
    """Exception raised for external service errors."""

    status_code = 503

    def __init__(self, message: str, code: str = "EXTERNAL_SERVICE_ERROR"):
        super().__init__(message, code)


class DataNotFoundError(FraudAnalyticsException):
    """Exception raised when requested data is not found."""

    status_code = 404

    def __init__(self, message: str, code: str = "NOT_FOUND"):
        super().__init__(message, code)


class DuplicateDataError(FraudAnalyticsException):
    """Exception raised when attempting to create duplicate data."""

    status_code = 409

    def __init__(self, message: str, code: str = "DUPLICATE_ERROR"):
        super().__init__(message, code)
