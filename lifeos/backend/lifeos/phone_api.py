"""The phone app's API: your life in first person, one screen at a time.

Everything goes through the same simulation as the lab. These endpoints only shape it for a phone:
second-person text, natural choice wording, the scene you're in, your texts, contacts and pets.
"""
from __future__ import annotations

import re

import socket

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import Response

from . import calendar as calm
from . import knowing, messages, pets, pov, scheduler
from .appearance import look_of

router = APIRouter()


def _lab():
    from . import api as A
    return A, A.get_lab()


def _me(L):
    p = L.w.meta.get("protagonist")
    if not p or p not in L.w.chars:
        raise HTTPException(409, "start a story first")
    return L.w.chars[p]


def _ready(L):
    """Make sure an older story has a phone and full pets."""
    from .story import start_phone
    if "phone" not in L.w.meta or not L.w.meta.get("pets_seeded"):
        start_phone(L.sim)


# --- scenes -------------------------------------------------------------------------------

def scene(sim, me) -> dict:
    w = sim.w
    ph = sim.current_phase()
    d = calm.date_of(w.day)
    month = d.month
    season = "winter" if month in (12, 1, 2) else "spring" if month in (3, 4, 5) else "summer" if month in (6, 7, 8) else "fall"
    weekend = calm.weekday(w.day) >= 5
    cal = sim.cat.world["calendar"]
    brk = calm.break_name(w.day, cal)
    school = sim.cat.world["school"]["short"]
    town = sim.cat.world["town"]["name"]
    games = [i for i in sim._today if i["kind"] == "game" and i.get("group") in me.memberships]
    practice = next((g for g in me.memberships if w.groups[g]["kind"] == "team" and sim.institutions.in_season(w.groups[g])), None)
    col = w.meta.get("college")
    art, title, line = "home_morning", "Home", ""
    if (me.path or {}).get("kind") == "pro":
        art, title, line = "ballpark", "Pro ball", f"Somewhere between bus rides and batting practice with the {me.path.get('team') or 'club'}."
    elif me.location == "college" and col:
        if ph in ("dawn", "night", "evening"):
            art, title, line = "dorm", "The dorm", f"Your room at {col['short']}. Someone down the hall is blasting music."
        elif games:
            art, title, line = "stadium", "Game day", f"{col['short']} plays today."
        elif ph == "lunch":
            art, title, line = "dining_hall", "Dining hall", "Lunch in the dining hall."
        else:
            art, title, line = "campus", col["short"], f"Afternoon on campus at {col['short']}."
    elif ph == "dawn":
        art, title = "home_morning", "At home"
        line = "Saturday morning. No alarm." if weekend else "The alarm goes off. Another day."
    elif ph == "classes":
        art, title, line = "classroom", school, "Classes drag on."
    elif ph == "lunch":
        art, title, line = "cafeteria", "Lunch", f"The {school} cafeteria is loud as usual. Where do you sit?"
    elif ph == "after_school":
        if games:
            g = w.groups[games[0]["group"]]
            art = {"football": "football_field", "basketball": "gym", "baseball": "baseball_field", "softball": "baseball_field", "soccer": "soccer_field"}.get(g.get("skill"), "school_hall")
            title, line = "Game day", f"{g['name']} plays tonight."
        elif practice:
            g = w.groups[practice]
            art = {"football": "football_field", "basketball": "gym", "baseball": "baseball_field", "softball": "baseball_field", "soccer": "soccer_field"}.get(g.get("skill"), "school_hall")
            title, line = "After school", f"The final bell. {g['name']} practice is in twenty minutes."
        else:
            art, title, line = "school_hall", "After school", "The final bell rings. The afternoon is yours."
    elif ph == "day":
        if season == "summer":
            art, title, line = "beach", "Summer", f"Summer in {town}. Jacobs Beach is packed."
        else:
            art, title, line = "town_green", "Weekend" if weekend else (brk or "Day off"), f"A free day in {town}. The Green is busy."
    elif ph in ("evening", "night"):
        art, title, line = "bedroom", "Tonight", "Homework's on your desk. Your phone keeps buzzing."
    return {"art": art, "title": title, "line": line, "phase": ph, "season": season, "weekend": weekend, "break": brk,
            "time": {"dawn": "Morning", "classes": "Class", "lunch": "Lunch", "after_school": "After school", "day": "Daytime",
                     "evening": "Evening", "night": "Night"}.get(ph, ph)}


# --- choice wording ----------------------------------------------------------------------------

PHRASE = {
    "study": "Hit the books", "study_at_lunch": "Study through lunch", "practice_skill": "Work on {t}", "train": "Hit the weight room",
    "hobby": "Spend time on {t}", "rest": "Chill and recharge", "sit_alone": "Eat alone with your headphones in",
    "sit_with": "Sit with {f}", "introduce": "Introduce yourself to {f}", "chat_online": "Message {f}",
    "hang_out": "Ask {f} to hang out", "help_friend": "Help {f} out", "flirt": "Flirt with {f}", "ask_out": "Ask {f} out",
    "ask_to_dance": "Ask {f} to the dance", "date": "Go on a date with {f}", "break_up": "Break up with {f}",
    "confront": "Confront {f}", "apologize": "Apologize to {f}", "gossip": "Gossip with {f}", "spread_rumor": "Start a rumor about {f}",
    "tease": "Give {f} a hard time", "prank": "Prank {f}", "sneak_out": "Sneak out tonight", "attend_practice": "Go to practice",
    "attend_event": "Go to {t}", "sign_up": "Sign up: {t}", "quit_group": "Quit {t}", "work_shift": "Work a shift at {t}",
    "throw_party": "Throw a party", "go_to_party": "Go to {t}", "spectate": "Watch {t}", "family_time": "Hang out with {f}",
    "pet_time": "Chill with {t}", "pet_walk": "Walk {t}", "pet_park": "Take {t} to the park", "pet_play": "Play with {t}",
    "pet_train": "Teach {t} a trick", "mentor": "Help {f} get better", "staff_chat": "Talk to {f}", "reply_invite": "Say yes to {f}",
}
ICON = {"social": "people", "romance": "heart", "school": "book", "conflict": "bolt", "rest": "moon", "family": "home",
        "activity": "star", "sport": "ball", "work": "work", "risk": "warn"}


def phrase(sim, opt) -> str:
    w = sim.w
    tmpl = PHRASE.get(opt["action"])
    tname = opt.get("target_name") or ""
    tid = opt.get("target")
    first = w.chars[tid].first if isinstance(tid, str) and tid in w.chars else tname.split(" ")[0] if tname else "them"
    if not tmpl:
        return opt["label"] + (f": {tname}" if tname else "")
    return tmpl.format(f=first, t=tname or "it")


