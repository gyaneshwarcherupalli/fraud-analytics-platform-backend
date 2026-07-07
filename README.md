# Fraud Analytics Platform - Backend

Real-time fraud detection and analytics platform built with FastAPI, PostgreSQL, and machine learning models.

## 🚀 Quick Start

### Prerequisites
- Python 3.9+ (we tested with 3.9.12)
- Docker & Docker Compose (optional)
- Git

### Local Development Setup

#### 1. Clone and Navigate
```bash
cd fraud-analytics-platform-backend
```

#### 2. Create Virtual Environment
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# macOS/Linux
python -m venv venv
source venv/bin/activate
```

#### 3. Install Dependencies
```bash
# Core dependencies (required)
pip install -r requirements.txt

# Optional dependencies (database, message brokers, AWS)
pip install -r requirements-optional.txt
```

#### 4. Configure Environment
```bash
# Create .env file from example
copy .env.example .env  # Windows
# or
cp .env.example .env    # macOS/Linux

# Edit .env with your configuration
```

#### 5. Run the Application
```bash
python -m uvicorn app.main:app --reload --port 8000
```

Visit: http://localhost:8000

- **Swagger Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

### Docker Development

#### Build and Run Services
```bash
cd docker
docker-compose up -d
```

#### View Logs
```bash
docker-compose logs -f app
```

#### Stop Services
```bash
docker-compose down
```

## 📋 Project Structure

```
app/
├── main.py              # FastAPI application entry point
├── __init__.py          # Package initialization
├── api/                 # API endpoints
├── core/                # Core modules
│   ├── config.py        # Configuration management
│   ├── database.py      # Database setup
│   └── security.py      # Authentication & authorization
├── models/              # SQLAlchemy ORM models
├── repositories/        # Data access layer (DAO)
├── schemas/             # Pydantic request/response models
├── services/            # Business logic
└── utils/               # Utilities
    ├── logger.py        # Structured logging
    ├── constants.py     # Constants
    ├── exceptions.py    # Custom exceptions
    └── helpers.py       # Helper functions
```

## 🔧 Configuration

### Environment Variables

Key variables in `.env`:

| Variable | Description | Example |
|----------|-------------|---------|
| ENVIRONMENT | Deployment environment | development, production |
| DEBUG | Debug mode | True, False |
| LOG_LEVEL | Logging level | INFO, DEBUG |
| DB_HOST | PostgreSQL host | localhost |
| DB_USER | Database user | fraud_admin |
| DB_PASSWORD | Database password | (set in .env) |
| SECRET_KEY | JWT secret | (generate with secrets.token_urlsafe()) |

See `.env.example` for complete list.

### Logging

Logs are configured in `app/utils/logger.py`:

- **Output**: Console + File (`logs/app.log`)
- **Format**: JSON (structured logging)
- **Level**: Configurable via `LOG_LEVEL` in `.env`

## 🧪 Testing

```bash
# Run all tests
pytest

# With coverage report
pytest --cov=app

# Specific test file
pytest tests/unit/test_fraud_scoring.py

# Verbose output
pytest -v
```

## 📝 Code Quality

### Format Code
```bash
black app/
```

### Lint
```bash
flake8 app/
ruff check app/
```

### Type Checking
```bash
mypy app/
```

## 🐳 Docker Setup

### Services Included

- **FastAPI App** (port 8000)
- **PostgreSQL** (port 5432)
- **Kafka** (port 9092)
- **Redis** (port 6379)
- **Zookeeper** (port 2181)

### Docker Commands

```bash
# Start all services
docker-compose up -d

# Check service status
docker-compose ps

# View application logs
docker-compose logs -f app

# Run commands in container
docker-compose exec app bash

# Stop services
docker-compose down

