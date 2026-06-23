# FraudLens

Real-time financial transaction fraud detection platform. Transactions are ingested via a Spring Boot REST API, streamed through Apache Kafka, scored by a Python FastAPI microservice using Isolation Forest anomaly detection, and persisted to AWS DynamoDB. Deployed on AWS (Elastic Beanstalk + Lambda + API Gateway).

## Architecture

```
Client
  │
  ▼
Spring Boot REST API (transaction-service)
  │  POST /api/v1/transactions
  │
  ├──► DynamoDB (fraudlens-transactions) — raw transaction store
  │
  └──► Kafka Topic: fraudlens.transactions
              │
              ▼
        Python FastAPI (fraud-scoring-service)
          │  Isolation Forest ML model
          │  Feature engineering: amount, category risk, country risk, tx type
          │
          ├──► POST /api/v1/transactions/{id}/score  (callback to Spring Boot)
          │
          └──► DynamoDB (fraudlens-alerts) — persists flagged transactions
```

## Stack

| Layer | Technology |
|---|---|
| Ingestion API | Java 17, Spring Boot 3.2, Kafka Producer |
| Message Bus | Apache Kafka |
| ML Scoring | Python 3.11, FastAPI, scikit-learn (Isolation Forest) |
| NoSQL Store | AWS DynamoDB |
| Cloud | AWS Elastic Beanstalk (Spring Boot), Lambda + API Gateway (FastAPI) |
| IaC | Terraform |
| Containers | Docker, Docker Compose |

## Running Locally

```bash
# Start all services (Kafka, DynamoDB Local, both microservices)
docker-compose up --build

# Ingest a transaction
curl -X POST http://localhost:8080/api/v1/transactions \
  -H "Content-Type: application/json" \
  -d '{
    "accountId": "ACC-001",
    "amount": 12500.00,
    "merchantCategory": "ELECTRONICS",
    "merchantCountry": "NG",
    "type": "PURCHASE"
  }'

# Check fraud alerts
curl http://localhost:8080/api/v1/alerts

# Score a transaction directly (sync, for testing)
curl -X POST http://localhost:8001/score \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 12500.00,
    "merchantCategory": "ELECTRONICS",
    "merchantCountry": "NG",
    "transactionType": "PURCHASE"
  }'

# Swagger UI
open http://localhost:8080/swagger-ui.html
open http://localhost:8001/docs
```

## AWS Deployment

```bash
cd infrastructure
terraform init
terraform apply -var="kafka_bootstrap_servers=<MSK_ENDPOINT>"
```

## ML Model

The fraud scoring service uses **Isolation Forest** — an unsupervised anomaly detection algorithm that isolates anomalies by randomly partitioning features. Anomalous transactions are isolated in fewer splits, resulting in higher fraud scores.

**Features used:**
- Transaction amount (log-normalized)
- Merchant category risk (HIGH_RISK_CATEGORIES lookup)
- Merchant country risk (HIGH_RISK_COUNTRIES lookup)
- Transaction type risk (WITHDRAWAL > TRANSFER > PURCHASE)

**Fraud score:** Normalized to [0.0, 1.0]. Transactions scoring ≥ 0.65 are flagged.

**Severity tiers:**
- CRITICAL: ≥ 0.90
- HIGH: ≥ 0.75
- MEDIUM: ≥ 0.50
- LOW: < 0.50

## API Endpoints

### transaction-service (port 8080)
| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/transactions` | Ingest transaction for scoring |
| GET | `/api/v1/transactions/account/{accountId}` | Get account transaction history |
| POST | `/api/v1/transactions/{id}/score` | Apply fraud score (internal) |
| GET | `/api/v1/alerts` | Retrieve all fraud alerts |
| GET | `/api/v1/health` | Health check |

### fraud-scoring-service (port 8001)
| Method | Path | Description |
|---|---|---|
| POST | `/score` | Score a transaction synchronously |
| GET | `/health` | Health check + model info |
