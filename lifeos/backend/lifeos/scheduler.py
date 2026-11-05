"""The story scheduler: when storyline scenes happen.

Days and scenes are separate things. Each morning the scheduler looks at every storyline scene (dialogue packs and a season
plan's schedule), works out which ones are ready today, and plans the day: how many interactive scenes, which ones, in what
order and roughly when (morning, class, lunch, after school, evening, night). Scenes come one at a time: the next one is
presented once you've answered the last (or right away with Continue story), and a scene that unlocks another (`after`,
no gap) can lead straight into it the same day. Advancing the calendar is never needed just to clear a cooldown.

Pacing profiles (relaxed, standard, dense, uncapped) say how many scenes a day to aim for. They're presentation targets, not
quotas: nothing is invented to fill a day, and nothing authored is spaced out just to slow it down. The old rules (one scene
every couple of days, five days between chapters) are the relaxed profile now; the default is dense.

A scene is ready today only when all of these hold (`gate`), and when it isn't, the reason is recorded:
  1. its school year, and any month / date / weekday / not_before-not_after window, fits today (a season window from the
     season map applies to scenes that don't say when, e.g. baseball tryouts in March, not September);
  2. it hasn't happened yet (once, the default) or its cooldown is over;
  3. its remembered / not_remembered facts, requirements and mood ranges fit;
  4. every scene in `after` has resolved (or can't happen anymore because its school years are over, the existing rule),
     and any explicit gap_days have passed since the last of them;
  5. in a storyline played in order, it's the storyline's next chapter (the existing rule: a chapter that can't happen yet
     for its year, facts or prerequisites is stepped over; one waiting on the calendar holds the storyline);
  6. nobody needed is missing (checked when it's about to start).
Reasons that can never clear (its years are over, the other branch was chosen, a prerequisite can't happen) are
"unreachable"; the rest are "not yet".

Importance (ambient, regular, major, finale) comes from the scene (`when.importance`, or the schedule) or is read from its
id and title. Dense pacing aims for about one major turning point a week across storylines, unless the next is a direct
consequence of the last or its window is closing: deadline-bound scenes are never let go for pacing.

Interactive scenes never resolve themselves: a scene waits for the player unless they've turned on Let my character
decide (control `auto_scenes`). Everything here is deterministic for a seed and a save.
"""
from __future__ import annotations

import functools
import re
import zlib

from . import calendar as calm

VERSION = 2
PHASE_BUCKETS = ("dawn", "classes", "lunch", "after_school", "day", "evening", "night")
PROFILES = {
    # school / weekend: interactive scenes to aim for in a day (low, high); None = as many as are ready
    "relaxed": {"label": "Relaxed", "global_gap": 2, "chapter_gap": 5, "school": (0, 1), "weekend": (1, 1), "chapter_chance": 0.5,
                "free_chance": 0.04, "major_week": 1, "chain_past_budget": False,
                "about": "The old pace: a scene every couple of days, chapters about five days apart."},
    "standard": {"label": "Standard", "global_gap": 0, "chapter_gap": 1, "school": (1, 2), "weekend": (1, 3), "chapter_chance": 0.8,
                 "free_chance": 0.07, "major_week": 1, "chain_past_budget": True,
                 "about": "A scene or two most days, more on weekends."},
    "dense": {"label": "Dense", "global_gap": 0, "chapter_gap": 0, "school": (2, 5), "weekend": (3, 7), "chapter_chance": 1.0,
              "free_chance": 0.12, "major_week": 1, "chain_past_budget": True,
              "about": "Life drama: two to five scenes on a school day, three to seven on a weekend, when the stories have them."},
    "uncapped": {"label": "Uncapped", "global_gap": 0, "chapter_gap": 0, "school": None, "weekend": None, "chapter_chance": 1.0,
                 "free_chance": 0.12, "major_week": None, "chain_past_budget": True,
                 "about": "Everything that's ready today, one after another."},
}
DEFAULT_PROFILE = "dense"
OVERRIDABLE = ("global_gap", "chapter_gap", "school", "weekend", "chapter_chance", "free_chance", "major_week", "aging_days")
GUARD = 100  # scenes per action, at most (a performance guard, not a story rule)
from .gameplay import REQS as GAME_REQS  # noqa: E402


def gameplay_last(sim, me):
    from .gameplay import last
    return last(sim.w, me)


def game_coming(sim, me, day, within=14) -> bool:
    """You have a game in the next couple of weeks (so a scene about your next game waits for it)."""
    return any(i.get("kind") == "game" and i.get("group") in me.memberships and day <= i["day"] <= day + within for i in sim.w.calendar)


AGING_DAYS = 3  # a planned scene nobody got to goes back in the pool after this long (it isn't used up)
PERMANENT = {"played", "year_passed", "exclusive_branch", "after_unreachable", "window_passed", "branch_closed", "skipped_by_plan",
             "fact_never_set"}
REASON_TEXT = {
    "your_order": "you put another episode first",
    "played": "already happened", "in_progress": "happening now", "cooldown": "on cooldown", "too_early": "not yet",
    "year_passed": "its school years are over", "exclusive_branch": "the other branch happened",
    "missing_fact": "needs something that hasn't happened", "waiting_for_scene": "waiting for another scene",
    "after_unreachable": "needs a scene that can't happen anymore", "missing_requirement": "a requirement isn't true now",
    "mood": "your mood or grades aren't in its range", "wrong_date": "only on certain dates", "wrong_season": "not its season",
    "wrong_weekday": "only on certain days", "window_passed": "its window this year is over", "chapter_order": "an earlier chapter comes first",
    "chance": "didn't come up today", "major_breather": "giving the last big moment room", "budget": "today is full",
    "missing_cast": "nobody in your story fits", "not_playable": "not enough people for its choices", "global_gap": "a quiet day",
    "branch_closed": "a choice already went the other way",
    "fact_never_set": "it needs a fact that nothing in your storylines ever remembers",
    "never_picked": "ready, but other scenes always came first", "missed": "its year ended first",
    "skipped_by_plan": "retired by a schedule (skip)",
    "waiting_for_game": "it's about how your next game goes: it waits for the game",
}
IMPORTANCE = ("ambient", "regular", "major", "finale")
FINALE_RX = re.compile(r"(^|_)(finale|culminat\w*|graduat\w*|commencement|senior_night|last_(school_)?game|final_game|state_(final|title|champ\w*)|"
                       r"championship|season_end|year_end|farewell|goodbye)(_|$)")
MAJOR_RX = re.compile(r"(^|_)(debut|playoffs?|decision|decides|tryouts?|cut|homecoming|prom|first_kiss|kiss|break_?up|breakup|ask(ed|s)?_out|"
                      r"confess\w*|fight|injur\w*|signing|commit\w*|offer|draft|move_in|funeral|arrest\w*|caught|reveal\w*|ultimatum|"
                      r"varsity|captain|rivalry_game|big_game)(_|$)")
AMBIENT_RX = re.compile(r"(^|_)(texts?|joke|meme|group_chat|hallway|bus|snack|selfie|chatter|banter|small_talk|locker)(_|$)")
SEASON_RULES = [
    # Windows come from the school's own calendar (world.json): the team schedules, the dances, breaks and graduation.
    # anchor: school_start | event:<calendar event id> | break:<break name> | sport:start|early|season|end, with days
    # before/after; or fixed from/to month-days; or months.
    {"id": "first_day", "label": "First days of school", "match": r"(^|_)(first_(day|morning|week)|orientation|back_to_school)(_|$)",
     "anchor": "school_start", "before": 7, "after": 20},
    {"id": "senior_night", "label": "Senior night", "needs_sport": True, "match": r"(^|_)senior_night(_|$)", "anchor": "sport:end",
     "before": 21, "after": -3},
    {"id": "end_of_season", "label": "Last games and playoffs", "needs_sport": True,
     "match": r"(^|_)(last_(school_)?game|final_game|playoffs?|state_(final|title|tourn\w*)|championship|sectionals?|season_ends?)(_|$)",
     "anchor": "sport:end", "before": 7, "after": 21},
    {"id": "season_start", "label": "Tryouts and the first practice", "needs_sport": True,
     "match": r"(^|_)(tryouts?|first_practice|preseason|cuts?|roster)(_|$)", "anchor": "sport:start"},
    {"id": "debut", "label": "Debuts and openers", "needs_sport": True,
     "match": r"(^|_)(debut|jv_debut|varsity_debut|opening_day|season_opener|first_game|first_start)(_|$)", "anchor": "sport:early"},
    {"id": "homecoming_ask", "label": "Homecoming: asking someone", "match": r"(^|_)(homecoming|hoco|hc)(_|$)",
     "also": r"(^|_)(asks?|asking|asked|invite\w*|propos\w*|hoco_?posal|date_hunt|who_to_take)(_|$)", "anchor": "event:homecoming", "before": 16, "after": 5},
    {"id": "homecoming_after", "label": "Homecoming: the aftermath", "match": r"(^|_)(homecoming|hoco|hc)(_|$)",
     "also": r"(^|_)(after\w*|aftermath|morning_after|monday|fallout)(_|$)", "anchor": "event:homecoming", "before": 0, "after": 12},
    {"id": "homecoming", "label": "Homecoming: the dance", "match": r"(^|_)(homecoming|hoco|hc)(_|$)", "anchor": "event:homecoming", "before": 1, "after": 7},
    {"id": "halloween", "label": "Halloween", "match": r"(^|_)halloween(_|$)", "from": [10, 18], "to": [10, 31]},
    {"id": "thanksgiving", "label": "Thanksgiving", "match": r"(^|_)thanksgiving(_|$)", "anchor": "break:Thanksgiving break", "before": 5, "after": 1},
    {"id": "holidays", "label": "Holidays", "match": r"(^|_)(christmas|holiday_break|winter_break|new_years?)(_|$)", "anchor": "break:Winter break",
     "before": 5, "after": 0},
    {"id": "valentines", "label": "Valentine's Day and the Snow Ball", "match": r"(^|_)(valentines?|snow_ball)(_|$)", "anchor": "event:snow_ball",
     "before": 12, "after": 3},
    {"id": "prom_ask", "label": "Prom: asking someone", "match": r"(^|_)prom(_|$)", "also": r"(^|_)(asks?|asking|asked|invite\w*|propos\w*|promposal)(_|$)",
     "anchor": "event:prom", "before": 21, "after": 5},
    {"id": "prom_after", "label": "Prom: the aftermath", "match": r"(^|_)prom(_|$)", "also": r"(^|_)(after\w*|aftermath|morning_after|fallout)(_|$)",
     "anchor": "event:prom", "before": 0, "after": 12},
    {"id": "prom", "label": "Prom night", "match": r"(^|_)(prom|promposal)(_|$)", "anchor": "event:prom", "before": 1, "after": 7},
    {"id": "graduation", "label": "Graduation", "match": r"(^|_)(graduat\w*|commencement|cap_and_gown|senior_week)(_|$)", "anchor": "event:graduation",
     "before": 4, "after": 7},
    {"id": "college_move", "label": "Moving in at college", "match": r"(^|_)(move_in|dorm|college_move|campus_(day|arrival)|first_week_at_college)(_|$)",
     "from": [8, 20], "to": [9, 15]},
    {"id": "summer", "label": "Summer", "match": r"(^|_)(summer|fourth_of_july|july_4)(_|$)", "anchor": "break:Summer"},
    {"id": "spring_break", "label": "Spring break", "match": r"(^|_)spring_break(_|$)", "anchor": "break:Spring break", "before": 2, "after": 0},
    {"id": "snow", "label": "Snow", "match": r"(^|_)(snow_day|snowball|blizzard)(_|$)", "months": [12, 1, 2, 3]},
    {"id": "sport_season", "label": "Games and practices, in season", "needs_sport": True,
     "match": r"(^|_)(game|games|practice|scrimmage|tip_?off|hoops|layups?|dunks?|free_throws?|touchdown|kickoff|innings?|at_bat|"
              r"batting|bullpen|goalie|penalty_kick|road_trip|bus_ride)(_|$)", "anchor": "sport:season"},
]
BUCKET_RX = [("night", re.compile(r"(^|_)(late_night|midnight|sleepover|party|bonfire|after_party|sneak_out|night)(_|$)")),
             ("evening", re.compile(r"(^|_)(dinner|evening|dance|movie|date|game_night|homecoming|prom)(_|$)")),
             ("dawn", re.compile(r"(^|_)(morning|breakfast|first_morning|bus|before_school|wake_up)(_|$)")),
             ("lunch", re.compile(r"(^|_)(lunch|cafeteria|lunch_table)(_|$)")),
             ("after_school", re.compile(r"(^|_)(practice|game|tryouts?|scrimmage|locker_room|film|weights|after_school)(_|$)")),
             ("classes", re.compile(r"(^|_)(class|hallway|quiz|teacher|homeroom|study_hall|lab)(_|$)"))]


