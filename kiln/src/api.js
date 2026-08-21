export function pollenKey() {
  return localStorage.getItem("kiln_pollen_key") || "";
}

export function setPollenKey(key) {
  if (key) localStorage.setItem("kiln_pollen_key", key);
  else localStorage.removeItem("kiln_pollen_key");
}

export async function api(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(opts.json);
  }
  if (opts.pollen) {
    const key = pollenKey();
    if (key) headers["X-Pollinations-Key"] = key;
  }
  const res = await fetch(path, { credentials: "include", ...opts, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || `request failed (${res.status})`);
    err.status = res.status;
    throw err;
  }
  return data;
}

export const getState = () => api("/api/state");
export const getMe = () => api("/api/auth/me");
export const getAsh = () => api("/api/ash");
export const getFighter = (id) => api(`/api/fighters/${id}`);
export const getMatch = (id) => api(`/api/matches/${id}`);
export const register = (username, password) =>
  api("/api/auth/register", { method: "POST", json: { username, password } });
export const login = (username, password) =>
  api("/api/auth/login", { method: "POST", json: { username, password } });
export const logout = () => api("/api/auth/logout", { method: "POST", json: {} });
export const fireSpark = (prompt, seed) =>
  api("/api/forge/spark", { method: "POST", pollen: true, json: { prompt, seed } });
export const submitVessel = (name, sparkId) =>
  api("/api/fighters", { method: "POST", json: { name, sparkId } });
