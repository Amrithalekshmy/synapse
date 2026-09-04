import React, { useState, useEffect } from 'react';
import { Save, Eye, EyeOff, RotateCcw, Brain, Zap } from 'lucide-react';
import { getSettings, updateSettings, resetSession, getRLStatus, getAgentStatus } from '../api';

function WeightBar({ value, max = 3.0, label }) {
  const pct = Math.max(0, Math.min(100, (Math.abs(value) / max) * 100));
  const color = value < 0 ? '#DC2626' : '#1E40AF';
  return (
    <div style={{ marginBottom: 6 }}>
      <div className="flex justify-between text-xs mb-1" style={{ color: 'var(--text-muted)' }}>
        <span>{label}</span><span style={{ fontFamily: 'var(--font-mono)', color }}>{value > 0 ? '+' : ''}{value.toFixed(3)}</span>
      </div>
      <div style={{ height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 2 }} />
      </div>
    </div>
  );
}

export default function Settings() {
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [keyConfigured, setKeyConfigured] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState('');
  const [resetting, setResetting] = useState(false);
  const [rlStatus, setRlStatus] = useState(null);
  const [agentStatus, setAgentStatus] = useState(null);

  useEffect(() => {
    getSettings()
      .then((res) => {
        setApiKey(res.openrouter_api_key || '');
        setModel(res.model || 'google/gemini-2.0-flash-exp:free');
        setKeyConfigured(res.key_configured || false);
      })
      .catch(console.error);
    getRLStatus().then(setRlStatus).catch(() => null);
    getAgentStatus().then(setAgentStatus).catch(() => null);
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setStatus('');
    try {
      const body = {};
      if (apiKey && !apiKey.startsWith('*')) body.openrouter_api_key = apiKey;
      if (model) body.model = model;
      await updateSettings(body);
      setStatus('Settings saved successfully');
      setKeyConfigured(true);
    } catch (err) {
      setStatus(`Error: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (!confirm('Reset the session? This clears all ingested events and conflicts but keeps the schedule.')) return;
    setResetting(true);
    try {
      await resetSession();
      setStatus('Session reset — schedule retained');
    } catch (err) {
      setStatus(`Error: ${err.message}`);
    } finally {
      setResetting(false);
    }
  };

  const rlFeatures = rlStatus?.feature_names || [];
  const agentFeatures = agentStatus?.feature_names || [];
  const agentActions = agentStatus?.action_names || ['auto_link', 'ask_clarification', 'send_to_planner'];

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Settings</h1>
        <p className="page-subtitle">LLM configuration, session control, and live RL policy inspector.</p>
      </div>

      <div className="grid-2" style={{ marginBottom: 24 }}>
        <div className="card">
          <div className="card-title" style={{ marginBottom: 16 }}>LLM Configuration</div>
          <div className="form-group">
            <label className="form-label">OpenRouter API Key</label>
            <div className="flex gap-2">
              <input
                className="form-input"
                type={showKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk-or-v1-..."
                style={{ flex: 1 }}
              />
              <button className="btn btn-ghost" onClick={() => setShowKey(!showKey)} type="button">
                {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            <p className="text-xs text-muted mt-2">
              {keyConfigured ? '✓ Key configured — LLM extraction active.' : 'No key set — rule-based extraction only.'}
            </p>
          </div>
          <div className="form-group">
            <label className="form-label">Model</label>
            <input
              className="form-input"
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="google/gemini-2.0-flash-exp:free"
            />
          </div>
          <div className="flex gap-2 items-center">
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
              <Save size={16} /> {saving ? 'Saving...' : 'Save settings'}
            </button>
            {status && <span className="text-xs text-muted">{status}</span>}
          </div>
        </div>

        <div className="card">
          <div className="card-title" style={{ marginBottom: 16 }}>Session Control</div>
          <p className="text-sm text-secondary mb-4">
            Reset clears all ingested events, conflicts, and actuals. The schedule is retained.
          </p>
          <button className="btn btn-danger" onClick={handleReset} disabled={resetting}>
            <RotateCcw size={16} /> {resetting ? 'Resetting...' : 'Reset session'}
          </button>
        </div>
      </div>

      {/* RL Priority Queue status */}
      {rlStatus && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="flex items-center gap-2 mb-3">
            <Zap size={16} color="var(--primary)" />
            <div className="card-title">RL Priority Queue — Live Weights</div>
            <span className="badge badge-info" style={{ background: '#EFF6FF', color: '#1E40AF', border: '1px solid #BFDBFE', marginLeft: 'auto' }}>
              {rlStatus.update_count} updates
            </span>
          </div>
          <p className="text-xs text-muted mb-3">{rlStatus.interpretation}</p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 16 }}>
            {(rlStatus.weights || []).map((w, i) => (
              <WeightBar key={i} label={rlFeatures[i] || `f${i}`} value={w} max={2} />
            ))}
          </div>
        </div>
      )}

      {/* RL Decision Agent status */}
      {agentStatus && (
        <div className="card">
          <div className="flex items-center gap-2 mb-3">
            <Brain size={16} color="var(--primary)" />
            <div className="card-title">RL Decision Agent — Policy Inspector</div>
            <span className="badge badge-info" style={{ background: '#F0FDF4', color: '#166534', border: '1px solid #BBF7D0', marginLeft: 'auto' }}>
              {agentStatus.update_count} updates · ε={agentStatus.epsilon}
            </span>
          </div>
          <p className="text-xs text-muted mb-4">{agentStatus.interpretation}</p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
            {agentActions.map((action, ai) => (
              <div key={action} style={{ background: 'var(--bg)', borderRadius: 8, padding: 12, border: '1px solid var(--border)' }}>
                <div className="text-xs font-semibold mb-2" style={{ color: 'var(--primary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  {action.replace(/_/g, ' ')}
                </div>
                {(agentStatus.weights[ai] || []).map((w, fi) => (
                  <WeightBar key={fi} label={agentFeatures[fi] || `f${fi}`} value={w} max={3} />
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
