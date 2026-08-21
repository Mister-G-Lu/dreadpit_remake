import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
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
  if (!match) return <p className="muted">Opening the mouth…</p>;
  return (
    <div className="duel">
      <p className="eyebrow">
        Hour {match.batch} · match {match.seq} · {match.status}
      </p>
      <div className="duel-ports">
        <Link to={`/vessel/${match.left.id}`} className={match.winnerId === match.left.id ? "won" : ""}>
          <img src={match.left.image} alt={match.left.name} />
          <strong>{match.left.name}</strong>
        </Link>
        <span className="vs-lg">VS</span>
        <Link to={`/vessel/${match.right.id}`} className={match.winnerId === match.right.id ? "won" : ""}>
          <img src={match.right.image} alt={match.right.name} />
          <strong>{match.right.name}</strong>
        </Link>
      </div>
      {match.narration && <blockquote className="narration">{match.narration}</blockquote>}
      {match.judge && (
        <p className="hint">
          Read by {match.judge}
          {match.margin ? ` · ${match.margin}` : ""}
        </p>
      )}
    </div>
  );
}
