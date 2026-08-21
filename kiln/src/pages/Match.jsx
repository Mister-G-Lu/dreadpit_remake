import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import { getMatch } from "../api.js";

function winnerOf(match) {
  if (match.winnerId === match.left.id) return match.left;
  if (match.winnerId === match.right.id) return match.right;
  return null;
}

function verdictDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat(undefined, {
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

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

  const winner = winnerOf(match);
  const date = verdictDate(match.judgedAt);

  return (
    <div className="duel">
      <p className="eyebrow">
        {match.source === "archived-gemini" ? "Archived Gemini verdict" : "The Eye’s verdict"}
        {date ? ` · ${date}` : ""}
      </p>
      <h1 className="verdict-title">{winner ? `${winner.name} wins` : "Awaiting a verdict"}</h1>
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
      {match.reasoning && (
        <motion.section
          className="verdict-reason"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.55 }}
        >
          <p className="eyebrow">Why the Eye chose {winner?.name}</p>
          <p>{match.reasoning}</p>
        </motion.section>
      )}
      {winner && <p className="verdict-line">{winner.name} remains in the stack.</p>}
    </div>
  );
}
