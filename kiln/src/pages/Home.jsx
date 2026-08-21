import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { getState } from "../api.js";
import Clock, { DAY_MS } from "../components/Clock.jsx";
import Grid from "../components/Grid.jsx";
import ForgeFire from "../components/ForgeFire.jsx";

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
        <p>Warming the kiln</p>
      </div>
    );

  const reading = state.round?.status === "running" || state.round?.status === "stalled";
  const next = state.nextFiringAt ||
    (state.round?.completedAt
      ? new Date(new Date(state.round.completedAt).getTime() + 24 * 3600 * 1000).toISOString()
      : null);
  const last = !reading
    ? [...(state.matches || [])].reverse().find((m) => m.status === "done")
    : null;

  return (
    <div className="home">
      <section className="hero">
        <ForgeFire />
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
          <em>One fighter.</em>
        </motion.h1>
        <motion.p
          className="lede"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.25 }}
        >
          Log in. Connect Pollinations. Generate ten portraits a day and keep one fighter.
          256 living at a time. Every 24 hours the Eye names the winners.
        </motion.p>
        {reading ? (
          <div className="reading-state" role="status">
            <span className="reading-mark" aria-hidden="true" />
            <div>
              <strong>The Eye is reading today&apos;s portraits</strong>
              <small>All winners will appear together when the firing closes.</small>
            </div>
          </div>
        ) : (
          <Clock target={next} label="Next night firing" repeatEveryMs={DAY_MS} />
        )}
        <div className="cta-row">
          <Link className="btn copper" to="/forge">
            Open the forge
          </Link>
          <Link className="btn ghost" to="/connect">
            Connect Pollinations
          </Link>
        </div>
        {state.static && <p className="hint gallery-note">Gallery preview — browse the stack and its archived verdicts.</p>}
      </section>

      <section className="panel pit-panel">
        <header className="panel-h">
          <h2>Living stack</h2>
          <p>
            {state.living.length} / {state.maxRoster} living
            {state.gate.length ? ` · ${state.gate.length} waiting` : ""}
          </p>
        </header>
        <Grid fighters={state.living} max={state.maxRoster} />
        <p className="center-link">
          <Link to="/stack">Open the stack →</Link>
        </p>
      </section>

      {last && (
        <motion.section
          className="last-duel"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
        >
          <p className="eyebrow">{state.static ? "Featured Gemini verdict" : "Latest verdict"}</p>
          <Link to={`/match/${last.id}`} className="duel-strip">
            <img src={last.left.image} alt={last.left.name} />
            <span>VS</span>
            <img src={last.right.image} alt={last.right.name} />
            <em>{last.narration?.slice(0, 140)}…</em>
          </Link>
        </motion.section>
      )}

      <section className="laws">
        <h2>House laws</h2>
        <ol>
          {[
            ["I · Ten sparks", "At most ten portraits a day from your Pollinations account. Pick one fighter. The rest go cold."],
            ["II · Two hundred fifty-six", "The stack holds 256 living fighters. If it is full, new ones wait in line."],
            ["III · Every 24 hours", "The Eye judges matchups once a day. Results appear together when the firing is complete."],
            ["IV · Sight only", "The Eye never reads the prompt. Winners stay. Losers go to Ash."],
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