def squad_view(sim):
    from . import squad
    return squad.view(sim)


def chat_vibe(sim, cid):
    from . import chat
    return chat.vibe(sim, cid)


def incoming_view(w):
    from .story import incoming_view as iv
    return iv(w)


def team_card(w, me, gid) -> dict:
    """A team on your Me tab: the team's record at your level, and yours (the games you played in this season)."""
    from .sports import season_key
    g = w.groups[gid]
    level = g.get("levels", {}).get(me.id, "varsity")
    st = me.stats.get(season_key(g.get("skill"), w.day, level)) or {}
    return {"id": gid, "name": g["name"], "sport": g.get("skill"), "level": level, "position": me.positions.get(g.get("skill")),
            "record": g.get("record_jv", {"w": 0, "l": 0}) if level == "jv" else g["record"],
            "mine": {"w": st.get("wins", 0), "l": st.get("losses", 0)}}


# --- state ----------------------------------------------------------------------------------

@router.get("/api/phone/state")
def phone_state(since: int | None = None):
    A, L = _lab()
    with L.lock:
        w = L.w
        if not w.meta.get("protagonist"):
            return {"active": False}
        _ready(L)
        sim = L.sim
        me = _me(L)
        from . import moments
        from .story import progress
        from .calendar import DECISION_SLOTS
        ph = sim.current_phase()
        busy_with = sim.committed(me.id, ph) if ph in DECISION_SLOTS else None
        ready = ph in DECISION_SLOTS and me.id in sim.slot_actors(ph) and not busy_with
        pend = []
        for m in moments.pending(w):
            mm = {k: v for k, v in m.items() if k != "_choices"}
            mm["text"] = pov.second_person(m["text"], me)
            mm["title"] = pov.second_person(m["title"], me)
            if m["kind"] in sim.cat.moments and (sim.cat.moments[m["kind"]].get("scene") or sim.cat.moments[m["kind"]].get("beat_of")):
                from . import dialogue
                mm["storyline"] = dialogue.chapter_label(sim, m["kind"])  # "Hoops with my brother · Chapter 2 of 5"
            from . import episodes, nights
            mm["episode_label"] = episodes.label(m)  # "Season 2 · Episode 6"
            if nights.is_night(m["kind"]):
                mm["storyline"] = nights.label(m)  # "Mike's party · 2 of 4"
            pend.append(mm)
        evs = w.history.by_char.get(me.id, [])
        feed = []
        for eid in evs[::-1]:
            e = w.history.events.get(eid)
            if not e or e["importance"] < 6 or private(e, me.id):
                continue
            if since is not None and eid <= since:
                break
            feed.append({"id": eid, "date": calm.label(e["day"]), "slot": e.get("slot"), "type": e["type"], "outcome": e.get("outcome"),
                         "text": pov.event_line(w, e, me.id), "with": [x for x in e["actors"] + e["targets"] if x != me.id][:3],
                         "importance": e["importance"]})
            if len(feed) >= (40 if since is not None else 25):
                break
        h = w.households.get(me.household_id) or {}
        threads = messages.threads_view(sim)
        hp = pets.household_pets(w, me.household_id or "")
        from . import planner
        q = w.meta.get("control", {}).get("queued")
        teams = [team_card(w, me, g) for g in me.memberships if w.groups[g]["kind"] == "team"]
        return {
            "active": True, "day": w.day, "date": calm.label(w.day), "weekday": calm.date_of(w.day).strftime("%A"),
            "term": calm.term_label(w.day, sim.cat.world["calendar"]), "scene": scene(sim, me), "decision_ready": ready,
            "progress": progress(w), "title": w.meta.get("story", {}).get("title"),
            "me": dict(A.char_summary(L, me), age=me.age(w.day), needs={k: round(v) for k, v in me.needs.items()}, money=round(me.money),
                       gpa=round(me.gpa, 2), injured=me.flags.get("injured_until", -1) >= w.day, path=me.path, body=me.body,
                       positions=me.positions, jersey=me.jersey),
            "moments": pend, "feed": feed, "last_event": w.history.next_event - 1, "committed": busy_with, "squad": squad_view(sim),
            "unread": sum(t["unread"] for t in threads), "needs_reply": sum(1 for t in threads if t["needs_reply"]),
            "pets": [pets.view(sim, p) for p in hp], "pet_setup_needed": any(pets.setup_needed(w, p["id"]) for p in hp),
            "pet_approved": w.meta.get("pet_approved"), "queued": q and {"label": planner.plan_label(sim, q) or "Saying yes to an invite"},
            "family": {"name": h.get("name"), "guardians": messages.parent_names(sim), "siblings": [
                {"id": s, "first": w.chars[s].first, "year_label": w.chars[s].year_label, "location": w.chars[s].location,
                 "look": look_of(w.chars[s]), "path": w.chars[s].path} for s in sim.siblings(me.id)],
                "younger": [x for x in incoming_view(w) if x["kind"] == "sibling"], "style": h.get("style_label"),
                "trust": round(messages.phone(w)["parent_trust"])},
            "teams": teams, "control": dict(scheduler.control(w), girl_asks_guy=w.rules.get("romance.girl_asks_guy", 1.0)), "stories": scheduler.brief(sim),
            "setting": {"town": sim.cat.world["town"]["name"], "school": sim.cat.world["school"]["name"],
                        "short": sim.cat.world["school"]["short"], "mascot": sim.cat.world["school"]["mascot"]},
        }


