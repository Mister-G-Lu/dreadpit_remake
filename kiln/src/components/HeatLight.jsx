import { useEffect, useState } from "react";

export default function HeatLight() {
  const [pos, setPos] = useState({ x: "50%", y: "20%" });

  useEffect(() => {
    const move = (e) => setPos({ x: `${e.clientX}px`, y: `${e.clientY}px` });
    window.addEventListener("pointermove", move);
    return () => window.removeEventListener("pointermove", move);
  }, []);

  return (
    <div
      className="heatlight"
      aria-hidden="true"
      style={{ "--hx": pos.x, "--hy": pos.y }}
    />
  );
}
