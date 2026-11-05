// Shared phone state: the latest /api/phone/state, a refresh function and lightweight toasts.
import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { PhoneState, phoneApi } from "./api";

type Toast = { id: number; text: string; tone?: "good" | "bad" | "info" };
type Ctx = {
  state: PhoneState | null; error: string | null; refresh: () => Promise<PhoneState | null>;
  toast: (text: unknown, tone?: Toast["tone"]) => void; toasts: Toast[]; busy: boolean; setBusy: (b: boolean) => void;
};
const PhoneCtx = createContext<Ctx>(null as any);

export function PhoneProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<PhoneState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [busy, setBusy] = useState(false);
  const seq = useRef(0);
  const refresh = useCallback(async () => {
    try {
      const s = await phoneApi.state();
      setState(s);
      setError(null);
      return s;
    } catch (e: any) {
      setError(e.message || String(e));
      return null;
    }
  }, []);
  const toast = useCallback((raw: unknown, tone?: Toast["tone"]) => {
    // always words: an error can come back as {line, text} or anything else, and showing an object would crash the screen
    const o = raw as any;
    const text = typeof raw === "string" ? raw : o && typeof o === "object" && "text" in o ? `${o.line ? `line ${o.line}: ` : ""}${o.text}`
      : o && typeof o === "object" && "message" in o ? String(o.message) : String(raw ?? "Something went wrong");
    const id = ++seq.current;
    setToasts((t) => [...t.slice(-2), { id, text, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3200);
  }, []);
  useEffect(() => {
    refresh();
  }, [refresh]);
  return <PhoneCtx.Provider value={{ state, error, refresh, toast, toasts, busy, setBusy }}>{children}</PhoneCtx.Provider>;
}

export function usePhone() {
  return useContext(PhoneCtx);
}
