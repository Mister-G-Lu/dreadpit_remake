import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import { getFighter } from "../api.js";

export default function Vessel() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    getFighter(id).then(setData).catch((e) => setErr(e.message));
  }, [id]);
  if (err)
    return (
      <p className="error" role="alert">
        {err}
      </p>
    );
  if (!data)
    return (
      <div className="boot">
        <span className="ring" />
        <p>Turning the vessel</p>
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
      <div>
        <p className="eyebrow">{f.status}</p>
        <h1>{f.name}</h1>
        <p className="lede">
          {f.wins} firings survived · thrown by {f.owner}
          {f.killerName ? ` · felled by ${f.killerName}` : ""}
        </p>
        {f.sealed ? (
          <p className="sealed">The summoning words are sealed in the ash.</p>
        ) : (
          <blockquote>{f.prompt}</blockquote>
        )}
        <h2>Firings</h2>
        <ul className="plain">
          {data.fights.map((x) => (
            <li key={x.id}>
              <Link to={`/match/${x.id}`}>
                Round {x.round} · {x.status}
                {x.winnerId === f.id ? " · held" : x.winnerId ? " · cracked" : ""}
              </Link>
            </li>
          ))}
          {!data.fights.length && <li className="muted">Not yet called.</li>}
        </ul>
      </div>
    </div>
  );
}
