import { useEffect, useRef } from "react";

export default function Embers() {
  const ref = useRef(null);

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let w = 0;
    let h = 0;
    let raf = 0;
    const n = reduced ? 18 : 90;
    const bits = Array.from({ length: n }, spawn);

    function spawn() {
      return {
        x: Math.random(),
        y: Math.random(),
        s: 0.5 + Math.random() * 2.2,
        v: 0.12 + Math.random() * 0.5,
        a: 0.15 + Math.random() * 0.55,
        hue: 18 + Math.random() * 28,
        drift: Math.random() * Math.PI * 2,
      };
    }

    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = c.width = Math.floor(window.innerWidth * dpr);
      h = c.height = Math.floor(window.innerHeight * dpr);
      c.style.width = `${window.innerWidth}px`;
      c.style.height = `${window.innerHeight}px`;
    }

    function tick() {
      ctx.clearRect(0, 0, w, h);
      for (const p of bits) {
        p.y -= p.v * 0.0018;
        p.drift += 0.01;
        p.x += Math.sin(p.drift) * 0.00035;
        if (p.y < -0.04) Object.assign(p, spawn(), { y: 1.04 });
        const gx = p.x * w;
        const gy = p.y * h;
        const r = p.s * (w / 900);
        const g = ctx.createRadialGradient(gx, gy, 0, gx, gy, r * 4);
        g.addColorStop(0, `hsla(${p.hue},100%,62%,${p.a})`);
        g.addColorStop(1, "hsla(20,100%,50%,0)");
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(gx, gy, r * 4, 0, Math.PI * 2);
        ctx.fill();
      }
      raf = requestAnimationFrame(tick);
    }

    resize();
    window.addEventListener("resize", resize);
    tick();
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return <canvas ref={ref} className="embers" aria-hidden="true" />;
}
