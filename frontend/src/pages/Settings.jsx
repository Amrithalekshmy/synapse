import React, { useState, useEffect } from 'react';
import { Save, Eye, EyeOff, RotateCcw } from 'lucide-react';
import { getSettings, updateSettings, resetSession } from '../api';

export default function Settings() {
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [keyConfigured, setKeyConfigured] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState('');
  const [resetting, setResetting] = useState(false);

  useEffect(() => {
    getSettings()
      .then((res) => {
        setApiKey(res.openrouter_api_key || '');
        setModel(res.model || 'google/gemini-2.0-flash-exp:free');
        setKeyConfigured(res.key_configured || false);
      })
      .catch(console.error);
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

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Settings</h1>
        <p className="page-subtitle">Configure LLM extraction and system preferences.</p>
      </div>

      <div className="grid-2">
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
              {keyConfigured ? 'Key is configured.' : 'No key set — rule-based extraction only.'}
              {' '}Get a key at openrouter.ai
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
            Reset clears all ingested events, conflicts, and actuals.
            The loaded schedule is retained.
          </p>
          <button className="btn btn-danger" onClick={handleReset} disabled={resetting}>
            <RotateCcw size={16} /> {resetting ? 'Resetting...' : 'Reset session'}
          </button>
        </div>
      </div>
    </div>
  );
}
