"""Groundwork: what you set up about the people in your story, kept so a replay starts with it.

Playing is how you find out who people should be: you change your brother's personality, add the friend a storyline
needs, set who's whose best friend, pick who a storyline is about. All of that is groundwork. It's written down as you
make it (in the world, so backups carry it), and **Start over** builds the same town from your setup on day one and
puts it all back. Where things stand in a run (mood, money, GPA, skills grown by practice) isn't groundwork: a replay
starts that fresh.

w.meta["groundwork"] = {
  "people": {id: {"name", "set": {field: value}}},     who they are (editor and lab edits)
  "added":  [{"id", "name", "spec", "extra"}],          people you added, in order (re-made on a replay)
  "pairs":  {"a|b": {"a", "b", "names", "body"}},       how two people feel about each other (editor)
  "slots":  {slot: {"id", "name"}},                     who a named storyline person is (your pick)
  "picks":  {pack: {kind: {"id", "name"}}},             who a storyline is about (your pick)
}
"""
from __future__ import annotations

import copy

CARRY = ("first", "last", "bio", "look", "traits", "aptitudes", "motives", "interests", "gender", "pronouns", "attracted_to",
         "birthday", "archetype", "body", "positions", "jersey", "path", "flirt")
LAYERS = ("traits", "aptitudes", "motives", "interests")
LABEL = {"first": "name", "last": "name", "bio": "bio", "look": "look", "traits": "personality", "aptitudes": "talents",
         "motives": "what drives them", "interests": "interests", "gender": "gender", "pronouns": "pronouns",
         "attracted_to": "who they're into", "birthday": "birthday", "archetype": "type", "body": "height and build",
         "positions": "positions", "jersey": "jersey", "path": "after high school", "flirt": "what works flirting"}

_replaying = False


def get(w) -> dict:
    g = w.meta.setdefault("groundwork", {})
    for k, v in (("people", {}), ("added", []), ("pairs", {}), ("slots", {}), ("picks", {})):
        g.setdefault(k, v)
    return g


# --- writing it down --------------------------------------------------------------------------------

def note_person(w, cid: str, body: dict):
    """An edit to someone: the parts that are who they are (as they are now, after the edit)."""
    if _replaying or cid not in w.chars:
        return
    c = w.chars[cid]
    keys = [k for k in body if k in CARRY]
    if not keys:
        return
    rec = get(w)["people"].setdefault(cid, {"set": {}})
    rec["name"] = c.name
    s = rec["set"]
    for k in keys:
        if k in LAYERS:
            s.setdefault(k, {}).update({x: round(float(getattr(c, k).get(x, 0)), 1) for x in body[k]})
        elif k == "birthday":
            s[k] = list(body[k])
        elif k in ("body", "positions", "look"):
            s[k] = copy.deepcopy(getattr(c, k))
        elif k == "flirt":
            s[k] = dict(c.flags.get("tastes") or {})
        else:
            s[k] = copy.deepcopy(getattr(c, k))


def note_added(w, cid: str, spec: dict, extra: dict | None = None):
    if _replaying or cid not in w.chars:
        return
    get(w)["added"].append({"id": cid, "name": w.chars[cid].name, "spec": copy.deepcopy(spec), "extra": copy.deepcopy(extra or {})})


def note_pair(w, a: str, b: str, body: dict):
    if _replaying or a not in w.chars or b not in w.chars:
        return
    pairs = get(w)["pairs"]
    key = f"{a}|{b}"
    rec = pairs.get(key) if key in pairs else pairs.get(f"{b}|{a}")
    if rec is not None and rec["a"] == b:  # (kept the other way round: swap sides)
        body = {"preset": body.get("preset"), "ab": body.get("ba"), "ba": body.get("ab")}
        a, b = b, a
        key = f"{a}|{b}"
    if rec is None or body.get("preset"):
        rec = {"a": a, "b": b, "body": {}}
    if body.get("preset"):
        rec["body"] = {"preset": body["preset"]}
    for side in ("ab", "ba"):
        if body.get(side):
            rec["body"].setdefault(side, {}).update(body[side])
    rec["names"] = f"{w.chars[a].name} and {w.chars[b].name}"
    pairs.pop(f"{b}|{a}", None)
    pairs[key] = rec


def note_slot(w, slot: str, cid):
    if _replaying:
        return
    if cid is None or cid not in w.chars:
        get(w)["slots"].pop(slot, None)
    else:
        get(w)["slots"][slot] = {"id": cid, "name": w.chars[cid].name}


def note_pick(w, pack: str, who: str, cid):
    if _replaying:
        return
    picks = get(w)["picks"]
    if cid is None or cid not in w.chars:
        (picks.get(pack) or {}).pop(who, None)
        if pack in picks and not picks[pack]:
            picks.pop(pack)
    else:
        picks.setdefault(pack, {})[who] = {"id": cid, "name": w.chars[cid].name}


def my_pick(w, pack: str, who: str):
    """Who you picked for this storyline (None: the game picks)."""
    rec = ((w.meta.get("groundwork") or {}).get("picks", {}).get(pack) or {}).get(who)
    return rec and rec.get("id")


# --- reading it -------------------------------------------------------------------------------------

