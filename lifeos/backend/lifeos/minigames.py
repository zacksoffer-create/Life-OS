"""Mini games: short playable rounds (penalty kicks, a quiz, shooting around...) whose results feed the simulation.

A round is a *session*. It starts from one of three places:
  - free play from the phone's Games list ("Pickup soccer at the park"): rewards once a day per game (practice, fun);
  - a story moment choice with a ["minigame", game, {tier: ops}, fallback odds] op ("Take over late. Play it yourself."):
    the tier you earn picks which ops run; if the moment resolves without you playing, the fallback odds roll instead;
  - a quiz day: the class quiz moment hands the trivia round to the exam, so your score counts toward that test;
  - a class game: most school days a teacher throws a quick one at the class (classgames.py): hold it to the line, stop the
    needle, quick math, flash, odd one out, in order, quick hands, or a three-question lightning round. A few seconds each.

The client plays the round and reports score/max. Tiers come from data/minigames.json (great >= 0.8, good >= 0.5, else miss).
Standalone HTML games talk to the app through a tiny postMessage bridge (frontend/public/minigames/README.md).
"""
from __future__ import annotations

import json
import os

from .catalogs import DATA_DIR
from .history import Effects
from .rng import clamp

_REG = None


def reg() -> dict:
    global _REG
    if _REG is None:
        with open(os.path.join(DATA_DIR, "minigames.json"), encoding="utf-8") as f:
            _REG = json.load(f)
    return _REG


def state(w) -> dict:
    s = w.meta.setdefault("minigames", {})
    s.setdefault("played", {})   # game -> last day rewarded (free play)
    s.setdefault("best", {})     # game -> best pct
    s.setdefault("history", [])  # recent rounds
    s.setdefault("next", 1)
    return s


def resolve_game(gid: str, ctx: dict | None = None) -> str | None:
    """'sport' means the mini game for the moment's sport; 'class' means today's class game."""
    if gid == "sport":
        return reg()["sport_games"].get((ctx or {}).get("sport_id") or (ctx or {}).get("sport"))
    if gid == "class":
        return (ctx or {}).get("cg_game")
    return gid


def ready(gid: str | None) -> bool:
    g = reg()["games"].get(gid or "")
    return bool(g and g.get("status") == "ready")


def title(sim, gid, c=None) -> str:
    g = reg()["games"][gid]
    if c is not None and g.get("college_title") and (c.grade or 0) >= 13:
        return g["college_title"]
    return g["title"]


def skill_of(c, g) -> float:
    s = c.skills.get(g.get("skill") or "", 40)
    a = c.aptitudes.get(g.get("aptitude") or "", 50)
    return round(clamp(0.6 * s + 0.4 * a, 0, 100), 1)


def top_op(ops):
    """The choice's top-level minigame op, if it has one."""
    for op in ops or []:
        if isinstance(op, list) and op and op[0] == "minigame":
            return op
    return None


def badge(ops, ctx) -> dict | None:
    """What a played choice shows on its button: which game, about how long."""
    op = top_op(ops)
    gid = op and resolve_game(op[1], ctx)
    if not gid or not ready(gid):
        return None
    g = reg()["games"][gid]
    return {"id": gid, "title": g["title"], "secs": g.get("secs"), "icon": g.get("icon", "ball")}


def choice_ok(ops, ctx) -> bool:
    """A choice that needs a mini game only shows when that game is ready."""
    op = top_op(ops)
    return op is None or ready(resolve_game(op[1], ctx))


def tier_of(gid, score, mx) -> tuple[str, float]:
    t = reg()["tiers"]
    pct = 0.0 if not mx else clamp(score / mx, 0, 1)
    tier = "great" if pct >= t["great"] else "good" if pct >= t["good"] else "miss"
    return tier, round(pct, 3)


def fallback(c, spec, rng) -> tuple[str, float, float]:
    """No one played it: roll the fallback odds against the character's own stats."""
    p = spec.get("base", 0.5)
    for k, coef in spec.items():
        if k != "base":
            v = c.traits.get(k, c.aptitudes.get(k, c.skills.get(k, 50)))
            p += coef * (v - 50) / 100
    p = clamp(p, 0.05, 0.95)
    roll = rng.random()
    tier = "great" if roll < p * 0.35 else "good" if roll < p else "miss"
    return tier, round(p, 3), round(roll, 4)


