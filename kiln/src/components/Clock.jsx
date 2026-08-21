import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

function Pair({ value }) {
  const digits = String(value).padStart(2, "0").split("");
  return (
    <span className="flip-pair">
      {digits.map((d, i) => (
        <span className="flip" key={i}>
          <AnimatePresence mode="popLayout" initial={false}>
            <motion.span
              key={d}
              initial={{ y: 18, opacity: 0, rotateX: -70 }}
              animate={{ y: 0, opacity: 1, rotateX: 0 }}
              exit={{ y: -18, opacity: 0, rotateX: 70 }}
              transition={{ duration: 0.28 }}
            >
              {d}
            </motion.span>
          </AnimatePresence>
        </span>
      ))}
    </span>
  );
}

export default function Clock({ target, label = "Next mouth" }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  if (!target) return <div className="clock muted">No firing scheduled</div>;
  const ms = new Date(target).getTime() - now;
  const ended = ms <= 0;
  const s = Math.max(0, Math.floor(ms / 1000));
  const hh = Math.floor(s / 3600);
  const mm = Math.floor((s % 3600) / 60);
  const ss = s % 60;
  return (
    <div className="clock">
      <div className="clock-label">{ended ? "Firing now" : label}</div>
      <div className="clock-digits" aria-live="polite">
        <Pair value={ended ? 0 : hh} />
        <span className="colon">:</span>
        <Pair value={ended ? 0 : mm} />
        <span className="colon">:</span>
        <Pair value={ended ? 0 : ss} />
      </div>
    </div>
  );
}
