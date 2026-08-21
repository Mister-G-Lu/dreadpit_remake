import { useEffect, useState } from "react";
import { Link, useNavigate, useOutletContext } from "react-router-dom";
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
  const [queued, setQueued] = useState(false);

  useEffect(() => {
    getState().then(setState).catch((e) => setErr(e.message));
  }, []);

  if (!me) {
    return (
      <div className="narrow">
        <h1>The forge is named</h1>
        <p className="lede">Take a kiln name before you throw clay.</p>
        <Link className="btn copper" to="/enter">
          Enter
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
      setErr("Describe the vessel in at least 8 characters (max 200).");
      return;
    }
    setBusy(true);
    try {
      const spark = await fireSpark(prompt.trim());
      const next = { ...spark, prompt: prompt.trim(), fresh: true };
      setSparks((s) => [next, ...s]);
      setPicked(next.id);
      setState((st) =>
        st
          ? { ...st, me: { ...st.me, sparksUsed: spark.sparksUsed } }
          : st
      );
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  }

  async function onSubmit(e) {
    e.preventDefault();
    if (!picked) return setErr("Pick a spark.");
    if (name.trim().length < 2) return setErr("Name the vessel.");
    setBusy(true);
    setErr("");
    try {
      const res = await submitVessel(name.trim(), picked);
      setQueued(res.queued);
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
          <h1>Throw ten sparks. Keep one.</h1>
        </div>
        <div className="sparks-meter">
          <span>{Math.max(0, max - (state?.me?.sparksUsed ?? 0))} left today</span>
          <div className="meter">
            {Array.from({ length: max }, (_, i) => (
              <i key={i} className={i < (state?.me?.sparksUsed ?? 0) ? "gone" : "live"} />
            ))}
          </div>
        </div>
      </header>

      {!pollenKey() && (
        <p className="banner">
          No Pollinations key — anonymous Flux will still fire, slowly, with a mark.
          <Link to="/connect"> Import your account</Link> for a clean plate.
        </p>
      )}

      <form className="form" onSubmit={onFire}>
        <label>
          Two hundred characters of clay
          <textarea
            maxLength={200}
            rows={3}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Cathedral-shaped stone elemental, stained glass in the body, bell-tower head…"
          />
          <small>{prompt.length}/200</small>
        </label>
        <button className="btn copper" disabled={busy || left <= 0}>
          {busy ? "In the fire…" : "Fire a spark"}
        </button>
      </form>

      {sparks.length > 0 && (
        <>
          <h2>Today’s plate</h2>
          <div className="contact">
            {sparks.map((s) => (
              <button
                key={s.id}
                type="button"
                className={picked === s.id ? "shot on" : "shot"}
                onClick={() => setPicked(s.id)}
              >
                <img src={s.image} alt="" />
                <span>seed {s.seed}</span>
              </button>
            ))}
          </div>
          <form className="form row" onSubmit={onSubmit}>
            <label>
              Vessel name
              <input value={name} onChange={(e) => setName(e.target.value)} maxLength={40} />
            </label>
            <button className="btn copper" disabled={busy || !picked}>
              Enter the kiln
            </button>
          </form>
        </>
      )}
      {queued && <p className="ok">The stack is full. Your vessel waits in the mouth.</p>}
      {err && <p className="error">{err}</p>}
    </div>
  );
}