def _h(*parts) -> int:
    return zlib.crc32(":".join(str(p) for p in parts).encode())


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")


# ---------------------------------------------------------------------------------------- state

def control(w) -> dict:
    from . import moments
    c = moments.control(w)
    c.setdefault("pacing", DEFAULT_PROFILE)
    c.setdefault("auto_scenes", False)
    c.setdefault("binge", False)  # Episodes back to back: the Story tab is just the next scene, with your life in between
    return c


def profile(w) -> dict:
    """The pacing in effect: the chosen profile with any Lab overrides on top."""
    name = control(w).get("pacing") or DEFAULT_PROFILE
    p = dict(PROFILES.get(name) or PROFILES[DEFAULT_PROFILE])
    p["name"] = name if name in PROFILES else DEFAULT_PROFILE
    for k, v in (w.meta.get("pacing_overrides") or {}).items():
        if k in OVERRIDABLE:
            p[k] = tuple(v) if isinstance(v, list) else v
    p.setdefault("aging_days", AGING_DAYS)
    return p


def queue(w) -> dict:
    q = w.meta.setdefault("scene_queue", {})
    q.setdefault("items", [])
    q.setdefault("day", None)
    q.setdefault("presented", 0)
    q.setdefault("target", 0)
    q.setdefault("rolled", {})
    return q


def done_map(w) -> dict:
    return w.meta.setdefault("scenes_done", {})


def seen_map(w) -> dict:
    return w.meta.setdefault("scenes_seen", {})


def log(w) -> dict:
    return w.meta.setdefault("scene_log", {})


def _note(w, sid, status, reason=None, detail=None):
    e = log(w).setdefault(sid, {})
    e.update({"status": status, "day": w.day})
    if reason:
        e["reason"] = reason
        e["detail"] = detail
    else:
        e.pop("reason", None)
        e.pop("detail", None)


def migrate(sim):
    """Saves from before the scheduler: scenes that already played count as resolved (nothing skipped fires now), the old
    last-scene days carry over, and what the old spacing rules were holding back is flagged for the Lab."""
    w = sim.w
    if w.meta.get("scheduler_version", 0) >= VERSION:
        return
    done = done_map(w)
    pending_roots = {_root(sim, m["kind"]) for m in w.meta.get("moments", []) if m["status"] == "pending"}
    for sid, days in seen_map(w).items():
        if days and sid not in done and sid not in pending_roots:
            done[sid] = list(days)
    w.meta["scheduler_version"] = VERSION
    if w.meta.get("protagonist") in w.chars and w.meta.get("story") and seen_map(w):  # an old save with progress
        try:
            ready = [r["sid"] for r in rows(sim) if r["state"] == "eligible"]
        except Exception:  # noqa: BLE001  diagnostics never block loading a save
            ready = []
        w.meta["scheduler_migrated"] = {"day": w.day, "newly_eligible": ready[:200]}


# ---------------------------------------------------------------------------------------- the catalog

@functools.lru_cache(maxsize=16384)
def _sport_counts(words: str) -> tuple:
    """How often a scene's words name each sport ((sport, count), ...): counted once per text, not every rebuild."""
    from . import dialogue
    return tuple((s, len(re.findall(rx, words))) for s, rx in dialogue.SPORT_WORDS.items())


_cat_cache: dict = {}


def _root(sim, kind) -> str:
    return (sim.cat.moments.get(kind) or {}).get("beat_of") or kind


def game_reqs(sc, info) -> list:
    """A scene's requirements, with the result its words take for granted (if it isn't tagged)."""
    req = list((sc.get("when") or {}).get("requires") or [])
    if (info or {}).get("assumes"):
        req.append(info["assumes"])
    return req


def game_twins(scenes, chapters, info=None) -> dict:
    """Chapters that are the two ways one game went: side by side in a storyline, one [if we won] and the other [if we
    lost] (or played great / badly, started / benched). Whichever matches the game plays; the other retires."""
    from .gameplay import OTHER_WAY
    out: dict = {}
    for pk, sids in chapters.items():
        for a, b in zip(sids, sids[1:]):
            ra = set(game_reqs(scenes[a], (info or {}).get(a)))
            rb = set(game_reqs(scenes[b], (info or {}).get(b)))
            if any(OTHER_WAY.get(r) in rb for r in ra):
                out.setdefault(a, []).append(b)
                out.setdefault(b, []).append(a)
    return out


def catalog(sim) -> dict:
    """Every storyline scene with what the scheduler needs: its pack and chapter order, who depends on it, importance,
    season window and time-of-day bucket. Built once per set of packs."""
    from . import dialogue
    m = dialogue.merged()
    key = (id(m), id(sim.cat.moments), _settings_key())
    if _cat_cache.get("key") == key:
        return _cat_cache["cat"]
    st = dialogue._state()
    over_imp = st.get("importance") or {}
    over_win = st.get("scene_windows") or {}
    rules = season_rules()
    scenes = {sid: mm["scene"] for sid, mm in sim.cat.moments.items() if mm.get("scene")}
    by_pack: dict = {}
    for sid, sc in scenes.items():
        by_pack.setdefault(sc.get("pack"), []).append((sc.get("order", 0), sid))
    chapters = {pk: [sid for _, sid in sorted(v)] for pk, v in by_pack.items()}
    ordered = {pk for pk in chapters if dialogue.in_order(pk)}
    deps: dict = {}
    for sid, sc in scenes.items():
        after = (sc.get("when") or {}).get("after") or []
        for a in (after if isinstance(after, list) else [after]):
            deps.setdefault(a, []).append(sid)
    slot_sport = {}
    for name, d in (m.get("cast") or {}).items():
        sp = (d.get("spec") or {}).get("sport")
        for pk in d.get("packs") or []:
            if sp:
                slot_sport.setdefault(pk, sp)
    pack_sport = {}
    info = {}
    for pk, sids in chapters.items():
        counts: dict = {}
        for sid in sids:
            mm = sim.cat.moments[sid]
            words = f"{mm.get('title', '')} {mm.get('text', '') if isinstance(mm.get('text'), str) else ''}".lower()
            for s, k in _sport_counts(words):
                counts[s] = counts.get(s, 0) + k
        best = max(counts, key=lambda s: counts[s]) if counts and max(counts.values()) >= 3 else None
        pack_sport[pk] = slot_sport.get(pk) or best
    for sid, sc in scenes.items():
        mm = sim.cat.moments[sid]
        title = mm.get("title", "")
        text = mm.get("text") if isinstance(mm.get("text"), str) else " ".join(mm.get("text") or [])
        key_s = _norm(f"{sid} {title}")
        when = sc.get("when") or {}
        own = dict(_sport_counts(f"{title} {text}".lower()))
        sport = max(own, key=lambda s: own[s]) if own and max(own.values()) >= 2 else pack_sport.get(sc.get("pack"))
        imp = over_imp.get(sid) or when.get("importance")
        if imp not in IMPORTANCE:
            imp = "finale" if FINALE_RX.search(key_s) else "major" if MAJOR_RX.search(key_s) else "ambient" if AMBIENT_RX.search(key_s) else "regular"
        window, rule = None, None
        if sid in over_win:
            window, rule = (list(over_win[sid]) or None), "your override"
        elif not (when.get("months") or when.get("dates") or when.get("not_before") or when.get("not_after")):
            ys = _years(when)
            college = bool(ys) and min(ys) >= 13
            for r in rules:
                if not re.search(r["match"], key_s) or (r.get("also") and not re.search(r["also"], key_s)):
                    continue
                win = rule_window(sim, r, sport, college)
                if not win:
                    continue
                window, rule = win, r.get("label") or r["id"]
                break
        bucket = None
        req = set(when.get("requires") or [])
        for b, rx in BUCKET_RX:
            if rx.search(key_s):
                bucket = b
                break
        if "late_night" in req:
            bucket = "night"
        info[sid] = {"pack": sc.get("pack"), "importance": imp, "window": window, "window_rule": rule, "bucket": bucket, "sport": sport,
                     "title": title}
        if not set(when.get("requires") or []) & GAME_REQS.keys():  # untagged: the result its words take for granted
            from .gameplay import assumed_result
            a = assumed_result(title, text or "", sporty=bool(sport))
            if a:
                info[sid]["assumes"] = a
    cat = {"scenes": scenes, "chapters": chapters, "ordered": ordered, "deps": deps, "info": info,
           "pos": {sid: i for pk, sids in chapters.items() for i, sid in enumerate(sids)}, "twins": game_twins(scenes, chapters, info)}
    _cat_cache.update({"key": key, "cat": cat})
    return cat


