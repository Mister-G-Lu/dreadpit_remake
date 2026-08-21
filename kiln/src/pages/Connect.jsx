import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { pollenKey, setPollenKey } from "../api.js";

function authorizeUrl() {
  const pages = import.meta.env.VITE_PAGES === "1";
  const redirect = pages
    ? `${window.location.origin}${import.meta.env.BASE_URL}#/connect`
    : `${window.location.origin}/connect`;
  const params = new URLSearchParams({
    redirect_url: redirect,
    models: "flux",
    budget: "5",
    expiry: "30",
    permissions: "balance,usage,profile",
  });
  const appKey = import.meta.env.VITE_POLLINATIONS_APP_KEY;
  if (appKey) params.set("app_key", appKey);
  return `https://enter.pollinations.ai/authorize?${params}`;
}

function readKeyFromLocation() {
  const hash = new URLSearchParams(window.location.hash.replace(/^#/, "").split("?")[1] || window.location.hash.replace(/^#/, ""));
  const query = new URLSearchParams(window.location.search);
  return hash.get("api_key") || hash.get("key") || query.get("api_key") || query.get("key") || "";
}

export default function Connect() {
  const [key, setKey] = useState(pollenKey());
  const [draft, setDraft] = useState("");
  const [note, setNote] = useState("");

  useEffect(() => {
    const incoming = readKeyFromLocation();
    if (incoming) {
      setPollenKey(incoming);
      setKey(incoming);
      setNote("Pollinations account imported. The key stays in this browser.");
      if (import.meta.env.VITE_PAGES === "1") window.location.hash = "#/connect";
      else window.history.replaceState({}, "", "/connect");
    }
  }, []);

  function savePaste(e) {
    e.preventDefault();
    const k = draft.trim();
    if (!k.startsWith("sk_") && !k.startsWith("pk_")) {
      setNote("Keys from enter.pollinations.ai start with sk_ or pk_.");
      return;
    }
    setPollenKey(k);
    setKey(k);
    setDraft("");
    setNote("Key saved in this browser. It is sent only when you fire a spark.");
  }

  function disconnect() {
    setPollenKey("");
    setKey("");
    setNote("Unlinked. Anonymous Flux still works, slower, with a watermark.");
  }

  return (
    <motion.div className="narrow cinematic" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
      <p className="eyebrow">Bring your own Pollen</p>
      <h1>Import a Pollinations account</h1>
      <p className="lede">
        Official BYOP. Authorize Kiln at enter.pollinations.ai. They mint a scoped key that spends{" "}
        <em>your</em> Pollen. Flux is free; the key buys a clean plate.
      </p>

      <div className={`status-card ${key ? "on" : ""}`}>
        <div>
          <strong>{key ? "Linked" : "Not linked"}</strong>
          <p>
            {key
              ? `${key.slice(0, 6)}…${key.slice(-4)} · this device only`
              : "Anonymous Flux still throws sparks, one slow portrait at a time."}
          </p>
        </div>
        {key && (
          <button className="btn ghost" onClick={disconnect}>
            Unlink
          </button>
        )}
      </div>

      <a className="btn copper" href={authorizeUrl()}>
        Connect with Pollinations
      </a>
      <p className="hint">You return with a key in the URL fragment. We never persist it on a server.</p>

      <form className="form" onSubmit={savePaste}>
        <label>
          Or paste a key from enter.pollinations.ai
          <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="sk_…" autoComplete="off" />
        </label>
        <button className="btn ghost" type="submit">
          Save key
        </button>
      </form>
      {note && <p className="ok">{note}</p>}
    </motion.div>
  );
}