@router.get("/api/phone/choices")
def phone_choices():
    A, L = _lab()
    L.guard()
    with L.lock:
        sim = L.sim
        me = _me(L)
        from .calendar import DECISION_SLOTS
        ph = sim.current_phase()
        if not (ph in DECISION_SLOTS and me.id in sim.slot_actors(ph)):
            return {"ready": False}
        busy_with = sim.committed(me.id, ph)
        if busy_with:
            return {"ready": False, "committed": busy_with}  # practice and games just happen
        res = sim.options_for(me.id)
        if res is None:
            return {"ready": False}
        slot, dec = res
        order = sorted(range(len(dec["cands"])), key=lambda i: -dec["cands"][i].u)
        opts = []
        for i in order:
            cd = dec["cands"][i]
            o = {"index": i, "action": cd.a["id"], "label": cd.a["label"], "category": cd.a["category"],
                 "target": cd.target if isinstance(cd.target, str) and cd.target in L.w.chars else None,
                 "target_name": sim.target_name(cd), "prob": round(cd.prob, 4), "risk": cd.a["risk"]}
            if cd.a["id"] == "chat_online" or cd.a["id"].startswith("pet_"):
                continue  # texting and your pet don't use up your time: those are quick, anytime, from the Phone and Home tabs
            o["text"] = phrase(sim, o)
            o["icon"] = ICON.get(cd.a["category"], "star")
            o["why"] = cd.why
            if isinstance(cd.extra, dict) and cd.extra.get("pet"):
                o["pet"] = cd.extra["pet"]
            if cd.a["id"] == "attend_event" and isinstance(cd.extra, dict) and cd.extra.get("kind") in ("game", "show"):
                o["own"] = cd.extra["kind"]  # your own game or show, not a night out
                if cd.extra["kind"] == "game" and cd.extra.get("group") in L.w.groups:
                    from .sports import opponent_name
                    tail = cd.extra["key"].split(":")[-1]
                    o["opponent"] = opponent_name(sim, L.w.groups[cd.extra["group"]], int(tail) if tail.isdigit() else 1)
                    o["text"] = f"Play in your game vs {o['opponent']}"
                else:
                    o["text"] = f"Perform in {cd.extra.get('production_name') or o['target_name'] or 'the show'}"
                o["icon"] = "ball" if cd.extra["kind"] == "game" else "star"
            opts.append(o)
        seen, uniq = set(), []
        for o in opts:
            if o["text"] in seen:
                continue
            seen.add(o["text"])
            uniq.append(o)
        if uniq:
            uniq[0]["gut"] = True
        from . import planner
        opts = planner.annotate(sim, me, uniq)
        from . import squad
        # nobody's free while they're at practice: they're not an option right now
        opts = [o for o in opts if not (o["action"] in ("hang_out", "date", "help_friend") and o.get("target") and sim.committed(o["target"], slot))]
        group = squad.option(sim, opts, slot)  # your group: the boys on the game, the park, a food run
        asked = squad.invite_option(sim, opts, slot)  # a friend asked you along with a few of their people
        crew = [] if group or squad.state(sim) else [x for x in [crew_option(L, me, opts)] if x]
        # one on one is for the people you're close to; everyone else comes after the group stuff
        solo = [o for o in opts if o["action"] == "hang_out" and o.get("target") and not squad.close_to(sim, me, o["target"])]
        for o in solo:
            o["minor"] = True
        opts = [o for o in opts if o not in solo] + solo
        at = next((i for i, o in enumerate(opts) if o["group"] != "should"), len(opts))
        opts[at:at] = asked + group + crew
        return {"ready": True, "slot": slot, "scene": scene(sim, me), "options": opts, "busy": squad.busy_friends(sim, slot)}


def crew_option(L, me, opts):
    """Hang out with the crew: your closest friends at once, one choice instead of one friend at a time."""
    w = L.w
    hang = sorted([o for o in opts if o["action"] == "hang_out" and o.get("target")],
                  key=lambda o: -(w.rels[(me.id, o["target"])].affection if (me.id, o["target"]) in w.rels else 0))
    family = set(L.sim.siblings(me.id))
    ok = lambda o: (o in w.chars and w.chars[o].status == "active" and w.chars[o].role in ("student", "alumni")  # noqa: E731
                    and w.chars[o].location == me.location and o != me.flags.get("partner") and o not in family
                    and (me.id, o) in w.rels and w.rels[(me.id, o)].affection >= 30)
    mains = [o for o in hang if ok(o["target"])]
    if not mains:
        return None
    main = mains[0]
    pals = sorted((o for o in w.out.get(me.id, {}) if ok(o) and o != main["target"]), key=lambda o: (-w.rels[(me.id, o)].affection, o))
    extra = pals[:2]
    if not extra:
        return None
    firsts = [w.chars[main["target"]].first] + [w.chars[x].first for x in extra]
    label = ", ".join(firsts[:-1]) + " and " + firsts[-1]
    return dict(main, key=f"crew{main['index']}", action="hang_group", crew=extra, text=f"Hang out with {label}",
                group="want", reason="The crew, all at once", later=None, gut=False, icon="people")


# --- the social scene: groups, couples, where you stand, people to meet --------------------------

@router.get("/api/phone/scene")
def phone_scene():
    A, L = _lab()
    from . import scene
    with L.lock:
        _me(L)
        return scene.view(L.sim)


@router.get("/api/phone/sports")
def phone_sports(team: str = ""):
    """The Sports tab: your season, your playing time, the league, the awards race and recruiting (for one of your teams)."""
    A, L = _lab()
    from . import sportshub
    with L.lock:
        _me(L)
        return sportshub.view(L.sim, team or None)


@router.get("/api/phone/mlb")
def phone_mlb():
    """MLB in the background: your team, the standings, October, the leaders, the news, and the what-ifs (mlb.py)."""
    A, L = _lab()
    from . import mlb
    with L.lock:
        _me(L)
        return mlb.view(L.sim)


@router.get("/api/phone/mlb/whatif")
def phone_mlb_whatif(id: str):
    """One what-if on its own: what moved, and season by season how it changed things (with the odds)."""
    A, L = _lab()
    from . import mlb
    if id not in mlb.WHATIF:
        raise HTTPException(404, f"no what-if called {id}")
    with L.lock:
        return mlb.whatif_view(L.sim, id)


@router.post("/api/phone/mlb/whatif")
def phone_mlb_whatif_set(body: dict = Body(...)):
    """Turn a what-if on or off in this world: history replays, and players it covers who are still playing move now."""
    A, L = _lab()
    from . import mlb
    wid = body.get("id")
    if wid not in mlb.WHATIF:
        raise HTTPException(404, f"no what-if called {wid}")
    with L.lock:
        r = mlb.set_whatif(L.sim, wid, bool(body.get("on")))
        return {**r, "view": mlb.whatif_view(L.sim, wid)}


@router.get("/api/phone/mlb/year")
def phone_mlb_year(y: int):
    """A past season in this world: final standings, October, the awards."""
    A, L = _lab()
    from . import mlb
    with L.lock:
        try:
            return mlb.year_view(L.sim, y)
        except (ValueError, KeyError) as e:
            raise HTTPException(404, str(e))


@router.post("/api/phone/mlb/team")
def phone_mlb_team(body: dict = Body(...)):
    """Pick your MLB team (it's who {my_team} is in scenes, and whose October you feel)."""
    A, L = _lab()
    from . import mlb
    with L.lock:
        try:
            mlb.set_team(L.sim, str(body.get("team") or ""))
        except ValueError as e:
            raise HTTPException(400, str(e))
        return mlb.view(L.sim)


