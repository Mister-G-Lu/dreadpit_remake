import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { getMe, logout, pollenKey } from "../api.js";

export default function Shell() {
  const loc = useLocation();
  const [me, setMe] = useState(null);
  const [pollen, setPollen] = useState(Boolean(pollenKey()));

  useEffect(() => {
    getMe()
      .then((d) => setMe(d.user))
      .catch(() => setMe(null));
    setPollen(Boolean(pollenKey()));
  }, [loc.pathname]);

  async function onLogout() {
    await logout();
    setMe(null);
  }

  return (
    <div className="shell">
      <div className="grain" aria-hidden="true" />
      <header className="top">
        <Link to="/" className="brand">
          <span className="brand-mark">▣</span>
          <span className="brand-name">KILN</span>
        </Link>
        <nav className="nav">
          <NavLink to="/stack">Stack</NavLink>
          <NavLink to="/forge">Forge</NavLink>
          <NavLink to="/firing">Firing</NavLink>
          <NavLink to="/ash">Ash</NavLink>
        </nav>
        <div className="top-right">
          <NavLink to="/connect" className={pollen ? "pill on" : "pill"}>
            {pollen ? "Pollen linked" : "Pollen"}
          </NavLink>
          {me ? (
            <button className="text-btn" onClick={onLogout}>
              {me.username} · leave
            </button>
          ) : (
            <NavLink to="/enter">Enter</NavLink>
          )}
        </div>
      </header>
      <main className="main">
        <Outlet context={{ me, setMe, pollen }} />
      </main>
      <footer className="foot">
        <span>The kiln fires in hourly mouths of ten.</span>
        <span>Two hundred fifty-six is the lip. Ten sparks a day.</span>
      </footer>
    </div>
  );
}
