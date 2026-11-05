// Keeping the phone app current. The site publishes version.json (the newest engine's id); the app checks it when it
// opens and whenever you come back to it. Opened on an old copy: it updates itself right away (saving first). Came back
// to it while it was open: it says there's an update and waits for a tap, so it never pulls you out of what you were
// doing (like pasting what ChatGPT just wrote).
import { flushNow } from "./bridge";

export type UpdateState = { running: string; latest: string; updating: boolean };

let state: UpdateState = { running: "", latest: "", updating: false };
const listeners = new Set<(s: UpdateState) => void>();

function set(p: Partial<UpdateState>) {
  state = { ...state, ...p };
  listeners.forEach((f) => f(state));
}

export function subscribe(f: (s: UpdateState) => void): () => void {
  listeners.add(f);
  f(state);
  return () => {
    listeners.delete(f);
  };
}

export const updateReady = (s: UpdateState) => !!(s.running && s.latest && s.running !== s.latest);

async function newest(): Promise<string | null> {
  try {
    const url = new URL("version.json", new URL(".", window.location.href)).href + "?t=" + Date.now();
    const r = await fetch(url, { cache: "no-store" });
    if (!r.ok) return null;
    const j = await r.json();
    return j && typeof j.engine === "string" ? j.engine : null;
  } catch {
    return null; // offline: play what's on the phone
  }
}

/** Save, get the newest files, and restart the app on them. */
export async function applyUpdate() {
  set({ updating: true });
  await flushNow();
  try {
    const reg = await navigator.serviceWorker?.getRegistration();
    await reg?.update();
  } catch {
    /* the page load gets the newest files either way */
  }
  window.location.reload();
}

const MARK = "lifeos-updating-to";

async function check(atStart: boolean) {
  const latest = await newest();
  if (!latest || !state.running || state.running === "lab") return;
  set({ latest });
  if (latest === state.running || !atStart) return;
  // just opened, on an old copy: update now, once per new version (if it didn't take, the banner offers it instead)
  let auto = false;
  try {
    if (sessionStorage.getItem(MARK) !== latest) {
      sessionStorage.setItem(MARK, latest);
      auto = true;
    }
  } catch {
    auto = false;
  }
  if (auto) applyUpdate();
}

export function watchForUpdates(running: string) {
  set({ running });
  check(true);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && !state.updating) check(false);
  });
  window.setInterval(() => {
    if (document.visibilityState === "visible" && !state.updating) check(false);
  }, 20 * 60 * 1000);
}
