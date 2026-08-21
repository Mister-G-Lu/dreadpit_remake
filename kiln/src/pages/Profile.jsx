import { useEffect, useState } from "react";
import { Link, useNavigate, useOutletContext } from "react-router-dom";
import { motion } from "framer-motion";
import { getMyFighters, logout, pollenKey, resurrectFighter } from "../api.js";

export default function Profile() {
  const { me, setMe, pollen } = useOutletContext();
  const nav = useNavigate();
  const [mine, setMine] = useState(null);
  const [note, setNote] = useState(null);
  const [busy, setBusy] = useState(null);

  useEffect(() => {
    if (me) getMyFighters().then(setMine).catch(() => setMine(null));
  }, [me]);

  if (!me) {
    return (
      <div className="narrow cinematic">
        <p className="eyebrow">Account</p>
        <h1>Profile</h1>
        <p className="lede">Log in to see your account, Pollinations link, and daily portrait quota.</p>
        <Link className="btn copper" to="/enter">
          Login
        </Link>
      </div>
    );
  }

  async function onLogout() {
    await logout().catch(() => {});
    setMe(null);
    nav("/");
  }

  async function onRaise(f) {
    setBusy(f.id);
    setNote(null);
    try {
      await resurrectFighter(f.id);
      setNote(`${f.name} climbs out of the ash and returns to the bottom of the stack.`);
      setMine(await getMyFighters());
    } catch (err) {
      setNote(err.message);
    } finally {
      setBusy(null);
    }
  }

  const linked = pollen || Boolean(pollenKey());
  const slots = mine?.slots;

  return (
    <motion.div className="narrow cinematic" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
      <p className="eyebrow">Account</p>
      <h1>Profile</h1>
      <p className="lede">This is your Kiln login. Pollinations is a separate link used only to generate portraits.</p>

      <div className="status-card on">
        <div>
          <strong>Username</strong>
          <p>{me.username}</p>
        </div>
      </div>

      <div className={`status-card ${linked ? "on" : ""}`}>
        <div>
          <strong>Pollinations</strong>
          <p>{linked ? "Connected on this device." : "Not connected. You can still generate, slower, with a watermark."}</p>
        </div>
        <Link className="btn ghost" to="/connect">
          {linked ? "Manage" : "Connect"}
        </Link>
      </div>

      <div className="status-card on">
        <div>
          <strong>Vessel slots</strong>
          <p>
            {slots ? `${slots.used} of ${slots.max} held by living or waiting vessels.` : "…"}
            {" "}The dead hold no slot — raise one and it takes a slot, restarting at the bottom with its career record carved on.
          </p>
        </div>
      </div>

      {mine && mine.fighters.length > 0 && (
        <section className="mine-list">
          <h2>Your vessels</h2>
          {mine.fighters.map((f) => (
            <div key={f.id} className="mine-row">
              <img src={f.image} alt="" />
              <Link to={`/vessel/${f.id}`}>
                {f.name}
                <small>
                  {f.status === "dead"
                    ? `in ash · ${f.careerWins} career win${f.careerWins === 1 ? "" : "s"}`
                    : f.status === "gate"
                      ? "waiting at the mouth"
                      : `${f.wins}w this life · ${f.careerWins} career`}
                </small>
              </Link>
              {f.status === "dead" && (
                <button
                  className="btn ghost small"
                  type="button"
                  disabled={busy === f.id || (slots && slots.used >= slots.max)}
                  onClick={() => onRaise(f)}
                >
                  {busy === f.id ? "Raising…" : "Raise from ash"}
                </button>
              )}
            </div>
          ))}
        </section>
      )}

      {note && <p className="center-link">{note}</p>}

      <div className="cta-row" style={{ justifyContent: "flex-start" }}>
        <Link className="btn copper" to="/forge">
          Open the forge
        </Link>
        <button className="btn ghost" type="button" onClick={onLogout}>
          Log out
        </button>
      </div>
    </motion.div>
  );
}
