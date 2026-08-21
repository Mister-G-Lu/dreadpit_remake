import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

export const DAY_MS = 24 * 60 * 60 * 1000;

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

function nextOccurrence(target, now, repeatEveryMs) {
  const parsed = new Date(target).getTime();
  if (!Number.isFinite(parsed)) return null;
  if (!repeatEveryMs || parsed > now) return parsed;
  const elapsedCycles = Math.floor((now - parsed) / repeatEveryMs) + 1;
  return parsed + elapsedCycles * repeatEveryMs;
}

export default function Clock({ target, label = "Next firing", repeatEveryMs = 0 }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  if (!target) return <div className="clock muted">No firing scheduled</div>;
  const targetTime = nextOccurrence(target, now, repeatEveryMs);
  if (targetTime === null) return <div className="clock muted">No firing scheduled</div>;

  const ms = targetTime - now;
  if (ms <= 0) {
    return (
      <div className="clock clock-ready" role="status">
        <div className="clock-label">Firing now</div>
        <strong>Results are arriving</strong>
      </div>
    );
  }

  const s = Math.floor(ms / 1000);
  const hh = Math.floor(s / 3600);
  const mm = Math.floor((s % 3600) / 60);
  const ss = s % 60;
  return (
    <div className="clock">
      <div className="clock-label">{label}</div>
      <div className="clock-digits" aria-live="polite" aria-atomic="true">
        <Pair value={hh} />
        <span className="colon">:</span>
        <Pair value={mm} />
        <span className="colon">:</span>
        <Pair value={ss} />
      </div>
    </div>
  );
}