@router.get("/api/phone/leagues")
def phone_leagues():
    """Every league behind the story with your team's line right now (the Pro and College menus)."""
    A, L = _lab()
    from . import realleagues
    with L.lock:
        return {"leagues": realleagues.summary(L.sim)}


@router.get("/api/phone/league")
def phone_league(lg: str):
    """One league as it really happened, through today: your team, the table or top 25, the postseason, the champions."""
    A, L = _lab()
    from . import realleagues
    if lg not in realleagues.LEAGUES:
        raise HTTPException(404, f"no league {lg}")
    with L.lock:
        _me(L)
        return realleagues.view(L.sim, lg)


@router.post("/api/phone/league/follow")
def phone_league_follow(body: dict = Body(...)):
    """Follow a team: an NFL or NBA team, a club in a European league, or a school for all of college sports (empty = back to
    your own college)."""
    A, L = _lab()
    from . import realleagues
    lg = str(body.get("lg") or "")
    if lg not in realleagues.LEAGUES:
        raise HTTPException(404, f"no league {lg}")
    with L.lock:
        try:
            realleagues.set_follow(L.sim, lg, str(body.get("team") or ""))
        except ValueError as e:
            raise HTTPException(400, str(e))
        return realleagues.view(L.sim, lg)


@router.get("/api/phone/ladder")
def phone_ladder(scope: str = "school"):
    """The Scene tab's ladder: you, the movers and why, what your standing is made of, your storylines' people, the
    superlatives and the full rankings (scope: school, grade, or 9-12)."""
    A, L = _lab()
    from . import ladder
    with L.lock:
        _me(L)
        return ladder.view(L.sim, scope if scope in ("school", "grade") or scope.isdigit() else "school")


@router.post("/api/phone/scene/intro")
def phone_scene_intro(body: dict = Body(...)):
    """Ask a friend ({via}) to introduce you to someone they know ({to}). Free, once a day."""
    A, L = _lab()
    L.guard()
    from . import scene
    with L.lock:
        me = _me(L)
        needs0, mood0 = dict(me.needs), me.mood
        rels0 = {o: (r.affection, r.attraction, r.trust) for o, r in L.w.out.get(me.id, {}).items()}
        try:
            ev = scene.intro(L.sim, str(body.get("via", "")), str(body.get("to", "")))
        except ValueError as e:
            raise HTTPException(409, str(e))
        L.autosave()
        return {"lines": _lines(L, [ev], me), "chips": _chips(L, me, needs0, mood0, rels0), "scene": scene.view(L.sim)}


@router.post("/api/phone/scene/rumor")
def phone_scene_rumor(body: dict = Body(...)):
    """Do something with a rumor you've heard: {id, what}. About you: deny, own, find. About someone else: tell, pass, drop."""
    A, L = _lab()
    L.guard()
    from . import drama, scene
    with L.lock:
        me = _me(L)
        needs0, mood0 = dict(me.needs), me.mood
        rels0 = {o: (r.affection, r.attraction, r.trust) for o, r in L.w.out.get(me.id, {}).items()}
        try:
            ev = drama.act(L.sim, str(body.get("id", "")), str(body.get("what", "")))
        except ValueError as e:
            raise HTTPException(409, str(e))
        L.autosave()
        return {"lines": _lines(L, [ev], me), "chips": _chips(L, me, needs0, mood0, rels0), "scene": scene.view(L.sim)}


@router.post("/api/phone/scene/plan")
def phone_scene_plan(body: dict = Body(...)):
    """Plan to hang out with someone at your next free time."""
    A, L = _lab()
    L.guard()
    from . import scene
    with L.lock:
        _me(L)
        try:
            note = scene.plan(L.sim, str(body.get("with", "")))
        except ValueError as e:
            raise HTTPException(409, str(e))
        L.autosave()
        return {"note": note}


# --- the editor: change anyone, and anything between two people ---------------------------------

def _editor(L):
    from . import editor
    if not editor.on(L.w):
        raise HTTPException(403, "The editor is off. Turn it on in Me → Story Studio → People.")
    return editor


@router.get("/api/phone/editor")
def phone_editor():
    """Everyone in your world (closest to you first) and what can be edited."""
    A, L = _lab()
    with L.lock:
        _me(L)
        ed = _editor(L)
        return {"schema": ed.schema(L.sim), "people": ed.people(L.sim)}


@router.get("/api/phone/editor/person/{cid}")
def phone_editor_person(cid: str):
    A, L = _lab()
    with L.lock:
        _me(L)
        ed = _editor(L)
        try:
            return ed.person(L.sim, cid)
        except ed.EditorError as e:
            raise HTTPException(404, str(e))


@router.post("/api/phone/editor/person/{cid}")
def phone_editor_save_person(cid: str, body: dict = Body(...)):
    """Change a person: {traits: {...}, aptitudes, motives, skills, interests, needs, mood, popularity, money, gpa, first, last, bio, look}."""
    A, L = _lab()
    L.guard()
    with L.lock:
        _me(L)
        ed = _editor(L)
        try:
            out = ed.save_person(L.sim, cid, body)
        except ed.EditorError as e:
            raise HTTPException(422, str(e))
        L.autosave()
        return out


@router.post("/api/phone/editor/new")
def phone_editor_new(body: dict = Body(...)):
    """Someone new: {first, last, gender, grade (or role: staff), archetype, to_me (friend, crush, rival...), family}."""
    A, L = _lab()
    L.guard()
    with L.lock:
        _me(L)
        ed = _editor(L)
        try:
            out = ed.create_person(L.sim, body)
        except ed.EditorError as e:
            raise HTTPException(422, str(e))
        L.autosave()
        return out


@router.get("/api/phone/roles")
def phone_roles():
    """Everything your storylines need from your story, by role: who fills it, or who's close and what would make them fit."""
    A, L = _lab()
    with L.lock:
        from . import roles
        return roles.board(L.sim)


@router.post("/api/phone/roles/{action}")
def phone_roles_do(action: str, body: dict = Body(...)):
    """pick {role, char|null}, fix {role, char, how: {sport} | {pair}}, add {role}."""
    A, L = _lab()
    L.guard()
    with L.lock:
        _me(L)
        from . import editor, roles
        key = str(body.get("role") or "")
        try:
            if action == "pick":
                out = roles.pick(L.sim, key, body.get("char"))
            elif action == "fix":
                out = roles.fix(L.sim, key, str(body.get("char") or ""), body.get("how") or {})
            elif action == "add":
                out = roles.add(L.sim, key)
            else:
                raise HTTPException(404, "no such action")
        except editor.EditorError as e:
            raise HTTPException(422, str(e))
        L.autosave()
        return out


