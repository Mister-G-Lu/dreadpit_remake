import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getState } from "../api.js";
import Grid from "../components/Grid.jsx";

export default function Stack() {
  const [state, setState] = useState(null);
  useEffect(() => {
    getState().then(setState).catch(console.error);
  }, []);
  if (!state) return <p className="muted">Reading the shelf…</p>;
  return (
    <div>
      <p className="eyebrow">The stack</p>
      <h1>
        {state.living.length} living · {state.maxRoster} lip
      </h1>
      <p className="lede">
        Ordered by firings survived. Adjacent vessels meet when the Eye wakes. Odd
        nights the top vessel sits a bye so the same mouth does not always eat the same
        clay.
      </p>
      <Grid fighters={state.living} max={state.maxRoster} />
      <ol className="rank">
        {state.living.map((f, i) => (
          <li key={f.id}>
            <span className="pos">{String(i + 1).padStart(2, "0")}</span>
            <img src={f.image} alt="" />
            <Link to={`/vessel/${f.id}`}>
              {f.name}
              <small>
                {f.wins}w · {f.owner}
              </small>
            </Link>
          </li>
        ))}
      </ol>
      {state.gate.length > 0 && (
        <section>
          <h2>The mouth</h2>
          <p className="lede">Waiting for a death. They do not fight tonight.</p>
          <ul className="rank">
            {state.gate.map((f) => (
              <li key={f.id}>
                <img src={f.image} alt="" />
                <Link to={`/vessel/${f.id}`}>{f.name}</Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
