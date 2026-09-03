import React, { useState, useEffect } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  PieChart, Pie, Cell
} from 'recharts';
import {
  Activity, CheckCircle, Clock, AlertTriangle,
  FileText, Zap, Users, TrendingUp
} from 'lucide-react';
import { getProgress, getSchedule, getRisk, getEvents } from '../api';

const COLORS = {
  completed: '#059669',
  in_progress: '#3B82F6',
  not_started: '#94A3B8',
  on_hold: '#D97706',
  cancelled: '#DC2626',
};

const RISK_COLORS = { HIGH: '#DC2626', MEDIUM: '#D97706', LOW: '#059669' };

function KPICard({ icon: Icon, label, value, sub, color }) {
  return (
    <div className="kpi-card">
      <div className="kpi-label">
        <Icon size={16} color={color || 'var(--text-muted)'} />
        {label}
      </div>
      <div className="kpi-value" style={{ color: color || 'var(--text)' }}>{value}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="recharts-custom-tooltip">
      <div className="label">{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color }}>
          {p.name}: {p.value}
        </div>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const [progress, setProgress] = useState(null);
  const [disciplineData, setDisciplineData] = useState([]);
  const [riskData, setRiskData] = useState([]);
  const [recentEvents, setRecentEvents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [prog, sched, risk, events] = await Promise.all([
          getProgress(),
          getSchedule(),
          getRisk(50),
          getEvents(),
        ]);
        setProgress(prog);

        const byDiscipline = {};
        (sched.activities || []).forEach((a) => {
          const d = a.discipline || 'Unknown';
          if (!byDiscipline[d]) byDiscipline[d] = { discipline: d, completed: 0, in_progress: 0, not_started: 0, on_hold: 0 };
          const status = (a.status || 'NOT_STARTED').toLowerCase().replace(/\s+/g, '_');
          if (byDiscipline[d][status] !== undefined) byDiscipline[d][status]++;
          else byDiscipline[d].not_started++;
        });
        setDisciplineData(Object.values(byDiscipline).sort((a, b) =>
          (b.completed + b.in_progress) - (a.completed + a.in_progress)
        ));

        setRiskData([
          { name: 'High', value: risk.high || 0, color: RISK_COLORS.HIGH },
          { name: 'Medium', value: risk.medium || 0, color: RISK_COLORS.MEDIUM },
          { name: 'Low', value: risk.low || 0, color: RISK_COLORS.LOW },
        ]);

        setRecentEvents((events.events || []).slice(0, 8));
      } catch (err) {
        console.error('Dashboard load error:', err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return <div className="loading-overlay"><div className="spinner" /> Loading dashboard...</div>;
  }

  const p = progress || {};

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Project Overview</h1>
        <p className="page-subtitle">
          Real-time planning-to-execution status for the Oil India EPC project.
        </p>
      </div>

      <div className="kpi-grid">
        <KPICard icon={Activity} label="Total Activities" value={p.total_activities || 0} sub={`${p.activities_with_actuals || 0} with field evidence`} />
        <KPICard icon={TrendingUp} label="Progress" value={`${p.overall_progress_percent || 0}%`} color="var(--success)" sub={`${p.completed_activities || 0} completed`} />
        <KPICard icon={FileText} label="Events Ingested" value={p.events_ingested || 0} sub={`${p.auto_linked || 0} auto-linked`} />
        <KPICard icon={Zap} label="Auto-Linked" value={p.auto_linked || 0} color="var(--success)" sub="High confidence matches" />
        <KPICard icon={Clock} label="In Review" value={p.in_review_queue || 0} color="var(--accent)" sub="Pending human decision" />
        <KPICard icon={AlertTriangle} label="Open Conflicts" value={p.open_conflicts || 0} color={p.open_conflicts > 0 ? 'var(--danger)' : 'var(--text-muted)'} sub="Multi-source disagreements" />
      </div>

      <div className="grid-2">
        <div className="chart-card">
          <div className="chart-title">Activities by Discipline</div>
          {disciplineData.length > 0 ? (
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={disciplineData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="discipline" tick={{ fontSize: 11 }} angle={-30} textAnchor="end" height={60} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="completed" name="Completed" fill={COLORS.completed} radius={[2, 2, 0, 0]} stackId="a" />
                <Bar dataKey="in_progress" name="In Progress" fill={COLORS.in_progress} radius={[2, 2, 0, 0]} stackId="a" />
                <Bar dataKey="not_started" name="Not Started" fill={COLORS.not_started} radius={[2, 2, 0, 0]} stackId="a" />
                <Bar dataKey="on_hold" name="On Hold" fill={COLORS.on_hold} radius={[2, 2, 0, 0]} stackId="a" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty-state"><p>No schedule data loaded</p></div>
          )}
        </div>

        <div className="chart-card">
          <div className="chart-title">Risk Distribution</div>
          {riskData.some((d) => d.value > 0) ? (
            <ResponsiveContainer width="100%" height={320}>
              <PieChart>
                <Pie
                  data={riskData}
                  cx="50%"
                  cy="50%"
                  innerRadius={70}
                  outerRadius={110}
                  paddingAngle={3}
                  dataKey="value"
                  label={({ name, value }) => `${name}: ${value}`}
                >
                  {riskData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty-state"><p>No risk data available</p></div>
          )}
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title">Recent Events</div>
          <span className="text-xs text-muted">{recentEvents.length} of {p.events_ingested || 0}</span>
        </div>
        {recentEvents.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Event ID</th>
                  <th>Description</th>
                  <th>Discipline</th>
                  <th>Status</th>
                  <th>Link State</th>
                  <th>Confidence</th>
                </tr>
              </thead>
              <tbody>
                {recentEvents.map((ev) => (
                  <tr key={ev.event_id}>
                    <td className="mono">{ev.event_id}</td>
                    <td className="truncate" style={{ maxWidth: 250 }}>{ev.description}</td>
                    <td>{ev.discipline || '—'}</td>
                    <td>{ev.status || '—'}</td>
                    <td><LinkStateBadge state={ev.link_state} /></td>
                    <td className="mono">{ev.match_confidence != null ? `${(ev.match_confidence * 100).toFixed(0)}%` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state"><p>No events ingested yet. Use the Supervisor or Ingest page to submit field data.</p></div>
        )}
      </div>
    </div>
  );
}

function LinkStateBadge({ state }) {
  const map = {
    auto_linked: { cls: 'badge-auto', text: 'Auto-linked' },
    approved: { cls: 'badge-approved', text: 'Approved' },
    pending_review: { cls: 'badge-pending', text: 'Pending' },
    clarification_needed: { cls: 'badge-pending', text: 'Clarification' },
    unmatched: { cls: 'badge-unmatched', text: 'Unmatched' },
    rejected: { cls: 'badge-rejected', text: 'Rejected' },
  };
  const info = map[state] || { cls: 'badge-muted', text: state || '—' };
  return <span className={`badge ${info.cls}`}>{info.text}</span>;
}
