import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { getState } from "../api.js";
import Grid from "../components/Grid.jsx";

export default function Stack() {
  const [state, setState] = useState(null);
  useEffect(() => {
    getState().then(setState).catch(console.error);
  }, []);
  if (!state)
    return (
      <div className="boot">
        <span className="ring" />
        <p>Reading the shelf</p>
      </div>
    );
  return (
    <div>
      <p className="eyebrow">The stack</p>
      <h1>
        {state.living.length} living · {state.maxRoster} lip
      </h1>
      <p className="lede">
        Ordered by firings survived. Adjacent vessels meet when the Eye wakes. Odd
        nights the top vessel sits a bye.
      </p>
      <Grid fighters={state.living} max={state.maxRoster} />
      <ol className="rank">
        {state.living.map((f, i) => (
          <motion.li
            key={f.id}
            initial={{ opacity: 0, x: -12 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ delay: Math.min(i, 12) * 0.03 }}
          >
            <span className="pos">{String(i + 1).padStart(2, "0")}</span>
            <img src={f.image} alt="" />
            <Link to={`/vessel/${f.id}`}>
              {f.name}
              <small>
                {f.wins}w · {f.owner}
              </small>
            </Link>
          </motion.li>
        ))}
      </ol>
    </div>
  );
}
