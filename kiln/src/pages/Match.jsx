import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import { getMatch } from "../api.js";

export default function Match() {
  const { id } = useParams();
  const [match, setMatch] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    getMatch(id)
      .then((d) => setMatch(d.match))
      .catch((e) => setErr(e.message));
  }, [id]);
  if (err) return <p className="error">{err}</p>;
  if (!match)
    return (
      <div className="boot">
        <span className="ring" />
        <p>Opening the mouth</p>
      </div>
    );
  return (
    <div className="duel">
      <p className="eyebrow">
        Hour {match.batch} · match {match.seq} · {match.status}
      </p>
      <div className="duel-ports">
        <motion.div initial={{ x: -80, opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ type: "spring", stiffness: 80 }}>
          <Link to={`/vessel/${match.left.id}`} className={match.winnerId === match.left.id ? "won" : match.winnerId ? "lost-link" : ""}>
            <img src={match.left.image} alt={match.left.name} />
            <strong>{match.left.name}</strong>
          </Link>
        </motion.div>
        <motion.span className="vs-lg" initial={{ scale: 0.4, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ delay: 0.2 }}>
          VS
        </motion.span>
        <motion.div initial={{ x: 80, opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ type: "spring", stiffness: 80 }}>
          <Link to={`/vessel/${match.right.id}`} className={match.winnerId === match.right.id ? "won" : match.winnerId ? "lost-link" : ""}>
            <img src={match.right.image} alt={match.right.name} />
            <strong>{match.right.name}</strong>
          </Link>
        </motion.div>
      </div>
      {match.narration && (
        <motion.blockquote className="narration" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }}>
          {match.narration}
        </motion.blockquote>
      )}
      {match.judge && (
        <p className="hint">
          Read by {match.judge}
          {match.margin ? ` · ${match.margin}` : ""}
          {match.winnerId
            ? ` · ${
                match.winnerId === match.left.id
                  ? match.left.name === match.right.name
                    ? `${match.left.name} (left)`
                    : match.left.name
                  : match.left.name === match.right.name
                    ? `${match.right.name} (right)`
                    : match.right.name
              } stands`
            : ""}
        </p>
      )}
    </div>
  );
}
