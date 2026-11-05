// What's going on with this phone, for when the screen won't show: tap the Me tab five times fast (the tab bar always
// shows), or open the app with #/m/diag. A plain white panel on top of everything (no animations, blur or shadows, so it
// paints even when the rest won't): the build, the phone, how much memory the engine holds and how big the story is, what
// the screen behind it is doing, and a Simple look switch that turns every visual effect off.
import React, { useEffect, useState } from "react";
import { api } from "../api";

const PLAIN_KEY = "lifeos.plain";

export function plainOn(): boolean {
  try {
    return localStorage.getItem(PLAIN_KEY) === "1";
  } catch {
    return false;
  }
}

export function applyPlain(on: boolean) {
  document.documentElement.classList.toggle("ph-plain", on);
}

// the Story page, a part at a time: if hiding one part stops the blank screen, that part is it
export const PARTS: [string, string][] = [["art", "The picture at the top"], ["topbar", "The date and energy pills"],
  ["day", "Today's strip, plate and week"], ["scene", "The scene card"], ["choices", "Free-time choices"], ["nudge", "Set your world up card"]];
const HIDE_KEY = "lifeos.hide";

export function hiddenParts(): string[] {
  try {
    return JSON.parse(localStorage.getItem(HIDE_KEY) || "[]");
  } catch {
    return [];
  }
}

export function applyHidden(parts: string[]) {
  for (const [k] of PARTS) document.documentElement.classList.toggle("ph-hide-" + k, parts.includes(k));
}

const PAGE_KEY = "lifeos.pagescroll";

