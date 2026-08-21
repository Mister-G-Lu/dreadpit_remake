import { demoAsh, demoFighters, demoMatches, demoState } from "./demo.js";

export function pollenKey() {
  return localStorage.getItem("kiln_pollen_key") || "";
}

export function setPollenKey(key) {
  if (key) localStorage.setItem("kiln_pollen_key", key);
  else localStorage.removeItem("kiln_pollen_key");
}

let live = import.meta.env.VITE_PAGES !== "1";

async function liveApi(path, opts = {}) {
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

function demoApi(path, opts = {}) {
  if (path === "/api/state") return Promise.resolve({ ...demoState });
  if (path === "/api/auth/me") return Promise.resolve({ user: null, sparksUsed: 0, sparksMax: 10 });
  if (path === "/api/ash") return Promise.resolve(demoAsh);
  if (path === "/api/me/fighters") return Promise.resolve({ fighters: [], slots: { used: 0, max: 15 } });
  const fighter = path.match(/^\/api\/fighters\/(.+)$/);
  if (fighter) {
    const hit = demoFighters[fighter[1]];
    if (!hit) return Promise.reject(Object.assign(new Error("No such fighter."), { status: 404 }));
    return Promise.resolve(hit);
  }
  const match = path.match(/^\/api\/matches\/(.+)$/);
  if (match) {
    const hit = demoMatches[match[1]];
    if (!hit) return Promise.reject(Object.assign(new Error("No such fight."), { status: 404 }));
    return Promise.resolve(hit);
  }
  if (opts.method === "POST") {
    return Promise.reject(
      Object.assign(new Error("This gallery is read-only. Log in on the live kiln to generate fighters."), {
        status: 501,
      })
    );
  }
  return Promise.reject(Object.assign(new Error("static kiln"), { status: 501 }));
}

export async function api(path, opts = {}) {
  if (live) {
    try {
      return await liveApi(path, opts);
    } catch (err) {
      if (err.status && err.status < 500) throw err;
      live = false;
    }
  }
  return demoApi(path, opts);
}

export const getState = () => api("/api/state");
export const getMe = () => api("/api/auth/me");
export const getAsh = () => api("/api/ash");
export const getFighter = (id) => api(`/api/fighters/${id}`);
export const getMatch = (id) => api(`/api/matches/${id}`);
export const getMyFighters = () => api("/api/me/fighters");
export const resurrectFighter = (id) =>
  api(`/api/fighters/${id}/resurrect`, { method: "POST", json: {} });
export const register = (username, password) =>
  api("/api/auth/register", { method: "POST", json: { username, password } });
export const login = (username, password) =>
  api("/api/auth/login", { method: "POST", json: { username, password } });
export const logout = () => api("/api/auth/logout", { method: "POST", json: {} });
export const fireSpark = (prompt, seed) =>
  api("/api/forge/spark", { method: "POST", pollen: true, json: { prompt, seed } });
export const submitVessel = (name, sparkId) =>
  api("/api/fighters", { method: "POST", json: { name, sparkId } });
