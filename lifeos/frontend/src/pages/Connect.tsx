// Play on your phone: the address and a QR code for phones on the same Wi-Fi, and how to add it to the home screen.
import qrcode from "qrcode-generator";
import React, { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { Panel } from "../ui";

function QR({ text, size = 220 }: { text: string; size?: number }) {
  const svg = useMemo(() => {
    const q = qrcode(0, "M");
    q.addData(text);
    q.make();
    const n = q.getModuleCount();
    const cell = size / (n + 8);
    let path = "";
    for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (q.isDark(r, c)) path += `M${(c + 4) * cell},${(r + 4) * cell}h${cell}v${cell}h-${cell}z`;
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${size}" width="${size}" height="${size}"><rect width="100%" height="100%" rx="18" fill="#fff"/><path d="${path}" fill="#10261a"/></svg>`;
  }, [text, size]);
  return <div style={{ width: size, height: size }} dangerouslySetInnerHTML={{ __html: svg }} />;
}

/** Where the phone app lives (GitHub Pages, built into the repo's docs/play/ folder by lifeos/tools/build_phone_app.py). */
export const PHONE_APP_URL = "https://zacksoffer-create.github.io/Life-OS/play/";

export default function Connect() {
  const [net, setNet] = useState<{ lan: boolean; port: number; urls: string[]; host: string } | null>(null);
  const [pick, setPick] = useState(0);
  useEffect(() => {
    api.get("/api/net").then(setNet).catch(() => setNet({ lan: false, port: 8765, urls: [], host: "" }));
  }, []);
  const url = net?.urls[pick];
  return (
    <div className="stack" style={{ maxWidth: 980 }}>
      <Panel title="The phone app: play anywhere, no computer needed" sub="LIFE OS: Story runs entirely on your phone. This lab stays here as your dashboard.">
        <div className="row" style={{ gap: 28, alignItems: "flex-start", flexWrap: "wrap" }}>
          <QR text={PHONE_APP_URL} />
          <div className="stack" style={{ flex: 1, minWidth: 280 }}>
            <div>
              <div className="hint">On your iPhone, point the camera at the code (or open this link in Safari):</div>
              <div style={{ fontSize: 18, fontWeight: 700, margin: "6px 0 2px", userSelect: "all", wordBreak: "break-all" }}>{PHONE_APP_URL}</div>
            </div>
            <ol className="muted" style={{ lineHeight: 1.7, margin: 0, paddingLeft: 18 }}>
              <li>Tap <b>Share</b>, then <b>Add to Home Screen</b>. It opens full screen like an app and works offline after the first time.</li>
              <li><b>Make your story:</b> tap <i>Create my story</i> in the app and build yourself, your family, your pet and your people right on the phone. Or build them here in <a href="#/story/new">Start your story</a>, click <i>Download cast</i>, send the file to your phone (AirDrop, email, iCloud), and tap <i>Load a cast file or backup</i>. The Excel worksheet and ChatGPT's answer work too.</li>
              <li>Your story saves on the phone. Use <i>Me → Back up my story</i> now and then.</li>
              <li><b>Look under the hood:</b> import a phone backup in <a href="#/saves">Saves &amp; Worlds</a> here, load it, and everything (history, decisions, the math) is in the lab.</li>
            </ol>
          </div>
        </div>
      </Panel>
      <Panel title="Or play over your Wi-Fi" sub="The story runs on this computer and your phone connects to it on the same Wi-Fi (the computer has to stay on).">
        {!net ? (
          <div className="loading">Checking the network...</div>
        ) : net.lan && url ? (
          <div className="row" style={{ gap: 28, alignItems: "flex-start", flexWrap: "wrap" }}>
            <QR text={url} />
            <div className="stack" style={{ flex: 1, minWidth: 280 }}>
              <div>
                <div className="hint">On your phone, open the camera and point it at the code, or type this into the browser:</div>
                <div style={{ fontSize: 22, fontWeight: 700, margin: "6px 0 2px", userSelect: "all" }}>{url}</div>
                {net.urls.length > 1 && (
                  <div className="row" style={{ gap: 6, flexWrap: "wrap", marginTop: 6 }}>
                    <span className="hint">This computer has more than one address. If one doesn't work, try another:</span>
                    {net.urls.map((u, i) => <button key={u} className={pick === i ? "small primary" : "small"} onClick={() => setPick(i)}>{u.split("//")[1].split("/")[0]}</button>)}
                  </div>
                )}
              </div>
              <ol className="muted" style={{ lineHeight: 1.7, margin: 0, paddingLeft: 18 }}>
                <li>Your phone has to be on the <b>same Wi-Fi</b> as this computer.</li>
                <li>If Windows asks whether to allow Python on the network, choose <b>Allow</b> (private networks).</li>
                <li><b>Make it an app:</b> on iPhone, tap Share, then <i>Add to Home Screen</i>. On Android, tap the menu, then <i>Add to Home screen</i> (or <i>Install app</i>). It gets its own icon and opens like an app.</li>
                <li>Keep this computer on and LIFE OS running while you play. Your progress saves here.</li>
              </ol>
              <div className="row" style={{ gap: 8 }}>
                <a className="btn" href="#/m">Preview the phone app here</a>
              </div>
            </div>
          </div>
        ) : (
          <div className="stack">
            <div className="callout warn">
              <b>Phones can't connect yet.</b> LIFE OS is only listening to this computer right now.
            </div>
            <ol className="muted" style={{ lineHeight: 1.8, margin: 0, paddingLeft: 18 }}>
              <li>Close the black LIFE OS window.</li>
              <li>Double-click <b>Play on Phone (Windows).bat</b> or <b>Play on Phone (Mac).command</b> in the LIFE OS folder instead.</li>
              <li>This page will open again with a QR code for your phone.</li>
            </ol>
            <div className="hint">Command line: <code>python run.py --phone</code></div>
            <div className="row" style={{ gap: 8 }}>
              <a className="btn" href="#/m">Preview the phone app here</a>
            </div>
          </div>
        )}
      </Panel>
      <Panel title="What the phone app is" sub="The single-player side of your story">
        <div className="muted" style={{ lineHeight: 1.7 }}>
          Your life in first person, one moment at a time: where you are, what's happening, and what you do about it. Your phone inside the
          game has your texts (friends, the family chat, the team chat) and your contacts, where you can see how you feel about everyone and how
          they seem to feel about you. Home is your family and your pets. Everything you do there happens in the same world you see here.
        </div>
      </Panel>
    </div>
  );
}
