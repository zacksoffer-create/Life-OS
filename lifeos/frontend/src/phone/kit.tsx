// Phone UI building blocks: sheets, meters, stat chips, toasts, and character lookups.
import React, { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useStore } from "../store";
import type { Chip, Line, Look } from "./api";
import { Portrait } from "./art";
import { PIcon } from "./icons";
import { usePhone } from "./PhoneContext";

export const cx = (...a: any[]) => a.filter(Boolean).join(" ");

/** Look and name for any character id, from the lab's character index. */
export function useWho() {
  const { chars } = useStore();
  return (id?: string | null) => {
    const c: any = id ? chars[id] : null;
    return c ? { id: c.id as string, first: c.first as string, name: c.name as string, look: (c.look || null) as Look | null, color: c.color as string } : null;
  };
}

export function Face({ id, size = 44, mood, ring }: { id?: string | null; size?: number; mood?: any; ring?: string }) {
  const who = useWho()(id);
  if (!who) return null;
  return <Portrait look={who.look} size={size} mood={mood} color={who.color} name={who.first} ring={ring} />;
}

export function Sheet({ open, onClose, children, title, full, className }: {
  open: boolean; onClose?: () => void; children: React.ReactNode; title?: React.ReactNode; full?: boolean; className?: string;
}) {
  const [show, setShow] = useState(open);
  const [leaving, setLeaving] = useState(false);
  useEffect(() => {
    if (open) {
      setShow(true);
      setLeaving(false);
    } else if (show) {
      setLeaving(true);
      const t = setTimeout(() => setShow(false), 220);
      return () => clearTimeout(t);
    }
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!show) return null;
  const host = typeof document !== "undefined" ? document.getElementById("ph-portal") : null;
  const node = (
    <div className={cx("ph-sheet-wrap", leaving && "leaving")} onClick={(e) => { if (e.target === e.currentTarget && onClose) onClose(); }}>
      <div className={cx("ph-sheet", full && "full", className)} role="dialog">
        <div className="ph-sheet-grab" />
        {(title || onClose) && (
          <div className="ph-sheet-h">
            <div className="ph-sheet-t">{title}</div>
            {onClose && <button className="ph-x" onClick={onClose} aria-label="Close"><PIcon name="x" size={18} /></button>}
          </div>
        )}
        <div className="ph-sheet-b">{children}</div>
      </div>
    </div>
  );
  return host ? createPortal(node, host) : node;
}

export function Bar({ label, value, max = 100, tone, right, invert }: { label: React.ReactNode; value: number; max?: number; tone?: string; right?: React.ReactNode; invert?: boolean }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const auto = invert ? (pct > 66 ? "bad" : pct > 40 ? "warn" : "good") : pct >= 60 ? "good" : pct >= 35 ? "warn" : "bad";
  return (
    <div className="ph-bar">
      <div className="ph-bar-l"><span>{label}</span><b>{right ?? Math.round(value)}</b></div>
      <div className="ph-bar-t"><i className={cx("tone-" + (tone || auto))} style={{ width: `${pct}%` }} /></div>
    </div>
  );
}

export function StatChips({ chips }: { chips: Chip[] }) {
  if (!chips?.length) return null;
  return (
    <div className="ph-chips">
      {chips.map((c, i) => (
        <span key={i} className={cx("ph-chip", c.good ? "up" : "down")} style={{ animationDelay: `${120 + i * 70}ms` }}>
          {c.who ? <Face id={c.who} size={20} /> : <PIcon name={c.label === "Energy" ? "bolt" : c.label === "Stress" ? "flame" : c.label === "Fun" ? "sparkle" : "people"} size={14} />}
          {c.kind === "heart" && <PIcon name="heart" size={13} fill="currentColor" stroke={0} />}
          <span>{c.label}</span>
          <b>{c.delta > 0 ? `+${c.delta}` : `−${Math.abs(c.delta)}`}</b>
        </span>
      ))}
    </div>
  );
}

// "Mike: You're actually trying out?" is someone talking (story scripts write scenes like a screenplay)
// (a name is one to three capitalized words: "Mike", "Coach Davis", "Ms. Lee"; "The tryout list: you chose..." isn't)
const SAY = /^([A-Z][A-Za-z.'\-]*(?: [A-Z][A-Za-z.'\-]*){0,2})(?: texts)?: (.+)$/;

/** Scene text as it was written: narration as paragraphs, "Name: line" as someone talking. */
export function Talk({ text, className }: { text: string; className?: string }) {
  const parts = (text || "").split("\n").map((l) => l.trim()).filter(Boolean);
  if (parts.length <= 1 && !SAY.test(parts[0] || "")) return <p className={className}>{text}</p>;
  return (
    <div className={cx("ph-talk", className)}>
      {parts.map((l, i) => {
        const m = SAY.exec(l);
        return m ? <p key={i} className="say"><b>{m[1]}</b> {m[2]}</p> : <p key={i}>{l}</p>;
      })}
    </div>
  );
}

export function Lines({ lines }: { lines: Line[] }) {
  return (
    <div className="ph-lines">
      {lines.map((l, i) => (
        <div key={l.id ?? i} className={l.type === "why" ? "ph-line why" : "ph-line"} style={{ animationDelay: `${i * 90}ms` }}>
          {l.with && l.with.length > 0 && (
            <div className="ph-line-faces">{l.with.slice(0, 2).map((w) => <Face key={w} id={w} size={36} />)}</div>
          )}
          <Talk text={l.text} />
        </div>
      ))}
    </div>
  );
}

export function Toasts() {
  const { toasts } = usePhone();
  return (
    <div className="ph-toasts">
      {toasts.map((t) => <div key={t.id} className={cx("ph-toast", t.tone)}>{t.text}</div>)}
    </div>
  );
}

export function money(n: number) {
  return `$${Math.round(n).toLocaleString()}`;
}

export function buzz(ms = 12) {
  try {
    (navigator as any).vibrate?.(ms);
  } catch {
    /* no haptics */
  }
}

export function errText(e: any) {
  return (e && (e.message || String(e))) || "Something went wrong";
}
