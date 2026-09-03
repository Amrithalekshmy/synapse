import React, { useState, useEffect } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  LineChart, Line, PieChart, Pie, Cell, Area, AreaChart
} from 'recharts';
import { TrendingUp, AlertTriangle, CheckCircle, Clock } from 'lucide-react';
import { getProgress, getSchedule, getRisk, getAudit } from '../api';

const STATUS_COLORS = {
  COMPLETED: '#059669',
  IN_PROGRESS: '#3B82F6',
  NOT_STARTED: '#94A3B8',
  ON_HOLD: '#D97706',
  CANCELLED: '#DC2626',
};

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="recharts-custom-tooltip">
      <div className="label">{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toFixed(1) : p.value}
        </div>
      ))}
    </div>
  );
}

export default function Analytics() {
  const [progress, setProgress] = useState(null);
  const [varianceData, setVarianceData] = useState([]);
  const [statusByDiscipline, setStatusByDiscipline] = useState([]);
  const [timelineData, setTimelineData] = useState([]);
  const [statusPie, setStatusPie] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [prog, sched, audit] = await Promise.all([
          getProgress(),
          getSchedule(),
          getAudit(),
        ]);
        setProgress(prog);

        const activities = sched.activities || [];
        const withVariance = activities
          .filter((a) => a.variance_days != null && a.variance_days !== 0)
          .sort((a, b) => Math.abs(b.variance_days) - Math.abs(a.variance_days))
          .slice(0, 12)
          .map((a) => ({
            name: a.activity_id,
            variance: a.variance_days,
            fill: a.variance_days > 0 ? '#DC2626' : '#059669',
            activity: a.activity_name,
          }));
        setVarianceData(withVariance);

        const byDiscipline = {};
        activities.forEach((a) => {
          const d = a.discipline || 'Unknown';
          if (!byDiscipline[d]) byDiscipline[d] = { discipline: d, COMPLETED: 0, IN_PROGRESS: 0, NOT_STARTED: 0, ON_HOLD: 0 };
          const s = (a.status || 'NOT_STARTED').toUpperCase().replace(/\s+/g, '_');
          if (byDiscipline[d][s] !== undefined) byDiscipline[d][s]++;
          else byDiscipline[d].NOT_STARTED++;
        });
        setStatusByDiscipline(Object.values(byDiscipline));

        const statusCounts = { COMPLETED: 0, IN_PROGRESS: 0, NOT_STARTED: 0, ON_HOLD: 0 };
        activities.forEach((a) => {
          const s = (a.status || 'NOT_STARTED').toUpperCase().replace(/\s+/g, '_');
          if (statusCounts[s] !== undefined) statusCounts[s]++;
          else statusCounts.NOT_STARTED++;
        });
        setStatusPie(
          Object.entries(statusCounts)
            .filter(([, v]) => v > 0)
            .map(([name, value]) => ({
              name: name.replace(/_/g, ' '),
              value,
              color: STATUS_COLORS[name] || '#94A3B8',
            }))
        );

        const entries = audit.entries || [];
        const byTime = {};
        entries.forEach((e) => {
          const d = (e.timestamp || '').slice(0, 10);
          if (!d) return;
          if (!byTime[d]) byTime[d] = { date: d, events: 0 };
          if (e.stage === 'EXTRACT' || e.stage === 'INGEST') byTime[d].events++;
        });
        setTimelineData(Object.values(byTime).sort((a, b) => a.date.localeCompare(b.date)));
      } catch (err) {
        console.error('Analytics load error:', err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return <div className="loading-overlay"><div className="spinner" /> Loading analytics...</div>;
  }

  const p = progress || {};

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Analytics</h1>
        <p className="page-subtitle">Progress tracking, variance analysis, and status breakdowns.</p>
      </div>

      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-label"><TrendingUp size={16} color="var(--success)" /> Overall Progress</div>
          <div className="kpi-value" style={{ color: 'var(--success)' }}>{p.overall_progress_percent || 0}%</div>
          <div className="kpi-sub">{p.completed_activities || 0} of {p.total_activities || 0} completed</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label"><AlertTriangle size={16} color="var(--danger)" /> Avg Variance</div>
          <div className="kpi-value" style={{ color: p.average_variance_days > 0 ? 'var(--danger)' : 'var(--success)' }}>
            {p.average_variance_days > 0 ? '+' : ''}{p.average_variance_days || 0}d
          </div>
          <div className="kpi-sub">Worst: {p.worst_variance_days > 0 ? '+' : ''}{p.worst_variance_days || 0} days</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label"><CheckCircle size={16} color="var(--primary)" /> Corrections Learned</div>
          <div className="kpi-value">{p.corrections_learned || 0}</div>
          <div className="kpi-sub">Active learning feedback</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label"><Clock size={16} color="var(--accent)" /> Delayed</div>
          <div className="kpi-value" style={{ color: 'var(--accent)' }}>{p.delayed_activities || 0}</div>
          <div className="kpi-sub">{p.in_progress_activities || 0} in progress</div>
        </div>
      </div>

      <div className="grid-2">
        <div className="chart-card">
          <div className="chart-title">Schedule Variance (days late/early)</div>
          {varianceData.length > 0 ? (
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={varianceData} layout="vertical" margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={80} />
                <Tooltip content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0].payload;
                  return (
                    <div className="recharts-custom-tooltip">
                      <div className="label">{d.activity || d.name}</div>
                      <div style={{ color: d.fill }}>
                        Variance: {d.variance > 0 ? `+${d.variance}` : d.variance} days
                      </div>
                    </div>
                  );
                }} />
                <Bar dataKey="variance" radius={[0, 4, 4, 0]}>
                  {varianceData.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty-state"><p>No variance data yet</p></div>
          )}
        </div>

        <div className="chart-card">
          <div className="chart-title">Activity Status Distribution</div>
          {statusPie.length > 0 ? (
            <ResponsiveContainer width="100%" height={320}>
              <PieChart>
                <Pie
                  data={statusPie}
                  cx="50%"
                  cy="50%"
                  innerRadius={65}
                  outerRadius={105}
                  paddingAngle={3}
                  dataKey="value"
                  label={({ name, value }) => `${name}: ${value}`}
                >
                  {statusPie.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty-state"><p>No status data</p></div>
          )}
        </div>
      </div>

      <div className="grid-2">
        <div className="chart-card">
          <div className="chart-title">Status Breakdown by Discipline</div>
          {statusByDiscipline.length > 0 ? (
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={statusByDiscipline} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="discipline" tick={{ fontSize: 11 }} angle={-25} textAnchor="end" height={55} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="COMPLETED" name="Completed" fill={STATUS_COLORS.COMPLETED} stackId="a" />
                <Bar dataKey="IN_PROGRESS" name="In Progress" fill={STATUS_COLORS.IN_PROGRESS} stackId="a" />
                <Bar dataKey="NOT_STARTED" name="Not Started" fill={STATUS_COLORS.NOT_STARTED} stackId="a" />
                <Bar dataKey="ON_HOLD" name="On Hold" fill={STATUS_COLORS.ON_HOLD} stackId="a" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty-state"><p>No discipline data</p></div>
          )}
        </div>

        <div className="chart-card">
          <div className="chart-title">Event Ingestion Timeline</div>
          {timelineData.length > 0 ? (
            <ResponsiveContainer width="100%" height={320}>
              <AreaChart data={timelineData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip content={<CustomTooltip />} />
                <Area
                  type="monotone"
                  dataKey="events"
                  name="Events"
                  stroke="var(--primary)"
                  fill="var(--primary)"
                  fillOpacity={0.15}
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty-state"><p>No timeline data — ingest events to see the trend</p></div>
          )}
        </div>
      </div>
    </div>
  );
}
