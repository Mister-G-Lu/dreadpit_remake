import { useRef } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";

export default function Grid({ fighters = [], max = 256, tilt = true }) {
  const stage = useRef(null);
  const dim = Math.ceil(Math.sqrt(max));
  const cells = Array.from({ length: max }, (_, i) => fighters[i] || null);

  function onMove(e) {
    if (!tilt || !stage.current) return;
    const r = stage.current.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5;
    const y = (e.clientY - r.top) / r.height - 0.5;
    stage.current.style.setProperty("--rx", `${8 - y * 10}deg`);
    stage.current.style.setProperty("--rz", `${x * -12}deg`);
  }

  function onLeave() {
    if (!stage.current) return;
    stage.current.style.setProperty("--rx", "18deg");
    stage.current.style.setProperty("--rz", "-18deg");
  }

  return (
    <div className="pit-stage" onMouseMove={onMove} onMouseLeave={onLeave}>
      <div className="pit-glow" />
      <div ref={stage} className="kiln-grid" style={{ gridTemplateColumns: `repeat(${dim}, minmax(0, 1fr))` }}>
        {cells.map((f, i) =>
          f ? (
            <motion.div key={f.id} whileHover={{ z: 28, scale: 1.08 }} style={{ transformStyle: "preserve-3d" }}>
              <Link to={`/vessel/${f.id}`} className="cell filled" title={`${f.name} · ${f.wins}w`}>
                <img src={f.image} alt={f.name} />
                <span className="cell-heat" />
              </Link>
            </motion.div>
          ) : (
            <div key={`e${i}`} className="cell empty" />
          )
        )}
      </div>
    </div>
  );
}
