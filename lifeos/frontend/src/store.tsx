// Global lab state: the world clock, the character index, time controls and toasts.
import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api, CharSummary, WorldInfo } from "./api";

/** The town and school names, from the world's setting (kept here so any component can use them). */
export const PLACE = { town: "Guilford", school: "Guilford High School", short: "Guilford High", mascot: "Grizzlies" };
function setPlace(w: any) {
  if (w?.town?.name) PLACE.town = w.town.name;
  if (w?.school?.name) PLACE.school = w.school.name;
  if (w?.school?.short) PLACE.short = w.school.short;
  if (w?.school?.mascot) PLACE.mascot = w.school.mascot;
}

export type Tone = "info" | "good" | "bad" | "warn";
interface Toast {
  id: number;
  msg: string;
  tone: Tone;
}

export const SPEEDS = [
  { id: "slow", label: "Slow", days: 1, ms: 1600 },
  { id: "normal", label: "Normal", days: 1, ms: 500 },
  { id: "fast", label: "Fast", days: 7, ms: 200 },
];

interface Store {
  world: WorldInfo | null;
  chars: Record<string, CharSummary>;
  charList: CharSummary[];
  tick: number;
  job: any;
  auto: boolean;
  speed: string;
  error: string | null;
  refresh: () => Promise<void>;
  bump: () => void;
  advance: (days: number) => Promise<any>;
  setAuto: (v: boolean) => void;
  setSpeed: (s: string) => void;
  toast: (msg: string, tone?: Tone) => void;
  toasts: Toast[];
}

const Ctx = createContext<Store>(null as any);
export const useStore = () => useContext(Ctx);

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export function StoreProvider({ children }: { children: React.ReactNode }) {
  const [world, setWorld] = useState<WorldInfo | null>(null);
  const [charList, setCharList] = useState<CharSummary[]>([]);
  const [tick, setTick] = useState(0);
  const [job, setJob] = useState<any>(null);
  const [auto, setAutoState] = useState(false);
  const [speed, setSpeed] = useState("normal");
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [error, setError] = useState<string | null>(null);
  const autoRef = useRef(false);
  const speedRef = useRef("normal");
  const running = useRef(false);

  const toast = useCallback((msg: string, tone: Tone = "info") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, msg, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4200);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const [w, cs] = await Promise.all([api.get("/api/state"), api.get("/api/characters")]);
      setPlace(w);
      setWorld(w);
      setCharList(cs);
      setError(null);
    } catch (e: any) {
      setError(e.message || "Could not reach the LIFE OS server");
    }
  }, []);

  const bump = useCallback(() => setTick((t) => t + 1), []);

  const advance = useCallback(
    async (days: number) => {
      if (running.current) return null;
      running.current = true;
      try {
        let j = await api.post("/api/sim/advance", { days });
        setJob(j);
        while (j.status === "running") {
          await sleep(days > 40 ? 500 : 250);
          j = await api.get("/api/sim/job");
          setJob(j);
          if (days > 20) {
            try {
              const w2 = await api.get("/api/state");
              setPlace(w2);
              setWorld(w2);
            } catch {
              /* keep polling */
            }
          }
        }
        if (j.status === "failed") toast(`The simulation hit an error: ${j.error}`, "bad");
        await refresh();
        setTick((t) => t + 1);
        return j;
      } catch (e: any) {
        toast(e.message, "bad");
        return null;
      } finally {
        running.current = false;
        setJob(null);
      }
    },
    [refresh, toast]
  );

  const setAuto = useCallback(
    (v: boolean) => {
      autoRef.current = v;
      setAutoState(v);
      if (v) {
        (async () => {
          while (autoRef.current) {
            const sp = SPEEDS.find((s) => s.id === speedRef.current) || SPEEDS[1];
            const r = await advance(sp.days);
            if (!r) {
              autoRef.current = false;
              setAutoState(false);
              break;
            }
            await sleep(sp.ms);
          }
        })();
      }
    },
    [advance]
  );

  const setSpeedBoth = (s: string) => {
    speedRef.current = s;
    setSpeed(s);
  };

  useEffect(() => {
    refresh();
  }, [refresh]);

  const chars: Record<string, CharSummary> = {};
  for (const c of charList) chars[c.id] = c;

  return (
    <Ctx.Provider
      value={{ world, chars, charList, tick, job, auto, speed, error, refresh, bump, advance, setAuto, setSpeed: setSpeedBoth, toast, toasts }}
    >
      {children}
    </Ctx.Provider>
  );
}

// Fetch helper that re-runs when deps or the global tick change.
export function useApi<T = any>(path: string | null, deps: any[] = []) {
  const { tick } = useStore();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!path) return;
    let live = true;
    setLoading(true);
    api
      .get(path)
      .then((d) => {
        if (live) {
          setData(d);
          setError(null);
        }
      })
      .catch((e) => live && setError(e.message))
      .finally(() => live && setLoading(false));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, tick, n, ...deps]);
  return { data, error, loading, reload: () => setN((x) => x + 1), setData };
}

// Hash router
export function useRoute(): string[] {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const f = () => setHash(window.location.hash);
    window.addEventListener("hashchange", f);
    return () => window.removeEventListener("hashchange", f);
  }, []);
  const h = hash.replace(/^#\/?/, "");
  return h ? h.split("/").map(decodeURIComponent) : ["overview"];
}

export function go(path: string) {
  window.location.hash = "#/" + path;
}
