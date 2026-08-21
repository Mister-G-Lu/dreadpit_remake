import { useState } from "react";
import { useNavigate, useOutletContext } from "react-router-dom";
import { motion } from "framer-motion";
import { login, register } from "../api.js";
import { validateCredentials } from "../authRules.js";

export default function Enter() {
  const nav = useNavigate();
  const { setMe } = useOutletContext();
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    const localErr = validateCredentials(mode, username, password);
    if (localErr) {
      setErr(localErr);
      return;
    }
    setErr("");
    setBusy(true);
    try {
      const data = mode === "login" ? await login(username, password) : await register(username, password);
      setMe?.(data.user);
      nav("/forge");
    } catch (ex) {
      setErr(ex.message || "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <motion.div className="narrow cinematic" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
      <p className="eyebrow">Account</p>
      <h1>{mode === "login" ? "Log in" : "Create an account"}</h1>
      <p className="lede">
        Username: 3–20 letters, numbers, or underscores. Password: at least 6 characters. This is separate from
        Pollinations — you can link that next.
      </p>
      <div className="tabs">
        <button type="button" className={mode === "login" ? "on" : ""} onClick={() => { setMode("login"); setErr(""); }}>
          Log in
        </button>
        <button
          type="button"
          className={mode === "register" ? "on" : ""}
          onClick={() => { setMode("register"); setErr(""); }}
        >
          Create account
        </button>
      </div>
      <form className="form" onSubmit={onSubmit}>
        <label>
          Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
          />
        </label>
        {err && (
          <p className="error" role="alert">
            {err}
          </p>
        )}
        <button className="btn copper" disabled={busy}>
          {busy ? (mode === "login" ? "Logging in…" : "Creating account…") : mode === "login" ? "Log in" : "Create account"}
        </button>
      </form>
    </motion.div>
  );
}
