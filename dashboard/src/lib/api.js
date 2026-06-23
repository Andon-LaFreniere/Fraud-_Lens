const BASE = process.env.REACT_APP_API_URL || '';

export async function fetchAlerts() {
  const res = await fetch(`${BASE}/api/v1/alerts`);
  if (!res.ok) throw new Error('Failed to fetch alerts');
  return res.json();
}

export async function submitTransaction(tx) {
  const res = await fetch(`${BASE}/api/v1/transactions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(tx),
  });
  if (!res.ok) throw new Error('Failed to submit transaction');
  return res.json();
}

export async function fetchHealth() {
  const res = await fetch(`${BASE}/api/v1/health`);
  if (!res.ok) throw new Error('Health check failed');
  return res.json();
}
