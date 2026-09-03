import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../App';
import { login } from '../api';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { loginUser } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const data = await login(username, password);
      loginUser(
        { username, role: data.role, display_name: data.display_name },
        data.access_token
      );
      navigate('/');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const quickLogin = (user, pass) => {
    setUsername(user);
    setPassword(pass);
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-brand">
          <div className="sidebar-brand-mark" style={{ width: 42, height: 42, fontSize: 22 }}>S</div>
          <div>
            <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)' }}>SYNAPSE</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Planning-to-Execution Bridge</div>
          </div>
        </div>

        <h2 className="login-title">Sign in</h2>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="username">Username</label>
            <input
              id="username"
              className="form-input"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter username"
              autoFocus
              required
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="password">Password</label>
            <input
              id="password"
              className="form-input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter password"
              required
            />
          </div>

          {error && <p className="login-error">{error}</p>}

          <button
            className="btn btn-primary w-full"
            type="submit"
            disabled={loading}
            style={{ marginTop: 16, padding: '12px 16px', fontSize: 14 }}
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>

        <div style={{ marginTop: 24, borderTop: '1px solid var(--border)', paddingTop: 16 }}>
          <div className="text-xs text-muted mb-2" style={{ textAlign: 'center' }}>Quick login</div>
          <div className="flex gap-2">
            <button
              className="btn btn-ghost"
              onClick={() => quickLogin('supervisor', 'site123')}
              style={{ flex: 1 }}
            >
              Supervisor
            </button>
            <button
              className="btn btn-ghost"
              onClick={() => quickLogin('admin', 'synapse2026')}
              style={{ flex: 1 }}
            >
              Admin
            </button>
          </div>
        </div>

        <p className="login-hint">
          Demo credentials: supervisor / site123 &middot; admin / synapse2026
        </p>
      </div>
    </div>
  );
}
