import { useEffect, useState } from "react";
import { Link, useNavigate, useOutletContext } from "react-router-dom";
import { motion } from "framer-motion";
import { fireSpark, getState, pollenKey, submitVessel } from "../api.js";

export default function Forge() {
  const { me } = useOutletContext();
  const nav = useNavigate();
  const [state, setState] = useState(null);
  const [name, setName] = useState("");
  const [prompt, setPrompt] = useState("");
  const [sparks, setSparks] = useState([]);
  const [picked, setPicked] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    getState().then(setState).catch((e) => setErr(e.message));
  }, []);

  if (!me) {
    return (
      <div className="narrow cinematic">
        <p className="eyebrow">Account required</p>
        <h1>Login to forge</h1>
        <p className="lede">Log in, then generate up to ten portraits today. Keep one fighter for the stack.</p>
        <Link className="btn copper" to="/enter">
          Login
        </Link>
      </div>
    );
  }

  const used = state?.me?.sparksUsed ?? 0;
  const max = state?.sparksMax ?? 10;
  const left = Math.max(0, max - used);

  async function onFire(e) {
    e.preventDefault();
    setErr("");
    if (prompt.trim().length < 8) {
      setErr("Describe the fighter in at least 8 characters (max 200).");
      return;
    }
    setBusy(true);
    try {
      const spark = await fireSpark(prompt.trim());
      const next = { ...spark, prompt: prompt.trim() };
      setSparks((s) => [next, ...s]);
      setPicked(next.id);
      setState((st) => (st ? { ...st, me: { ...st.me, sparksUsed: spark.sparksUsed } } : st));
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  }

  async function onSubmit(e) {
    e.preventDefault();
    if (!picked) return setErr("Pick a portrait.");
    if (name.trim().length < 2) return setErr("Name the fighter.");
    setBusy(true);
    setErr("");
    try {
      const res = await submitVessel(name.trim(), picked);
      nav(res.queued ? "/stack" : `/vessel/${res.fighter.id}`);
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="forge">
      <header className="forge-h">
        <div>
          <p className="eyebrow">The forge</p>
          <h1>Throw ten. Keep one.</h1>
        </div>
        <div className="sparks-meter">
          <span>{left} left today</span>
          <div className="meter">
            {Array.from({ length: max }, (_, i) => (
              <i key={i} className={i < used ? "gone" : "live"} />
            ))}
          </div>
        </div>
      </header>

      {!pollenKey() && (
        <p className="banner">
          No Pollinations key — anonymous Flux still generates, slower, with a watermark.
          <Link to="/connect"> Connect Pollinations</Link>
        </p>
      )}

      <form className="form" onSubmit={onFire}>
        <label>
          Prompt (max 200 characters)
          <textarea
            maxLength={200}
            rows={3}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Cathedral-shaped stone elemental, stained glass in the body, bell-tower head…"
          />
          <small>{prompt.length}/200</small>
        </label>
        <button className={`btn copper ${busy ? "pulse" : ""}`} disabled={busy || left <= 0}>
          {busy ? "Generating…" : "Generate portrait"}
        </button>
      </form>

      {sparks.length > 0 && (
        <>
          <h2>Today’s portraits</h2>
          <div className="contact">
            {sparks.map((s) => (
              <motion.button
                key={s.id}
                type="button"
                layout
                className={picked === s.id ? "shot on" : "shot"}
                onClick={() => setPicked(s.id)}
                whileHover={{ y: -6 }}
              >
                <img src={s.image} alt="" />
                <span>seed {s.seed}</span>
              </motion.button>
            ))}
          </div>
          <form className="form row" onSubmit={onSubmit}>
            <label>
              Fighter name
              <input value={name} onChange={(e) => setName(e.target.value)} maxLength={40} />
            </label>
            <button className="btn copper" disabled={busy || !picked}>
              Submit to the stack
            </button>
          </form>
        </>
      )}
      {err && <p className="error">{err}</p>}
    </div>
  );
}
