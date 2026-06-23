import { useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { RefreshCw, Shield } from 'lucide-react';
import { useAlerts } from './hooks/useAlerts';
import { submitTransaction } from './lib/api';
import './App.css';

/* ── Helpers ─────────────────────────────────────────────────────────────── */
const SEV_ORDER = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];
const SEV_COLOR = {
  CRITICAL: 'var(--critical)',
  HIGH:     'var(--high)',
  MEDIUM:   'var(--medium)',
  LOW:      'var(--low)',
};
const SCORE_CLASS = {
  CRITICAL: 'score-critical',
  HIGH:     'score-high',
  MEDIUM:   'score-medium',
  LOW:      'score-low',
};

function fmt(isoString) {
  if (!isoString) return '—';
  const d = new Date(isoString);
  return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function shortId(id = '') {
  return id.slice(0, 8).toUpperCase();
}

function getSeverity(alert) {
  return alert.severity || 'LOW';
}

/* ── Stat cards ──────────────────────────────────────────────────────────── */
function StatsRow({ alerts }) {
  const counts = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, total: alerts.length };
  alerts.forEach(a => {
    if (a.severity === 'CRITICAL') counts.CRITICAL++;
    else if (a.severity === 'HIGH') counts.HIGH++;
    else if (a.severity === 'MEDIUM') counts.MEDIUM++;
  });
  const avgScore = alerts.length
    ? (alerts.reduce((s, a) => s + (parseFloat(a.fraudScore) || 0), 0) / alerts.length).toFixed(3)
    : '—';

  return (
    <div className="stats-row">
      <div className="stat-card">
        <div className="stat-label">Total Alerts</div>
        <div className="stat-value" style={{ color: 'var(--text)' }}>{counts.total}</div>
        <div className="stat-sub">all time</div>
      </div>
      <div className="stat-card">
        <div className="stat-label">Critical</div>
        <div className="stat-value critical">{counts.CRITICAL}</div>
        <div className="stat-sub">score ≥ 0.90</div>
      </div>
      <div className="stat-card">
        <div className="stat-label">High</div>
        <div className="stat-value high">{counts.HIGH}</div>
        <div className="stat-sub">score ≥ 0.75</div>
      </div>
      <div className="stat-card">
        <div className="stat-label">Avg Score</div>
        <div className="stat-value medium">{avgScore}</div>
        <div className="stat-sub">across flagged txns</div>
      </div>
    </div>
  );
}

