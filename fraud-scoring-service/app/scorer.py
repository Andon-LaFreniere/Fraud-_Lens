"""
FraudScorer - Isolation Forest anomaly detection for financial transactions.

Isolation Forest works by isolating anomalies rather than profiling normal data.
Anomalous transactions are isolated in fewer splits, giving them higher fraud scores.
No labeled fraud data is required — ideal for unsupervised anomaly detection.

Scoring pipeline:
  1. Isolation Forest produces a raw anomaly score from feature space
  2. Raw score is normalized to [0, 1]
  3. A rule-based risk multiplier boosts scores when multiple risk signals stack
     (e.g. high amount + high-risk country + CRYPTO + WITHDRAWAL simultaneously)
  4. Final score determines severity tier: LOW / MEDIUM / HIGH / CRITICAL
"""

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


# High-risk merchant categories (empirically associated with fraud)
HIGH_RISK_CATEGORIES = {
    "ATM", "CRYPTO", "WIRE_TRANSFER", "GAMBLING", "ELECTRONICS"
}

# High-risk countries (simplified — in production, use a real risk registry)
HIGH_RISK_COUNTRIES = {
    "NG", "RO", "UA", "VN", "PK"
}

TRANSACTION_TYPE_RISK = {
    "WITHDRAWAL": 0.6,
    "TRANSFER": 0.4,
    "PURCHASE": 0.1,
}

# Thresholds for flagging and severity
FLAG_THRESHOLD   = 0.50
MEDIUM_THRESHOLD = 0.50
HIGH_THRESHOLD   = 0.70
CRITICAL_THRESHOLD = 0.88


