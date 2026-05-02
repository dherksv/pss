/**
 * api.ts - API client | OWNER: Engineer C
 * All backend calls go through here. Never call fetch() directly in components.
 */
const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function get(path: string) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

async function post(path: string, body: any) {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export const api = {
  // Projects
  getProjects:      () => get("/api/projects/"),
  createProject:    (data: any) => post("/api/projects/", data),
  getProject:       (id: string) => get(`/api/projects/${id}`),

  // Signals
  getSignals:       (params?: any) => get(`/api/signals/?${new URLSearchParams(params)}`),
  getSignal:        (id: string) => get(`/api/signals/${id}`),

  // Analysis
  getDrugTrend:     (drug: string, days = 30) => get(`/api/analysis/trends/${drug}?days=${days}`),
  getTopEntities:   (projectId: string) => get(`/api/analysis/top-entities/${projectId}`),
  getGoogleTrends:  (keywords: string) => get(`/api/analysis/google-trends?keywords=${keywords}`),

  // Source discovery
  discoverSources:  (topic: string, keywords: string[]) =>
                      post("/api/sources/discover", { topic, keywords }),

  // Alerts
  getAlerts:        () => get("/api/alerts/"),
  getOutbreaks:     () => get("/api/alerts/outbreaks"),
  resolveAlert:     (id: number) => fetch(`${BASE}/api/alerts/${id}/resolve`, { method: "PATCH" }),
};