def _settings_key():
    from . import dialogue
    st = dialogue._state()
    return (repr(st.get("importance")), repr(st.get("scene_windows")), repr(st.get("season_map")), repr(st.get("order")))


def _md_shift(md, days) -> list:
    d = calm.date_of(calm.md_to_day(0, tuple(md)) + days)
    return [d.month, d.day]


def _sport_dates(sim, sport, college=False):
    """(tryout, season start, season end) month-days for a sport at the school (or the college)."""
    if college:
        from .college import COLLEGE_TEAMS
        t = COLLEGE_TEAMS.get(sport)
        return (t["tryout"], t["season"]["start"], t["season"]["end"]) if t else None
    for g in sim.cat.world["groups"]:
        if g.get("kind") == "team" and g.get("skill") == sport and g.get("school", "hchs") == "hchs":
            return g["tryout"], g["season"]["start"], g["season"]["end"]
    return None


def rule_window(sim, r, sport=None, college=False):
    """A season-map rule's window for this school's calendar: a list of months, or {"from": [m, d], "to": [m, d]}."""
    if r.get("months"):
        return list(r["months"])
    if r.get("from") and r.get("to"):
        return {"from": list(r["from"]), "to": list(r["to"])}
    a = r.get("anchor") or ""
    cal = sim.cat.world["calendar"]
    b, af = int(r.get("before", 0)), int(r.get("after", 0))
    if a == "school_start":
        md = cal["school_year_start"]
        return {"from": _md_shift(md, -b), "to": _md_shift(md, af)}
    if a.startswith("event:"):
        ev = next((e for e in cal["events"] if e["id"] == a[6:]), None)
        return {"from": _md_shift(ev["date"], -b), "to": _md_shift(ev["date"], af)} if ev else None
    if a.startswith("break:"):
        br = next((x for x in cal["breaks"] if x["name"] == a[6:]), None)
        return {"from": _md_shift(br["from"], -b), "to": _md_shift(br["to"], af)} if br else None
    if a.startswith("sport:"):
        if not sport:
            return None
        dates = _sport_dates(sim, sport, college)
        if not dates:
            return None
        tryout, start, end = dates
        phase = a[6:]
        if phase == "start":
            return {"from": _md_shift(tryout, -2), "to": _md_shift(tryout, 14)}
        if phase == "early":
            return {"from": list(tryout), "to": _md_shift(tryout, 35)}
        if phase == "season":
            return {"from": list(start), "to": list(end)}
        if phase == "end":
            b2, a2 = (r.get("before", 21), r.get("after", 0))
            return {"from": _md_shift(end, -int(b2)), "to": _md_shift(end, int(a2))}
    return None


def window_text(win) -> str:
    if not win:
        return "any time"
    if isinstance(win, dict):
        f, t = win["from"], win["to"]
        return f"{MONTH_NAMES[f[0]]} {f[1]} to {MONTH_NAMES[t[0]]} {t[1]}"
    return ", ".join(MONTH_NAMES[m] for m in win)


MONTH_NAMES = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def season_rules() -> list:
    """The season map: broad default windows for scenes that don't say when (Lab-editable; your edits replace a rule by id,
    and a rule set to "off" is skipped)."""
    from . import dialogue
    over = {r["id"]: r for r in (dialogue._state().get("season_map") or []) if isinstance(r, dict) and r.get("id")}
    out = []
    for r in SEASON_RULES:
        r2 = dict(r, **over.get(r["id"], {}))
        if not r2.get("off"):
            out.append(r2)
    out += [r for k, r in over.items() if k not in {x["id"] for x in SEASON_RULES} and not r.get("off") and r.get("match")]
    return out


# ---------------------------------------------------------------------------------------- the gate

_DLG = None


def _dlg():
    """The dialogue module (imported once: the scheduler's hot paths run millions of times)."""
    global _DLG
    if _DLG is None:
        from . import dialogue as d
        _DLG = d
    return _DLG


def _years(when) -> list:
    ys = when.get("years") or []
    Y = _dlg().YEARS
    return [g for y in (ys if isinstance(ys, list) else [ys]) for g in Y.get(y, ())]


def _md(s) -> tuple | None:
    try:
        mm, dd = str(s).split("-")
        return int(mm), int(dd)
    except Exception:  # noqa: BLE001
        return None


def _in_window(d, nb, na) -> bool:
    """not_before / not_after as month-day inside the school year (Sept 1 to Aug 31)."""
    def sy(md):  # position in the school year: Sept = 0
        return ((md[0] - 9) % 12) * 31 + md[1]
    x = sy((d.month, d.day))
    if nb and na and sy(nb) > sy(na):  # a window across the summer (late August into September)
        return x >= sy(nb) or x <= sy(na)
    if nb and x < sy(nb):
        return False
    if na and x > sy(na):
        return False
    return True


def calendar_ok(sim, sid, when, info, day) -> tuple | None:
    """Today's date against the scene's dates, months, weekdays, window and season-map window."""
    WEEKDAYS = _dlg().WEEKDAYS
    d = calm.date_of(day)
    if when.get("dates") and not calm.date_matches(day, when["dates"], sim.cat.world["calendar"]):
        return ("wrong_date", ", ".join(when["dates"][:3]))
    win = (info or {}).get("window")
    months = when.get("months") or (win if isinstance(win, list) else None)
    if months and d.month not in months:
        return ("wrong_season", months)
    if isinstance(win, dict) and not when.get("months") and not _in_window(d, tuple(win["from"]), tuple(win["to"])):
        return ("wrong_season", window_text(win))
    if when.get("weekdays") and WEEKDAYS[d.weekday()] not in when["weekdays"]:
        return ("wrong_weekday", when["weekdays"])
    nb, na = _md(when.get("not_before")), _md(when.get("not_after"))
    if (nb or na) and not _in_window(d, nb, na):
        return ("wrong_season", f"{when.get('not_before', '')} to {when.get('not_after', '')}")
    return None


def _done_or_skipped(sim, me, a, cat, depth=0) -> str:
    """'done', 'skipped' (it can't happen anymore under the existing rules: its school years are over) or 'waiting' /
    'unreachable'."""
    w = sim.w
    if a in done_map(w):
        return "done"
    sc = cat["scenes"].get(a)
    if sc is None:
        return "skipped"  # not in any loaded pack: nothing to wait for
    when = sc.get("when") or {}
    if when.get("skip"):
        return "skipped"  # retired by a season plan or an addition
    grades = _years(when)
    if grades and max(grades) < (me.grade or 0):
        return "skipped"
    if depth < 6 and permanent(sim, me, a, cat, depth + 1):
        return "unreachable"
    return "waiting"


def permanent(sim, me, sid, cat, depth=0) -> str | None:
    """Why a scene can never happen in this run, or None."""
    w = sim.w
    sc = cat["scenes"].get(sid)
    if sc is None:
        return None
    when = sc.get("when") or {}
    mem = w.meta.get("remembered", {})
    if sid in done_map(w) and when.get("once", True):
        return "played"
    if when.get("skip"):
        return "skipped_by_plan"
    for k in when.get("not_remembered") or []:  # the most telling reason first: a branch beats "its years are over"
        if k in mem:
            return "exclusive_branch"
    for k in when.get("remembered") or []:
        if k not in mem and not _fact_sources(sim).get(k):
            return "fact_never_set"  # no choice in any storyline remembers it: it can never come
        if k not in mem and _fact_closed(sim, me, k, cat, depth):
            return "branch_closed"
    for a in _after(when):
        if depth < 6 and a not in done_map(w) and _same_line(cat, a, sid) \
                and permanent(sim, me, a, cat, depth + 1) in ("exclusive_branch", "branch_closed", "after_unreachable"):
            return "after_unreachable"
    grades = _years(when)
    if grades and max(grades) < (me.grade or 0):
        return "year_passed"
    for a in _after(when):
        if depth < 6 and _same_line(cat, a, sid) and _done_or_skipped(sim, me, a, cat, depth + 1) == "unreachable":
            return "after_unreachable"
    return None


def _same_line(cat, a, sid) -> bool:
    """Both scenes are in the same storyline (pack). An after-link inside a storyline is part of its branches; one across
    storylines (a season plan weaving them) only orders them."""
    sa, sb = cat["scenes"].get(a), cat["scenes"].get(sid)
    return bool(sa and sb and sa.get("pack") == sb.get("pack"))


