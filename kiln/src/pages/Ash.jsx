import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { getAsh } from "../api.js";

export default function Ash() {
  const [dead, setDead] = useState(null);
  useEffect(() => {
    getAsh()
      .then((d) => setDead(d.dead))
      .catch(console.error);
  }, []);
  if (!dead)
    return (
      <div className="boot">
        <span className="ring" />
        <p>Raking the heap</p>
      </div>
    );
  if (!dead.length)
    return (
      <div className="narrow cinematic">
        <h1>The ash heap</h1>
        <p className="lede">No vessel has cracked yet. The rake is clean.</p>
      </div>
    );
  return (
    <div>
      <p className="eyebrow">The ash heap</p>
      <h1>Fired. Did not hold.</h1>
      <p className="lede">Prompts sealed. Portraits remain as soot.</p>
      <div className="ash-grid">
        {dead.map((f, i) => (
          <motion.div key={f.id} initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.05 }}>
            <Link to={`/vessel/${f.id}`} className="ash-card">
              <img src={f.image} alt={f.name} />
              <div>
                <strong>{f.name}</strong>
                <small>
                  {f.wins}w · felled by {f.killerName || "the flue"}
                </small>
              </div>
            </Link>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