export function pageScrollOn(): boolean {
  try {
    return localStorage.getItem(PAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export function applyPageScroll(on: boolean) {
  document.documentElement.classList.toggle("ph-docscroll", on);
}

function screenReport(): Record<string, string> {
  const out: Record<string, string> = {};
  const scr = document.querySelector(".ph-screen") as HTMLElement | null;
  if (!scr) return { screen: "none on the page" };
  const cs = getComputedStyle(scr);
  out.screen = `opacity ${cs.opacity}, visibility ${cs.visibility}, display ${cs.display}, transform ${cs.transform}, `
    + `animation ${cs.animationName} ${cs.animationFillMode}`;
  out.size = `${Math.round(scr.clientWidth)}x${Math.round(scr.clientHeight)}, content ${scr.scrollHeight} tall, scrolled ${Math.round(scr.scrollTop)}`
    + (document.documentElement.classList.contains("ph-docscroll") ? ` (page scrolled ${Math.round(window.scrollY)})` : "");
  out.inside = `${scr.querySelectorAll("*").length} elements`;
  const x = window.innerWidth / 2;
  const y = window.innerHeight / 3;
  const at = (document.elementsFromPoint ? document.elementsFromPoint(x, y) : [])
    .filter((e) => !e.closest(".ph-diag")).slice(0, 4)
    .map((e) => `${e.tagName.toLowerCase()}${typeof e.className === "string" && e.className ? "." + e.className.split(" ").slice(0, 2).join(".") : ""}`);
  out.at_center = at.join(" > ") || "nothing";
  const story = scr.querySelector(".ph-story");
  if (story) {
    const parts = [...story.querySelectorAll(":scope > *, .ph-story-b > *")]
      .map((e) => `${(typeof e.className === "string" && e.className.split(" ")[0]) || e.tagName.toLowerCase()} ${Math.round((e as HTMLElement).offsetHeight)}`);
    out.story_parts = parts.join(", ");
  }
  out.drawings = `${scr.querySelectorAll("svg").length} svg, ${scr.querySelectorAll("img").length} img`;
  const vw = window.innerWidth;
  const huge = [...scr.querySelectorAll("*")].map((e) => {
    const r = e.getBoundingClientRect();
    return { e, w: Math.max(r.width, (e as HTMLElement).scrollWidth || 0), h: Math.max(r.height, (e as HTMLElement).scrollHeight || 0) };
  }).filter((x) => x.w > vw * 2 || x.h > 6000).slice(0, 5)
    .map((x) => `${x.e.tagName.toLowerCase()}.${(typeof x.e.className === "string" && x.e.className.split(" ")[0]) || ""} ${Math.round(x.w)}x${Math.round(x.h)}`);
  out.oversized = huge.join(", ") || "none";
  const longest = [...scr.querySelectorAll("p, span, div, b, small")].reduce((m, e) => Math.max(m, e.childNodes.length === 1 && e.firstChild?.nodeType === 3 ? (e.textContent || "").length : 0), 0);
  out.longest_text = `${longest} characters`;
  return out;
}

export default function Diagnostics({ onClose }: { onClose: () => void }) {
  const [info, setInfo] = useState<Record<string, any>>({});
  const [plain, setPlain] = useState(plainOn());
  const [page, setPage] = useState(pageScrollOn());
  const [hide, setHide] = useState<string[]>(hiddenParts());
  const flipPart = (k: string) => {
    const next = hide.includes(k) ? hide.filter((x) => x !== k) : [...hide, k];
    setHide(next);
    try {
      localStorage.setItem(HIDE_KEY, JSON.stringify(next));
    } catch { /* private mode */ }
    applyHidden(next);
  };
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    const base: Record<string, any> = {
      device: navigator.userAgent,
      screen_px: `${window.innerWidth}x${window.innerHeight} @${window.devicePixelRatio}x`,
      device_memory_gb: (navigator as any).deviceMemory ?? "not reported",
      installed_app: (navigator as any).standalone ? "yes (home screen)" : "no (browser)",
      ...screenReport(),
    };
    setInfo(base);
    api.get("/api/version").then((v: any) => setInfo((i) => ({ ...i, engine_running: v.engine }))).catch(() => undefined);
    fetch("version.json", { cache: "no-store" }).then((r) => r.json())
      .then((v: any) => setInfo((i) => ({ ...i, latest_online: `engine ${v.engine}, build ${v.build}` })))
      .catch(() => setInfo((i) => ({ ...i, latest_online: "couldn't check (offline?)" })));
    const own = [...document.querySelectorAll("script[src]")].map((e) => (e as HTMLScriptElement).src.split("/").pop()).find((n) => n && /^play-/.test(n));
    if (own) setInfo((i) => ({ ...i, screens_file: own }));
    api.get("/api/sim/memory?full=1").then((m: any) => setInfo((i) => ({ ...i, ...m }))).catch((e: any) => setInfo((i) => ({ ...i, memory: `couldn't read (${String(e?.message || e)})` })));
    api.get("/api/phone/state").then((st: any) => setInfo((i) => ({ ...i,
      story_now: `${st.date}, ${st.scene?.phase}; ${(st.moments || []).length} waiting${st.moments?.[0] ? ` (first: ${st.moments[0].kind}, ${String(st.moments[0].title || "").slice(0, 40)}, ${String(st.moments[0].text || "").length} chars, ${(st.moments[0].choices || []).length} choices)` : ""}`,
      modes: `episodes back to back ${st.control?.binge ? "on" : "off"}, decision ready ${st.decision_ready ? "yes" : "no"}` }))).catch(() => undefined);
    api.get("/api/sim/job").then((j: any) => setInfo((i) => ({ ...i, engine_job: `${j.status}${j.until ? ` (${j.until}, ${j.done ?? 0} days)` : ""}` }))).catch(() => undefined);
  }, []);
  const text = Object.entries(info).map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`).join("\n");
  const flip = () => {
    const on = !plain;
    setPlain(on);
    try {
      localStorage.setItem(PLAIN_KEY, on ? "1" : "0");
    } catch { /* private mode */ }
    applyPlain(on);
  };
  const flipPage = () => {
    const on = !page;
    setPage(on);
    try {
      localStorage.setItem(PAGE_KEY, on ? "1" : "0");
    } catch { /* private mode */ }
    applyPageScroll(on);
  };
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(`LIFE OS diagnostics\n${text}\nsimple look: ${plain ? "on" : "off"}\npage scrolling: ${page ? "on" : "off"}\nhidden: ${hide.join(", ") || "none"}`);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };
  return (
    <div className="ph-diag" role="dialog">
      <div className="ph-diag-in">
        <div className="ph-diag-h">
          <b>Diagnostics</b>
          <button onClick={onClose}>Close</button>
        </div>
        <p>Take a screenshot of this (or copy it) and send it over.</p>
        <label className="ph-diag-sw">
          <input type="checkbox" checked={plain} onChange={flip} />
          <span><b>Simple look</b><br />No animations, blur or shadows. If the screen stops going blank with this on, it's how the phone draws the effects.</span>
        </label>
        <label className="ph-diag-sw">
          <input type="checkbox" checked={page} onChange={flipPage} />
          <span><b>Page scrolling</b><br />The whole page scrolls instead of a box inside the app. If the screen stops going blank with this on, it's the
            scrolling box (and this becomes the normal way).</span>
        </label>
        <div className="ph-diag-sw ph-diag-parts">
          <span><b>Story page: hide a part</b><br />Hide one, close this, and open the Story page. If it stops going blank, that part is the problem.</span>
          {PARTS.map(([k, label]) => (
            <label key={k}><input type="checkbox" checked={hide.includes(k)} onChange={() => flipPart(k)} /> {label}</label>
          ))}
        </div>
        <pre>{text || "Reading…"}</pre>
        <div className="ph-diag-b">
          <button onClick={copy}>{copied ? "Copied" : "Copy all of it"}</button>
          <button onClick={() => window.location.reload()}>Restart the app</button>
        </div>
      </div>
    </div>
  );
}