def _fact_closed(sim, me, fact, cat, depth) -> bool:
    """A fact only a choice can set, where every scene with that choice has already gone by without it."""
    srcs = _fact_sources(sim).get(fact)
    if not srcs:
        return False
    w = sim.w
    for s in srcs:
        root = _root(sim, s)
        if root not in done_map(w) and (depth >= 6 or not permanent(sim, me, root, cat, depth + 1)):
            return False
    return True


_fact_cache: dict = {}


def _fact_sources(sim) -> dict:
    key = id(sim.cat.moments)
    if _fact_cache.get("key") == key:
        return _fact_cache["v"]
    out: dict = {}
    for kind, mm in sim.cat.moments.items():
        for ch in mm.get("choices") or []:
            for op in ch.get("ops") or []:
                if op and op[0] == "remember" and len(op) > 1:
                    out.setdefault(op[1], set()).add(kind)
    _fact_cache.update({"key": key, "v": out})
    return out


def _after(when) -> list:
    a = when.get("after") or []
    return a if isinstance(a, list) else [a]


def gate(sim, me, sid, cat, day=None, prof=None) -> tuple | None:
    """None if the scene is ready today; else (reason, detail). Chance and pacing aren't part of this."""
    dialogue = _dlg()
    w = sim.w
    day = w.day if day is None else day
    sc = cat["scenes"][sid]
    when = sc.get("when") or {}
    info = cat["info"].get(sid) or {}
    done, seen = done_map(w), seen_map(w)
    if sid in seen and sid not in done:
        return ("in_progress", None)
    if when.get("skip"):
        return ("skipped_by_plan", None)
    if sid in done:
        if when.get("once", True):
            return ("played", done[sid][-1])
        cd = when.get("cooldown_days")
        if cd and day - done[sid][-1] < cd:
            return ("cooldown", done[sid][-1] + cd)
    grades = _years(when)
    if grades and (me.grade or 0) not in grades:
        return ("year_passed", None) if max(grades) < (me.grade or 0) else ("too_early", "school year")
    mem = w.meta.get("remembered", {})
    for k in when.get("not_remembered") or []:
        if k in mem:
            return ("exclusive_branch", k)
    for k in when.get("remembered") or []:
        if k not in mem:
            if not _fact_sources(sim).get(k):
                return ("fact_never_set", k)
            return ("branch_closed", k) if _fact_closed(sim, me, k, cat, 0) else ("missing_fact", k)
    after = _after(when)
    last_pre = None
    for a in after:
        st = _done_or_skipped(sim, me, a, cat)
        if st == "unreachable" and not _same_line(cat, a, sid):
            continue  # another storyline's scene that can't happen anymore: "after" orders the story, it doesn't cut it off
        if st == "unreachable":
            return ("after_unreachable", a)
        if st == "waiting":
            return ("waiting_for_scene", a)
        if st == "done":
            last_pre = max(last_pre or -10**9, done_map(w)[a][-1])
    for a in holds(w).get(sid) or []:  # episodes you moved ahead of this one
        if a in cat["scenes"] and _done_or_skipped(sim, me, a, cat) == "waiting":
            return ("your_order", a)
    pk = sc.get("pack")
    gap = when.get("gap_days")
    if pk in cat["ordered"]:
        lst = cat["chapters"][pk]
        prev = [done[s][-1] for s in lst[: cat["pos"][sid]] if s in done]
        if prev:
            g = gap if gap is not None else (prof or profile(w))["chapter_gap"]
            if g and day - max(prev) < g:
                return ("too_early", f"day {max(prev) + g}")
    if gap and last_pre is not None and day - last_pre < gap:
        return ("too_early", f"day {last_pre + gap}")
    twin = next((t for t in (cat.get("twins") or {}).get(sid, []) if t in done), None)
    if twin:
        return ("exclusive_branch", twin)  # the game went the other way, and that scene happened
    for r in game_reqs(sc, cat["info"].get(sid)):
        if r in GAME_REQS:
            g_ = gameplay_last(sim, me)
            used = g_ is not None and any(  # another chapter of this storyline already told this game
                x != sid and x in done and done[x][-1] >= g_["day"] and set(game_reqs(cat["scenes"][x], cat["info"].get(x))) & GAME_REQS.keys()
                for x in cat["chapters"].get(sc.get("pack"), []))
            if g_ is None or used:
                if game_coming(sim, me, day):
                    return ("waiting_for_game", r)  # about your next game: it waits for it
                return ("missing_requirement", r)
        if not dialogue._requirement(sim, me, r):
            return ("missing_requirement", r)
    for f, rng in (when.get("me") or {}).items():
        v = me.mood if f == "mood" else me.gpa if f == "gpa" else me.needs.get(f, 50)
        if not dialogue._in(v, rng):
            return ("mood", f)
    cal = calendar_ok(sim, sid, when, info, day)
    if cal:
        if cal[0] in ("wrong_season", "wrong_date") and grades and max(grades) == (me.grade or 0) and _window_over(sim, when, info, day):
            return ("window_passed", cal[1])  # its day (or season) has gone by in its last school year: it can't come now
        return cal
    return None


_LAST_OK: dict = {}
_EMPTY: dict = {}


def _window_over(sim, when, info, day) -> bool:
    """Its season window this school year has gone by (and its years end this year). The calendar part of a scene only
    depends on the date, so the last day it fits in each school year is worked out once and kept."""
    when, info = when or _EMPTY, info or _EMPTY  # (an empty {} made on the fly isn't the same object twice)
    sy = calm.school_year_of(day)
    key = (id(when), id(info), sy)
    hit = _LAST_OK.get(key)
    if hit is None or hit[0] is not when or hit[1] is not info:
        if len(_LAST_OK) > 60000:
            _LAST_OK.clear()
        first, end = calm.md_to_day(sy, (9, 1)), calm.md_to_day(sy, (8, 31))  # this school year
        last = next((x for x in range(end, first - 1, -1) if calendar_ok(sim, None, when, info, x) is None), None)
        hit = _LAST_OK[key] = (when, info, last)
    return hit[2] is None or hit[2] < day


# chapter order: which reasons step over a chapter (the story moves on) and which hold the storyline (it waits)
STEP_OVER = {"too_early_year", "year_passed", "missing_requirement", "missing_fact", "exclusive_branch", "waiting_for_scene",
             "after_unreachable", "mood", "played", "branch_closed", "missing_cast", "window_passed", "fact_never_set"}


def castable(sim, me, sid, cat) -> tuple | None:
    """Is there someone in your story to play this scene's people right now (checked without binding anyone)? None, or
    ("missing_cast", who)."""
    from . import dialogue
    w = sim.w
    sc = cat["scenes"][sid]
    who = sc.get("who")
    when = sc.get("when") or {}

    def feels(o):
        return (all(dialogue._in(dialogue._rel(w, me.id, o, f), r) for f, r in (when.get("you_feel") or {}).items())
                and all(dialogue._in(dialogue._rel(w, o, me.id, f), r) for f, r in (when.get("they_feel") or {}).items()))
    if who and who.startswith("cast:"):
        name = who[5:]
        cid = dialogue.bound(sim, name)
        if cid:
            if not feels(cid):
                return ("missing_cast", f"{name}: how you feel about each other isn't in its range")
        else:
            spec = dialogue.slot_spec(name)
            if not spec or not [o for o in dialogue.slot_candidates(sim, me, spec) if feels(o)]:
                return ("missing_cast", f"nobody fits {name}" + (f" ({dialogue.slot_label(spec)})" if spec else ""))
    elif who:
        if not [o for o in dialogue.candidates(sim, me, who) if feels(o)]:
            return ("missing_cast", f"no {who.replace('_', ' ')} in your story right now")
    needs = set(sc.get("needs") or [])
    if needs & {"partner", "partner_first"} and me.flags.get("partner") not in w.chars:
        return ("missing_cast", "you're not dating anyone")
    return None


def next_chapter(sim, me, pk, cat, day=None, prof=None):
    """A storyline played in order: (its next chapter, why it can't happen today or None). The existing rule: a chapter that
    can't happen yet for its year, facts or prerequisites is stepped over; one waiting on the calendar or a gap holds."""
    w = sim.w
    done, seen = done_map(w), seen_map(w)
    for sid in cat["chapters"][pk]:
        if sid in seen and sid not in done:
            return sid, ("in_progress", None)
        if sid in seen:
            continue
        g = gate(sim, me, sid, cat, day, prof) or castable(sim, me, sid, cat)
        if g is None:
            return sid, None
        code = "too_early_year" if g == ("too_early", "school year") else g[0]
        if code in STEP_OVER:
            continue
        return sid, g
    return None, None


# ---------------------------------------------------------------------------------------- planning a day

def _school_day(sim, day) -> bool:
    return calm.is_school_day(day, sim.cat.world["calendar"])


def _target(w, prof, sim, day) -> int | None:
    rng_ = prof["school"] if _school_day(sim, day) else prof["weekend"]
    if rng_ is None:
        return None
    lo, hi = rng_
    return lo + (_h(w.seed, "target", day) % (hi - lo + 1)) if hi > lo else hi


def _roll(w, sid, day) -> float:
    return (_h(w.seed, "scene-roll", sid, day) % 100000) / 100000


def _free_scenes(cat) -> list:
    """The scenes that aren't storyline chapters, with their years, months and dates ready for a quick check (kept with
    the catalog: built once per set of packs)."""
    pre = cat.get("_free")
    if pre is None:
        pre = []
        for sid, sc in sorted(cat["scenes"].items()):
            if sc.get("pack") in cat["ordered"]:
                continue
            when = sc.get("when") or {}
            win = (cat["info"].get(sid) or {}).get("window")
            months = when.get("months") or (win if isinstance(win, list) else None)
            dates = when.get("dates") or ()
            plain = all(len(x) == 5 and x[2] == "-" for x in dates)  # (named days like Thanksgiving move: the gate checks those)
            pre.append((sid, sc, frozenset(_years(when)), frozenset(months or ()), frozenset(dates if plain else ())))
        cat["_free"] = pre
    return pre


