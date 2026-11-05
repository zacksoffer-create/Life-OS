"""Persistent history: events, decision traces, and the state-change recorder.

Every meaningful state change goes through Effects, which applies it (clamped) and, when
tracing is on, records [entity, field, before, after, why] on the event that caused it.
So an event's change list is a log of what actually happened to state, not a description.
"""
from __future__ import annotations

from .model import REL_FIELDS
from .rng import clamp


class History:
    def __init__(self):
        self.events: dict[int, dict] = {}
        self.traces: dict[int, dict] = {}
        self.by_char: dict[str, list[int]] = {}
        self.consequences: dict[int, list[int]] = {}
        self.folded: dict[str, dict[str, int]] = {}
        self.next_event = 1
        self.next_trace = 1
        self.folded_total = 0

    def reserve(self) -> int:
        eid = self.next_event
        self.next_event += 1
        return eid

    def add(self, ev: dict) -> int:
        eid = ev.get("id")
        if eid is None:
            eid = self.reserve()
            ev["id"] = eid
        self.events[eid] = ev
        seen = set()
        for cid in ev.get("actors", []) + ev.get("targets", []) + ev.get("involved", []):
            if cid not in seen:
                seen.add(cid)
                self.by_char.setdefault(cid, []).append(eid)
        for c in ev.get("causes", []):
            self.consequences.setdefault(c, []).append(eid)
        return eid

    def add_trace(self, tr: dict) -> int:
        tid = self.next_trace
        self.next_trace += 1
        tr["id"] = tid
        self.traces[tid] = tr
        return tid

    def compact(self, day: int, rules: dict):
        """Fold old routine events into per-character counters; drop old routine traces."""
        ev_window = rules["history.event_window_days"]
        ev_keep = rules["history.event_keep_importance"]
        tr_window = rules["history.trace_window_days"]
        tr_keep = rules["history.trace_keep_importance"]
        drop = []
        for eid, ev in self.events.items():
            if ev["day"] >= day - ev_window:
                break
            if ev["importance"] < ev_keep and eid not in self.consequences:
                drop.append(eid)
        for eid in drop:
            ev = self.events.pop(eid)
            for cid in ev.get("actors", []):
                f = self.folded.setdefault(cid, {})
                f[ev["type"]] = f.get(ev["type"], 0) + 1
            self.folded_total += 1
            if ev.get("trace") and ev["trace"] in self.traces:
                del self.traces[ev["trace"]]
        if drop:
            dropset = set(drop)
            self.by_char = {cid: [e for e in lst if e not in dropset] for cid, lst in self.by_char.items()}
        tdrop = []
        for tid, tr in self.traces.items():
            if tr["day"] >= day - tr_window:
                break
            ev = self.events.get(tr.get("event")) if tr.get("event") else None
            if ev is None or ev["importance"] < tr_keep:
                tdrop.append(tid)
        for tid in tdrop:
            del self.traces[tid]
            # leave the event's trace pointer; the API reports it as compacted

    def to_dict(self) -> dict:
        return {"events": list(self.events.values()), "traces": list(self.traces.values()),
                "folded": self.folded, "next_event": self.next_event, "next_trace": self.next_trace,
                "folded_total": self.folded_total}

    @classmethod
    def from_dict(cls, d: dict) -> "History":
        h = cls()
        for ev in d.get("events", []):
            h.events[ev["id"]] = ev
            seen = set()
            for cid in ev.get("actors", []) + ev.get("targets", []) + ev.get("involved", []):
                if cid not in seen:
                    seen.add(cid)
                    h.by_char.setdefault(cid, []).append(ev["id"])
            for c in ev.get("causes", []):
                h.consequences.setdefault(c, []).append(ev["id"])
        for tr in d.get("traces", []):
            h.traces[tr["id"]] = tr
        h.folded = d.get("folded", {})
        h.next_event = d.get("next_event", max(h.events, default=0) + 1)
        h.next_trace = d.get("next_trace", max(h.traces, default=0) + 1)
        h.folded_total = d.get("folded_total", 0)
        return h


LIMITS = {"needs": (0, 100), "traits": (0, 100), "skills": (0, 100), "interests": (0, 100),
          "aptitudes": (0, 100), "motives": (0, 100), "reputation": (0, 100)}