@router.post("/api/phone/editor/fit")
def phone_editor_fit(body: dict = Body(...)):
    """Someone who fits a storyline's person nobody in your story fits: {slot}. They're made to fit and picked for it."""
    A, L = _lab()
    L.guard()
    with L.lock:
        _me(L)
        from . import editor
        try:
            out = editor.create_for_slot(L.sim, str(body.get("slot") or ""))
        except editor.EditorError as e:
            raise HTTPException(422, str(e))
        L.autosave()
        return out


@router.get("/api/phone/editor/pair/{a}/{b}")
def phone_editor_pair(a: str, b: str):
    A, L = _lab()
    with L.lock:
        _me(L)
        ed = _editor(L)
        try:
            return ed.pair(L.sim, a, b)
        except ed.EditorError as e:
            raise HTTPException(404, str(e))


@router.post("/api/phone/editor/pair/{a}/{b}")
def phone_editor_save_pair(a: str, b: str, body: dict = Body(...)):
    """How two people feel about each other: {preset} and/or {ab: {field: value}, ba: {...}} (a's feelings, b's feelings)."""
    A, L = _lab()
    L.guard()
    with L.lock:
        _me(L)
        ed = _editor(L)
        try:
            out = ed.save_pair(L.sim, a, b, body)
        except ed.EditorError as e:
            raise HTTPException(422, str(e))
        L.autosave()
        return out


@router.get("/api/phone/episodes")
def phone_episodes():
    """Your seven years as one show: every season, every episode and what you chose, and what's coming up."""
    A, L = _lab()
    from . import episodes
    with L.lock:
        _me(L)
        return episodes.guide(L.sim)


@router.get("/api/phone/today")
def phone_today():
    """Your day at a glance: the parts of today, what needs you, and the next seven days."""
    A, L = _lab()
    with L.lock:
        _me(L)
        _ready(L)
        from . import planner
        return planner.today(L.sim)


@router.post("/api/phone/later")
def phone_later(body: dict = Body(...)):
    """Save one of the current choices for the next part of today you get to decide in."""
    A, L = _lab()
    L.guard()
    with L.lock:
        me = _me(L)
        res = phone_choices()
        if not res.get("ready"):
            raise HTTPException(409, "there's nothing to plan right now")
        try:
            idx = int(body["index"])
        except (KeyError, TypeError, ValueError):
            raise HTTPException(422, "index must be a whole number")
        opt = next((o for o in res["options"] if o["index"] == idx and o["action"] not in ("hang_group", "squad")), None)
        if opt is None or not opt.get("later"):
            raise HTTPException(409, "that one can't wait")
        from . import planner
        try:
            plan = planner.save_for_later(L.sim, opt)
        except ValueError as e:
            raise HTTPException(409, str(e))
        L.autosave()
        return {"queued": plan["label"], "note": f"Saved: {plan['label']}. It's picked for you then."}


@router.post("/api/phone/choose")
def phone_choose(body: dict = Body(...)):
    A, L = _lab()
    L.guard()
    with L.lock:
        sim = L.sim
        me = _me(L)
        try:
            idx = int(body["index"])
        except (KeyError, TypeError, ValueError):
            raise HTTPException(422, "index must be a whole number")
        if body.get("crew"):  # bring the crew (or your group, doing something) along on this hangout
            L.w.meta.setdefault("control", {})["crew"] = {"day": L.w.day, "slot": sim.current_phase(),
                                                          "ids": [x for x in body["crew"] if x in L.w.chars][:3],
                                                          "act": body.get("act") if body.get("act") else None}
        needs0 = dict(me.needs)
        mood0 = me.mood
        rels0 = {o: (r.affection, r.attraction, r.trust) for o, r in L.w.out.get(me.id, {}).items()}
        try:
            evs = sim.act_as(me.id, idx)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(409, str(e))
        L.autosave()
        return {"lines": _lines(L, evs, me), "chips": _chips(L, me, needs0, mood0, rels0)}


def private(e, me_id) -> bool:
    """Single player: you don't get to read other people's minds (how they now see you, what they secretly think)."""
    return e["type"] == "milestone" and (e.get("actors") or [None])[0] != me_id


def _lines(L, evs, me):
    w = L.w
    out = []
    for e in evs:
        if private(e, me.id):
            continue
        if e.get("outcome") == "invited" and me.id in e["targets"] and me.id not in e["actors"]:
            continue  # someone else's invite arrives as a text, it isn't part of what you just did
        if (e.get("data") or {}).get("swap") and me.id in e["actors"]:
            out.append({"id": f"swap{e['id']}", "type": "swap", "text": e["data"]["swap"]})
        if e.get("importance", 0) < 3 and e["type"] in ("practice", "exam"):
            continue
        out.append({"id": e["id"], "type": e["type"], "outcome": e.get("outcome"), "text": pov.event_line(w, e, me.id),
                    "with": [x for x in e["actors"] + e["targets"] if x != me.id][:3]})
        if (e.get("data") or {}).get("crew_line") and me.id in e["actors"]:
            out.append({"id": f"crew{e['id']}", "type": "crew", "text": e["data"]["crew_line"], "with": e["data"].get("crew", [])[:3]})
        if (e.get("data") or {}).get("why") and me.id in e["actors"]:
            out.append({"id": f"why{e['id']}", "type": "why", "text": e["data"]["why"]})
    return out[:8]


def _chips(L, me, needs0, mood0, rels0):
    w = L.w
    chips = []
    for k, label in (("energy", "Energy"), ("stress", "Stress"), ("fun", "Fun"), ("social", "Social")):
        d = me.needs.get(k, 0) - needs0.get(k, 0)
        if abs(d) >= 2:
            chips.append({"label": label, "delta": round(d), "good": d > 0 if k != "stress" else d < 0})
    for o, r in w.out.get(me.id, {}).items():
        a0, at0, t0 = rels0.get(o, (0, 0, 0))
        if abs(r.affection - a0) >= 1.5:
            chips.append({"label": w.chars[o].first, "delta": round(r.affection - a0), "good": r.affection > a0, "who": o, "kind": "friend"})
        if abs(r.attraction - at0) >= 2:
            chips.append({"label": w.chars[o].first, "delta": round(r.attraction - at0), "good": r.attraction > at0, "who": o, "kind": "heart"})
    return chips[:6]


