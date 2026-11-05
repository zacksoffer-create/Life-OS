"""Play a storyline start to finish, right now, to see what's in it.

Every chapter in its order, one after another, no waiting for its day: you read it, you choose, you see what happens,
next chapter. It's played on a copy of your story (your family, your people, everything that's happened so far), so
nothing here counts in your real story. Your choices still steer it: a chapter that only happens on another branch is
skipped and says which choice leads to it, and a chapter about someone nobody in your story fits says so.

The timing (school years, months, gaps) is left out on purpose: this is for the content. The Story schedule screen is
where the timing lives.
"""
from __future__ import annotations

from . import dialogue, moments, pov, scheduler


def storyline_order(sim, pack: str) -> list:
    """A storyline as it reads now: its chapters in order, with the scenes you added to it ("Additions: <name> #n" packs)
    folded in right after the chapter each one comes after."""
    cat = scheduler.catalog(sim)
    order = list(cat["chapters"].get(pack) or [])
    p = next((x for x in dialogue.packs() if x["id"] == pack), None)
    name = (p["pack"].get("name") if p else None) or ""
    live = dialogue.merged()["moments"]
    added: set = set()
    for x in dialogue.packs():
        if not (x["enabled"] and name and (x["pack"].get("name") or "").startswith(f"Additions: {name} #")):
            continue
        for sid in cat["chapters"].get(x["id"]) or []:
            after = scheduler._after(((live.get(sid) or {}).get("scene") or {}).get("when") or {})
            anchors = [order.index(a) for a in after if a in order]
            if anchors:
                pos = max(anchors) + 1
                while pos < len(order) and order[pos] in added:
                    pos += 1
                order.insert(pos, sid)
            else:
                order.append(sid)
            added.add(sid)
    return order


def _copy(sim):
    from .engine import Simulation
    from .storage import world_from_bytes, world_to_bytes
    return Simulation(world_from_bytes(world_to_bytes(sim.w)))


def _facts_in(sc_spec) -> set:
    return {op[1] for op in dialogue._all_ops({"choices": sc_spec.get("choices") or []})
            if isinstance(op, list) and len(op) > 1 and op[0] == "remember" and isinstance(op[1], str)}


def fact_sources(sim) -> dict:
    """fact -> [(scene title, choice label)]: which choice in which scene remembers it (to say what leads where)."""
    out: dict = {}

    def walk(title, chs, path=""):
        for ch in chs or []:
            if not isinstance(ch, dict):
                continue
            label = (path + " → " if path else "") + (ch.get("label") or "")
            for op in ch.get("ops") or []:
                if isinstance(op, list) and len(op) > 1 and op[0] == "remember" and isinstance(op[1], str):
                    out.setdefault(op[1], []).append((title, label))
            if isinstance(ch.get("then"), dict):
                walk(title, ch["then"].get("choices"), label)
    for sid, mm in sim.cat.moments.items():
        if mm.get("scene"):
            walk(mm.get("title") or sid, mm.get("choices"))
    return out


def _words(fact: str, src: dict, me) -> str:
    where = src.get(fact) or []
    if where:
        t, label = where[0]
        return f"you chose “{label}” in “{pov.second_person(t, me)}”"
    return f"“{fact.replace('_', ' ')}” happened"


