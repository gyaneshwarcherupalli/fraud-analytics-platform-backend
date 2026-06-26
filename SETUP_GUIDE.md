# Fraud Analytics Platform Backend - Setup Guide

## Overview
This is a FastAPI-based fraud detection and analytics platform with real-time fraud scoring, transaction monitoring, and alert management.

## Prerequisites
- Python 3.11+
- Docker and Docker Compose
- Git
- Virtual Environment (venv, virtualenv, or conda)

## Project Structure
```
fraud-analytics-platform-backend/
├── app/
│   ├── main.py                 # FastAPI application entry point
│   ├── api/                    # API route handlers
│   ├── core/                   # Core configurations (config, database, security)
│   ├── models/                 # SQLAlchemy ORM models
│   ├── repositories/           # Data access layer
│   ├── schemas/                # Pydantic request/response schemas
│   ├── services/               # Business logic
│   └── utils/                  # Utilities (logger, helpers, exceptions, constants)
├── airflow/                    # Apache Airflow DAGs
├── database/                   # Database schemas and seed data
├── docker/                     # Docker configuration
├── ml_models/                  # Machine learning models
├── monitoring/                 # Monitoring and alerting config
├── tests/                      # Test suite
├── requirements.txt            # Python dependencies
├── .env                        # Environment variables (local)
├── .env.example                # Example environment file
└── docker-compose.yml          # Docker Compose configuration
```

## Quick Start

### Option 1: Local Development

#### 1. Clone and Navigate to Project
```bash
cd fraud-analytics-platform-backend
```

#### 2. Create Virtual Environment
```bash
# Using venv
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

#### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

#### 4. Configure Environment
```bash
# Copy and customize the .env file
cp .env.example .env

# Edit .env with your configuration
# Important: Update DB credentials, API keys, etc.
```

#### 5. Initialize Database
```bash
python setup.py
```

#### 6. Run Development Server
```bash
python -m uvicorn app.main:app --reload
```

The API will be available at: http://localhost:8000

API Documentation:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Option 2: Docker Development

#### 1. Build and Start Services
```bash
docker-compose up -d
```

This will start:
- FastAPI application (port 8000)
- PostgreSQL database (port 5432)
- Kafka broker (port 9092)
- Redis cache (port 6379)
- Zookeeper (port 2181)

#### 2. Verify Services
```bash
# Check service status
docker-compose ps

# View application logs
docker-compose logs -f app

# Health check
curl http://localhost:8000/health
```

#### 3. Stop Services
```bash
docker-compose down

# Remove volumes (careful!)
docker-compose down -v
```

## Environment Configuration

### Key Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| ENVIRONMENT | Environment type | development, production |
| DEBUG | Debug mode | True, False |
| LOG_LEVEL | Logging level | INFO, DEBUG, WARNING, ERROR |
| DB_HOST | Database host | localhost, postgres |
| DB_PORT | Database port | 5432 |
| DB_NAME | Database name | fraud_analytics |
| DB_USER | Database user | fraud_admin |
| DB_PASSWORD | Database password | secure_password |
| KAFKA_BROKER | Kafka broker address | localhost:9092 |
| SECRET_KEY | JWT secret key | your-secret-key |
| AWS_REGION | AWS region | us-east-1 |

See `.env.example` for complete list of variables.

## Logging Configuration

The application uses structured JSON logging by default:

```python
# Logs are written to:
# - Console (STDOUT)
# - File: logs/app.log

# Configure in .env:
LOG_LEVEL=INFO        # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT=json       # json, standard
LOG_FILE_PATH=logs/app.log
```

## Database Setup

### PostgreSQL Schema
```bash
# Database is initialized automatically on startup
# Manual initialization:
psql -U fraud_admin -d fraud_analytics -f database/postgres/schema.sql

# Seed test data:
psql -U fraud_admin -d fraud_analytics -f database/postgres/seed_data.sql
```

### Snowflake Connection
Update `.env` with Snowflake credentials:
```
SNOWFLAKE_ACCOUNT=your_account
SNOWFLAKE_USER=your_user
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_DATABASE=fraud_analytics
SNOWFLAKE_SCHEMA=public
```

## API Endpoints

### Health Check
```bash
GET /health
GET /
```

### Transactions
```bash
POST   /api/transactions          # Create transaction
GET    /api/transactions          # List transactions
GET    /api/transactions/{id}     # Get transaction details
```

### Fraud Detection
```bash
POST   /api/fraud/score           # Score a transaction
GET    /api/fraud/alerts          # Get fraud alerts
```

### Investigations
```bash
POST   /api/investigations        # Create investigation
GET    /api/investigations        # List investigations
PUT    /api/investigations/{id}   # Update investigation
```

## Testing

### Run Tests
```bash
# All tests
pytest

# With coverage
pytest --cov=app

# Specific test file
pytest tests/unit/test_fraud_scoring.py

# Verbose output
pytest -v
```

### Test Structure
```
tests/
├── api/              # API endpoint tests
├── unit/             # Unit tests
└── integration/      # Integration tests
```

## Code Quality

### Format Code
```bash
black app/
```

### Lint Code
```bash
flake8 app/
ruff check app/
```

### Type Checking
```bash
mypy app/
```

## Monitoring and Logging

### View Logs
```bash
# Local file
tail -f logs/app.log

# Docker container
docker logs -f fraud-analytics-app

# Filter by level
grep "ERROR" logs/app.log
```

### CloudWatch Integration
Configure AWS CloudWatch metrics in `monitoring/cloudwatch_metrics.py`

### Alerts Configuration
See `monitoring/alerts_config.json` for alert rules and thresholds

## Development Tools

### Database Migrations
```bash
# Using Alembic (when integrated)
alembic init alembic
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

### Interactive Shell
```bash
# IPython shell with app context
python -c "from app.main import app; import IPython; IPython.embed()"
```

## Troubleshooting

### Virtual Environment Issues
```bash
# Recreate virtual environment
deactivate
rm -rf venv/
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Database Connection Issues
```bash
# Test PostgreSQL connection
psql -U fraud_admin -h localhost -d fraud_analytics

# Check if port 5432 is in use
netstat -an | grep 5432
```

### Docker Issues
```bash
# Rebuild images
docker-compose build --no-cache

# Remove everything and start fresh
docker-compose down -v
docker system prune -a
docker-compose up -d
```

### Port Already in Use
```bash
# Change port in .env or docker-compose.yml
# Or kill process on port
# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# macOS/Linux:
lsof -i :8000
kill -9 <PID>
```

## Production Deployment

### Pre-deployment Checklist
- [ ] Set ENVIRONMENT=production in .env
- [ ] Set DEBUG=False
- [ ] Update SECRET_KEY with secure value
- [ ] Configure database for production
- [ ] Set up SSL/TLS certificates
- [ ] Configure logging aggregation
- [ ] Set up monitoring and alerting
- [ ] Review security policies in .env

### Security Best Practices
1. Change default passwords
2. Use environment variables for secrets
3. Enable authentication/authorization
4. Set up rate limiting
5. Use HTTPS in production
6. Keep dependencies updated
7. Regular security audits

## Support and Documentation

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Kafka Python Documentation](https://kafka-python.readthedocs.io/)
- [AWS SDK Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)

## License
[Your License Here]

## Contributing
[Your Contributing Guidelines Here]
