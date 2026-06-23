package com.fraudlens.model;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import software.amazon.awssdk.enhanced.dynamodb.mapper.annotations.DynamoDbBean;
import software.amazon.awssdk.enhanced.dynamodb.mapper.annotations.DynamoDbPartitionKey;
import software.amazon.awssdk.enhanced.dynamodb.mapper.annotations.DynamoDbSortKey;

import java.time.Instant;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@DynamoDbBean
public class FraudAlert {

    private String alertId;
    private String transactionId;
    private String accountId;
    private Double fraudScore;
    private String flagReason;
    private String severity;           // LOW, MEDIUM, HIGH, CRITICAL

    @Builder.Default
    private Instant detectedAt = Instant.now();

    private String merchantCategory;
    private String merchantCountry;
    private Double amount;

    @DynamoDbPartitionKey
    public String getAlertId() { return alertId; }

    @DynamoDbSortKey
    public String getTransactionId() { return transactionId; }
}