class FraudScorer:
    """
    Trains an Isolation Forest on synthetic transaction data
    and scores incoming transactions for anomaly probability.
    """

    def __init__(self, contamination: float = 0.08):
        self.contamination = contamination
        self.model = IsolationForest(
            n_estimators=300,
            contamination=contamination,
            random_state=42,
            max_samples=256,
        )
        self.scaler = StandardScaler()
        self._train_on_synthetic_data()

    def _generate_synthetic_data(self, n_samples: int = 10000) -> np.ndarray:
        """
        Generate realistic synthetic transaction features.
        Normal transactions cluster tightly around everyday spending patterns.
        Anomalous transactions combine large amounts with multiple risk signals.
        """
        rng = np.random.default_rng(42)

        # Normal transactions (92%) — everyday low-risk spending
        n_normal = int(n_samples * 0.92)
        normal = np.column_stack([
            rng.lognormal(mean=3.5, sigma=0.9, size=n_normal),  # $10–$200
            rng.uniform(0.0, 0.15, n_normal),   # low category risk
            rng.uniform(0.0, 0.08, n_normal),   # low country risk
            rng.uniform(0.0, 0.15, n_normal),   # low type risk
            rng.uniform(0.0, 0.1,  n_normal),   # low composite risk
        ])

        # Moderate anomalies (5%) — one risk signal elevated
        n_moderate = int(n_samples * 0.05)
        moderate = np.column_stack([
            rng.lognormal(mean=6.0, sigma=1.0, size=n_moderate),  # $500–$5k
            rng.uniform(0.3, 0.6, n_moderate),
            rng.uniform(0.1, 0.4, n_moderate),
            rng.uniform(0.2, 0.5, n_moderate),
            rng.uniform(0.2, 0.5, n_moderate),
        ])

        # Severe anomalies (3%) — multiple risk signals stacked
        n_fraud = n_samples - n_normal - n_moderate
        fraud = np.column_stack([
            rng.lognormal(mean=9.0, sigma=1.2, size=n_fraud),   # $5k–$200k
            rng.uniform(0.8, 1.0, n_fraud),    # high-risk category
            rng.uniform(0.7, 1.0, n_fraud),    # high-risk country
            rng.uniform(0.6, 1.0, n_fraud),    # high-risk type
            rng.uniform(0.8, 1.0, n_fraud),    # high composite
        ])

        return np.vstack([normal, moderate, fraud])

    def _train_on_synthetic_data(self):
        X = self._generate_synthetic_data()
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled)

    def _composite_risk(
        self,
        amount: float,
        merchant_category: str,
        merchant_country: str,
        transaction_type: str,
    ) -> float:
        """
        Rule-based composite risk score [0, 1].
        Stacking multiple risk signals multiplies the score — one signal alone
        produces moderate risk; all four together pushes toward 1.0.
        """
        signals = []
        if amount > 10000:
            signals.append(0.9)
        elif amount > 3000:
            signals.append(0.5)
        elif amount > 1000:
            signals.append(0.25)

        if merchant_category in HIGH_RISK_CATEGORIES:
            signals.append(0.8)

        if merchant_country in HIGH_RISK_COUNTRIES:
            signals.append(0.75)

        if transaction_type == "WITHDRAWAL":
            signals.append(0.6)
        elif transaction_type == "TRANSFER":
            signals.append(0.35)

        if not signals:
            return 0.05

        # Diminishing returns combination: each signal adds less than the last
        combined = signals[0]
        for s in signals[1:]:
            combined = combined + s * (1 - combined)
        return float(np.clip(combined, 0.0, 1.0))

    def _extract_features(
        self,
        amount: float,
        merchant_category: str,
        merchant_country: str,
        transaction_type: str,
    ) -> np.ndarray:
        category_risk  = 1.0 if merchant_category in HIGH_RISK_CATEGORIES else 0.0
        country_risk   = 1.0 if merchant_country in HIGH_RISK_COUNTRIES else 0.0
        type_risk      = TRANSACTION_TYPE_RISK.get(transaction_type, 0.1)
        composite_risk = self._composite_risk(amount, merchant_category, merchant_country, transaction_type)

        return np.array([[amount, category_risk, country_risk, type_risk, composite_risk]])

    def score(
        self,
        amount: float,
        merchant_category: str,
        merchant_country: str,
        transaction_type: str = "PURCHASE",
    ) -> tuple[float, bool, str]:
        """
        Returns (fraud_score, flagged, reason).
        fraud_score normalized to [0, 1] where 1 = maximally anomalous.
        """
        features = self._extract_features(amount, merchant_category, merchant_country, transaction_type)
        features_scaled = self.scaler.transform(features)

        # decision_function: negative = anomalous, positive = normal
        raw_score = self.model.decision_function(features_scaled)[0]

        # Map raw score to [0, 1] with steeper curve for clearer separation
        # Typical range of decision_function is roughly [-0.5, 0.5]
        normalized = float(np.clip((0.5 - raw_score) / 0.6, 0.0, 1.0))

        # Blend with composite rule-based score to amplify stacked risk signals
        composite = self._composite_risk(amount, merchant_category, merchant_country, transaction_type)
        fraud_score = float(np.clip(0.55 * normalized + 0.45 * composite, 0.0, 1.0))

        flagged = fraud_score >= FLAG_THRESHOLD
        reason  = self._build_reason(fraud_score, amount, merchant_category, merchant_country, transaction_type)

        return fraud_score, flagged, reason

    def _build_reason(
        self,
        score: float,
        amount: float,
        category: str,
        country: str,
        tx_type: str,
    ) -> str:
        reasons = []
        if amount > 10000:
            reasons.append(f"very high transaction amount (${amount:,.2f})")
        elif amount > 3000:
            reasons.append(f"elevated transaction amount (${amount:,.2f})")
        if category in HIGH_RISK_CATEGORIES:
            reasons.append(f"high-risk merchant category ({category})")
        if country in HIGH_RISK_COUNTRIES:
            reasons.append(f"high-risk origin country ({country})")
        if tx_type == "WITHDRAWAL" and amount > 500:
            reasons.append("large cash withdrawal")
        elif tx_type == "TRANSFER" and amount > 2000:
            reasons.append("large transfer")
        if not reasons:
            reasons.append("anomalous pattern detected by Isolation Forest model")
        return "; ".join(reasons)

    def model_info(self) -> dict:
        return {
            "type": "IsolationForest",
            "n_estimators": self.model.n_estimators,
            "contamination": self.contamination,
            "features": ["amount", "categoryRisk", "countryRisk", "typeRisk", "compositeRisk"],
            "thresholds": {
                "flag": FLAG_THRESHOLD,
                "medium": MEDIUM_THRESHOLD,
                "high": HIGH_THRESHOLD,
                "critical": CRITICAL_THRESHOLD,
            }
        }