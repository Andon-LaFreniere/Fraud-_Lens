package com.fraudlens.config;

import com.fraudlens.model.FraudAlert;
import com.fraudlens.model.Transaction;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import software.amazon.awssdk.auth.credentials.DefaultCredentialsProvider;
import software.amazon.awssdk.enhanced.dynamodb.DynamoDbEnhancedClient;
import software.amazon.awssdk.enhanced.dynamodb.DynamoDbTable;
import software.amazon.awssdk.enhanced.dynamodb.TableSchema;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.dynamodb.DynamoDbClient;

@Configuration
public class DynamoDbConfig {

    @Value("${aws.region:us-east-1}")
    private String region;

    @Bean
    public DynamoDbClient dynamoDbClient() {
        return DynamoDbClient.builder()
                .region(Region.of(region))
                // Uses env vars AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY or IAM role
                .credentialsProvider(DefaultCredentialsProvider.create())
                .build();
    }

    @Bean
    public DynamoDbEnhancedClient dynamoDbEnhancedClient(DynamoDbClient dynamoDbClient) {
        return DynamoDbEnhancedClient.builder()
                .dynamoDbClient(dynamoDbClient)
                .build();
    }

    @Bean
    public DynamoDbTable<Transaction> transactionTable(DynamoDbEnhancedClient client) {
        return client.table("fraudlens-transactions", TableSchema.fromBean(Transaction.class));
    }

    @Bean
    public DynamoDbTable<FraudAlert> fraudAlertTable(DynamoDbEnhancedClient client) {
        return client.table("fraudlens-alerts", TableSchema.fromBean(FraudAlert.class));
    }
}
