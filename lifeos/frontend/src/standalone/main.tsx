// LIFE OS: Story, the phone app. The game engine runs on the phone (Python compiled to WebAssembly, in a worker).
import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import PhoneApp from "../phone/PhoneApp";
import { StoreProvider, useRoute } from "../store";
import "../styles.css";
import "./standalone.css";
import { ready, startEngine } from "./bridge";
import { applyUpdate, subscribe, updateReady, UpdateState, watchForUpdates } from "./update";

(window as any).__LIFEOS_STANDALONE__ = true;

function Root() {
  const route = useRoute();
  useEffect(() => {
    if (route[0] !== "m") window.location.replace("#/m");
  }, [route[0]]);
  if (route[0] !== "m") return null;
  return <PhoneApp route={route.slice(1)} />;
}

// "a newer version is out": shown when you come back to the app while it was open (it never restarts on its own then)
function UpdateBanner() {
  const [s, setS] = useState<UpdateState | null>(null);
  const [later, setLater] = useState("");
  useEffect(() => subscribe(setS), []);
  if (!s || !updateReady(s) || later === s.latest) return null;
  return (
    <div className="sa-update" role="status">
      <span>{s.updating ? "Updating… (your game is saved)" : "A newer version of LIFE OS is out."}</span>
      {!s.updating && (
        <>
          <button className="sa-update-go" onClick={() => applyUpdate()}>Update</button>
          <button className="sa-update-x" aria-label="Later" onClick={() => setLater(s.latest)}>×</button>
        </>
      )}
    </div>
  );
}

function Boot() {
  const [msg, setMsg] = useState("Getting ready…");
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState(false);
  useEffect(() => {
    startEngine(setMsg);
    ready
      .then((info) => {
        setOk(true);
        if (info && info.engine) watchForUpdates(info.engine);
      })
      .catch((e) => setErr(e.message || String(e)));
    try {
      (navigator as any).storage?.persist?.();
    } catch {
      /* not supported */
    }
  }, []);
  if (ok) {
    return (
      <StoreProvider>
        <UpdateBanner />
        <Root />
      </StoreProvider>
    );
  }
  return (
    <div className="sa-boot">
      <img src="./icon.svg" alt="" width={84} height={84} />
      <h1>LIFE OS</h1>
      {err ? (
        <>
          <p className="sa-err">{err}</p>
          <button onClick={() => window.location.reload()}>Try again</button>
        </>
      ) : (
        <>
          <div className="sa-spin" />
          <p>{msg}</p>
          <small>The first time, this downloads about 12 MB. After that it starts fast and works offline.</small>
        </>
      )}
    </div>
  );
}

if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost")) {
  // updateViaCache "none": the browser checks sw.js itself with the server, never its own saved copy
  navigator.serviceWorker.register("./sw.js", { updateViaCache: "none" }).catch(() => {});
}

createRoot(document.getElementById("root")!).render(<Boot />);