def candidates(sim, me, cat, prof, day=None) -> list:
    """Everything ready today, best first: deadlines, then storyline chapters (the one that's waited longest first, across
    storylines), then other scenes. Chance applies here (deterministic per seed, scene and day)."""
    from . import dialogue
    w = sim.w
    day = w.day if day is None else day
    weights = w.meta.get("story_weights") or {}
    done = done_map(w)
    out = []
    for pk in sorted(cat["ordered"]):
        sid, why = next_chapter(sim, me, pk, cat, day, prof)
        if sid is None or why is not None:
            continue
        when = cat["scenes"][sid].get("when") or {}
        ch = when.get("chance", prof["chapter_chance"])
        if _roll(w, sid, day) >= ch:
            continue
        prev = [done[s][-1] for s in cat["chapters"][pk] if s in done]
        out.append({"sid": sid, "kind": "chapter", "pack": pk, "waited": day - max(prev) if prev else 10**4,
                    "weight": float(weights.get(pk, 1))})
    d = calm.date_of(day)
    md, grade = f"{d.month:02d}-{d.day:02d}", me.grade or 0
    for sid, sc, grades, months, dates in _free_scenes(cat):
        if (grades and grade not in grades) or (dates and md not in dates) or (months and d.month not in months):
            continue  # (the gate would say no too: it's not this scene's year, month or day)
        if gate(sim, me, sid, cat, day, prof) is not None:
            continue
        when = sc.get("when") or {}
        ch = when.get("chance", 1.0 if when.get("dates") else prof["free_chance"])
        if _roll(w, sid, day) >= ch or castable(sim, me, sid, cat):
            continue
        out.append({"sid": sid, "kind": "free", "pack": sc.get("pack"), "waited": 0, "weight": float(weights.get(sc.get("pack"), 1))})
    for c in out:
        when = cat["scenes"][c["sid"]].get("when") or {}
        c["importance"] = cat["info"][c["sid"]]["importance"]
        c["deadline"] = deadline(sim, me, c["sid"], cat, day) if (when.get("dates") or when.get("months") or cat["info"][c["sid"]]["window"]
                                                              or when.get("not_after") or _years(when)) else None
        c["due"] = c["deadline"] is not None and c["deadline"] <= day
    return out


def deadline(sim, me, sid, cat, day) -> int | None:
    """The last day this scene can still happen in its current window (dates, months, season window, school years)."""
    sc = cat["scenes"][sid]
    when = sc.get("when") or {}
    info = cat["info"].get(sid) or {}
    grades = _years(when)
    end = calm.md_to_day(calm.school_year_of(day), (8, 31))  # the last day of this school year
    if grades and (me.grade or 0) + 1 in grades:
        end = calm.md_to_day(calm.school_year_of(day) + 1, (8, 31))
    if not (when.get("dates") or when.get("months") or info.get("window") or when.get("not_after")):
        return end if grades else None
    last = None
    for x in range(day, min(end, day + 400) + 1):
        if calendar_ok(sim, sid, when, info, x) is None:
            last = x
        elif last is not None:
            break
    return last


def _order(cands, prof, day=None) -> list:
    """Due today first, then anything whose window closes within two weeks (soonest first: overdue pressure, so a year's
    leftovers don't pile onto its last day), then chapters across storylines (longest wait, then weight), with another
    scene after every two."""
    due = [c for c in cands if c["due"]]
    rest = [c for c in cands if not c["due"]]
    if day is not None:
        soon = sorted((c for c in rest if c["deadline"] is not None and c["deadline"] - day <= 14), key=lambda c: (c["deadline"], c["sid"]))
        rest = [c for c in rest if c not in soon]
        due = sorted(due, key=lambda c: (c["deadline"], c["sid"])) + soon
        out = list(due)
        chapters = sorted((c for c in rest if c["kind"] == "chapter"), key=lambda c: (-c["weight"], -c["waited"], c["pack"] or "", c["sid"]))
        free = sorted((c for c in rest if c["kind"] != "chapter"), key=lambda c: (-c["weight"], c["sid"]))
        while chapters or free:
            out += chapters[:2]
            chapters = chapters[2:]
            if free:
                out.append(free.pop(0))
        return out
    chapters = sorted((c for c in rest if c["kind"] == "chapter"), key=lambda c: (-c["weight"], -c["waited"], c["pack"] or "", c["sid"]))
    free = sorted((c for c in rest if c["kind"] != "chapter"), key=lambda c: (-c["weight"], c["sid"]))
    out = sorted(due, key=lambda c: (c["deadline"], c["sid"]))
    while chapters or free:
        out += chapters[:2]
        chapters = chapters[2:]
        if free:
            out.append(free.pop(0))
    return out


def _major_ok(sim, c, prof, cat) -> bool:
    """About one big turning point a week, unless this one follows straight from the last or its window is closing."""
    w = sim.w
    if c["importance"] not in ("major", "finale") or not prof.get("major_week") or c["due"]:
        return True
    recent = [d for d in w.meta.get("scene_majors", []) if w.day - d < 7]
    if len(recent) < prof["major_week"]:
        return True
    after = _after(cat["scenes"][c["sid"]].get("when") or {})
    done = done_map(w)
    return any(a in done and done[a][-1] >= w.day - 1 and cat["info"].get(a, {}).get("importance") in ("major", "finale") for a in after)


def _phases(sim, day) -> list:
    return calm.phases_for(day, sim.cat.world["calendar"])


def _assign_phases(sim, items, cat, day, start_ix=0):
    """Spread the day's scenes across its parts, in time order: a scene that says when (lunch, a party at night) goes then."""
    phs = _phases(sim, day)
    usable = [p for p in phs[start_ix:] if p in PHASE_BUCKETS] or [phs[-1]]
    spread = [p for p in usable if p in ("dawn", "lunch", "after_school", "day", "evening")] or usable
    for i, it in enumerate(items):
        b = cat["info"].get(it["sid"], {}).get("bucket")
        it["phase"] = b if b in usable else spread[i % len(spread)]
    items.sort(key=lambda it: phs.index(it["phase"]) if it["phase"] in phs else 99)


def plan_day(sim):
    """Each morning: plan today's scenes, keep anything planned that nobody's got to yet (for a few days), let deadlines
    lapse visibly, and present the first one."""
    w = sim.w
    me = _me(sim)
    if me is None:
        return
    from . import dialogue
    for name, d in dialogue.merged()["cast"].items():  # slots that bind at the start of the story bind now
        if d["spec"].get("bind") == "start" and name not in w.meta.get("cast_slots", {}):
            dialogue.bind(sim, me, name)
    cat = catalog(sim)
    if not cat["scenes"]:
        return
    prof = profile(w)
    nxt = calm.date_of(w.day + 1)
    if nxt.month == 9 and nxt.day == 1:
        year_end(sim, me, cat, prof)
    q = queue(w)
    seen_q = set()
    keep = []
    for it in q["items"]:  # yesterday's leftovers
        if it["sid"] in seen_q or it["sid"] in seen_map(w):
            continue
        g = gate(sim, me, it["sid"], cat, w.day, prof)
        if g is not None and g[0] in PERMANENT | {"wrong_date", "wrong_season", "window_passed", "too_early"}:
            status = "expired" if g[0] in ("wrong_date", "wrong_season", "window_passed") else "dropped"
            _note(w, it["sid"], status, "deadline_missed" if status == "expired" else g[0], g[1])
            continue
        if w.day - it.get("queued", w.day) >= prof["aging_days"]:
            _note(w, it["sid"], "returned", "aged_out")
            continue
        it["phase"] = "dawn"
        keep.append(it)
        seen_q.add(it["sid"])
    q.update({"day": w.day, "presented": 0, "items": keep})
    last = max((d[-1] for d in seen_map(w).values() if d), default=-10**9)
    cands = [c for c in candidates(sim, me, cat, prof) if c["sid"] not in seen_q]
    target = _target(w, prof, sim, w.day)
    quiet = prof["global_gap"] and w.day - last < prof["global_gap"]
    picked = []
    for c in _order(cands, prof, w.day):
        if not c["due"]:
            if quiet:
                _note(w, c["sid"], "waiting", "global_gap")
                continue
            if target is not None and len(picked) >= target:
                continue
            if not _major_ok(sim, c, prof, cat):
                _note(w, c["sid"], "waiting", "major_breather")
                continue
            if c["importance"] in ("major", "finale") and any(p["importance"] in ("major", "finale") and not p["due"] for p in picked):
                continue  # one big turn a day at most, outside deadlines
        picked.append({"sid": c["sid"], "queued": w.day, "due": c["due"], "deadline": c["deadline"], "importance": c["importance"],
                       "pack": c["pack"], "kind": c["kind"]})
    _assign_phases(sim, picked, cat, w.day)
    q["items"] += picked
    q["target"] = len(picked) if target is None else target
    for it in picked:
        _note(w, it["sid"], "queued")
    deliver(sim)


def year_end(sim, me, cat, prof):
    """The school year's last day: for every scene this was the last year for that never got to play, note what it was
    still waiting on (nobody fits, an earlier chapter, a fact, a requirement...) so the report can say."""
    w = sim.w
    lg = log(w)
    g9 = me.grade or 0
    heads = {pk: next_chapter(sim, me, pk, cat, w.day, prof)[0] for pk in cat["ordered"]}
    for sid, sc in cat["scenes"].items():
        if sid in seen_map(w):
            continue
        grades = _years(sc.get("when") or {})
        if not grades or max(grades) != g9:
            continue
        why = gate(sim, me, sid, cat, w.day, prof) or castable(sim, me, sid, cat)
        if why is None:
            pk = sc.get("pack")
            if pk in cat["ordered"] and heads.get(pk) not in (None, sid):
                why = ("chapter_order", heads[pk])
            else:
                why = ("never_picked", None)
        lg[sid] = {"status": "missed", "day": w.day, "reason": why[0], "detail": why[1]}


def _me(sim):
    w = sim.w
    pid = w.meta.get("protagonist")
    me = w.chars.get(pid) if pid else None
    if not me or me.status != "active" or "story" not in w.meta:
        return None
    return me