class Player:
    def __init__(self, sim, pack: str, start: str | None = None):
        self.sim = _copy(sim)
        w = self.sim.w
        self.me = scheduler._me(self.sim)
        cat = scheduler.catalog(self.sim)
        if pack not in cat["chapters"]:
            raise KeyError(pack)
        self.pack = pack
        self.order = storyline_order(self.sim, pack)
        self.i = self.start = self.order.index(start) if start in self.order else 0
        self.cur: str | None = None
        self.path: list = []        # [{"sid", "title", "picks": [labels]}]
        self.played: set = set()
        for m in moments.pending(w):  # whatever was waiting in your real story isn't part of this
            m["status"] = "resolved"
        self._quiet()
        # replaying from here: the facts these chapters set are yours to choose again
        mem = w.meta.setdefault("remembered", {})
        for sid in self.order[self.i:]:
            for f in _facts_in(self.sim.cat.moments.get(sid) or {}):
                mem.pop(f, None)
        self.src = fact_sources(self.sim)

    def _quiet(self):
        """Only this storyline happens here: nothing else gets queued or delivered in the copy."""
        q = scheduler.queue(self.sim.w)
        q.update({"items": [], "day": self.sim.w.day})

    def _name(self) -> str:
        p = next((x for x in dialogue.packs() if x["id"] == self.pack), None)
        return (p["pack"].get("name") if p else None) or "A storyline"

    def _blocked(self, sid, cat) -> str | None:
        """Why this chapter doesn't happen on the path you've played (branches and people; not dates)."""
        w = self.sim.w
        when = cat["scenes"][sid].get("when") or {}
        mem = w.meta.get("remembered", {})
        if when.get("skip"):
            return "the season plan retired it"
        for f in when.get("remembered") or []:
            if f not in mem:
                if not self.src.get(f):
                    return (f"it needs “{f.replace('_', ' ')}”, but no choice in any of your storylines ever remembers that, "
                            f"so it can't happen. Take the if {f} off this scene, or have a choice remember {f}")
                return "only if " + _words(f, self.src, self.me)
        for f in when.get("not_remembered") or []:
            if f in mem:
                return "not after " + _words(f, self.src, self.me)
        for a in scheduler._after(when):  # a chapter of this storyline it follows, skipped on this path (links elsewhere: timing, left out)
            if a in self.order and self.start <= self.order.index(a) < self.order.index(sid) and a not in self.played:
                return f"it follows “{pov.second_person(cat['info'][a]['title'], self.me)}”, which didn't happen on this path"
        g = scheduler.castable(self.sim, self.me, sid, cat)
        if g:
            return f"nobody in your story fits who it's about ({g[1] or 'its person'})"
        return None

    def _fire(self, sid):
        sim, w = self.sim, self.sim.w
        spec = sim.cat.moments[sid]
        when = {k: v for k, v in (spec["scene"].get("when") or {}).items() if k not in ("you_feel", "they_feel", "me")}
        ctx = dialogue._context(sim, self.me, spec["scene"].get("who"), when, sim.streams.get("preview", w.day, sid), pack=spec["scene"].get("pack"),
                                cast_refs=spec["scene"].get("cast_refs"))
        if ctx is None or not dialogue._playable(spec, ctx):
            return None
        return dialogue.fire(sim, sid, ctx)

    def view(self, m) -> dict:
        mm = {k: v for k, v in m.items() if k != "_choices"}
        mm["text"] = pov.second_person(m["text"], self.me)
        mm["title"] = pov.second_person(m["title"], self.me)
        root = scheduler._root(self.sim, m["kind"])
        pk = (scheduler.catalog(self.sim)["scenes"].get(root) or {}).get("pack")
        n = self.order.index(root) + 1 if root in self.order else None
        mm["storyline"] = (f"{self._name()} · Chapter {n} of {len(self.order)}" if n else self._name()) + (" · a scene you added" if pk != self.pack else "")
        return mm

    def chapters(self) -> list:
        cat = scheduler.catalog(self.sim)
        return [{"sid": s, "title": pov.second_person(cat["info"][s]["title"], self.me)} for s in self.order]

    def present(self) -> dict:
        cat = scheduler.catalog(self.sim)
        skipped = []
        while self.i < len(self.order):
            sid = self.order[self.i]
            why = self._blocked(sid, cat)
            m = None if why else self._fire(sid)
            if m is None:
                skipped.append({"sid": sid, "chapter": self.i + 1, "title": pov.second_person(cat["info"][sid]["title"], self.me),
                                "why": why or "it couldn't be set up with the people in your story"})
                self.i += 1
                continue
            self.cur = sid
            self.path.append({"sid": sid, "title": pov.second_person(cat["info"][sid]["title"], self.me), "picks": []})
            return {"moment": self.view(m), "skipped": skipped, "chapter": self.i + 1, "of": len(self.order), "storyline": self._name()}
        self.cur = None
        return {"done": True, "skipped": skipped, "of": len(self.order), "storyline": self._name(), "path": self.path}

    def choose(self, index: int | None) -> dict:
        """Answer the scene (None: your character decides; a mini game's odds roll for you). What you read, what you
        chose, what happened, and the next beat if the scene keeps going."""
        w = self.sim.w
        root = self.cur
        m = next((x for x in moments.pending(w) if scheduler._root(self.sim, x["kind"]) == root), None)
        if m is None:
            raise ValueError("nothing is waiting for a choice")
        if index is not None and not 0 <= index < len(m["_choices"]):
            raise ValueError("no such choice")
        read = self.view(m)
        self._quiet()
        ev = moments.resolve(self.sim, m["id"], index)
        i = index if index is not None else ev["data"].get("choice_index", ev["data"].get("index"))
        label = (m["_choices"][i].get("label") if isinstance(i, int) and 0 <= i < len(m["_choices"]) else None) or ev["data"].get("choice") or "you let it happen"
        self.path[-1]["picks"].append(pov.second_person(label, self.me))
        lines = [{"id": f"pv{ev['id']}", "type": "moment", "text": pov.event_line(w, ev, self.me.id)}]
        lines += [{"id": f"pvs{ev['id']}-{i}", "type": "say", "text": t} for i, t in enumerate(ev["data"].get("say", []))]
        nxt = None
        for x in moments.pending(w):
            if scheduler._root(self.sim, x["kind"]) == root and nxt is None:
                nxt = x
            elif scheduler._root(self.sim, x["kind"]) != root:
                x["status"] = "resolved"  # only this storyline here
        if nxt is None:
            self.played.add(root)
            self.i += 1
        return {"read": {"title": read["title"], "text": read["text"], "storyline": read["storyline"], "chose": pov.second_person(label, self.me)},
                "lines": lines, "moment": self.view(nxt) if nxt else None, "chapter_done": nxt is None}
