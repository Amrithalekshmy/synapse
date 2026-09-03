import React, { useState, useEffect } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell
} from 'recharts';
import { AlertTriangle, Shield, ChevronDown, ChevronUp } from 'lucide-react';
import { getRisk } from '../api';

const RISK_COLORS = { HIGH: '#DC2626', MEDIUM: '#D97706', LOW: '#059669', UNKNOWN: '#94A3B8' };

export default function Risk() {
  const [data, setData] = useState(null);
  const [discipline, setDiscipline] = useState('');
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const res = await getRisk(50, discipline || undefined);
      setData(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [discipline]);

  const activities = data?.activities || [];

  const delayRateChart = activities
    .filter((a) => a.delay_rate_percent > 0)
    .sort((a, b) => b.delay_rate_percent - a.delay_rate_percent)
    .slice(0, 15)
    .map((a) => ({
      name: a.activity_id,
      rate: a.delay_rate_percent,
      color: RISK_COLORS[a.historical_risk] || '#94A3B8',
      activity: a.activity_name,
    }));

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Risk Dashboard</h1>
        <p className="page-subtitle">
          Forward-looking delay risk derived from how similar activities behaved on completed projects.
        </p>
      </div>

      <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
        <div className="kpi-card">
          <div className="kpi-label"><AlertTriangle size={16} color={RISK_COLORS.HIGH} /> High Risk</div>
          <div className="kpi-value" style={{ color: RISK_COLORS.HIGH }}>{data?.high || 0}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label"><AlertTriangle size={16} color={RISK_COLORS.MEDIUM} /> Medium Risk</div>
          <div className="kpi-value" style={{ color: RISK_COLORS.MEDIUM }}>{data?.medium || 0}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label"><Shield size={16} color={RISK_COLORS.LOW} /> Low Risk</div>
          <div className="kpi-value" style={{ color: RISK_COLORS.LOW }}>{data?.low || 0}</div>
        </div>
      </div>

      {delayRateChart.length > 0 && (
        <div className="chart-card mb-6">
          <div className="chart-title">Historical Delay Rate (%)</div>
          <ResponsiveContainer width="100%" height={350}>
            <BarChart data={delayRateChart} layout="vertical" margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={80} />
              <Tooltip content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const d = payload[0].payload;
                return (
                  <div className="recharts-custom-tooltip">
                    <div className="label">{d.activity || d.name}</div>
                    <div>Delay rate: {d.rate}%</div>
                  </div>
                );
              }} />
              <Bar dataKey="rate" radius={[0, 4, 4, 0]}>
                {delayRateChart.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="flex gap-4 mb-4 items-center">
        <select className="form-input" style={{ maxWidth: 200 }} value={discipline} onChange={(e) => setDiscipline(e.target.value)}>
          <option value="">All disciplines</option>
          {[...new Set(activities.map((a) => a.discipline).filter(Boolean))].sort().map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
        <span className="text-xs text-muted">{activities.length} activities</span>
      </div>

      {loading ? (
        <div className="loading-overlay"><div className="spinner" /> Loading risk data...</div>
      ) : activities.length === 0 ? (
        <div className="card"><div className="empty-state"><p>No risk data available.</p></div></div>
      ) : (
        <div className="flex-col gap-2">
          {activities.map((a) => (
            <div key={a.activity_id} className="risk-card" onClick={() => setExpanded(expanded === a.activity_id ? null : a.activity_id)} style={{ cursor: 'pointer' }}>
              <div className="flex justify-between items-center">
                <div className="flex gap-3 items-center">
                  <span className={`badge badge-${a.historical_risk?.toLowerCase() || 'muted'}`}>
                    {a.historical_risk || '?'}
                  </span>
                  <div>
                    <span className="font-mono text-sm font-semibold">{a.activity_id}</span>
                    <span className="text-sm text-secondary" style={{ marginLeft: 8 }}>{a.activity_name}</span>
                  </div>
                </div>
                <div className="flex gap-4 items-center">
                  <span className="font-mono text-sm">{a.delay_rate_percent}% delay rate</span>
                  {expanded === a.activity_id ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </div>
              </div>

              {expanded === a.activity_id && (
                <div className="mt-4" style={{ paddingLeft: 40 }}>
                  <div className="grid-3 text-sm">
                    <div><span className="text-muted">Discipline:</span> {a.discipline}</div>
                    <div><span className="text-muted">Location:</span> {a.location || '—'}</div>
                    <div><span className="text-muted">Status:</span> {a.status}</div>
                    <div><span className="text-muted">Avg Variance:</span> {a.avg_variance_days?.toFixed(1) || '—'} days</div>
                    <div><span className="text-muted">Buffer:</span> {a.suggested_buffer_days || '—'} days</div>
                    <div><span className="text-muted">Historical Matches:</span> {a.historical_matches}</div>
                  </div>
                  {a.common_causes?.length > 0 && (
                    <div className="mt-2">
                      <span className="text-xs text-muted">Common causes: </span>
                      {a.common_causes.map((c, i) => (
                        <span key={i} className="badge badge-muted" style={{ marginRight: 4 }}>{c}</span>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