class Effects:
    """Applies and records state changes for one event."""

    def __init__(self, world, ev: dict | None):
        self.w = world
        self.ev = ev
        self.rec = world.tracing and ev is not None
        self.pairs: set = set()
        self.chars: set = set()

    def _log(self, entity, fld, before, after, why):
        if not self.rec:
            return
        if isinstance(before, (int, float)) and isinstance(after, (int, float)):
            if abs(after - before) >= 0.05:
                self.ev["changes"].append([entity, fld, round(before, 2), round(after, 2), why])
        elif before != after:
            self.ev["changes"].append([entity, fld, before, after, why])

    def attr(self, cid: str, layer: str, key: str, delta: float, why: str = ""):
        c = self.w.chars[cid]
        d = getattr(c, layer)
        before = d.get(key, 0.0)
        lo, hi = LIMITS[layer]
        after = clamp(before + delta, lo, hi)
        d[key] = after
        self.chars.add(cid)
        self._log(cid, f"{layer}.{key}", before, after, why)
        return after - before

    def need(self, cid, key, delta, why=""):
        return self.attr(cid, "needs", key, delta, why)

    def skill(self, cid, key, delta, why=""):
        return self.attr(cid, "skills", key, delta, why)

    def trait(self, cid, key, delta, why=""):
        return self.attr(cid, "traits", key, delta, why)

    def interest(self, cid, key, delta, why=""):
        return self.attr(cid, "interests", key, delta, why)

    def rep(self, cid, tag, delta, why=""):
        return self.attr(cid, "reputation", tag, delta, why)

    def mood(self, cid, delta, why=""):
        c = self.w.chars[cid]
        before = c.mood
        c.mood = clamp(before + delta, 0, 100)
        self.chars.add(cid)
        self._log(cid, "mood", before, c.mood, why)

    def money(self, cid, delta, why=""):
        c = self.w.chars[cid]
        before = c.money
        c.money = max(0.0, before + delta)
        self._log(cid, "money", before, c.money, why)

    def scalar(self, cid, fld, value, why=""):
        c = self.w.chars[cid]
        before = getattr(c, fld)
        setattr(c, fld, value)
        self._log(cid, fld, before, value, why)

    def rel(self, a: str, b: str, fld: str, delta: float, why: str = ""):
        if fld == "attraction" and delta > 0:
            from .social import can_be_into
            if not can_be_into(self.w, a, b):
                return 0.0  # family, a teacher, or not who they're into: never, whatever happened
        r = self.w.ensure_rel(a, b, self.w.day)
        before = getattr(r, fld)
        lo, hi = REL_FIELDS[fld]
        after = clamp(before + delta, lo, hi)
        setattr(r, fld, after)
        if fld == "affection" and after > r.peak_affection:
            r.peak_affection = after
        self.pairs.add((a, b))
        self._log(f"{a}>{b}", fld, before, after, why)
        return after - before

    def touch(self, a: str, b: str, kind: str, quality: float):
        r = self.w.ensure_rel(a, b, self.w.day)
        r.last_day = self.w.day
        if quality >= 0.1:
            r.pos += 1
        elif quality <= -0.1:
            r.neg += 1
        r.recent.append([self.w.day, kind, round(quality, 2), self.ev["id"] if self.ev and "id" in self.ev else None])
        if len(r.recent) > 8:
            del r.recent[0]
        self.pairs.add((a, b))

    def flag(self, cid: str, key: str, value, why: str = ""):
        c = self.w.chars[cid]
        before = c.flags.get(key)
        if value is None:
            c.flags.pop(key, None)
        else:
            c.flags[key] = value
        if self.rec and before != value:
            self.ev["changes"].append([cid, f"flags.{key}", before, value, why])

    def join(self, cid: str, gid: str, why: str = ""):
        c = self.w.chars[cid]
        g = self.w.groups[gid]
        if gid not in c.memberships:
            c.memberships.append(gid)
        if cid not in g["members"]:
            g["members"].append(cid)
        g.setdefault("joined", {})[cid] = self.w.day
        if self.rec:
            self.ev["changes"].append([cid, "memberships", None, f"+{gid}", why])

    def leave(self, cid: str, gid: str, why: str = ""):
        c = self.w.chars[cid]
        g = self.w.groups[gid]
        if gid in c.memberships:
            c.memberships.remove(gid)
            c.past_memberships.append({"group": gid, "name": g["name"], "from": g.get("joined", {}).get(cid),
                                       "to": self.w.day, "why": why})
        if cid in g["members"]:
            g["members"].remove(cid)
        if cid in g.get("leaders", []):
            g["leaders"].remove(cid)
        g.get("absences", {}).pop(cid, None)
        if self.rec:
            self.ev["changes"].append([cid, "memberships", f"{gid}", f"-{gid}", why])

    def add_bond(self, a: str, b: str, role: str, why: str = ""):
        from .model import pair_key
        k = pair_key(a, b)
        bd = self.w.bonds.setdefault(k, {"roles": [], "since": {}})
        if role not in bd["roles"]:
            bd["roles"].append(role)
            bd["since"][role] = self.w.day
            if self.rec:
                self.ev["changes"].append([k, "bond", None, f"+{role}", why])

    def drop_bond(self, a: str, b: str, role: str, why: str = ""):
        from .model import pair_key
        k = pair_key(a, b)
        bd = self.w.bonds.get(k)
        if bd and role in bd["roles"]:
            bd["roles"].remove(role)
            bd["since"].pop(role, None)
            if self.rec:
                self.ev["changes"].append([k, "bond", role, f"-{role}", why])

    def memory(self, cid: str, kind: str, with_ids: list, valence: float, intensity: float, text: str,
               tags: list | None = None) -> str:
        w = self.w
        c = w.chars[cid]
        mid = f"m{w.next_id('mem')}"
        m = {"id": mid, "day": w.day, "kind": kind, "with": list(with_ids), "valence": round(valence, 3),
             "intensity": round(intensity, 1), "text": text,
             "event": self.ev.get("id") if self.ev else None, "tags": tags or []}
        c.memories.append(m)
        if len(c.memories) > 60:
            hl = w.rules["dev.memory_half_life"]
            def sal(x):
                age = w.day - x["day"]
                return x["intensity"] * 0.5 ** (age / (hl * (1 + x["intensity"] / 50)))
            c.memories.sort(key=sal, reverse=True)
            del c.memories[60:]
            c.memories.sort(key=lambda x: x["day"])
        if self.ev is not None:
            self.ev.setdefault("memories", []).append([cid, mid])
        self.chars.add(cid)
        return mid