@router.post("/api/phone/moment/{mid}")
def phone_moment(mid: str, body: dict = Body(default={})):
    """Answer a moment. A choice you play yourself (a mini game) comes back as {"minigame": config} first; post again with
    the round's {session, score, max} to finish it. {"auto": true} lets the dice decide instead."""
    A, L = _lab()
    L.guard()
    from . import minigames, moments
    with L.lock:
        me = _me(L)
        idx = body.get("index")
        m = next((x for x in L.w.meta.get("moments", []) if x["id"] == mid), None)
        if m is None or m["status"] != "pending":
            raise HTTPException(409, "that moment is no longer waiting for a choice")
        if idx is not None and not body.get("auto") and not body.get("session"):
            i = int(idx)
            if not 0 <= i < len(m["_choices"]):
                raise HTTPException(409, "no such choice")
            op = minigames.top_op(m["_choices"][i]["ops"])
            if op and minigames.ready(minigames.resolve_game(op[1], m["ctx"])):
                try:
                    cfg = minigames.start(L.sim, op[1], kind="moment", mid=mid, index=i, ctx=m["ctx"])
                except ValueError as e:
                    raise HTTPException(409, str(e))
                L.autosave()
                return {"minigame": cfg}
        needs0, mood0 = dict(me.needs), me.mood
        rels0 = {o: (r.affection, r.attraction, r.trust) for o, r in L.w.out.get(me.id, {}).items()}
        played = None
        try:
            if body.get("session"):
                played = minigames.finish(L.sim, body["session"], body.get("score"), body.get("max"), body.get("stats"))
                ev = played["event"]
            else:
                ev = moments.resolve(L.sim, mid, None if idx is None else int(idx))
        except ValueError as e:
            raise HTTPException(409, str(e))
        follow = [L.w.history.events[i] for i in range(ev["id"] + 1, L.w.history.next_event) if i in L.w.history.events
                  and me.id in L.w.history.events[i]["actors"] + L.w.history.events[i]["targets"]]
        L.autosave()
        says = [{"id": f"say{ev['id']}-{i}", "type": "say", "text": t} for i, t in enumerate(ev["data"].get("say", []))]
        lines = [{"id": ev["id"], "type": "moment", "text": pov.event_line(L.w, ev, me.id), "calc": ev.get("calc")}] + says + _lines(L, follow, me)
        if ev["data"].get("why") and m["kind"].startswith("hang_"):
            lines.insert(1 + len(says), {"id": f"why{ev['id']}", "type": "why", "text": ev["data"]["why"]})
        out = {"lines": lines, "chips": _chips(L, me, needs0, mood0, rels0)}
        if played:
            out["minigame"] = {k: played[k] for k in ("tier", "pct", "score", "max", "game")}
        return out


# --- mini games and classes --------------------------------------------------------------------

@router.get("/api/phone/minigames")
def phone_minigames():
    A, L = _lab()
    from . import minigames
    with L.lock:
        _me(L)
        st = minigames.state(L.w)
        return {"games": minigames.free_list(L.sim), "recent": st["history"][-10:][::-1]}


@router.post("/api/phone/minigame/start")
def phone_minigame_start(body: dict = Body(...)):
    A, L = _lab()
    L.guard()
    from . import minigames
    with L.lock:
        _me(L)
        try:
            cfg = minigames.start(L.sim, str(body.get("game", "")), kind="free")
        except ValueError as e:
            raise HTTPException(409, str(e))
        return cfg


@router.post("/api/phone/minigame/finish")
def phone_minigame_finish(body: dict = Body(...)):
    """Finish a free-play round. (Rounds started from a moment finish through /api/phone/moment/{mid}.)"""
    A, L = _lab()
    L.guard()
    from . import minigames
    with L.lock:
        me = _me(L)
        sess = minigames.state(L.w).get("session") or {}
        if sess.get("kind") == "moment":
            raise HTTPException(409, "finish this round through its moment")
        needs0, mood0 = dict(me.needs), me.mood
        rels0 = {o: (r.affection, r.attraction, r.trust) for o, r in L.w.out.get(me.id, {}).items()}
        try:
            r = minigames.finish(L.sim, body.get("session"), body.get("score"), body.get("max"), body.get("stats"))
        except ValueError as e:
            raise HTTPException(409, str(e))
        L.autosave()
        ev = r["event"]
        return {"result": {k: r[k] for k in ("tier", "pct", "score", "max", "game")}, "rewarded": ev["data"].get("rewarded"),
                "lines": [{"id": ev["id"], "type": "minigame", "text": pov.event_line(L.w, ev, me.id)}],
                "chips": _chips(L, me, needs0, mood0, rels0)}


@router.post("/api/phone/minigame/quit")
def phone_minigame_quit():
    A, L = _lab()
    from . import minigames
    with L.lock:
        minigames.state(L.w).pop("session", None)
        return {"ok": True}


@router.get("/api/phone/classes")
def phone_classes():
    A, L = _lab()
    from . import classes
    with L.lock:
        me = _me(L)
        w = L.w
        upcoming = [i for i in w.calendar if i["kind"] == "exam" and i["day"] >= w.day and i.get("school", "hchs") == me.school][:3]
        tests = classes.store(w)["quizzes"].get("_tests", [])
        return {"gpa": round(me.gpa, 2), "year": me.year_label, "classes": classes.grades(L.sim, me),
                "upcoming": [{"name": i["name"], "date": calm.label(i["day"]), "in_days": i["day"] - w.day,
                              "weight": i.get("weight", 1)} for i in upcoming],
                "tests_played": len(tests)}


# --- messages -------------------------------------------------------------------------------

@router.get("/api/phone/threads")
def phone_threads():
    A, L = _lab()
    with L.lock:
        _me(L)
        _ready(L)
        return {"threads": messages.threads_view(L.sim)}


@router.get("/api/phone/thread/{tid}")
def phone_thread(tid: str):
    A, L = _lab()
    with L.lock:
        me = _me(L)
        _ready(L)
        ph = messages.phone(L.w)
        if tid not in ph["threads"]:
            if tid.startswith("dm:") and tid[3:] in L.w.chars:
                messages.dm(L.sim, tid[3:])
            elif tid == "family":
                messages.family_thread(L.sim)
            elif tid.startswith("team:") and tid[5:] in L.w.groups:
                g = L.w.groups[tid[5:]]
                messages.thread(L.sim, tid, title=g["name"], members=[m for m in g["members"] if m != me.id], kind="group")
            else:
                raise HTTPException(404, "no such conversation")
        return messages.thread_view(L.sim, tid, mark_read=True)


@router.post("/api/phone/thread/{tid}/reply")
def phone_reply(tid: str, body: dict = Body(...)):
    A, L = _lab()
    L.guard()
    with L.lock:
        _me(L)
        try:
            out = messages.reply(L.sim, tid, body.get("msg"), int(body.get("index", -1)))
        except ValueError as e:
            raise HTTPException(409, str(e))
        L.autosave()
        return out


