import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import { getFighter } from "../api.js";

function fightDate(value) {
  if (!value) return "Previous fight";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Previous fight";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

export default function Vessel() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    getFighter(id).then(setData).catch((e) => setErr(e.message));
  }, [id]);
  if (err) return <p className="error">{err}</p>;
  if (!data)
    return (
      <div className="boot">
        <span className="ring" />
        <p>Loading fighter</p>
      </div>
    );
  const f = data.fighter;
  return (
    <div className="vessel">
      <motion.img
        src={f.image}
        alt={f.name}
        className="hero-port"
        initial={{ clipPath: "inset(12% 12% 12% 12%)", filter: "brightness(0.4)" }}
        animate={{ clipPath: "inset(0% 0% 0% 0%)", filter: "brightness(1)" }}
        transition={{ duration: 0.8 }}
      />
      <div className="vessel-copy">
        <p className="eyebrow">{f.status}</p>
        <h1>{f.name}</h1>
        <p className="lede">
          {f.wins} fights survived · by {f.owner}
          {f.killerName ? ` · felled by ${f.killerName}` : ""}
        </p>
        {f.sealed ? (
          <p className="sealed">This prompt is sealed.</p>
        ) : f.prompt ? (
          <blockquote>{f.prompt}</blockquote>
        ) : (
          <p className="sealed">No prompt was saved with this fighter.</p>
        )}
        <h2>Fight record</h2>
        <div className="fight-history">
          {data.fights.map((fight, i) => {
            const won = fight.winnerId === f.id;
            const decided = Boolean(fight.winnerId);
            const outcome = decided ? (won ? "Victory" : "Defeat") : "Awaiting verdict";
            return (
              <motion.div
                key={fight.id}
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.06 }}
              >
                <Link
                  to={`/match/${fight.id}`}
                  className={`fight-card ${decided ? (won ? "victory" : "defeat") : "pending"}`}
                  aria-label={`${outcome} against ${fight.opponent?.name || "an unknown opponent"}`}
                >
                  <div className="fight-thumb">
                    {fight.opponent?.image ? (
                      <img src={fight.opponent.image} alt={fight.opponent.name} />
                    ) : (
                      <span className="fight-thumb-missing" aria-hidden="true">?</span>
                    )}
                    <span className="fight-outcome">{outcome}</span>
                  </div>
                  <div className="fight-card-copy">
                    <small>{fightDate(fight.foughtAt)}</small>
                    <strong>{fight.opponent?.name || "Unknown opponent"}</strong>
                    <span>View the fight →</span>
                  </div>
                </Link>
              </motion.div>
            );
          })}
          {!data.fights.length && <p className="muted empty-record">No fights yet.</p>}
        </div>
      </div>
    </div>
  );
}