# ------------------------------------------------------------------------------------------- free play

def _now_ok(sim, c, free) -> tuple[bool, str]:
    from . import calendar as calm
    w = sim.w
    phase = sim.current_phase()
    if phase not in free.get("phases", []):
        return False, "not right now"
    if free.get("weekend") and calm.date_of(w.day).weekday() < 5 and calm.is_school_day(w.day, sim.cat.world["calendar"]):
        return False, "weekends"
    if c.flags.get("injured_until", -1) >= w.day and free.get("phases") != ["after_school", "day", "evening", "night"]:
        return False, "you're hurt"
    return True, ""


def free_list(sim) -> list:
    w = sim.w
    c = w.chars[w.meta["protagonist"]]
    st = state(w)
    out = []
    for gid, g in reg()["games"].items():
        if not g.get("free"):
            continue
        ok, why = _now_ok(sim, c, g["free"])
        rdy = g.get("status") == "ready"
        label = g["free"].get("college_label") if (c.grade or 0) >= 13 and g["free"].get("college_label") else g["free"]["label"]
        out.append({"id": gid, "title": title(sim, gid, c), "label": label, "blurb": g.get("blurb", ""), "icon": g.get("icon", "ball"),
                    "ready": rdy, "available": rdy and ok, "why": "coming soon" if not rdy else why,
                    "rewarded_today": st["played"].get(gid) == w.day, "best": st["best"].get(gid)})
    out.sort(key=lambda x: (not x["ready"], not x["available"], x["title"]))
    return out


# ------------------------------------------------------------------------------------------- sessions

def start(sim, gid, kind="free", mid=None, index=None, ctx=None) -> dict:
    w = sim.w
    c = w.chars[w.meta["protagonist"]]
    gid = resolve_game(gid, ctx)
    g = reg()["games"].get(gid or "")
    if not g:
        raise ValueError("no such game")
    if g.get("status") != "ready":
        raise ValueError(f"{g['title']} isn't ready yet")
    if kind == "free":
        ok, why = _now_ok(sim, c, g.get("free") or {})
        if not g.get("free") or not ok:
            raise ValueError(f"You can't play {title(sim, gid, c).lower()} right now ({why}).")
    st = state(w)
    sid = f"mg{st['next']}"
    st["next"] += 1
    skill = skill_of(c, g)
    difficulty = (ctx or {}).get("difficulty")
    if difficulty is None:
        difficulty = 45 + ((w.chars[c.id].grade or 9) - 9) * 3
    sess = {"id": sid, "game": gid, "kind": kind, "day": w.day, "mid": mid, "index": index, "ctx": dict(ctx or {}),
            "skill": skill, "difficulty": round(float(difficulty), 1), "seed": (w.seed * 7919 + st["next"] * 104729) % 2_147_483_647}
    if gid == "trivia":
        from . import trivia
        sess["questions"] = trivia.round_for(sim, c, sess["ctx"], sess["seed"])
    if g.get("class"):
        from . import classgames
        sess["round"] = classgames.round_for(sim, c, gid, sess["ctx"], sess["seed"], sess["difficulty"], skill)
    st["session"] = sess
    return config(sim, sess)


def config(sim, sess) -> dict:
    w = sim.w
    c = w.chars[w.meta["protagonist"]]
    g = reg()["games"][sess["game"]]
    ctx = sess.get("ctx") or {}
    them = ctx.get("them") or ctx.get("other")
    cfg = {"session": sess["id"], "game": sess["game"], "title": title(sim, sess["game"], c), "kind": g["kind"], "file": g.get("file"),
           "mode": "clutch" if sess["kind"] == "moment" and ctx.get("group") else "class" if ctx.get("cg") else "quiz" if sess["game"] == "trivia"
           else sess["kind"],
           "skill": sess["skill"], "difficulty": sess["difficulty"], "seed": sess["seed"], "me": c.first,
           "them": w.chars[them].first if them in w.chars else None, "college": (c.grade or 0) >= 13,
           "sport": ctx.get("sport_id") or ctx.get("sport"), "opponent": ctx.get("opponent"), "label": ctx.get("mg_label")}
    plays = g.get("play") or {}
    ctx_kind = "clutch" if cfg["mode"] == "clutch" else "free" if sess["kind"] == "free" else "scene"
    cfg["play"] = plays.get(ctx_kind) or plays.get("free") or "menu"
    if sess["game"] == "trivia":
        cfg["questions"] = sess["questions"]
        cfg["subject"] = ctx.get("class_name") or "Trivia"
        cfg["seconds"] = int(ctx.get("seconds") or 15)
    if ctx.get("cg"):
        cfg["title"] = ctx.get("cg_title") or cfg["title"]
        cfg["subject"] = ctx.get("class_name")
        cfg["how"] = ctx.get("cg_how")
    if g.get("class"):
        from . import classgames
        cfg["round"] = sess.get("round")
        cfg["skin"] = classgames.skin_for(sess["game"], ctx, title(sim, sess["game"], c))
    return cfg