# ---------------------------------------------------------------------------------------- presenting scenes

def deliver(sim, force=False) -> dict | None:
    """Present the next planned scene if nothing else is waiting on the player and its part of the day has come (or now,
    with force: Continue story). One at a time."""
    from . import moments
    w = sim.w
    me = _me(sim)
    if me is None or moments.pending(w):
        return None
    q = queue(w)
    if q.get("day") != w.day and not force:
        return None
    cat = catalog(sim)
    phs = _phases(sim, w.day)
    cur = w.phase if w.phase < len(phs) else len(phs) - 1
    prof = profile(w)
    tries = 0
    held = []
    try:
        while q["items"] and tries < GUARD:
            tries += 1
            it = q["items"][0]
            ix = phs.index(it["phase"]) if it.get("phase") in phs else 0
            if ix > cur and not force:
                return None
            q["items"].pop(0)
            sid = it["sid"]
            if sid not in cat["scenes"] or sid in seen_map(w):
                continue
            g = gate(sim, me, sid, cat, w.day, prof)
            if g is not None and g[0] == "your_order":
                held.append(it)  # it comes after the one you put first
                continue
            if g is not None:
                _note(w, sid, "dropped" if g[0] not in PERMANENT else "unreachable", g[0], g[1])
                continue
            m = _start(sim, me, sid, cat)
            if m is not None:
                q["presented"] = q.get("presented", 0) + 1
                return m
        return None
    finally:
        q["items"] += held


def _start(sim, me, sid, cat):
    from . import dialogue
    w = sim.w
    spec = sim.cat.moments[sid]
    when = spec["scene"].get("when") or {}
    rng = sim.streams.get("scene", w.day, sid)
    ctx = dialogue._context(sim, me, spec["scene"].get("who"), when, rng, pack=spec["scene"].get("pack"),
                            cast_refs=spec["scene"].get("cast_refs"))
    if ctx is None:
        _note(w, sid, "waiting", "missing_cast", spec["scene"].get("who"))
        return None
    if not dialogue._playable(spec, ctx):
        _note(w, sid, "waiting", "not_playable")
        return None
    m = dialogue.fire(sim, sid, ctx)
    if m is not None:
        _note(w, sid, "presented")
    return m


def after_resolve(sim, m):
    """A moment was answered. If it finished a storyline scene (its last beat), the scene counts as resolved now: scenes
    waiting on it are looked at again for today, and the next scene is presented."""
    w = sim.w
    cat = catalog(sim)
    root = _root(sim, m["kind"])
    if root in cat["scenes"]:
        from . import moments
        still = any(_root(sim, x["kind"]) == root for x in moments.pending(w))
        if not still:
            done_map(w).setdefault(root, []).append(w.day)
            _note(w, root, "played")
            if cat["info"][root]["importance"] in ("major", "finale"):
                w.meta.setdefault("scene_majors", []).append(w.day)
                del w.meta["scene_majors"][:-20]
            _chain(sim, root, cat)
    deliver(sim)


def _chain(sim, sid, cat):
    """Scenes that were waiting on this one (and this storyline's next chapter) can come today if they're ready."""
    w = sim.w
    me = _me(sim)
    q = queue(w)
    if me is None or q.get("day") != w.day:
        return
    prof = profile(w)
    target = q.get("target")
    have = {it["sid"] for it in q["items"]}
    room = target is None or prof["name"] == "uncapped" or (q.get("presented", 0) + len(q["items"])) < (target or 0)
    nxt = []
    mine = [y for y, xs in holds(w).items() if sid in xs and y in cat["scenes"]]
    for d in sorted(set(cat["deps"].get(sid, [])) | set(mine)):
        when = cat["scenes"][d].get("when") or {}
        direct = not when.get("gap_days")
        if d in have or d in seen_map(w):
            continue
        pk = cat["scenes"][d].get("pack")
        if pk in cat["ordered"] and next_chapter(sim, me, pk, cat, w.day, prof)[0] != d:
            continue
        if gate(sim, me, d, cat, w.day, prof) is None and (room or (direct and prof.get("chain_past_budget"))):
            nxt.append(d)
    pk = cat["scenes"][sid].get("pack")
    if pk in cat["ordered"] and room:
        c, why = next_chapter(sim, me, pk, cat, w.day, prof)
        if c and why is None and c not in have and c not in nxt:
            when = cat["scenes"][c].get("when") or {}
            if _roll(w, c, w.day) < when.get("chance", prof["chapter_chance"]):
                nxt.append(c)
    cur = _phases(sim, w.day)[min(w.phase, len(_phases(sim, w.day)) - 1)]
    items = [{"sid": d, "queued": w.day, "due": False, "deadline": None, "importance": cat["info"][d]["importance"],
              "pack": cat["scenes"][d].get("pack"), "kind": "chained", "phase": cur} for d in nxt]
    for it in items:
        _note(w, it["sid"], "queued")
    picked = [it for it in q["items"] if it.get("kind") == "yours"]  # the one you picked to play next still goes first
    q["items"] = picked + items + [it for it in q["items"] if it.get("kind") != "yours"]  # then straight from what just happened


# ---------------------------------------------------------------------------------------- your order

def holds(w) -> dict:
    """Episodes you moved: {scene: [scenes it now waits for]}. Your order, on top of the story's own."""
    return w.meta.setdefault("episode_order", {}).setdefault("holds", {})


def _waits_on(sim, cat, x, y, seen=None) -> bool:
    """Does x have to wait for y: through its after links, its storyline's chapter order, or your order?"""
    seen = set() if seen is None else seen
    if x in seen or len(seen) > 400:
        return False
    seen.add(x)
    sc = cat["scenes"].get(x)
    if not sc:
        return False
    pre = list(_after(sc.get("when") or {})) + list(holds(sim.w).get(x) or [])
    pk = sc.get("pack")
    if pk in cat["ordered"] and cat["pos"][x] > 0:
        pre.append(cat["chapters"][pk][cat["pos"][x] - 1])
    return y in pre or any(_waits_on(sim, cat, p, y, seen) for p in pre if p in cat["scenes"])


def move_before(sim, x, y) -> dict:
    """Put episode x ahead of episode y: y waits for x. Moving it back undoes your earlier move instead of stacking."""
    cat = catalog(sim)
    for s in (x, y):
        if s not in cat["scenes"]:
            return {"ok": False, "why": f"'{s}' isn't a scene in your story"}
    if x == y:
        return {"ok": False, "why": "that's the same episode"}
    H = holds(sim.w)
    ix, iy = cat["info"][x], cat["info"][y]
    if y in (H.get(x) or []):
        H[x].remove(y)
        if not H[x]:
            del H[x]
        if not _waits_on(sim, cat, x, y):
            return {"ok": True, "undid": True}
        H.setdefault(x, []).append(y)
    if _waits_on(sim, cat, x, y):
        if ix["pack"] == iy["pack"] and ix["pack"] in cat["ordered"]:
            return {"ok": False, "why": "chapters of one storyline play in order"}
        return {"ok": False, "why": f"“{ix['title']}” follows “{iy['title']}” in the story"}
    if x not in (H.get(y) or []):
        H.setdefault(y, []).append(x)
    return {"ok": True, "undid": False}


def clear_order(w, sid=None):
    """Undo your moves: every one, or just what one episode waits for."""
    H = holds(w)
    if sid is None:
        H.clear()
    else:
        H.pop(sid, None)


WHO_WORDS = {"best_friend": "your best friend", "crush": "your crush", "partner": "your partner", "rival": "your rival",
             "older_sibling": "your older sibling", "younger_sibling": "your younger sibling", "older_brother": "your brother",
             "older_sister": "your sister", "teammate": "a teammate", "coach": "your coach", "friend": "a friend"}


def display_title(sim, sid, cat) -> str:
    """A scene's title for a list, before it happens: names filled in where the story already knows who, else who in words."""
    from . import dialogue
    t = (cat["info"].get(sid) or {}).get("title") or sid
    if "{" not in t:
        return t
    w = sim.w
    me = _me(sim)
    who = cat["scenes"][sid].get("who") or ""
    them = None
    if who.startswith("cast:"):
        cid = dialogue.bound(sim, who[5:])
        them = w.chars[cid].first if cid else None
    if not them and who and me is not None:
        try:
            cands = dialogue.candidates(sim, me, who)
        except Exception:  # an unusual kind of person: say it in words
            cands = []
        them = w.chars[cands[0]].first if len(cands) == 1 else None
    them = them or WHO_WORDS.get(who) or "someone"
    fill = {"them": them, "them_first": them, "me_first": me.first if me else "you", "best_friend": "your best friend",
            "best_friend_first": "your best friend", "sibling": "your sibling", "sibling_first": "your sibling",
            "partner": "your partner", "partner_first": "your partner", "sport": "the game", "pet": "your pet",
            "my_team": "your team", "my_team_record": "", "my_team_star": "their best player", "mlb_champ": "the champs",
            "my_nfl_team": "your team", "my_nba_team": "your team", "my_college": "your school", "nfl_champ": "the champs",
            "nba_champ": "the champs", "cfb_champ": "the champs", "mbb_champ": "the champs", "wbb_champ": "the champs",
            "my_club": "your club", "epl_champ": "the champs", "ucl_champ": "the champs", "ballon_dor": "the best player"}
    s = re.sub(r"\{(\w+)\}", lambda m: fill.get(m.group(1)) or m.group(1).replace("_", " "), t)
    return s[:1].upper() + s[1:]


def ready_now(sim, me, sid, cat) -> tuple | None:
    """None if this scene could start right now (its storyline's turn included); else (reason, detail)."""
    g = gate(sim, me, sid, cat) or castable(sim, me, sid, cat)
    pk = cat["scenes"][sid].get("pack")
    if g is None and pk in cat["ordered"]:
        nxt = next_chapter(sim, me, pk, cat)[0]
        if nxt != sid:
            return ("chapter_order", nxt)
    return g


