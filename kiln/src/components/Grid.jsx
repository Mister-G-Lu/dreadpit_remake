import { Link } from "react-router-dom";

export default function Grid({ fighters = [], max = 256 }) {
  const cells = Array.from({ length: max }, (_, i) => fighters[i] || null);
  const dim = Math.ceil(Math.sqrt(max));
  return (
    <div
      className="kiln-grid"
      style={{ gridTemplateColumns: `repeat(${dim}, minmax(0, 1fr))` }}
      title={`${fighters.length} of ${max}`}
    >
      {cells.map((f, i) =>
        f ? (
          <Link
            key={f.id}
            to={`/vessel/${f.id}`}
            className="cell filled"
            title={`${f.name} · ${f.wins}w`}
          >
            <img src={f.image} alt={f.name} />
          </Link>
        ) : (
          <div key={`e${i}`} className="cell empty" />
        )
      )}
    </div>
  );
}
