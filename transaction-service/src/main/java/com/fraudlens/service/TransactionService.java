package com.fraudlens.service;

import com.fraudlens.model.FraudAlert;
import com.fraudlens.model.Transaction;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;
import software.amazon.awssdk.enhanced.dynamodb.DynamoDbTable;
import software.amazon.awssdk.enhanced.dynamodb.Key;
import software.amazon.awssdk.enhanced.dynamodb.model.QueryConditional;

import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class TransactionService {

    private static final String TRANSACTION_TOPIC = "fraudlens.transactions";

    private final KafkaTemplate<String, Transaction> kafkaTemplate;
    private final DynamoDbTable<Transaction> transactionTable;
    private final DynamoDbTable<FraudAlert> fraudAlertTable;

    /**
     * Ingests a transaction: persists to DynamoDB and publishes to Kafka
     * for async fraud scoring by the Python microservice.
     */
    public Transaction ingest(Transaction transaction) {
        // Persist raw transaction
        transactionTable.putItem(transaction);
        log.info("Persisted transaction {} for account {}", transaction.getTransactionId(), transaction.getAccountId());

        // Publish to Kafka — fraud-scoring-service consumes this topic
        kafkaTemplate.send(TRANSACTION_TOPIC, transaction.getTransactionId(), transaction);
        log.info("Published transaction {} to topic {}", transaction.getTransactionId(), TRANSACTION_TOPIC);

        return transaction;
    }

    /**
     * Retrieves all transactions for a given account from DynamoDB.
     */
    public List<Transaction> getByAccount(String accountId) {
        QueryConditional query = QueryConditional
                .keyEqualTo(Key.builder().partitionValue(accountId).build());

        return transactionTable.index("accountId-index")
                .query(query)
                .stream()
                .flatMap(page -> page.items().stream())
                .collect(Collectors.toList());
    }

    /**
     * Called by the fraud-scoring-service (via REST) to update a transaction
     * with its fraud score and persist an alert if flagged.
     */
    public void applyFraudScore(String transactionId, String accountId,
                                 Double score, Boolean flagged, String reason) {
        // Fetch and update the transaction record
        Key key = Key.builder()
                .partitionValue(transactionId)
                .sortValue(accountId)
                .build();

        Transaction tx = transactionTable.getItem(key);
        if (tx == null) {
            log.warn("Transaction {} not found for scoring update", transactionId);
            return;
        }

        tx.setFraudScore(score);
        tx.setFlagged(flagged);
        tx.setFlagReason(reason);
        transactionTable.putItem(tx);

        // If flagged, write a FraudAlert to the alerts table
        if (Boolean.TRUE.equals(flagged)) {
            FraudAlert alert = FraudAlert.builder()
                    .alertId(UUID.randomUUID().toString())
                    .transactionId(transactionId)
                    .accountId(accountId)
                    .fraudScore(score)
                    .flagReason(reason)
                    .severity(resolveSeverity(score))
                    .merchantCategory(tx.getMerchantCategory())
                    .merchantCountry(tx.getMerchantCountry())
                    .amount(tx.getAmount().doubleValue())
                    .build();

            fraudAlertTable.putItem(alert);
            log.warn("FRAUD ALERT created for transaction {} — score={} severity={}",
                    transactionId, score, alert.getSeverity());
        }
    }

    public List<FraudAlert> getAllAlerts() {
        return fraudAlertTable.scan().items().stream().collect(Collectors.toList());
    }

    private String resolveSeverity(Double score) {
        if (score >= 0.9) return "CRITICAL";
        if (score >= 0.75) return "HIGH";
        if (score >= 0.5) return "MEDIUM";
        return "LOW";
    }
}
