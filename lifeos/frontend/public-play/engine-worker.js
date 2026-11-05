// LIFE OS game engine, running on the phone: Python (Pyodide) in a web worker.
// Saves live in the phone's storage (IndexedDB, mounted at /data). Long jobs are run a slice at a time.
/* global loadPyodide */
importScripts("./pyodide/pyodide.js");

let py = null;
let api = null;
let pumping = false;
let dirtySince = 0;
let lastFlush = 0;
// While you play, saving waits at least this long between saves: a save blocks the engine for a few seconds on a phone,
// so every 8 seconds made menus and scenes lag. Leaving the app (or a backup) still saves right away.
const SAVE_EVERY = 45000;
const queue = [];
let busy = false;

function progress(text) { postMessage({ type: "progress", text }); }

function syncfs(populate) {
  return new Promise((resolve) => py.FS.syncfs(populate, (err) => resolve(!err)));
}

async function boot() {
  try {
    progress("Loading the game engine…");
    py = await loadPyodide({ indexURL: new URL("./pyodide/", self.location.href).href });
    progress("Opening your saved story…");
    py.FS.mkdirTree("/data");
    py.FS.mount(py.FS.filesystems.IDBFS, {}, "/data");
    await syncfs(true);
    progress("Unpacking the world…");
    const res = await fetch("./engine.zip", { cache: "no-cache" });
    if (!res.ok) throw new Error("Couldn't download the game files (" + res.status + ").");
    py.unpackArchive(await res.arrayBuffer(), "zip", { extractDir: "/app" });
    py.runPython('import sys; sys.path[:0] = ["/app/standalone", "/app/vendor", "/app"]');
    progress("Waking up the town…");
    const info = JSON.parse(py.runPython('from lifeos import local_api; import json; json.dumps(local_api.boot("/data/saves"))'));
    api = py.globals.get("local_api");
    await syncfs(false);
    setInterval(maybeFlush, 8000);
    postMessage({ type: "ready", info });
  } catch (e) {
    postMessage({ type: "fatal", message: String(e && e.message ? e.message : e).slice(-600) });
  }
}

async function handleOne(m) {
  const bytes = m.body ? new Uint8Array(m.body) : null;
  let out;
  try {
    const r = await api.handle(m.method, m.path, m.query || "", bytes);
    out = r.toJs({ dict_converter: Object.fromEntries });
    r.destroy && r.destroy();
  } catch (e) {
    out = { status: 500, headers: { "content-type": "application/json" }, body: new TextEncoder().encode(JSON.stringify({ detail: String(e).slice(-500) })) };
  }
  const body = out.body instanceof Uint8Array ? out.body : new Uint8Array(out.body || []);
  const copy = body.slice().buffer;
  postMessage({ type: "res", id: m.id, status: out.status, headers: out.headers, body: copy }, [copy]);
  if (m.method !== "GET") dirtySince = dirtySince || Date.now();
  if (!pumping) pumpSoon();
}

async function drain() {
  if (busy) return;
  busy = true;
  while (queue.length) await handleOne(queue.shift());
  busy = false;
}

function pumpSoon() {
  if (pumping) return;
  pumping = true;
  const step = () => {
    let more = false;
    try { more = api.pump(0.12); } catch (e) { more = false; }
    if (more) {
      dirtySince = dirtySince || Date.now();
      setTimeout(step, 0); // let requests (like progress polls) in between slices
    } else {
      pumping = false;
    }
  };
  setTimeout(step, 0);
}

async function flush(force) {
  if (!api) return;
  try {
    const wrote = api.flush();
    // sync whenever anything changed (a save, a dialogue pack...), not only when the autosave wrote just now
    if (wrote || force || dirtySince) await syncfs(false);
    dirtySince = 0;
    lastFlush = Date.now();
  } catch (e) { /* try again next time */ }
}

function maybeFlush() {
  if (!pumping && dirtySince && Date.now() - dirtySince > 6000 && Date.now() - lastFlush > SAVE_EVERY) flush(false);
}

onmessage = (e) => {
  const m = e.data;
  if (m.type === "req") { queue.push(m); drain(); }
  else if (m.type === "flush") flush(true).then(() => postMessage({ type: "flushed" }));
};

boot();
