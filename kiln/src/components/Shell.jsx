import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import { getMe, logout, pollenKey } from "../api.js";
import Embers from "./Embers.jsx";
import HeatLight from "./HeatLight.jsx";

export default function Shell() {
  const loc = useLocation();
  const [me, setMe] = useState(null);
  const [pollen, setPollen] = useState(Boolean(pollenKey()));
  const [open, setOpen] = useState(false);

  useEffect(() => {
    getMe()
      .then((d) => setMe(d.user))
      .catch(() => setMe(null));
    setPollen(Boolean(pollenKey()));
    setOpen(false);
  }, [loc.pathname]);

  async function onLogout() {
    await logout().catch(() => {});
    setMe(null);
  }

  return (
    <div className="shell">
      <Embers />
      <HeatLight />
      <div className="vignette" aria-hidden="true" />
      <div className="grain" aria-hidden="true" />
      <header className="top">
        <Link to="/" className="brand">
          <span className="brand-mark" />
          <span className="brand-name">KILN</span>
        </Link>
        <nav className={`nav ${open ? "open" : ""}`}>
          <NavLink to="/stack">Stack</NavLink>
          <NavLink to="/forge">Forge</NavLink>
          <NavLink to="/firing">Firing</NavLink>
          <NavLink to="/ash">Ash</NavLink>
        </nav>
        <div className="top-right">
          <NavLink to="/connect" className={pollen ? "pill on" : "pill"}>
            {pollen ? "Pollen" : "Pollen"}
            {pollen && <i className="dot" />}
          </NavLink>
          {me ? (
            <button className="text-btn" onClick={onLogout}>
              {me.username}
            </button>
          ) : (
            <NavLink to="/enter" className="enter-link">
              Log in
            </NavLink>
          )}
          <button className="burger" aria-label="Menu" onClick={() => setOpen((v) => !v)}>
            <span />
            <span />
          </button>
        </div>
      </header>
      <motion.main
        key={loc.pathname}
        className="main"
        initial={{ opacity: 0, y: 18, filter: "blur(8px)" }}
        animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
        exit={{ opacity: 0, y: -12, filter: "blur(6px)" }}
        transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      >
        <Outlet context={{ me, setMe, pollen }} />
      </motion.main>
      <footer className="foot">
        <span>Hourly mouths of ten · two hundred fifty-six at the lip</span>
        <span>Sight only. The shelf does not argue.</span>
      </footer>
    </div>
  );
}
