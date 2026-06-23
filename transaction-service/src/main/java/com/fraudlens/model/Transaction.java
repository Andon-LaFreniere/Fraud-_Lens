package com.fraudlens.model;

import jakarta.validation.constraints.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import software.amazon.awssdk.enhanced.dynamodb.mapper.annotations.DynamoDbBean;
import software.amazon.awssdk.enhanced.dynamodb.mapper.annotations.DynamoDbPartitionKey;
import software.amazon.awssdk.enhanced.dynamodb.mapper.annotations.DynamoDbSortKey;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@DynamoDbBean
public class Transaction {

    @Builder.Default
    private String transactionId = UUID.randomUUID().toString();

    @NotBlank
    private String accountId;

    @NotNull
    @DecimalMin("0.01")
    private BigDecimal amount;

    @NotBlank
    private String merchantCategory;   // e.g. "ELECTRONICS", "GROCERY", "ATM"

    @NotBlank
    private String merchantCountry;    // ISO 3166 alpha-2

    @NotNull
    private TransactionType type;      // PURCHASE, WITHDRAWAL, TRANSFER

    @Builder.Default
    private Instant timestamp = Instant.now();

    // Populated after scoring by the ML microservice
    private Double fraudScore;         // 0.0 – 1.0
    private Boolean flagged;
    private String flagReason;

    @DynamoDbPartitionKey
    public String getTransactionId() { return transactionId; }

    @DynamoDbSortKey
    public String getAccountId() { return accountId; }

    public enum TransactionType {
        PURCHASE, WITHDRAWAL, TRANSFER
    }
}
