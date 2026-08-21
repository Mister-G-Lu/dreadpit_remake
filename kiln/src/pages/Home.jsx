import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getState } from "../api.js";
import Clock from "../components/Clock.jsx";
import Grid from "../components/Grid.jsx";

export default function Home() {
  const [state, setState] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    getState()
      .then(setState)
      .catch((e) => setErr(e.message));
  }, []);

  if (err) return <p className="error">{err}</p>;
  if (!state) return <p className="muted">Warming the flue…</p>;

  const next =
    state.round?.status === "running" || state.round?.status === "stalled"
      ? state.round.nextBatchAt
      : state.round?.completedAt
        ? new Date(new Date(state.round.completedAt).getTime() + 24 * 3600 * 1000).toISOString()
        : null;

  return (
    <div className="home">
      <section className="hero">
        <p className="eyebrow">The night firing · MMXXVI</p>
        <h1>
          Ten sparks.
          <br />
          <em>One vessel.</em>
        </h1>
        <p className="lede">
          Bring your own Pollen. Fire up to ten portraits a day. Two hundred fifty-six
          vessels fit in the mouth. The Eye reads the clay in hourly batches of ten.
        </p>
        <Clock
          target={next}
          label={
            state.round?.status === "running"
              ? `Hour ${state.round.batchIndex + 1} · next ten`
              : "Next night firing"
          }
        />
        <div className="cta-row">
          <Link className="btn copper" to="/forge">
            Charge the forge
          </Link>
          <Link className="btn ghost" to="/connect">
            Import Pollinations
          </Link>
        </div>
      </section>

      <section className="panel">
        <header className="panel-h">
          <h2>The stack</h2>
          <p>
            {state.living.length} / {state.maxRoster} living
            {state.gate.length ? ` · ${state.gate.length} in the mouth` : ""}
          </p>
        </header>
        <Grid fighters={state.living} max={state.maxRoster} />
        <p className="center-link">
          <Link to="/stack">Open the full stack →</Link>
        </p>
      </section>

      <section className="laws">
        <h2>Laws of the flue</h2>
        <ol>
          <li>
            <strong>I · Ten sparks</strong>
            Your Pollinations account (or the anonymous flue) will throw at most ten
            portraits per day. Pick one to become a vessel.
          </li>
          <li>
            <strong>II · Two hundred fifty-six</strong>
            The stack holds 256. Overflow waits in the mouth. No more than 256 new
            vessels are admitted in a UTC day.
          </li>
          <li>
            <strong>III · Hourly mouths of ten</strong>
            Once a night the Eye wakes. Matches 1–10 fire in the first hour, 11–20 in
            the second, and so on. If the Eye is rate-limited, the kiln stutters and
            retries.
          </li>
          <li>
            <strong>IV · The shelf does not argue</strong>
            The Eye judges portraits only. The loser is raked into ash. The prompt is
            sealed.
          </li>
        </ol>
      </section>
    </div>
  );
}
