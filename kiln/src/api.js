import { localApi } from "./local.js";

export function pollenKey() {
  return localStorage.getItem("kiln_pollen_key") || "";
}

export function setPollenKey(key) {
  if (key) localStorage.setItem("kiln_pollen_key", key);
  else localStorage.removeItem("kiln_pollen_key");
}

function statusMessage(status) {
  if (status === 401) return "Please log in first.";
  if (status === 403) return "You don't have permission to do that.";
  if (status === 404) return "Not found.";
  if (status === 429) return "Too many requests. Please wait a moment and try again.";
  if (status >= 500) return "Something went wrong on the server. Please try again.";
  return `Request failed (${status}).`;
}

function networkMessage(err) {
  const name = err?.name || "";
  if (name === "AbortError") return "The request timed out. Please try again.";
  return "Can't reach the server. Check your connection and try again.";
}

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

  let res;
  try {
    res = await fetch(path, { credentials: "include", ...opts, headers });
  } catch (err) {
    throw Object.assign(new Error(networkMessage(err)), { status: 0 });
  }

  const text = await res.text();
  let data = {};
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = {};
    }
  }
  if (!res.ok) {
    const err = new Error(data.error || statusMessage(res.status));
    err.status = res.status;
    throw err;
  }
  return data;
}

let modePromise = null;

function detectMode() {
  if (import.meta.env.VITE_PAGES === "1") return Promise.resolve("local");
  if (!modePromise) {
    modePromise = Promise.race([
      fetch("/api/health", { credentials: "include" })
        .then(async (res) => {
          const data = await res.json().catch(() => ({}));
          return res.ok && data.ok === true ? "live" : "local";
        })
        .catch(() => "local"),
      new Promise((resolve) => setTimeout(() => resolve("local"), 2500)),
    ]);
  }
  return modePromise;
}

export async function api(path, opts = {}) {
  const mode = await detectMode();
  if (mode === "live") return liveApi(path, opts);
  return localApi(path, opts);
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
