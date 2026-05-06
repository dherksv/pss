const BASE = '';  // Vite proxy handles routing to http://api:8000

async function get(path: string) {
  const res = await fetch(BASE + path);
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
  return res.json();
}

async function post(path: string, body: any) {
  const res = await fetch(BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} → ${res.status}`);
  return res.json();
}

async function patch(path: string) {
  const res = await fetch(BASE + path, { method: 'PATCH' });
  if (!res.ok) throw new Error(`PATCH ${path} → ${res.status}`);
  return res.json();
}

export const api = {
  // Projects — routes/projects.py
  getProjects:     ()                              => get('/api/projects/'),
  createProject:   (data: any)                     => post('/api/projects/', data),
  getProject:      (id: string)                    => get(`/api/projects/${id}`),

  // Signals — routes/signals.py
  getSignals:      (params?: Record<string,string>) =>
                     get(`/api/signals/?${new URLSearchParams(params || {})}`),
  getSignalStats:  ()                              => get('/api/signals/stats'),
  getSignal:       (id: string)                    => get(`/api/signals/${id}`),

  // Analysis — routes/analysis.py
  getDrugTrend:    (drug: string, days = 30)       => get(`/api/analysis/trends/${drug}?days=${days}`),
  getTopEntities:  (projectId?: string)            =>
                     projectId
                       ? get(`/api/analysis/top-entities/${projectId}`)
                       : get('/api/analysis/top-entities'),
  getGoogleTrends: (keywords: string)              => get(`/api/analysis/google-trends?keywords=${encodeURIComponent(keywords)}`),

  // Sources — routes/sources.py
  discoverSources: (topic: string, keywords: string[]) =>
                     post('/api/sources/discover', { topic, keywords }),
  approveSources:  (project_id: string, source_names: string[]) =>
                     post('/api/sources/approve', { project_id, source_names }),

  // Alerts — routes/alerts.py
  getAlerts:       (resolved = false)              => get(`/api/alerts/?resolved=${resolved}`),
  resolveAlert:    (id: number)                    => patch(`/api/alerts/${id}/resolve`),
  getOutbreaks:    (severity?: string)             =>
                     get(`/api/alerts/outbreaks${severity ? `?severity=${severity}` : ''}`),
  getOutbreak:     (id: string)                    => get(`/api/alerts/outbreaks/${id}`),

  // Health
  health:          ()                              => get('/health'),
};