def play_next(sim, sid) -> dict:
    """This one next, right now, if it can happen today (ahead of today's plan). Otherwise why it can't."""
    w = sim.w
    me = _me(sim)
    cat = catalog(sim)
    if me is None or sid not in cat["scenes"]:
        return {"ok": False, "why": "that isn't a scene in your story"}
    g = ready_now(sim, me, sid, cat)
    if g is not None:
        why = REASON_TEXT.get(g[0], g[0].replace("_", " "))
        if g[0] in ("waiting_for_scene", "your_order", "chapter_order") and g[1] in cat["info"]:
            why += f": “{cat['info'][g[1]]['title']}”"
        elif g[1] and g[0] in ("wrong_season", "too_early"):
            why += f" ({g[1]})"
        return {"ok": False, "why": why}
    q = queue(w)
    if q.get("day") != w.day:
        q.update({"day": w.day, "items": [], "presented": 0})
    q["items"] = [it for it in q["items"] if it["sid"] != sid]
    phs = _phases(sim, w.day)
    q["items"].insert(0, {"sid": sid, "queued": w.day, "due": False, "deadline": None, "importance": cat["info"][sid]["importance"],
                          "pack": cat["info"][sid]["pack"], "kind": "yours", "phase": phs[min(w.phase, len(phs) - 1)]})
    _note(w, sid, "queued", "your_order")
    return {"ok": True}


def upcoming(sim, n: int = 10, max_days: int = 400, watch: str | None = None) -> dict:
    """On a copy (pass one): the next n episodes in the order they'd come, with about when, your character answering.
    Fast: only the calendar and the stories move. With watch, keep going until that one plays (or can't anymore)."""
    from . import moments
    w = sim.w
    control(w)["auto_scenes"] = True
    cat = catalog(sim)
    out, got = [], set()
    start = w.day
    me = _me(sim)

    def drain():
        for _ in range(GUARD * 3):
            pend = moments.pending(w)
            if not pend:
                if continue_planned(sim) is None:
                    return
                continue
            m = pend[0]
            root = _root(sim, m["kind"])
            if root in cat["scenes"] and root not in got and m["kind"] == root:
                got.add(root)
                out.append({"sid": root, "day": w.day})
            moments.resolve(sim, m["id"], None)

    def done():
        if len(out) < n:
            return False
        if not watch or watch in got:
            return True
        return bool(me and (w.day - start) % 7 == 0 and permanent(sim, me, watch, cat))

    drain()
    while not done() and w.day < start + max_days:
        _light_day(sim)
        plan_day(sim)
        drain()
    res = {"list": out[:n], "start": start}
    if watch:
        hit = next((x for x in out if x["sid"] == watch), None)
        res["watch"] = {"sid": watch, "day": hit["day"] if hit else None}
    return res


def continue_story(sim) -> dict | None:
    """Continue story: the next scene now, without moving the calendar. When today's plan is used up, the next one that's
    ready (past the day's target: the target is only a default)."""
    from . import moments
    w = sim.w
    me = _me(sim)
    if me is None:
        return None
    pend = moments.pending(w)
    if pend:
        return pend[0]
    q = queue(w)
    if q.get("day") != w.day:
        q.update({"day": w.day, "items": [], "presented": 0})
    m = deliver(sim, force=True)
    if m is not None:
        return m
    cat = catalog(sim)
    prof = profile(w)
    for c in _order(candidates(sim, me, cat, prof), prof, w.day):
        if not _major_ok(sim, c, prof, cat):
            continue
        q["items"].append({"sid": c["sid"], "queued": w.day, "due": c["due"], "deadline": c["deadline"], "importance": c["importance"],
                           "pack": c["pack"], "kind": c["kind"], "phase": "dawn"})
        m = deliver(sim, force=True)
        if m is not None:
            return m
    return None


def finish_today(sim, auto=True, limit=GUARD) -> list:
    """Lab: present and (with auto) let your character answer every scene left today. Returns the scene ids played."""
    from . import moments
    w = sim.w
    out = []
    for _ in range(limit):
        pend = moments.pending(w)
        if pend:
            if not auto:
                break
            moments.resolve(sim, pend[0]["id"], None)
            continue
        m = deliver(sim, force=True)
        if m is None:
            break
        out.append(_root(sim, m["kind"]))
    return out


def auto_ok(w, m) -> bool:
    """May the game answer this moment for the player? Not a storyline scene, unless they turned on Let my character decide."""
    return bool(control(w).get("auto_scenes")) or not _is_story(m.get("kind"))


def ahead(sim) -> dict:
    """Can any storyline scene still come? {"open": how many could (now or later), "why": the most common reason the
    rest are held up, in plain words}. Next episode checks this before living days forward looking for one."""
    from collections import Counter
    try:
        rs = rows(sim)
    except Exception:  # noqa: BLE001
        return {"open": 1, "why": None}
    live = [r for r in rs if r.get("state") in ("eligible", "queued", "presented", "waiting")]
    held = Counter(r.get("why") for r in rs if r.get("state") in ("waiting", "unreachable", "expired") and r.get("why"))
    top = held.most_common(1)
    return {"open": len(live), "ready": sum(1 for r in live if r.get("state") in ("eligible", "queued", "presented")),
            "why": (f"{top[0][1]} scene{'s' if top[0][1] != 1 else ''}: {top[0][0]}" if top else None)}


def is_episode(sim, kind) -> bool:
    """What Next episode stops for: a storyline scene (any beat of one), or the end of the story."""
    return kind == "story_end" or _is_story(kind)


def _is_story(kind) -> bool:
    from . import dialogue
    mm = dialogue.merged()["moments"].get(kind) or {}
    return bool(mm.get("scene") or mm.get("beat_of"))


# ---------------------------------------------------------------------------------------- diagnostics

def rows(sim, day=None) -> list:
    """Every storyline scene and where it stands today: played, queued, eligible, waiting (not yet, with why) or
    unreachable (with why)."""
    w = sim.w
    me = _me(sim)
    if me is None:
        return []
    cat = catalog(sim)
    prof = profile(w)
    q = queue(w)
    queued = {it["sid"] for it in q["items"]}
    lg = log(w)
    nxt = {pk: next_chapter(sim, me, pk, cat, day, prof) for pk in cat["ordered"]}
    out = []
    for sid, sc in sorted(cat["scenes"].items(), key=lambda kv: (kv[1].get("pack") or "", kv[1].get("order", 0))):
        info = cat["info"][sid]
        when = sc.get("when") or {}
        own = when.get("months") or ({"from": [int(x) for x in when["not_before"].split("-")] if when.get("not_before") else [9, 1],
                                     "to": [int(x) for x in when["not_after"].split("-")] if when.get("not_after") else [8, 31]}
                                    if (when.get("not_before") or when.get("not_after")) else None)
        r = {"sid": sid, "pack": sc.get("pack"), "title": info["title"], "importance": info["importance"], "window": info["window"],
             "window_rule": info["window_rule"] if info["window"] else ("the scene says" if own or when.get("dates") else None),
             "window_text": window_text(info["window"] or own) if (info["window"] or own) else (", ".join(when["dates"]) if when.get("dates") else ""),
             "order": sc.get("order", 0)}
        done = done_map(w).get(sid)
        if done:
            r.update({"state": "played", "day": done[-1], "date": calm.label(done[-1])})
        elif sid in seen_map(w):
            r.update({"state": "presented", "day": seen_map(w)[sid][-1]})
        elif sid in queued:
            r["state"] = "queued"
        else:
            g = gate(sim, me, sid, cat, day, prof)
            pk = sc.get("pack")
            if g is None and pk in cat["ordered"] and nxt.get(pk, (None,))[0] != sid:
                g = ("chapter_order", nxt[pk][0])
            if g is None:
                r["state"] = "eligible"
            else:
                p = permanent(sim, me, sid, cat) or (g[0] if g[0] in PERMANENT else None)
                r.update({"state": "unreachable" if p else "waiting", "reason": p or g[0],
                          "detail": g[1] if not p or p == g[0] else None})
            le = lg.get(sid)
            if le and le.get("status") == "missed" and r.get("reason") == "year_passed":
                d = le.get("detail")
                r["missed"] = {"reason": le["reason"], "detail": d}
                r["detail"] = (REASON_TEXT.get(le["reason"], le["reason"].replace("_", " ")) + (f": {d}" if d else ""))
                r["why_missed"] = True
            elif le and le.get("status") in ("expired", "dropped", "returned"):
                r["last"] = le
                if le["status"] == "expired" and r["state"] != "eligible":
                    r["state"] = "expired"
        r["why"] = ("its school years ended while it was waiting" if r.get("why_missed")
                    else REASON_TEXT.get(r.get("reason", ""), ""))
        out.append(r)
    return out


def brief(sim) -> dict:
    """For the phone's Story tab: how many scenes are waiting today and the pacing (cheap: no full scan)."""
    w = sim.w
    q = queue(w)
    today = q.get("day") == w.day
    return {"waiting": len(q["items"]) if today else 0, "presented_today": q.get("presented", 0) if today else 0,
            "target": q.get("target") if today else None, "pacing": profile(w)["name"], "label": profile(w)["label"],
            "played": len(done_map(w)), "binge": bool(control(w).get("binge"))}


