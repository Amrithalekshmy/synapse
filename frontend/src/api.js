const BASE = '';

function authHeaders() {
  const token = localStorage.getItem('synapse_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request(method, path, body = null) {
  const opts = {
    method,
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(`${BASE}${path}`, opts);
  if (res.status === 401) {
    localStorage.removeItem('synapse_token');
    localStorage.removeItem('synapse_user');
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

export async function login(username, password) {
  const form = new URLSearchParams();
  form.append('username', username);
  form.append('password', password);
  const res = await fetch(`${BASE}/api/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Login failed');
  }
  return res.json();
}

export const getHealth = () => request('GET', '/api/health');
export const getProgress = () => request('GET', '/api/progress');
export const getSchedule = (discipline, touched) => {
  const params = new URLSearchParams();
  if (discipline) params.set('discipline', discipline);
  if (touched) params.set('only_touched', 'true');
  return request('GET', `/api/schedule?${params}`);
};
export const getEvents = (linkState, discipline) => {
  const params = new URLSearchParams();
  if (linkState) params.set('link_state', linkState);
  if (discipline) params.set('discipline', discipline);
  return request('GET', `/api/events?${params}`);
};
export const getEvent = (id) => request('GET', `/api/events/${id}`);
export const getReviewQueue = () => request('GET', '/api/matches/queue');
export const getActivities = (q) => {
  const params = new URLSearchParams();
  if (q) params.set('q', q);
  return request('GET', `/api/activities?${params}`);
};
export const reviewMatch = (eventId, body) => request('POST', `/api/matches/${eventId}/review`, body);
export const getConflicts = (includeResolved) => request('GET', `/api/conflicts?include_resolved=${!!includeResolved}`);
export const resolveConflict = (id, body) => request('POST', `/api/conflicts/${id}/resolve`, body);
export const getRisk = (limit, discipline) => {
  const params = new URLSearchParams();
  if (limit) params.set('limit', String(limit));
  if (discipline) params.set('discipline', discipline);
  return request('GET', `/api/risk?${params}`);
};
export const getRiskEvidence = (activityId) => request('GET', `/api/risk/${activityId}/evidence`);
export const getProductivity = () => request('GET', '/api/productivity');
export const searchHistory = (q) => request('GET', `/api/history/search?q=${encodeURIComponent(q)}`);
export const getAudit = (stage) => {
  const params = new URLSearchParams();
  if (stage) params.set('stage', stage);
  return request('GET', `/api/audit?${params}`);
};
export const getDemoSources = () => request('GET', '/api/demo/sources');
export const seedDemo = () => request('POST', '/api/demo/seed');
export const supervisorMessage = (text, supervisor) => request('POST', '/api/supervisor/message', { text, supervisor });
export const supervisorClarify = (eventId, answer, supervisor) =>
  request('POST', '/api/supervisor/clarify', { event_id: eventId, answer, supervisor });
export const extractFromText = (text) => request('POST', '/api/events/extract', { text });
export const loadSample = (path) => request('POST', `/api/events/load-sample?path=${encodeURIComponent(path)}`);
export const uploadDocument = async (file) => {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${BASE}/api/events/upload`, {
    method: 'POST',
    headers: authHeaders(),
    body: form,
  });
  if (!res.ok) throw new Error('Upload failed');
  return res.json();
};
export const getSettings = () => request('GET', '/api/settings');
export const updateSettings = (body) => request('POST', '/api/settings', body);
export const resetSession = () => request('POST', '/api/session/reset');
export const getRLStatus = () => request('GET', '/api/rl/status');
export const getAgentStatus = () => request('GET', '/api/agent/status');
export const getCascade = (activityId, delayDays = 1) => request('GET', `/api/cascade/${activityId}?delay_days=${delayDays}`);
export const createActivity = (body) => request('POST', '/api/activities/create', body);
