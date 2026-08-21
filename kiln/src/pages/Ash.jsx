import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getAsh } from "../api.js";

export default function Ash() {
  const [dead, setDead] = useState(null);
  useEffect(() => {
    getAsh()
      .then((d) => setDead(d.dead))
      .catch(console.error);
  }, []);
  if (!dead) return <p className="muted">Raking the heap…</p>;
  if (!dead.length)
    return (
      <div className="narrow">
        <h1>The ash heap</h1>
        <p className="lede">No vessel has cracked yet. The rake is clean.</p>
      </div>
    );
  return (
    <div>
      <p className="eyebrow">The ash heap</p>
      <h1>They were fired. They did not hold.</h1>
      <p className="lede">Prompts sealed. Portraits remain as soot.</p>
      <div className="ash-grid">
        {dead.map((f) => (
          <Link to={`/vessel/${f.id}`} key={f.id} className="ash-card">
            <img src={f.image} alt={f.name} />
            <div>
              <strong>{f.name}</strong>
              <small>
                {f.wins}w · felled by {f.killerName || "the flue"}
              </small>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
