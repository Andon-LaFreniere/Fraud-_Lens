package com.fraudlens.controller;

import com.fraudlens.model.FraudAlert;
import com.fraudlens.model.Transaction;
import com.fraudlens.service.TransactionService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
@Tag(name = "FraudLens", description = "Real-time transaction fraud detection API")
public class TransactionController {

    private final TransactionService transactionService;

    @PostMapping("/transactions")
    @Operation(summary = "Ingest a transaction for fraud scoring")
    public ResponseEntity<Transaction> ingest(@Valid @RequestBody Transaction transaction) {
        return ResponseEntity.status(HttpStatus.ACCEPTED)
                .body(transactionService.ingest(transaction));
    }

    @GetMapping("/transactions/account/{accountId}")
    @Operation(summary = "Get all transactions for an account")
    public ResponseEntity<List<Transaction>> getByAccount(@PathVariable String accountId) {
        return ResponseEntity.ok(transactionService.getByAccount(accountId));
    }

    /**
     * Internal callback endpoint — called by fraud-scoring-service after ML scoring.
     */
    @PostMapping("/transactions/{transactionId}/score")
    @Operation(summary = "Apply fraud score (called by scoring microservice)")
    public ResponseEntity<Void> applyScore(
            @PathVariable String transactionId,
            @RequestBody Map<String, Object> scorePayload) {

        transactionService.applyFraudScore(
                transactionId,
                (String) scorePayload.get("accountId"),
                (Double) scorePayload.get("fraudScore"),
                (Boolean) scorePayload.get("flagged"),
                (String) scorePayload.get("flagReason")
        );
        return ResponseEntity.ok().build();
    }

    @GetMapping("/alerts")
    @Operation(summary = "Retrieve all fraud alerts")
    public ResponseEntity<List<FraudAlert>> getAlerts() {
        return ResponseEntity.ok(transactionService.getAllAlerts());
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        return ResponseEntity.ok(Map.of("status", "UP", "service", "transaction-service"));
    }
}
