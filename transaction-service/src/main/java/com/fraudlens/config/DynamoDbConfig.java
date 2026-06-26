package com.fraudlens.config;

import com.fraudlens.model.FraudAlert;
import com.fraudlens.model.Transaction;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import software.amazon.awssdk.auth.credentials.AwsBasicCredentials;
import software.amazon.awssdk.auth.credentials.StaticCredentialsProvider;
import software.amazon.awssdk.enhanced.dynamodb.DynamoDbEnhancedClient;
import software.amazon.awssdk.enhanced.dynamodb.DynamoDbTable;
import software.amazon.awssdk.enhanced.dynamodb.TableSchema;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.dynamodb.DynamoDbClient;

import java.net.URI;

@Configuration
public class DynamoDbConfig {

    @Value("${aws.region:us-east-1}")
    private String region;

    @Value("${aws.dynamodb.endpoint:}")
    private String dynamoEndpoint;

    @Bean
    public DynamoDbClient dynamoDbClient() {
        var builder = DynamoDbClient.builder()
                .region(Region.of(region))
                .credentialsProvider(StaticCredentialsProvider.create(
                        AwsBasicCredentials.create("local", "local")));

        if (dynamoEndpoint != null && !dynamoEndpoint.isBlank()) {
            builder.endpointOverride(URI.create(dynamoEndpoint));
        }

        return builder.build();
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