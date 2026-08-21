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
        <p>Loading the fallen</p>
      </div>
    );
  if (!dead.length)
    return (
      <div className="narrow cinematic">
        <h1>Ash</h1>
        <p className="lede">No fighter has fallen yet.</p>
      </div>
    );
  return (
    <div>
      <p className="eyebrow">The fallen</p>
      <h1>Fired. Did not hold.</h1>
      <p className="lede">Dead fighters stay here. Their prompts are sealed.</p>
      <div className="ash-grid">
        {dead.map((f, i) => (
          <motion.div key={f.id} initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.05 }}>
            <Link to={`/vessel/${f.id}`} className="ash-card">
              <img src={f.image} alt={f.name} />
              <div>
                <strong>{f.name}</strong>
                <small>
                  {f.wins}w · felled by {f.killerName || "the kiln"}
                </small>
              </div>
            </Link>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
