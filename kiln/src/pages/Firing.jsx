import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { getState } from "../api.js";
import Clock, { DAY_MS } from "../components/Clock.jsx";

function winnerOf(match) {
  if (match.winnerId === match.left.id) return match.left;
  if (match.winnerId === match.right.id) return match.right;
  return null;
}

export default function Firing() {
  const [state, setState] = useState(null);

  useEffect(() => {
    let live = true;
    const load = () => getState().then((s) => live && setState(s)).catch(() => {});
    load();
    const t = setInterval(load, 8000);
    return () => {
      live = false;
      clearInterval(t);
    };
  }, []);

  if (!state)
    return (
      <div className="boot">
        <span className="ring" />
        <p>Loading the firing</p>
      </div>
    );
  if (!state.round)
    return (
      <div className="narrow cinematic">
        <p className="eyebrow">The firing</p>
        <h1>No verdicts yet</h1>
        <p className="lede">Once two fighters stand, the Eye returns winners after the next daily firing.</p>
      </div>
    );

  const reading = state.round.status === "running" || state.round.status === "stalled";
  if (reading)
    return (
      <div className="narrow cinematic results-pending">
        <p className="eyebrow">Today&apos;s firing</p>
        <h1>The Eye is judging.</h1>
        <p className="lede">
          Every portrait is being read. The complete results—and every winner—will appear here together.
        </p>
        <div className="reading-state" role="status">
          <span className="reading-mark" aria-hidden="true" />
          <div>
            <strong>Results are being collected</strong>
            <small>Return when the firing closes.</small>
          </div>
        </div>
      </div>
    );

  const matches = state.matches.filter((match) => match.status === "done");
  const next = state.clock?.nextFireAt ||
    state.nextFiringAt ||
    (state.round.completedAt
      ? new Date(new Date(state.round.completedAt).getTime() + 24 * 3600 * 1000).toISOString()
      : null);

  return (
    <div className="firing-results">
      <p className="eyebrow">{state.static ? "Gallery results" : "Latest firing"}</p>
      <h1>{matches.length} {matches.length === 1 ? "verdict" : "verdicts"} returned</h1>
      <p className="lede">The winners remain in the stack. The defeated enter the ash.</p>
      <Clock target={next} label="Next results" repeatEveryMs={DAY_MS} />

      <section className="results-feed">
        <h2>Winners</h2>
        <div className="result-list">
          {matches.map((match, i) => {
            const winner = winnerOf(match);
            return (
              <motion.div
                key={match.id}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: Math.min(i, 8) * 0.05 }}
              >
                <Link to={`/match/${match.id}`} className="result-row">
                  <div className={`result-fighter ${match.winnerId === match.left.id ? "winner" : "defeated"}`}>
                    <img src={match.left.image} alt={match.left.name} />
                    <span>{match.left.name}</span>
                  </div>
                  <div className="result-verdict">
                    {match.source === "archived-gemini" && <small>Real Gemini record</small>}
                    <span>VS</span>
                    <strong>{winner ? `${winner.name} wins` : "Verdict pending"}</strong>
                  </div>
                  <div className={`result-fighter ${match.winnerId === match.right.id ? "winner" : "defeated"}`}>
                    <img src={match.right.image} alt={match.right.name} />
                    <span>{match.right.name}</span>
                  </div>
                </Link>
              </motion.div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