def _record(w, sess, score, mx, tier, pct):
    st = state(w)
    st["best"][sess["game"]] = max(st["best"].get(sess["game"], 0), pct)
    st["history"].append({"day": w.day, "game": sess["game"], "kind": sess["kind"], "score": score, "max": mx, "tier": tier})
    st["history"] = st["history"][-60:]
    st.pop("session", None)


def finish(sim, sid, score, mx, stats=None) -> dict:
    """The client says how the round went. Returns what happened."""
    w = sim.w
    st = state(w)
    sess = st.get("session")
    if not sess or sess["id"] != sid:
        raise ValueError("that round is over (or was never started)")
    try:
        score, mx = float(score), float(mx)
    except (TypeError, ValueError):
        raise ValueError("score and max must be numbers")
    if mx <= 0 or mx > 1000 or score < 0 or score > mx:
        raise ValueError("score must be between 0 and max")
    tier, pct = tier_of(sess["game"], score, mx)
    c = w.chars[w.meta["protagonist"]]
    g = reg()["games"][sess["game"]]
    out = {"tier": tier, "pct": pct, "score": score, "max": mx, "game": sess["game"], "kind": sess["kind"]}
    if sess["kind"] == "free":
        out["event"] = _free_rewards(sim, c, sess, g, score, mx, tier, pct)
        _record(w, sess, score, mx, tier, pct)
    elif sess["kind"] == "moment":
        from . import moments
        m = next((x for x in w.meta.get("moments", []) if x["id"] == sess["mid"]), None)
        if not m or m["status"] != "pending":
            st.pop("session", None)
            raise ValueError("that moment has already been decided")
        m["ctx"]["_mg"] = {"tier": tier, "pct": pct, "score": score, "max": mx, "game": sess["game"], "stats": stats or {}}
        if sess["game"] == "trivia" and m["kind"] == "class_quiz":
            c.flags["quiz_played"] = {"day": w.day, "pct": pct, "class": m["ctx"].get("class_id"), "exam": m["ctx"].get("exam")}
        _record(w, sess, score, mx, tier, pct)
        out["event"] = moments.resolve(sim, sess["mid"], sess["index"])
    return out


def _free_rewards(sim, c, sess, g, score, mx, tier, pct):
    w = sim.w
    st = state(w)
    first_today = st["played"].get(sess["game"]) != w.day
    label = (g.get("free") or {}).get("label") or g["title"]
    shown = f"{int(score)} of {int(mx)}" if mx <= 20 and float(score).is_integer() else f"{round(pct * 100)}%"
    ev = sim.new_event("minigame", tier, [c.id], [], 10 if tier == "great" else 6,
                       {"label": g["title"], "game": sess["game"], "score": score, "max": mx, "rewarded": first_today})
    ev["text"] = f"{c.first} played {title(sim, sess['game'], c).lower()} ({label[0].lower() + label[1:]}): {shown}."
    fx = Effects(w, ev)
    pr = g.get("practice") or {}
    if first_today:
        scale = 0.3 + 0.7 * pct
        if pr.get("skill"):
            fx.skill(c.id, pr["skill"], round(pr.get("gain", 0.5) * scale, 2), label)
        if pr.get("fun"):
            fx.need(c.id, "fun", round(pr["fun"] * scale, 1), label)
        if pr.get("social"):
            fx.need(c.id, "social", round(pr["social"] * scale, 1), label)
        if pr.get("energy"):
            fx.need(c.id, "energy", pr["energy"], label)
        if tier == "great":
            fx.mood(c.id, 3, label)
        st["played"][sess["game"]] = w.day
    sim.finish(ev, fx)
    return ev
