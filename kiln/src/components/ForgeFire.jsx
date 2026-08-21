import { useEffect, useRef } from "react";

// Forge-mouth fire for the home hero. Technique: additive-blended
// ("lighter") radial-gradient particles rising from a coal bed, with a
// destination-out fade each frame so flames leave licking trails —
// the classic canvas flame approach.
export default function ForgeFire() {
  const ref = useRef(null);

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let w = 0;
    let h = 0;
    let raf = 0;

    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      const r = c.getBoundingClientRect();
      w = c.width = Math.max(1, Math.floor(r.width * dpr));
      h = c.height = Math.max(1, Math.floor(r.height * dpr));
    }

    // gaussian-ish spread so the flame is dense in the middle, wispy at edges
    const bell = () => (Math.random() + Math.random() + Math.random()) / 3 - 0.5;

    const BASE_Y = 0.8; // coal bed line, fraction of canvas height

    function spawnFlame(p = {}) {
      p.x0 = 0.5 + bell() * 0.4;
      p.ttl = 0.6 + Math.random() * 0.9;
      p.life = Math.random() * 0.05;
      p.rise = 0.42 + Math.random() * 0.3; // how high it climbs (fraction of h)
      p.r = 9 + Math.random() * 24;
      p.wob = Math.random() * Math.PI * 2;
      p.wobV = 1.8 + Math.random() * 3.2;
      p.hueJ = Math.random() * 14;
      return p;
    }

    function spawnSpark(s = {}) {
      s.x0 = 0.5 + bell() * 0.22;
      s.ttl = 0.5 + Math.random() * 0.9;
      s.life = Math.random() * s.ttl;
      s.rise = 0.55 + Math.random() * 0.35;
      s.drift = (Math.random() - 0.5) * 0.16;
      s.r = 0.8 + Math.random() * 1.6;
      return s;
    }

    const flames = Array.from({ length: reduced ? 0 : 120 }, () => {
      const p = spawnFlame();
      p.life = Math.random() * p.ttl;
      return p;
    });
    const sparks = Array.from({ length: reduced ? 0 : 16 }, () => spawnSpark());

    function coalBed() {
      const cx = w * 0.5;
      const cy = h * BASE_Y + h * 0.03;
      const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, w * 0.3);
      g.addColorStop(0, "hsla(28, 100%, 58%, 0.5)");
      g.addColorStop(0.4, "hsla(16, 100%, 45%, 0.22)");
      g.addColorStop(1, "hsla(10, 100%, 35%, 0)");
      ctx.fillStyle = g;
      ctx.save();
      ctx.translate(cx, cy);
      ctx.scale(1, 0.32);
      ctx.beginPath();
      ctx.arc(0, 0, w * 0.3, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }

    function staticGlow() {
      // prefers-reduced-motion: one calm forge glow, no animation
      ctx.clearRect(0, 0, w, h);
      ctx.globalCompositeOperation = "lighter";
      coalBed();
      const cx = w * 0.5;
      const cy = h * (BASE_Y - 0.16);
      const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, h * 0.34);
      g.addColorStop(0, "hsla(38, 100%, 60%, 0.4)");
      g.addColorStop(0.5, "hsla(18, 100%, 48%, 0.18)");
      g.addColorStop(1, "hsla(10, 100%, 40%, 0)");
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(cx, cy, h * 0.34, 0, Math.PI * 2);
      ctx.fill();
    }

    let prev = performance.now();
    function tick(now) {
      const dt = Math.min((now - prev) / 1000, 0.05);
      prev = now;

      // fade last frame -> licking trails
      ctx.globalCompositeOperation = "destination-out";
      ctx.fillStyle = "rgba(0, 0, 0, 0.3)";
      ctx.fillRect(0, 0, w, h);
      ctx.globalCompositeOperation = "lighter";

      coalBed();

      for (const p of flames) {
        p.life += dt;
        if (p.life >= p.ttl) spawnFlame(p);
        const t = p.life / p.ttl;
        p.wob += p.wobV * dt;
        // taper: licks pinch toward the center as they climb
        const pinch = 1 - t * 0.7;
        const px = (0.5 + (p.x0 - 0.5) * pinch + Math.sin(p.wob) * 0.02 * t) * w;
        const py = (BASE_Y - p.rise * t) * h;
        const rad = Math.max(0.6, p.r * (1 - t * 0.85) * (w / 560));
        const hue = 55 - t * 47 + p.hueJ; // white-yellow core -> deep red tips
        const alpha = 0.52 * (1 - t * 0.8);
        const g = ctx.createRadialGradient(px, py, 0, px, py, rad);
        g.addColorStop(0, `hsla(${hue}, 100%, ${64 - t * 20}%, ${alpha})`);
        g.addColorStop(0.6, `hsla(${Math.max(hue - 16, 4)}, 100%, 44%, ${alpha * 0.4})`);
        g.addColorStop(1, "hsla(8, 100%, 38%, 0)");
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(px, py, rad, 0, Math.PI * 2);
        ctx.fill();
      }

      for (const s of sparks) {
        s.life += dt;
        if (s.life >= s.ttl) spawnSpark(s);
        const t = s.life / s.ttl;
        const px = (s.x0 + s.drift * t) * w;
        const py = (BASE_Y - s.rise * t * t) * h; // accelerate upward
        const a = 0.9 * (1 - t);
        ctx.fillStyle = `hsla(${44 - t * 24}, 100%, ${72 - t * 18}%, ${a})`;
        ctx.beginPath();
        ctx.arc(px, py, s.r * (w / 560), 0, Math.PI * 2);
        ctx.fill();
      }

      raf = requestAnimationFrame(tick);
    }

    resize();
    window.addEventListener("resize", resize);
    if (reduced) {
      staticGlow();
    } else {
      raf = requestAnimationFrame(tick);
    }
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return <canvas ref={ref} className="forgefire" aria-hidden="true" />;
}