/* ── Severity distribution chart ─────────────────────────────────────────── */
function SeverityChart({ alerts }) {
  const data = SEV_ORDER.map(sev => ({
    name: sev,
    count: alerts.filter(a => a.severity === sev).length,
  }));
  return (
    <div className="chart-wrap">
      <div className="score-bar-label">Severity Distribution</div>
      <ResponsiveContainer width="100%" height={100}>
        <BarChart data={data} barSize={28}>
          <XAxis dataKey="name" tick={{ fill: 'var(--text-3)', fontSize: 10, fontFamily: 'IBM Plex Mono' }} axisLine={false} tickLine={false} />
          <YAxis hide />
          <Tooltip
            contentStyle={{ background: 'var(--surface-2)', border: '1px solid var(--border-2)', borderRadius: 6, fontFamily: 'IBM Plex Mono', fontSize: 11 }}
            itemStyle={{ color: 'var(--text)' }}
            cursor={{ fill: 'var(--border)' }}
          />
          <Bar dataKey="count" radius={[3, 3, 0, 0]}>
            {data.map(entry => (
              <Cell key={entry.name} fill={SEV_COLOR[entry.name]} fillOpacity={0.85} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ── Submit transaction form ─────────────────────────────────────────────── */
const CATEGORIES = ['GROCERY', 'ELECTRONICS', 'ATM', 'CRYPTO', 'GAMBLING', 'WIRE_TRANSFER', 'RESTAURANT', 'TRAVEL', 'RETAIL'];
const COUNTRIES  = ['US', 'GB', 'CA', 'DE', 'NG', 'RO', 'UA', 'VN', 'PK', 'AU', 'FR'];
const TX_TYPES   = ['PURCHASE', 'WITHDRAWAL', 'TRANSFER'];

const DEFAULT_FORM = {
  accountId: 'ACC-' + Math.floor(Math.random() * 9000 + 1000),
  amount: '',
  merchantCategory: 'ELECTRONICS',
  merchantCountry: 'US',
  type: 'PURCHASE',
};

function SubmitPanel({ onSubmitted }) {
  const [form, setForm] = useState(DEFAULT_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  async function handleSubmit() {
    if (!form.amount || isNaN(Number(form.amount))) {
      setToast({ type: 'error', msg: 'Enter a valid amount' });
      return;
    }
    setSubmitting(true);
    setToast(null);
    try {
      const tx = { ...form, amount: Number(form.amount) };
      await submitTransaction(tx);
      setToast({ type: 'success', msg: `Submitted — scoring in progress` });
      setForm(f => ({ ...f, amount: '' }));
      setTimeout(onSubmitted, 1500);
    } catch (e) {
      setToast({ type: 'error', msg: e.message });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Submit Transaction</span>
      </div>
      <div className="form-body">
        <div className="field">
          <label>Account ID</label>
          <input value={form.accountId} onChange={e => set('accountId', e.target.value)} placeholder="ACC-0001" />
        </div>
        <div className="field">
          <label>Amount (USD)</label>
          <input type="number" value={form.amount} onChange={e => set('amount', e.target.value)} placeholder="0.00" min="0.01" step="0.01" />
        </div>
        <div className="field">
          <label>Merchant Category</label>
          <select value={form.merchantCategory} onChange={e => set('merchantCategory', e.target.value)}>
            {CATEGORIES.map(c => <option key={c}>{c}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Merchant Country</label>
          <select value={form.merchantCountry} onChange={e => set('merchantCountry', e.target.value)}>
            {COUNTRIES.map(c => <option key={c}>{c}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Transaction Type</label>
          <select value={form.type} onChange={e => set('type', e.target.value)}>
            {TX_TYPES.map(t => <option key={t}>{t}</option>)}
          </select>
        </div>
        <button className="submit-btn" onClick={handleSubmit} disabled={submitting}>
          {submitting ? 'Submitting…' : 'Run Transaction →'}
        </button>
        {toast && (
          <div className={`toast toast-${toast.type}`}>{toast.msg}</div>
        )}
        <div style={{ marginTop: 8 }}>
          <div className="score-bar-label" style={{ marginBottom: 8 }}>Try a suspicious transaction</div>
          <button
            className="refresh-btn"
            style={{ width: '100%', padding: '7px 10px' }}
            onClick={() => setForm({ accountId: 'ACC-SUSP', amount: '14500', merchantCategory: 'CRYPTO', merchantCountry: 'NG', type: 'WITHDRAWAL' })}
          >
            Load high-risk example
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Alert table ─────────────────────────────────────────────────────────── */
function AlertTable({ alerts, loading, onRefresh }) {
  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Fraud Alerts</span>
        <button className="refresh-btn" onClick={onRefresh}>
          <RefreshCw size={10} style={{ marginRight: 4, verticalAlign: 'middle' }} />
          Refresh
        </button>
      </div>

      {loading && <div className="loading">Loading alerts…</div>}

      {!loading && alerts.length === 0 && (
        <div className="empty-state">
          No alerts yet — submit a transaction to begin.
        </div>
      )}

      {!loading && alerts.length > 0 && (
        <div className="alert-table">
          <div className="alert-row-header">
            <span>Time</span>
            <span>Account</span>
            <span>Severity</span>
            <span>Reason</span>
            <span style={{ textAlign: 'right' }}>Score</span>
          </div>
          {alerts.map(alert => {
            const sev = getSeverity(alert);
            const score = parseFloat(alert.fraudScore) || 0;
            return (
              <div className="alert-row" key={alert.alertId}>
                <span className="cell-mono">{fmt(alert.detectedAt)}</span>
                <span className="cell-id">{shortId(alert.accountId)}</span>
                <span><span className={`badge badge-${sev}`}>{sev}</span></span>
                <span className="cell-reason" title={alert.flagReason}>{alert.flagReason || '—'}</span>
                <span className={`cell-score ${SCORE_CLASS[sev]}`} style={{ textAlign: 'right' }}>
                  {score.toFixed(3)}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ── Root ────────────────────────────────────────────────────────────────── */
export default function App() {
  const { alerts, loading, lastUpdated, apiOnline, refresh } = useAlerts(4000);

  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <div className="wordmark">Fraud<span>Lens</span></div>
          <div className="status-pill">
            <span className={`status-dot ${apiOnline === true ? 'online' : apiOnline === false ? 'offline' : ''}`} />
            {apiOnline === true ? 'API online' : apiOnline === false ? 'API offline' : 'Connecting…'}
          </div>
        </div>
        <div className="header-right">
          <Shield size={13} style={{ color: 'var(--text-3)' }} />
          {lastUpdated ? `Last updated ${fmt(lastUpdated.toISOString())}` : 'Waiting…'}
        </div>
      </header>

      <main className="main">
        <StatsRow alerts={alerts} />

        <div className="content-grid">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <AlertTable alerts={alerts} loading={loading} onRefresh={refresh} />
            <div className="panel">
              <div className="panel-header">
                <span className="panel-title">Alert Distribution</span>
              </div>
              <SeverityChart alerts={alerts} />
            </div>
          </div>

          <SubmitPanel onSubmitted={refresh} />
        </div>
      </main>
    </div>
  );
}