def status(sim) -> dict:
    """The Lab's view: pacing, today's queue, and counts per storyline."""
    w = sim.w
    rs = rows(sim)
    from . import dialogue
    names = {p["id"]: (p["pack"].get("name") or p["id"]) for p in dialogue.packs()}
    by: dict = {}
    for r in rs:
        b = by.setdefault(r["pack"], {"pack": r["pack"], "name": names.get(r["pack"], r["pack"]), "in_order": dialogue.in_order(r["pack"]),
                                      "played": 0, "queued": 0, "eligible": 0, "waiting": 0, "unreachable": 0, "expired": 0, "presented": 0})
        b[r["state"]] = b.get(r["state"], 0) + 1
    q = queue(w)
    backlog = [it for it in q["items"] if it.get("queued", w.day) < w.day]
    prof = profile(w)
    return {"profile": prof["name"], "profiles": {k: {kk: v[kk] for kk in ("label", "about")} for k, v in PROFILES.items()},
            "settings": {k: prof.get(k) for k in OVERRIDABLE}, "overrides": w.meta.get("pacing_overrides") or {},
            "auto_scenes": bool(control(w).get("auto_scenes")), "day": w.day, "date": calm.label(w.day),
            "queue": [dict(it, title=(sim.cat.moments.get(it["sid"]) or {}).get("title")) for it in q["items"]],
            "presented_today": q.get("presented", 0) if q.get("day") == w.day else 0, "target_today": q.get("target"),
            "backlog": len(backlog), "oldest": min((it["queued"] for it in backlog), default=None),
            "overdue": sum(1 for it in q["items"] if it.get("deadline") is not None and it["deadline"] <= w.day),
            "storylines": sorted(by.values(), key=lambda b: b["name"]), "scenes": rs, "weights": w.meta.get("story_weights") or {},
            "majors_this_week": sum(1 for d in w.meta.get("scene_majors", []) if w.day - d < 7),
            "migrated": w.meta.get("scheduler_migrated"), "season_map": [dict(r, window_text=_rule_text(sim, r)) for r in season_rules()]}


def _rule_text(sim, r) -> str:
    if r.get("needs_sport") or str(r.get("anchor", "")).startswith("sport:"):
        from .sports import SPORTS
        return " · ".join(f"{sp}: {window_text(rule_window(sim, r, sp))}" for sp in SPORTS if rule_window(sim, r, sp))
    return window_text(rule_window(sim, r))


def timeline(sim) -> dict:
    """Played scenes by day and storyline, with chain arrows and warnings for anything that broke the calendar or the
    chapter order."""
    w = sim.w
    me = _me(sim)
    cat = catalog(sim)
    done = done_map(w)
    items, warn = [], []
    for sid, days in done.items():
        if sid not in cat["scenes"]:
            continue
        sc = cat["scenes"][sid]
        info = cat["info"][sid]
        when = sc.get("when") or {}
        items.append({"sid": sid, "day": days[-1], "date": calm.label(days[-1]), "pack": sc.get("pack"), "importance": info["importance"],
                      "title": info["title"], "after": [a for a in _after(when) if a in done]})
        cal = calendar_ok(sim, sid, {k: v for k, v in when.items() if k != "dates"}, info, days[-1])
        if cal and cal[0] == "wrong_season":
            warn.append({"sid": sid, "kind": "out_of_season", "text": f"{info['title']} played on {calm.label(days[-1])}, outside {cal[1]}"})
        for a in _after(when):
            if a in done and done[a][-1] > days[-1]:
                warn.append({"sid": sid, "kind": "before_prerequisite", "text": f"{info['title']} played before {a}"})
        pk = sc.get("pack")
        if pk in cat["ordered"]:
            lst = cat["chapters"][pk]
            later = [s for s in lst[cat["pos"][sid] + 1:] if s in done and done[s][-1] < days[-1]
                     and not (cat["scenes"][s].get("when") or {}).get("remembered")]
            if later and not (when.get("remembered") or when.get("years") or when.get("after")):
                warn.append({"sid": sid, "kind": "chapter_order", "text": f"{info['title']} came after a later chapter ({later[0]})"})
    items.sort(key=lambda x: (x["day"], x["sid"]))
    return {"items": items, "warnings": warn, "lanes": sorted({i["pack"] for i in items if i["pack"]})}


# ---------------------------------------------------------------------------------------- dry runs and the report

def _light_day(sim):
    """Fast mode: move the calendar one day without simulating the town (school years still turn over on Sept 1)."""
    w = sim.w
    w.day += 1
    w.phase = 0
    d = calm.date_of(w.day)
    if d.month == 9 and d.day == 1:
        for c in w.chars.values():
            if c.status == "active" and c.role == "student" and c.grade:
                c.grade += 1
                if c.grade > 16:
                    c.role, c.grade = "alumni", None
    sim._refresh_day()


def dry_run(sim, days: int, profile_name: str | None = None, full: bool = True, seed_note: str = "") -> dict:
    """Play the story forward on this world (pass a copy) with your character answering every scene, and record what
    played when. full: the whole town simulated (accurate, slow); fast: only the calendar and the stories (seconds)."""
    from . import moments
    w = sim.w
    c = control(w)
    if profile_name:
        c["pacing"] = profile_name
    c["auto_scenes"] = True  # this copy answers for you: it's a dry run
    q = queue(w)
    q.update({"items": [], "day": None, "presented": 0})  # the copy plans its own days from here (fair comparisons)
    start = w.day
    per_day: dict = {}

    def drain():
        for _ in range(GUARD * 3):
            pend = moments.pending(w)
            if not pend:
                m = deliver(sim, force=False) if full else continue_planned(sim)
                if m is None:
                    return
                continue
            m = pend[0]
            if _root(sim, m["kind"]) in catalog(sim)["scenes"] and m["kind"] == _root(sim, m["kind"]):
                per_day.setdefault(w.day, []).append(m["kind"])
            moments.resolve(sim, m["id"], None)
    while w.day < start + days:
        if full:
            sim.step()
        else:
            _light_day(sim)
            plan_day(sim)
        drain()
    return {"start": start, "end": w.day, "profile": profile(w)["name"], "full": full, "per_day": per_day, "note": seed_note}


def continue_planned(sim):
    """Fast mode: today's planned scenes, one after another, regardless of the part of the day."""
    w = sim.w
    q = queue(w)
    if q.get("day") != w.day or not q["items"]:
        return None
    return deliver(sim, force=True)


def identity(sim) -> list:
    """Who every cast slot is bound to, and anything that contradicts what the slot says (a sister for a brother, the wrong
    grade gap)."""
    from . import dialogue
    w = sim.w
    me = w.chars.get(w.meta.get("protagonist") or "")
    out = []
    for name, d in dialogue.merged()["cast"].items():
        spec = d["spec"]
        e = (w.meta.get("cast_slots") or {}).get(name)
        cid = e.get("id") if isinstance(e, dict) else e
        row = {"slot": name, "who": spec.get("who"), "bound": cid, "name": w.chars[cid].name if cid in w.chars else None, "problems": []}
        if cid in w.chars and me:
            o = w.chars[cid]
            want = dialogue.GENDERS.get(spec.get("gender") or "") or ("m" if "brother" in (spec.get("who") or "") else
                                                                       "f" if "sister" in (spec.get("who") or "") else None)
            if want and o.gender != want:
                row["problems"].append(f"{o.first} is {'a girl' if o.gender == 'f' else 'not a girl'}, but the slot is a {spec.get('who')}")
            off = spec.get("grade_offset")
            if o.role == me.role == "student" and o.grade and me.grade:
                gap = o.grade - me.grade
            else:  # one of you has graduated: go by age
                gap = round((me.birth_day - o.birth_day) / 365.25)
            row["grade_gap"] = gap
            if off is not None and abs(gap - off) > (0 if o.role == me.role == "student" else 1):
                row["problems"].append(f"{o.first} is {gap} grades ahead, the slot says {off}")
            row["gender"] = o.gender
        out.append(row)
    return out


def report(sim, run: dict | None = None) -> dict:
    """Every storyline scene: when it played, or why not (not yet / unreachable, with the reason), deadline misses, and
    contradictions (out of season, before its prerequisite, out of chapter order, cast identity)."""
    w = sim.w
    rs = rows(sim)
    tl = timeline(sim)
    missed = [{"sid": sid, **e} for sid, e in log(w).items() if e.get("status") == "expired"]
    by_state: dict = {}
    for r in rs:
        by_state[r["state"]] = by_state.get(r["state"], 0) + 1
    per_day = (run or {}).get("per_day") or {}
    busiest = sorted(((d, len(v)) for d, v in per_day.items()), key=lambda x: -x[1])[:5]
    return {"day": w.day, "date": calm.label(w.day), "profile": profile(w)["name"], "counts": by_state, "scenes": rs,
            "deadline_misses": missed, "warnings": tl["warnings"], "identity": identity(sim),
            "busiest_days": [{"day": d, "date": calm.label(d), "scenes": n} for d, n in busiest],
            "days_with_scenes": len(per_day), "run": {k: v for k, v in (run or {}).items() if k != "per_day"}}


def report_markdown(rep: dict, title: str = "Story schedule report") -> str:
    L = [f"# {title}", "", f"Profile **{rep['profile']}**, run to {rep['date']} (day {rep['day']}).", ""]
    L.append("| state | scenes |\n|---|---|")
    for k in ("played", "presented", "queued", "eligible", "waiting", "expired", "unreachable"):
        if rep["counts"].get(k):
            L.append(f"| {k} | {rep['counts'][k]} |")
    L.append("")
    if rep["busiest_days"]:
        L.append("Busiest days: " + ", ".join(f"{b['date']} ({b['scenes']})" for b in rep["busiest_days"]) + "\n")
    L.append("## Cast identity\n")
    for r in rep["identity"]:
        L.append(f"- `{r['slot']}` ({r['who']}): {r['name'] or 'not bound'}" + ("" if not r["problems"] else " — **" + "; ".join(r["problems"]) + "**"))
    L.append("\n## Contradictions\n")
    L += [f"- {x['kind']}: {x['text']}" for x in rep["warnings"]] or ["- none"]
    L.append("\n## Deadline misses\n")
    L += [f"- `{x['sid']}` on day {x['day']}: {x.get('reason')} {x.get('detail') or ''}" for x in rep["deadline_misses"]] or ["- none"]
    L.append("\n## Every scene\n")
    L.append("| scene | storyline | importance | state | day | why |\n|---|---|---|---|---|---|")
    for r in rep["scenes"]:
        why = r.get("why") or ""
        if r.get("reason"):
            why = f"{r['reason']}: {why}" + (f" ({r['detail']})" if r.get("detail") else "")
        L.append(f"| `{r['sid']}` | {r['pack']} | {r['importance']} | {r['state']} | {r.get('date') or ''} | {why} |")
    return "\n".join(L) + "\n"