@router.post("/api/phone/thread/{tid}/say")
def phone_say(tid: str, body: dict = Body(...)):
    """Text someone: {"text": "anything you want"} or {"suggestion": index}. They answer like themselves."""
    A, L = _lab()
    L.guard()
    from . import chat
    with L.lock:
        _me(L)
        if not tid.startswith("dm:") or tid[3:] not in L.w.chars:
            raise HTTPException(404, "you can only text one person at a time here")
        try:
            sug = body.get("suggestion")
            res = chat.send(L.sim, tid[3:], body.get("text"), int(sug) if sug is not None else None)
        except ValueError as e:
            raise HTTPException(409, str(e))
        L.autosave()
        return {"thread": messages.thread_view(L.sim, tid, mark_read=True), "result": res.get("result"), "why": res.get("why"),
                "plans": bool(res.get("plans"))}


@router.get("/api/phone/flirting")
def phone_flirting():
    """How flirting works, in plain words."""
    from . import chat
    return {"guide": chat.GUIDE, "stages": chat.STAGES}


@router.post("/api/phone/text")
def phone_text(body: dict = Body(...)):
    A, L = _lab()
    L.guard()
    with L.lock:
        _me(L)
        try:
            out = messages.text_first(L.sim, body.get("to"), body.get("kind"))
        except ValueError as e:
            raise HTTPException(409, str(e))
        L.autosave()
        return out


# --- contacts -------------------------------------------------------------------------------

def _hearts(x) -> int:
    return max(0, min(5, int(round((x + 10) / 22))))


def _feel(x, kind="affection") -> str:
    if kind == "perceived":
        return ("they really like you" if x >= 60 else "they like you" if x >= 30 else "they're friendly" if x >= 10
                else "hard to read" if x >= -10 else "they're cold toward you")
    return ("love them" if x >= 80 else "really close" if x >= 60 else "good friends" if x >= 35 else "friendly" if x >= 15
            else "don't know them well" if x >= -10 else "not a fan" if x >= -40 else "can't stand them")


def contact_row(L, me, oid):
    w = L.w
    o = w.chars[oid]
    r = w.rels.get((me.id, oid))
    ph = messages.phone(w)
    sib = oid in L.sim.siblings(me.id)
    t = ph["threads"].get(f"dm:{oid}")
    last = t["msgs"][-1] if t and t["msgs"] else None
    roles = (w.bond(me.id, oid) or {"roles": []})["roles"]
    return {"id": oid, "name": o.name, "first": o.first, "year_label": o.year_label, "look": look_of(o), "color": o.color,
            "label": "sibling" if sib else (r.label if r else "stranger"), "crush": bool(r and r.crush),
            "partner": me.flags.get("partner") == oid, "roles": [x.split(":")[0] for x in roles],
            "affection": round(r.affection) if r else 0, "hearts": _hearts(r.affection if r else 0),
            "attraction": round(r.attraction) if r else 0, "rivalry": round(r.rivalry) if r else 0,
            "perceived": round(r.perceived) if r else 0, "has_number": oid in ph["contacts"] or sib,
            "unread": t["unread"] if t else 0, "last": last and {"text": last["text"], "at": last["at"], "from": last["from"]},
            "location": o.location, "role": o.role, "glance": knowing.glance(L.sim, oid)}


@router.get("/api/phone/contacts")
def phone_contacts():
    A, L = _lab()
    with L.lock:
        me = _me(L)
        _ready(L)
        w = L.w
        sibs = set(L.sim.siblings(me.id))
        rows = []
        for oid, r in w.out.get(me.id, {}).items():
            o = w.chars.get(oid)
            if not o or o.status not in ("active",) or (r.familiarity < 10 and oid not in sibs):
                continue
            rows.append(contact_row(L, me, oid))
        for s in sibs:
            if not any(x["id"] == s for x in rows):
                rows.append(contact_row(L, me, s))
        team = {m for g in me.memberships if w.groups[g]["kind"] == "team" for m in w.groups[g]["members"]}
        groups = {"Family": [], "Favorites": [], "Friends": [], "Teammates": [], "Rivals": [], "People you know": []}
        for x in sorted(rows, key=lambda x: (-x["affection"], x["name"])):
            if x["id"] in sibs:
                groups["Family"].append(x)
            elif x["partner"] or x["affection"] >= 70 or x["crush"]:
                groups["Favorites"].append(x)
            elif x["rivalry"] >= 40 or x["affection"] <= -30:
                groups["Rivals"].append(x)
            elif x["affection"] >= w.rules["rel.friend_threshold"]:
                groups["Friends"].append(x)
            elif x["id"] in team:
                groups["Teammates"].append(x)
            else:
                groups["People you know"].append(x)
        parents = [{"id": p["id"], "name": p["name"], "full": p["full"], "parent": True} for p in messages.parent_names(L.sim)]
        return {"groups": [{"name": k, "people": v} for k, v in groups.items() if v], "parents": parents}


@router.get("/api/phone/contact/{cid}")
def phone_contact(cid: str):
    A, L = _lab()
    with L.lock:
        me = _me(L)
        _ready(L)
        w = L.w
        o = w.chars.get(cid)
        if not o:
            raise HTTPException(404, "unknown person")
        r = w.rels.get((me.id, cid))
        row = contact_row(L, me, cid)
        mems = [{"text": pov.second_person(m["text"], me), "date": calm.label(m["day"]), "valence": m["valence"]}
                for m in sorted(me.memories, key=lambda m: -m["day"]) if cid in m.get("with", [])][:8]
        shared = []
        for eid in w.history.by_char.get(me.id, [])[::-1]:
            e = w.history.events.get(eid)
            if e and cid in e["actors"] + e["targets"] and e["importance"] >= 5 and not private(e, me.id) and e["type"] != "text":
                shared.append({"id": eid, "date": calm.label(e["day"]), "text": pov.event_line(w, e, me.id)})
                if len(shared) >= 10:
                    break
        teams = [w.groups[g]["name"] for g in o.memberships]
        return dict(row, bio=o.bio, archetype=o.archetype, pronouns=o.pronouns, teams=teams, school=o.school,
                    since=calm.label(r.met_day) if r and r.met_day is not None else None,
                    feel=_feel(r.affection if r else 0), seems=_feel(r.perceived if r else 0, "perceived"),
                    trust=round(r.trust) if r else 0, respect=round(r.respect) if r else 0, familiarity=round(r.familiarity) if r else 0,
                    memories=mems, shared=shared, text_options=messages.text_options(L.sim, cid) if row["has_number"] else [],
                    partner_of=o.flags.get("partner") and w.chars[o.flags["partner"]].first if o.flags.get("partner") in w.chars else None,
                    vibe=chat_vibe(L.sim, cid), who=knowing.profile(L.sim, me.id, cid))


