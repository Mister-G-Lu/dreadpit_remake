import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { getState } from "../api.js";
import Clock from "../components/Clock.jsx";

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
        <p>Listening at the flue</p>
      </div>
    );
  if (!state.round)
    return (
      <div className="narrow cinematic">
        <h1>No firing yet</h1>
        <p className="lede">When two vessels stand, the Eye opens. First ten matches fire at once; the rest wait an hour each.</p>
      </div>
    );

  const byBatch = new Map();
  for (const m of state.matches) {
    if (!byBatch.has(m.batch)) byBatch.set(m.batch, []);
    byBatch.get(m.batch).push(m);
  }

  return (
    <div>
      <p className="eyebrow">Night firing {String(state.round.number).padStart(3, "0")}</p>
      <h1>
        {state.round.matchesDone}/{state.round.matchesTotal} mouths fed
      </h1>
      <p className="lede">
        {state.round.status}. {state.batchSize} matches per hour
        {state.gemini ? " through Gemini Flash" : " with the lesser eye"}
        . Rate-limits stutter; they do not skip.
      </p>
      {(state.round.status === "running" || state.round.status === "stalled") && (
        <Clock target={state.round.nextBatchAt} label={`Hour ${state.round.batchIndex + 1} · next ten`} />
      )}

      {[...byBatch.entries()].map(([batch, matches]) => (
        <section key={batch} className="batch">
          <h2>
            Hour {batch}
            <small>
              matches {(batch - 1) * state.batchSize + 1}–
              {Math.min(batch * state.batchSize, state.round.matchesTotal)}
            </small>
          </h2>
          <div className="match-list">
            {matches.map((m, i) => (
              <motion.div
                key={m.id}
                initial={{ opacity: 0, x: i % 2 ? 24 : -24 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
              >
                <Link to={`/match/${m.id}`} className={`match-row ${m.status}`}>
                  <span className="seq">{m.seq}</span>
                  <img src={m.left.image} alt={m.left.name} className={m.winnerId === m.left.id ? "won" : m.winnerId ? "lost" : ""} />
                  <span className="vs">
                    <strong>{m.left.name}</strong>
                    <em>vs</em>
                    <strong>{m.right.name}</strong>
                  </span>
                  <img src={m.right.image} alt={m.right.name} className={m.winnerId === m.right.id ? "won" : m.winnerId ? "lost" : ""} />
                  <span className="st">{m.status === "done" ? m.margin : m.status}</span>
                </Link>
              </motion.div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