def summary(w) -> dict:
    """What a replay brings along, in words, each with a key to leave it out."""
    from . import dialogue
    g = w.meta.get("groundwork") or {}
    rows = []
    for a in g.get("added") or []:
        x = a.get("extra") or {}
        slot = x.get("slot") or x.get("role")
        rows.append({"kind": "added", "key": a["id"], "title": a["name"], "what": f"for {slot.replace('_', ' ')}" if slot else ""})
    for cid, rec in (g.get("people") or {}).items():
        what = []
        for k in rec.get("set") or {}:
            if LABEL.get(k) and LABEL[k] not in what:
                what.append(LABEL[k])
        rows.append({"kind": "person", "key": cid, "title": rec.get("name") or cid, "what": ", ".join(what)})
    for key, rec in (g.get("pairs") or {}).items():
        b = rec.get("body") or {}
        rows.append({"kind": "pair", "key": key, "title": rec.get("names") or key,
                     "what": (b.get("preset") or "").replace("_", " ") or "how they feel about each other"})
    for slot, rec in (g.get("slots") or {}).items():
        rows.append({"kind": "slot", "key": slot, "title": slot.replace("_", " "), "what": f"is {rec['name']}"})
    names = {p["id"]: p["pack"].get("name") or p["id"] for p in dialogue.packs()}
    for pack, kinds in (g.get("picks") or {}).items():
        for who, rec in kinds.items():
            rows.append({"kind": "pick", "key": f"{pack}|{who}", "title": names.get(pack, pack),
                         "what": f"{dialogue.WHO.get(who, who)[:-1].lower() if who in dialogue.WHO else who}: {rec['name']}"})
    return {"rows": rows, "count": len(rows)}


def remove(w, kind: str, key: str) -> bool:
    """Leave one thing out of the next replay (it stays as it is in this run)."""
    g = get(w)
    if kind == "added":
        n = len(g["added"])
        g["added"] = [a for a in g["added"] if a["id"] != key]
        return len(g["added"]) < n
    if kind == "person":
        return g["people"].pop(key, None) is not None
    if kind == "pair":
        return g["pairs"].pop(key, None) is not None
    if kind == "slot":
        return g["slots"].pop(key, None) is not None
    if kind == "pick":
        pack, _, who = key.rpartition("|")
        hit = (g["picks"].get(pack) or {}).pop(who, None) is not None
        if pack in g["picks"] and not g["picks"][pack]:
            g["picks"].pop(pack)
        return hit
    return False


def clear(w):
    w.meta["groundwork"] = {}


# --- a replay ---------------------------------------------------------------------------------------

def apply(sim, g: dict) -> dict:
    """Put groundwork from an earlier run into this (new) world: people added again first (so edits and relationships can
    name them), then who everyone is, how pairs feel, and the storyline picks. What can't go back in (someone who isn't in
    this town, a value that's no longer allowed) is skipped and said. {"done", "skipped": [text]}"""
    global _replaying
    from . import dialogue, editor
    w = sim.w
    g = copy.deepcopy(g or {})
    done, skipped, idmap = 0, [], {}
    me_id = w.meta.get("protagonist")
    mp = lambda x: idmap.get(x, x)  # noqa: E731
    _replaying = True
    try:
        for a in g.get("added") or []:
            extra = copy.deepcopy(a.get("extra") or {})
            extra["rel_with"] = [[mp(o), t] for o, t in extra.get("rel_with") or []]
            try:
                c = editor.make_person(sim, a["spec"], extra)
                idmap[a["id"]] = c.id
                a["id"], a["name"] = c.id, c.name
                done += 1
            except editor.EditorError as e:
                skipped.append(f"{a.get('name')}: couldn't be added again ({e})")
        for cid, rec in (g.get("people") or {}).items():
            nid = mp(cid)
            if nid not in w.chars:
                skipped.append(f"{rec.get('name') or cid}: isn't in this town")
                continue
            body = {k: v for k, v in (rec.get("set") or {}).items() if k in CARRY}
            try:
                editor.save_person(sim, nid, body)
                done += 1
            except editor.EditorError as e:
                skipped.append(f"{rec.get('name') or cid}: {e}")
        for key, rec in (g.get("pairs") or {}).items():
            a, b = mp(rec["a"]), mp(rec["b"])
            if a not in w.chars or b not in w.chars:
                skipped.append(f"{rec.get('names') or key}: one of them isn't in this town")
                continue
            try:
                editor.save_pair(sim, a, b, rec.get("body") or {})
                done += 1
            except editor.EditorError as e:
                skipped.append(f"{rec.get('names') or key}: {e}")
        me = w.chars.get(me_id)
        for slot, rec in (g.get("slots") or {}).items():
            nid = mp(rec["id"])
            if me and nid in w.chars and slot in dialogue.merged()["cast"]:
                dialogue.bind(sim, me, slot, nid, by="you")
                rec["id"] = nid
                done += 1
            else:
                skipped.append(f"{slot.replace('_', ' ')}: {rec.get('name')} isn't in this town")
        for pack, kinds in (g.get("picks") or {}).items():
            for who, rec in kinds.items():
                nid = mp(rec["id"])
                if nid in w.chars:
                    dialogue.set_cast(w, pack, who, nid)
                    rec["id"] = nid
                    done += 1
    finally:
        _replaying = False
    remap = {}
    for cid, rec in (g.get("people") or {}).items():
        remap[mp(cid)] = rec
    g["people"] = remap
    g["pairs"] = {f"{mp(r['a'])}|{mp(r['b'])}": {**r, "a": mp(r["a"]), "b": mp(r["b"])} for r in (g.get("pairs") or {}).values()}
    w.meta["groundwork"] = g
    return {"done": done, "skipped": skipped}