# --- pets -----------------------------------------------------------------------------------

@router.get("/api/phone/pets")
def phone_pets():
    A, L = _lab()
    with L.lock:
        me = _me(L)
        _ready(L)
        w = L.w
        hp = pets.household_pets(w, me.household_id or "")
        kids = [{"id": k, "first": w.chars[k].first, "me": k == me.id} for k in pets._kids(L.sim, hp[0])] if hp else []
        return {"pets": [pets.view(L.sim, p) for p in hp], "kids": kids, "approved": w.meta.get("pet_approved"),
                "species": {k: {"label": v["label"], "breeds": v["breeds"], "coats": v["coats"],
                                "duties": [{"id": d, **{kk: pets.DUTIES[d][kk] for kk in ("label", "hint", "when")}} for d in v["duties"]]}
                            for k, v in pets.SPECIES.items()},
                "asked": w.meta.get("pet_asked")}


@router.post("/api/phone/pet/{pid}/setup")
def phone_pet_setup(pid: str, body: dict = Body(...)):
    A, L = _lab()
    L.guard()
    with L.lock:
        _me(L)
        if pid not in pets.pets(L.w):
            raise HTTPException(404, "no such pet")
        try:
            pets.set_duties(L.sim, pid, body.get("duties") or {})
        except ValueError as e:
            raise HTTPException(422, str(e))
        L.autosave()
        return pets.view(L.sim, pets.pets(L.w)[pid])


@router.post("/api/phone/pet/{pid}/do")
def phone_pet_do(pid: str, body: dict = Body(...)):
    A, L = _lab()
    L.guard()
    with L.lock:
        me = _me(L)
        act = body.get("activity")
        spec = pets.ACTIVITIES.get(act)
        if not spec:
            raise HTTPException(422, "unknown activity")
        try:
            if spec.get("quick"):
                out = pets.quick(L.sim, pid, act)
                L.autosave()
                return dict(out, done=True)
            q = pets.queue(L.sim, pid, act, body.get("trick"))
        except ValueError as e:
            raise HTTPException(409, str(e))
        sim = L.sim
        from .calendar import DECISION_SLOTS
        ph = sim.current_phase()
        if body.get("now") and ph in DECISION_SLOTS and me.id in sim.slot_actors(ph):
            res = sim.options_for(me.id)
            hit = None
            if res:
                slot, dec = res
                hit = next((i for i, cd in enumerate(dec["cands"]) if cd.a["id"] == q["action"]
                            and isinstance(cd.extra, dict) and cd.extra.get("pet") == pid), None)
            if hit is not None:
                needs0, mood0 = dict(me.needs), me.mood
                rels0 = {o: (r.affection, r.attraction, r.trust) for o, r in L.w.out.get(me.id, {}).items()}
                before = L.w.history.next_event
                sim.step()  # the queued plan is picked up in this slot (with the trick, if any)
                evs = [e for eid, e in L.w.history.events.items() if eid >= before and
                       (me.id in e["actors"] or me.id in e["targets"] or me.id in e.get("involved", []))]
                L.autosave()
                return {"done": True, "lines": _lines(L, evs, me), "chips": _chips(L, me, needs0, mood0, rels0),
                        "pet": pets.view(sim, pets.pets(L.w)[pid])}
        L.autosave()
        return {"done": False, "queued": q["label"], "note": f"{q['label']}: planned for your next free time."}


@router.post("/api/phone/pet/ask")
def phone_pet_ask(body: dict = Body(...)):
    A, L = _lab()
    L.guard()
    with L.lock:
        _me(L)
        try:
            out = pets.ask_for_pet(L.sim, body.get("species", "dog"))
        except ValueError as e:
            raise HTTPException(409, str(e))
        L.autosave()
        return out


@router.post("/api/phone/pet/adopt")
def phone_pet_adopt(body: dict = Body(...)):
    A, L = _lab()
    L.guard()
    with L.lock:
        _me(L)
        try:
            out = pets.adopt(L.sim, body.get("species"), body.get("name"), body.get("breed"), body.get("coat"))
        except ValueError as e:
            raise HTTPException(409, str(e))
        L.autosave()
        return out


# --- backups: move a story between your phone and the lab -----------------------------------------

@router.get("/api/phone/backup")
def phone_backup():
    """Your whole story in one file: the world and everything you wrote for it (storylines, expansions, texting)."""
    from . import backup
    A, L = _lab()
    with L.lock:
        w = L.w
        title = re.sub(r'[\\/:*?"<>|]+', "-", w.meta.get("story", {}).get("title") or "LIFE OS story").strip() or "LIFE OS story"
        data = backup.make(w)
        name = f"{title} - {calm.date_of(w.day).isoformat()}.lifeos"
    return Response(data, media_type="application/octet-stream", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.post("/api/phone/restore")
async def phone_restore(request: Request, keep: int = 0):
    """Open a backup: its world becomes this one, and what you wrote for it joins your storylines. keep=1 (the desktop):
    the story that was open is kept under Saves first."""
    from . import backup
    A, L = _lab()
    data = await request.body()
    try:
        w, b = backup.read(data)
    except ValueError as e:
        raise HTTPException(422, str(e))
    with L.lock:
        kept = None
        if keep and L.w.meta.get("protagonist"):
            old = L.w.meta.get("story", {}).get("title") or "Your story"
            kept = L.store.save_world(L.w, f"{old} - before loading a backup ({calm.label(L.w.day)})"[:120], notes="kept when a backup was loaded")
    got = backup.install(b)
    with L.lock:
        L.replace_world(w)
    A._dialogue_changed(L)
    p = w.meta.get("protagonist")
    return {"ok": True, "story": bool(p), "name": w.chars[p].name if p in w.chars else None, "date": calm.label(w.day),
            "title": w.meta.get("story", {}).get("title"), "storylines": got, "said": backup.summary(got),
            "newer": backup.newer_note(b), "kept": kept}


# --- playing on your phone ------------------------------------------------------------------------

def lan_ips() -> list:
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    return sorted(ip for ip in ips if not ip.startswith("127."))


@router.get("/api/net")
def net_info():
    import os
    port = int(os.environ.get("LIFEOS_PORT", "8765"))
    lan = os.environ.get("LIFEOS_LAN") == "1"
    return {"lan": lan, "port": port, "urls": [f"http://{ip}:{port}/#/m" for ip in lan_ips()] if lan else [],
            "host": socket.gethostname()}
