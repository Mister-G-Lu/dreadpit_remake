import { useEffect, useState } from "react";

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
  const hh = String(Math.floor(s / 3600)).padStart(2, "0");
  const mm = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  return (
    <div className="clock">
      <div className="clock-label">{ended ? "Firing now" : label}</div>
      <div className="clock-digits">{ended ? "00:00:00" : `${hh}:${mm}:${ss}`}</div>
    </div>
  );
}
