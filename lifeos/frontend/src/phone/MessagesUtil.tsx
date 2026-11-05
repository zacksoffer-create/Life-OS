// Shared bits for the Messages and Contacts apps: time labels, avatars for people, parents and groups.
import React from "react";
import { useStore } from "../store";
import { Portrait } from "./art";
import type { Look, Mood } from "./api";

export type PersonInfo = { id: string; first: string; name: string; look?: Look | null; color?: string; year_label?: string };

/** Everyone the lab knows about (looks, names), keyed by id. Used for group chat members and senders. */
export function usePeople(): Record<string, PersonInfo> {
  const { chars } = useStore() as any;
  return (chars || {}) as Record<string, PersonInfo>;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "Fri, Sep 12, 2025" -> { weekday: "Fri", short: "Fri, Sep 12", numeric: "9/12" } */
export function parseDate(date: string) {
  const m = /^(\w{3}), (\w{3}) (\d{1,2})(?:, (\d{4}))?/.exec(date || "");
  if (!m) return { weekday: "", short: date, numeric: date };
  const mi = MONTHS.indexOf(m[2]) + 1;
  return { weekday: m[1], short: `${m[1]}, ${m[2]} ${m[3]}`, numeric: `${mi}/${m[3]}` };
}

/** Day separators inside a conversation. */
export function dayLabel(day: number, date: string, today: number | undefined) {
  if (today !== undefined) {
    if (day === today) return "Today";
    if (day === today - 1) return "Yesterday";
  }
  return parseDate(date).short;
}

/** Time in the conversation list: today -> 7:45 PM, yesterday, this week -> weekday, older -> 9/12. */
export function listTime(day: number | undefined, date: string, at: string, today: number | undefined) {
  if (today === undefined || day === undefined) return at;
  if (day === today) return at;
  if (day === today - 1) return "Yesterday";
  if (today - day < 7) return { Mon: "Monday", Tue: "Tuesday", Wed: "Wednesday", Thu: "Thursday", Fri: "Friday", Sat: "Saturday", Sun: "Sunday" }[parseDate(date).weekday] || parseDate(date).short;
  return parseDate(date).numeric;
}

/** "7:45 PM" -> minutes since midnight. */
export function minutes(at: string) {
  const m = /(\d{1,2}):(\d{2})\s*(AM|PM)/i.exec(at || "");
  if (!m) return 0;
  let h = Number(m[1]) % 12;
  if (m[3].toUpperCase() === "PM") h += 12;
  return h * 60 + Number(m[2]);
}

const PARENT_TINTS = ["linear-gradient(140deg,#ffb59e,#ff8a8a)", "linear-gradient(140deg,#9ec5ff,#7b8cff)"];

export function ParentAvatar({ id, name, size = 44 }: { id: string; name: string; size?: number }) {
  const i = Number(id.replace(/\D/g, "")) || 0;
  return (
    <div className="pm-parent-av" style={{ width: size, height: size, fontSize: size * 0.42, background: PARENT_TINTS[i % 2] }} aria-hidden>
      {name.slice(0, 1)}
    </div>
  );
}

export function PersonAvatar({ id, people, size = 44, mood, parents }: {
  id: string; people: Record<string, PersonInfo>; size?: number; mood?: Mood; parents?: { id: string; name: string }[];
}) {
  if (id.startsWith("parent")) {
    const p = parents?.find((x) => x.id === id);
    return <ParentAvatar id={id} name={p?.name || "P"} size={size} />;
  }
  const c = people[id];
  return <Portrait look={c?.look || null} name={c?.first || "?"} color={c?.color} size={size} mood={mood} />;
}

function HouseGlyph() {
  return (
    <svg viewBox="0 0 24 24" width="13" height="13" aria-hidden>
      <path d="M3 11.2 12 4l9 7.2V20a1 1 0 0 1-1 1h-5.5v-5.5h-5V21H4a1 1 0 0 1-1-1z" fill="currentColor" />
    </svg>
  );
}
function JerseyGlyph() {
  return (
    <svg viewBox="0 0 24 24" width="13" height="13" aria-hidden>
      <path d="M8.5 3 4 5.5 2.5 10l3 1.2V21h13v-9.8l3-1.2L20 5.5 15.5 3a3.5 3.5 0 0 1-7 0z" fill="currentColor" />
    </svg>
  );
}

/** A small cluster of faces for group chats, with a badge for family or team. */
export function GroupAvatar({ members, kind, people, parents, size = 52 }: {
  members: string[]; kind: "family" | "team" | "group"; people: Record<string, PersonInfo>; parents?: { id: string; name: string }[]; size?: number;
}) {
  const faces = members.filter((m) => m.startsWith("parent") || people[m]).slice(0, size < 44 ? 1 : 2);
  const s = faces.length === 1 ? size : Math.round(size * 0.66);
  return (
    <div className="pm-group-av" style={{ width: size, height: size }}>
      {faces.map((m, i) => (
        <div key={m} className="pm-group-face" style={{ left: i === 0 ? 0 : size - s, top: i === 0 ? 0 : size - s, zIndex: 2 - i }}>
          <PersonAvatar id={m} people={people} parents={parents} size={s} />
        </div>
      ))}
      <span className={`pm-group-badge ${kind}${size < 44 ? " sm" : ""}`}>{kind === "family" ? <HouseGlyph /> : <JerseyGlyph />}</span>
    </div>
  );
}

export function Hearts({ n, max = 5 }: { n: number; max?: number }) {
  return (
    <span className="pm-hearts" aria-label={`${n} of ${max} hearts`}>
      {Array.from({ length: max }, (_, i) => (
        <svg key={i} viewBox="0 0 24 24" width="11" height="11" className={i < n ? "on" : ""} aria-hidden>
          <path d="M12 20.5s-7.5-4.6-9.3-9.3C1.4 7.6 3.6 4.5 6.9 4.5c2 0 3.6 1.1 5.1 3 1.5-1.9 3.1-3 5.1-3 3.3 0 5.5 3.1 4.2 6.7-1.8 4.7-9.3 9.3-9.3 9.3z" />
        </svg>
      ))}
    </span>
  );
}

export function Chevron({ dir = "left" }: { dir?: "left" | "right" }) {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden style={{ transform: dir === "right" ? "rotate(180deg)" : undefined }}>
      <path d="M15 4.5 7.5 12 15 19.5" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** Relationship labels as badges, with a tone per kind of relationship. */
export function labelTone(label: string, crush?: boolean, partner?: boolean) {
  if (partner || /dating|partner/.test(label)) return "love";
  if (crush || /crush/.test(label)) return "crush";
  if (/rival|enemy|ex\b/.test(label)) return "rival";
  if (/best/.test(label)) return "best";
  if (/close|friend/.test(label)) return "friend";
  if (/sibling|family/.test(label)) return "family";
  return "plain";
}

export function LabelBadge({ label, crush, partner }: { label: string; crush?: boolean; partner?: boolean }) {
  const tone = labelTone(label, crush, partner);
  const text = partner ? "dating" : crush && !/crush/.test(label) ? `${label} · crush` : label;
  return <span className={`pm-badge ${tone}`}>{text}</span>;
}

export function moodFor(row: { partner?: boolean; crush?: boolean; rivalry?: number; affection?: number; perceived?: number }): Mood {
  if (row.partner) return "happy";
  if (row.crush) return "flirty";
  if ((row.rivalry || 0) >= 40 || (row.affection || 0) <= -30) return "angry";
  if ((row.perceived ?? row.affection ?? 0) >= 35) return "happy";
  return "neutral";
}

export function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

/** A conversation the profile page asked to start (opened thread sends it on arrival). */
export const pendingCompose: { tid: string | null; kind: string | null } = { tid: null, kind: null };
