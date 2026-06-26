"""
FraudLens - Fraud Scoring Microservice
Consumes transactions from Kafka, scores with Isolation Forest,
posts results back to transaction-service, and persists alerts to DynamoDB.
"""

import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

import boto3
import httpx
import numpy as np
from fastapi import FastAPI, HTTPException
from kafka import KafkaConsumer
from pydantic import BaseModel

from app.scorer import FraudScorer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Config from env ---
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TRANSACTION_TOPIC = "fraudlens.transactions"
TRANSACTION_SERVICE_URL = os.getenv("TRANSACTION_SERVICE_URL", "http://localhost:8080")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
ALERTS_TABLE = "fraudlens-alerts"

scorer = FraudScorer()
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
alerts_table = dynamodb.Table(ALERTS_TABLE)


# --- Kafka consumer loop (runs in background thread) ---
def consume_transactions():
    consumer = KafkaConsumer(
        TRANSACTION_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        group_id="fraud-scoring-group",
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )
    logger.info("Kafka consumer started, listening on topic: %s", TRANSACTION_TOPIC)

    for message in consumer:
        tx = message.value
        try:
            process_transaction(tx)
        except Exception as e:
            logger.error("Error processing transaction %s: %s", tx.get("transactionId"), e)


def process_transaction(tx: dict):
    transaction_id = tx["transactionId"]
    account_id = tx["accountId"]
    amount = float(tx["amount"])
    merchant_category = tx.get("merchantCategory", "UNKNOWN")
    merchant_country = tx.get("merchantCountry", "US")

    # Score the transaction
    score, flagged, reason = scorer.score(
        amount=amount,
        merchant_category=merchant_category,
        merchant_country=merchant_country,
        transaction_type=tx.get("type", "PURCHASE"),
    )

    logger.info(
        "Scored transaction %s: score=%.3f flagged=%s reason=%s",
        transaction_id, score, flagged, reason
    )

    # Post score back to transaction-service
    payload = {
        "accountId": account_id,
        "fraudScore": score,
        "flagged": flagged,
        "flagReason": reason,
    }
    response = httpx.post(
        f"{TRANSACTION_SERVICE_URL}/api/v1/transactions/{transaction_id}/score",
        json=payload,
        timeout=5.0,
    )
    response.raise_for_status()

    # If flagged, also write alert directly to DynamoDB from Python side
    if flagged:
        severity = resolve_severity(score)
        alerts_table.put_item(Item={
            "alertId": str(uuid.uuid4()),
            "transactionId": transaction_id,
            "accountId": account_id,
            "fraudScore": str(round(score, 4)),
            "flagReason": reason,
            "severity": severity,
            "amount": str(amount),
            "merchantCategory": merchant_category,
            "merchantCountry": merchant_country,
            "detectedAt": datetime.utcnow().isoformat(),
        })
        logger.warning(
            "Alert written to DynamoDB for tx %s — severity=%s", transaction_id, severity
        )


def resolve_severity(score: float) -> str:
    if score >= 0.88: return "CRITICAL"
    if score >= 0.70: return "HIGH"
    if score >= 0.50: return "MEDIUM"
    return "LOW"


# --- Lifespan: start Kafka consumer on startup ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, consume_transactions)
    yield


app = FastAPI(
    title="FraudLens Scoring Service",
    description="ML-powered fraud scoring microservice using Isolation Forest",
    version="1.0.0",
    lifespan=lifespan,
)


# --- REST endpoints ---
class ScoreRequest(BaseModel):
    amount: float
    merchantCategory: str
    merchantCountry: str
    transactionType: str = "PURCHASE"


class ScoreResponse(BaseModel):
    fraudScore: float
    flagged: bool
    flagReason: str
    severity: str


@app.post("/score", response_model=ScoreResponse)
def score_transaction(req: ScoreRequest):
    """Score a single transaction synchronously (for testing/demo)."""
    score, flagged, reason = scorer.score(
        amount=req.amount,
        merchant_category=req.merchantCategory,
        merchant_country=req.merchantCountry,
        transaction_type=req.transactionType,
    )
    return ScoreResponse(
        fraudScore=round(score, 4),
        flagged=flagged,
        flagReason=reason,
        severity=resolve_severity(score),
    )


@app.get("/health")
def health():
    return {"status": "UP", "service": "fraud-scoring-service", "model": scorer.model_info()}