// The phone app has no server: requests to /api/... go to the game engine running in a web worker on the phone.

type Pending = { resolve: (r: Response) => void; reject: (e: any) => void; timers?: number[] };

/** What a request is doing, in words (for "still working on it" and "stuck" messages). */
function doing(path: string): string {
  const p = path.replace(/^\/api\//, "");
  const words: [RegExp, string][] = [
    [/^story\/build\/outline/, "checking or saving the outline"], [/^story\/build\/scenes/, "adding the scenes"],
    [/^story\/build\/batch-prompt/, "making the prompt for the next scenes"], [/^story\/build\/outline-prompt/, "making the outline prompt"],
    [/^story\/add\/preview/, "playing your years forward with it in"], [/^story\/storyline\/read/, "laying out the storyline"],
    [/^dialogue\/packs/, "loading your storylines"], [/^texting\//, "adding texting"], [/^story\/advance|advance/, "moving time forward"],
  ];
  const hit = words.find(([rx]) => rx.test(p));
  return hit ? hit[1] : p.split("?")[0];
}
const SLOW_MS = 20000;
const STUCK_MS = 60000;
let worker: Worker | null = null;
let seq = 0;
const pending = new Map<number, Pending>();
let onProgress: (msg: string) => void = () => {};
let flushed: (() => void)[] = [];
let readyResolve: (info: any) => void;
let readyReject: (e: any) => void;
export const ready = new Promise<any>((res, rej) => {
  readyResolve = res;
  readyReject = rej;
});

export function startEngine(progress: (msg: string) => void) {
  onProgress = progress;
  const base = new URL(".", window.location.href);
  worker = new Worker(new URL("engine-worker.js", base));
  worker.onmessage = (e: MessageEvent) => {
    const m = e.data;
    if (m.type === "progress") onProgress(m.text);
    else if (m.type === "ready") readyResolve(m.info);
    else if (m.type === "fatal") readyReject(new Error(m.message));
    else if (m.type === "flushed") flushed.splice(0).forEach((f) => f());
    else if (m.type === "res") {
      const p = pending.get(m.id);
      if (!p) return;
      pending.delete(m.id);
      (p.timers || []).forEach((t) => clearTimeout(t));
      p.resolve(new Response(m.body, { status: m.status, headers: m.headers }));
    }
  };
  worker.onerror = (e) => {
    readyReject(new Error(e.message || "The game engine couldn't start."));
    // the engine stopped: nothing waiting on it will ever be answered, so say so instead of spinning
    for (const [id, p] of pending) {
      pending.delete(id);
      (p.timers || []).forEach((t) => clearTimeout(t));
      p.reject(new Error("The game engine stopped. Close the app and open it again: your story is saved."));
    }
  };
  const realFetch = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(typeof input === "string" ? input : input instanceof URL ? input.href : input.url, window.location.href);
    const path = url.pathname.replace(/^.*?(\/api\/)/, "/api/");
    if (!path.startsWith("/api/") || url.origin !== window.location.origin) return realFetch(input as any, init);
    await ready;
    let body: ArrayBuffer | null = null;
    const b: any = init?.body;
    if (typeof b === "string") body = new TextEncoder().encode(b).buffer as ArrayBuffer;
    else if (b instanceof ArrayBuffer) body = b;
    else if (b instanceof Blob) body = await b.arrayBuffer();
    else if (b && b.buffer instanceof ArrayBuffer) body = b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength);
    const id = ++seq;
    return new Promise<Response>((resolve, reject) => {
      const say = (kind: string, text: string) => window.dispatchEvent(new CustomEvent("lifeos-slow", { detail: { kind, text } }));
      const timers = [
        window.setTimeout(() => say("slow", `Still working on it (${doing(path)})…`), SLOW_MS),
        window.setTimeout(() => say("stuck", `This is taking too long (${doing(path)}). If it's still going in a minute, close the app `
          + "and open it again: your story is saved."), STUCK_MS),
      ];
      pending.set(id, { resolve, reject, timers });
      worker!.postMessage({ type: "req", id, method: (init?.method || "GET").toUpperCase(), path, query: url.search.replace(/^\?/, ""), body },
        body ? [body] : []);
    });
  };
  // save when the app goes to the background (people close phone apps by swiping them away)
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") worker?.postMessage({ type: "flush" });
  });
  window.addEventListener("pagehide", () => worker?.postMessage({ type: "flush" }));
}

/** Write the save to the phone's storage now, and wait until it's written (or a few seconds, whichever comes first). */
export function flushNow(timeoutMs = 4000): Promise<void> {
  return new Promise((resolve) => {
    if (!worker) return resolve();
    flushed.push(resolve);
    worker.postMessage({ type: "flush" });
    setTimeout(resolve, timeoutMs);
  });
}
