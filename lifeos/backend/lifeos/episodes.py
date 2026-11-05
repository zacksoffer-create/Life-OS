"""Your seven years as one show: seasons and episodes.

Every school year is a season. Every big thing that happens to you is an episode, numbered in the order it aired: the chapters
of your storylines (dialogue packs) and the game's own big moments (tryouts, getting asked out, the college decision...).
Hangouts, quizzes, class games and game-day calls aren't episodes; they're the days in between. When a storyline picks back up, its episode
starts with what happened last time ("Previously..."). The episode guide on the phone lists every season, every episode and
what you chose, and what's coming up next in each storyline.
"""
from __future__ import annotations

from . import calendar as calm

SKIP_PREFIX = ("hang_",)
SKIP = {"class_quiz", "class_game", "game_day", "pet_setup"}
YEAR_LABEL = {9: "Freshman year", 10: "Sophomore year", 11: "Junior year", 12: "Senior year", 13: "College, year one",
              14: "College, year two", 15: "College, year three", 16: "College, year four"}


def counts(kind: str) -> bool:
    return not kind.startswith(SKIP_PREFIX) and kind not in SKIP


def season(sim) -> tuple[int, str]:
    """Which season you're in (school years since the story started) and what it's called."""
    w = sim.w
    st = w.meta.get("story") or {}
    n = calm.school_year_of(w.day) - calm.school_year_of(st.get("start_day", 0)) + 1
    me = w.chars.get(w.meta.get("protagonist") or "")
    g = (me.grade if me else None) or 0
    label = YEAR_LABEL.get(g) or ("After college" if g > 16 else f"Year {n}")
    return max(1, n), label


def _root(sim, kind) -> str:
    return (sim.cat.moments.get(kind) or {}).get("beat_of") or kind


def _storyline(sim, root) -> tuple[str | None, str]:
    sc = (sim.cat.moments.get(root) or {}).get("scene")
    if not sc:
        return None, "Your life"
    from . import dialogue
    p = next((x for x in dialogue.packs() if x["id"] == sc.get("pack")), None)
    return sc.get("pack"), ((p["pack"].get("name") if p else None) or "A storyline")


def log(w) -> list:
    return w.meta.setdefault("episodes", [])


def on_trigger(sim, m):
    """A moment just started: if it's an episode (or the next beat of one), number it, and say what happened last time."""
    w = sim.w
    kind = m["kind"]
    if not counts(kind) or (sim.cat.moments.get(kind) or {}).get("no_episode"):
        return
    root = _root(sim, kind)
    eps = log(w)
    if root != kind:  # a beat: still the same episode
        cur = next((e for e in reversed(eps) if e["kind"] == root), None)
        if cur:
            m["episode"] = {k: cur[k] for k in ("season", "season_label", "number", "premiere", "finale", "storyline")}
        return
    n, label = season(sim)
    number = sum(1 for e in eps if e["season"] == n) + 1
    pack, name = _storyline(sim, root)
    e = {"id": m["id"], "kind": root, "pack": pack, "storyline": name, "title": m["title"], "day": w.day, "season": n,
         "season_label": label, "number": number, "premiere": number == 1, "finale": root == "year_review",
         "choices": [], "said": None, "who": next((v for k, v in m.get("ctx", {}).items() if k in ("them", "other", "coach", "sibling")
                                                    and isinstance(v, str) and v in w.chars), None)}
    if pack:
        last = next((x for x in reversed(eps) if x["pack"] == pack and x["choices"]), None)
        if last:
            picks = " then ".join(f"“{c.rstrip('.!?')}”" for c in last["choices"][:3])
            m["previously"] = f"Previously, in “{last['title']}”: you went with {picks}." + (f" {last['said']}" if last.get("said") else "")
    eps.append(e)
    m["episode"] = {k: e[k] for k in ("season", "season_label", "number", "premiere", "finale", "storyline")}


def on_resolve(sim, m, ch, ev):
    """You made a call in an episode: remember it for the guide and for next time's 'Previously'."""
    w = sim.w
    if not counts(m["kind"]):
        return
    if (sim.cat.moments.get(m["kind"]) or {}).get("no_episode"):  # the rest of a night out: still that episode
        e = next((x for x in reversed(log(w)) if x["kind"].startswith("night_") and x["day"] >= w.day - 1), None)
        if e:
            e["choices"].append(ch["label"])
        return
    root = _root(sim, m["kind"])
    e = next((x for x in reversed(log(w)) if x["kind"] == root), None)
    if not e:
        return
    e["choices"].append(ch["label"])
    said = (ev.get("data") or {}).get("say") or []
    if said and not e.get("said"):
        from .pov import second_person
        me = w.chars.get(w.meta.get("protagonist") or "")
        e["said"] = second_person(said[0], me)[:220]


def label(m) -> str | None:
    ep = m.get("episode")
    if not ep:
        return None
    tag = " · Season premiere" if ep["premiere"] else " · Season finale" if ep["finale"] else ""
    return f"Season {ep['season']} · Episode {ep['number']}{tag}"


def guide(sim) -> dict:
    """The episode guide: every season and episode so far, and what's coming up in each storyline."""
    from . import dialogue
    w = sim.w
    seasons = {}
    for e in log(w):
        s = seasons.setdefault(e["season"], {"n": e["season"], "label": e["season_label"], "episodes": []})
        s["episodes"].append({"number": e["number"], "title": e["title"], "storyline": e["storyline"], "date": calm.label(e["day"]),
                              "choices": e["choices"], "said": e.get("said"), "who": e.get("who"), "premiere": e["premiere"],
                              "finale": e["finale"]})
    coming = []
    for p in dialogue.packs():
        if not p["enabled"] or not dialogue.in_order(p["id"]):
            continue
        pr = dialogue.progress(sim, p["id"])
        if pr["of"] and pr["next"]:
            coming.append({"storyline": p["pack"].get("name") or "A storyline", "next": pr["next"], "chapter": pr["done"] + 1, "of": pr["of"]})
    n, lbl = season(sim)
    return {"now": {"season": n, "label": lbl}, "seasons": [seasons[k] for k in sorted(seasons)], "coming_up": coming}
