import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { login, register } from "../api.js";

export default function Enter() {
  const nav = useNavigate();
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      if (mode === "login") await login(username, password);
      else await register(username, password);
      nav("/profile");
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <motion.div className="narrow cinematic" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
      <p className="eyebrow">Account</p>
      <h1>{mode === "login" ? "Login" : "Sign up"}</h1>
      <p className="lede">
        Username 3–20 characters. This is your Kiln account — connect Pollinations after, from Profile.
      </p>
      <div className="tabs">
        <button className={mode === "login" ? "on" : ""} onClick={() => setMode("login")}>
          Login
        </button>
        <button className={mode === "register" ? "on" : ""} onClick={() => setMode("register")}>
          Sign up
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
        {err && <p className="error">{err}</p>}
        <button className="btn copper" disabled={busy}>
          {busy ? "Please wait…" : mode === "login" ? "Log in" : "Create account"}
        </button>
      </form>
    </motion.div>
  );
}
