import { Link, useNavigate, useOutletContext } from "react-router-dom";
import { motion } from "framer-motion";
import { logout, pollenKey } from "../api.js";

export default function Profile() {
  const { me, setMe, pollen } = useOutletContext();
  const nav = useNavigate();

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

  const linked = pollen || Boolean(pollenKey());

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