# Clean up (remove volumes)
docker-compose down -v
```

### Kafka and Zookeeper

Kafka and Zookeeper are configured in `docker/docker-compose.yml` with:

- `zookeeper` service on port `2181`
- `kafka` service on ports `9092` (internal) and `29092` (host access)
- `kafka-init` one-shot service that creates topics on startup

Default topics created:

- `transactions`
- `alerts`

The backend also validates topic existence at application startup via `app/core/kafka.py`.

### Producer and Consumer Configuration

Kafka producer/consumer defaults are configurable in `.env`:

- Producer: `KAFKA_PRODUCER_ACKS`, `KAFKA_PRODUCER_RETRIES`, `KAFKA_PRODUCER_BATCH_SIZE`, `KAFKA_PRODUCER_LINGER_MS`, `KAFKA_PRODUCER_COMPRESSION_TYPE`
- Consumer: `KAFKA_AUTO_OFFSET_RESET`, `KAFKA_ENABLE_AUTO_COMMIT`, `KAFKA_AUTO_COMMIT_INTERVAL_MS`, `KAFKA_MAX_POLL_RECORDS`
- Topics: `KAFKA_TOPIC_TRANSACTIONS`, `KAFKA_TOPIC_ALERTS`, `KAFKA_TOPIC_PARTITIONS`, `KAFKA_TOPIC_REPLICATION_FACTOR`

### Kafka Smoke-Test Endpoints

Use these endpoints to verify end-to-end Kafka publishing and consuming from the API:

- `POST /api/transactions/kafka/smoke/publish`
- `POST /api/transactions/kafka/synthetic/publish`
- `GET /api/transactions/kafka/smoke/consume`

Examples:

```bash
curl -X POST http://localhost:8000/api/transactions/kafka/smoke/publish \
    -H "Content-Type: application/json" \
    -d '{"customer_id":"customer-101","amount":320.50,"merchant":"test-store"}'

curl -X POST "http://localhost:8000/api/transactions/kafka/synthetic/publish?count=50&delay_ms=20&seed=7"

curl "http://localhost:8000/api/transactions/kafka/smoke/consume?timeout_ms=2000&max_records=20"
```

## 🔐 Security

### Best Practices

1. **Never commit `.env` to version control**
2. **Use strong SECRET_KEY** in production
3. **Enable HTTPS** in production
4. **Change default database credentials**
5. **Keep dependencies updated**
6. **Enable authentication** for all endpoints
7. **Use rate limiting** for public endpoints
8. **Regular security audits**

### Generate Secure Keys

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 📦 Dependencies

### Core
- **FastAPI** - Modern web framework
- **Uvicorn** - ASGI server
- **Pydantic** - Data validation
- **SQLAlchemy** - ORM

### Development
- **pytest** - Testing
- **black** - Code formatting
- **flake8** - Linting
- **mypy** - Type checking
- **ruff** - Fast Python linter

### Optional
- **boto3** - AWS services
- **kafka-python** - Kafka client
- **psycopg2** - PostgreSQL driver

## 🆘 Troubleshooting

### Virtual Environment Issues
```bash
# Recreate venv
deactivate
rmdir /s venv  # Windows
rm -rf venv    # macOS/Linux
python -m venv venv
.\venv\Scripts\activate  # Windows
```

### Port Already in Use
```bash
# Change port in .env or command:
python -m uvicorn app.main:app --port 8001
```

### Database Connection Failed
```bash
# Test PostgreSQL connection
psql -U fraud_admin -h localhost -d fraud_analytics
```

### Docker Issues
```bash
# Rebuild images
docker-compose build --no-cache

# Fresh start
docker-compose down -v
docker-compose up -d
```

## 📚 API Documentation

Once running, view interactive documentation:

- **Swagger UI** - http://localhost:8000/docs
- **ReDoc** - http://localhost:8000/redoc

## 🤝 Contributing

1. Create a feature branch
2. Make changes
3. Run tests and linting
4. Submit pull request

## 📄 License

[Your License]

## 📞 Support

For issues, questions, or contributions, please contact the development team.

---

**Last Updated**: 2026-06-26  
**Version**: 1.0.0