import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
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

  if (!state) return <p className="muted">Listening at the flue…</p>;
  if (!state.round)
    return (
      <div className="narrow">
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
        Status: {state.round.status}. The Eye reads {state.batchSize} matches per hour
        {state.gemini ? " through Gemini Flash" : " with the lesser eye (no Gemini key)"}
        . Rate-limits stutter the flue; they do not skip a vessel.
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
            {matches.map((m) => (
              <Link to={`/match/${m.id}`} key={m.id} className={`match-row ${m.status}`}>
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
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
