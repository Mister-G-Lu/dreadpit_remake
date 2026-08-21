import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
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
  if (!state)
    return (
      <div className="boot">
        <span className="ring" />
        <p>Warming the flue</p>
      </div>
    );

  const next =
    state.round?.status === "running" || state.round?.status === "stalled"
      ? state.round.nextBatchAt
      : state.round?.completedAt
        ? new Date(new Date(state.round.completedAt).getTime() + 24 * 3600 * 1000).toISOString()
        : null;

  const last = [...(state.matches || [])].reverse().find((m) => m.status === "done");

  return (
    <div className="home">
      <section className="hero">
        <div className="halo" aria-hidden="true" />
        <motion.p className="eyebrow" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }}>
          Night firing · MMXXVI
        </motion.p>
        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
        >
          Ten sparks.
          <br />
          <em>One vessel.</em>
        </motion.h1>
        <motion.p
          className="lede"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.25 }}
        >
          Import Pollinations. Fire ten portraits a day. Two hundred fifty-six fit the mouth.
          The Eye reads clay in hourly batches of ten — and stutters rather than skip.
        </motion.p>
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
            Import Pollen
          </Link>
        </div>
        {state.static && <p className="hint gallery-note">Gallery firing — this GitHub Pages cut is the pit under glass.</p>}
      </section>

      <section className="panel pit-panel">
        <header className="panel-h">
          <h2>The mouth</h2>
          <p>
            {state.living.length} / {state.maxRoster} living
            {state.gate.length ? ` · ${state.gate.length} waiting` : ""}
          </p>
        </header>
        <Grid fighters={state.living} max={state.maxRoster} />
        <p className="center-link">
          <Link to="/stack">Walk the stack →</Link>
        </p>
      </section>

      {last && (
        <motion.section
          className="last-duel"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
        >
          <p className="eyebrow">Last mouth</p>
          <Link to={`/match/${last.id}`} className="duel-strip">
            <img src={last.left.image} alt={last.left.name} />
            <span>VS</span>
            <img src={last.right.image} alt={last.right.name} />
            <em>{last.narration?.slice(0, 140)}…</em>
          </Link>
        </motion.section>
      )}

      <section className="laws">
        <h2>Laws of the flue</h2>
        <ol>
          {[
            ["I · Ten sparks", "Your Pollinations account throws at most ten portraits a day. Pick one. The rest go cold."],
            ["II · Two hundred fifty-six", "The stack holds 256. Overflow waits in the mouth. 256 new vessels per UTC day, no more."],
            ["III · Hourly mouths of ten", "Matches 1–10 fire at once. 11–20 wait an hour. A 429 stutters the Eye; it does not skip a vessel."],
            ["IV · Sight only", "The Eye never reads the prompt. Losers are ash. Words sealed."],
          ].map(([t, b], i) => (
            <motion.li
              key={t}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.08 }}
            >
              <strong>{t}</strong>
              {b}
            </motion.li>
          ))}
        </ol>
      </section>
    </div>
  );
}
