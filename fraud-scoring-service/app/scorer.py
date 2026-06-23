"""
FraudScorer - Isolation Forest anomaly detection for financial transactions.

Isolation Forest works by isolating anomalies rather than profiling normal data.
Anomalous transactions are isolated in fewer splits, giving them higher fraud scores.
No labeled fraud data is required — ideal for unsupervised anomaly detection.
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


class FraudScorer:
    """
    Trains an Isolation Forest on synthetic transaction data
    and scores incoming transactions for anomaly probability.
    """

    def __init__(self, contamination: float = 0.05):
        self.contamination = contamination
        self.model = IsolationForest(
            n_estimators=200,
            contamination=contamination,
            random_state=42,
            max_samples="auto",
        )
        self.scaler = StandardScaler()
        self._train_on_synthetic_data()

    def _generate_synthetic_data(self, n_samples: int = 5000) -> np.ndarray:
        """
        Generate realistic synthetic transaction features.
        Normal transactions cluster around low amounts with common categories.
        Anomalous transactions have extreme amounts and risky attributes.
        """
        rng = np.random.default_rng(42)

        # Normal transactions (95%)
        n_normal = int(n_samples * 0.95)
        normal = np.column_stack([
            rng.lognormal(mean=4.0, sigma=1.2, size=n_normal),  # amount ($5–$500 range)
            rng.uniform(0.0, 0.2, n_normal),   # category risk
            rng.uniform(0.0, 0.1, n_normal),   # country risk
            rng.uniform(0.0, 0.2, n_normal),   # type risk
        ])

        # Anomalous transactions (5%) — large amounts, high-risk attributes
        n_fraud = n_samples - n_normal
        fraud = np.column_stack([
            rng.lognormal(mean=7.5, sigma=1.5, size=n_fraud),   # large amounts ($1k–$50k)
            rng.uniform(0.5, 1.0, n_fraud),    # high category risk
            rng.uniform(0.4, 1.0, n_fraud),    # high country risk
            rng.uniform(0.3, 0.8, n_fraud),    # high type risk
        ])

        return np.vstack([normal, fraud])

    def _train_on_synthetic_data(self):
        X = self._generate_synthetic_data()
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled)

    def _extract_features(
        self,
        amount: float,
        merchant_category: str,
        merchant_country: str,
        transaction_type: str,
    ) -> np.ndarray:
        category_risk = 1.0 if merchant_category in HIGH_RISK_CATEGORIES else 0.0
        country_risk = 1.0 if merchant_country in HIGH_RISK_COUNTRIES else 0.0
        type_risk = TRANSACTION_TYPE_RISK.get(transaction_type, 0.1)

        return np.array([[amount, category_risk, country_risk, type_risk]])

    def score(
        self,
        amount: float,
        merchant_category: str,
        merchant_country: str,
        transaction_type: str = "PURCHASE",
    ) -> tuple[float, bool, str]:
        """
        Returns (fraud_score, flagged, reason).
        fraud_score is normalized to [0, 1] where 1 = highly anomalous.
        """
        features = self._extract_features(amount, merchant_category, merchant_country, transaction_type)
        features_scaled = self.scaler.transform(features)

        # decision_function returns negative scores for anomalies
        raw_score = self.model.decision_function(features_scaled)[0]

        # Normalize to [0, 1]: more negative raw_score → higher fraud score
        fraud_score = float(np.clip(1 - (raw_score + 0.5), 0.0, 1.0))

        flagged = fraud_score >= 0.65
        reason = self._build_reason(fraud_score, amount, merchant_category, merchant_country, transaction_type)

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
        if amount > 5000:
            reasons.append(f"high transaction amount (${amount:,.2f})")
        if category in HIGH_RISK_CATEGORIES:
            reasons.append(f"high-risk merchant category ({category})")
        if country in HIGH_RISK_COUNTRIES:
            reasons.append(f"high-risk origin country ({country})")
        if tx_type == "WITHDRAWAL" and amount > 1000:
            reasons.append("large cash withdrawal")

        if not reasons:
            reasons.append("anomalous pattern detected by Isolation Forest model")

        return "; ".join(reasons)

    def model_info(self) -> dict:
        return {
            "type": "IsolationForest",
            "n_estimators": self.model.n_estimators,
            "contamination": self.contamination,
            "features": ["amount", "categoryRisk", "countryRisk", "typeRisk"],
        }
