"""Your day at a glance, for the phone: where you are in it, what needs you, and what's coming this week. Plus the reasons
behind each choice, sorted into what you should, want to and could do.

Nothing here changes the simulation. It reads what the game already tracks (the day's slots, your teams, the calendar,
texts waiting on you, pet chores, who you've lost touch with) and says it in plain words. The one thing it writes is a plan:
save a choice for later today and it's picked for you when that part of the day comes (engine.py honors the slot).
"""
from __future__ import annotations

from . import calendar as calm

LABEL = {"dawn": "Morning", "classes": "Class", "lunch": "Lunch", "after_school": "After school", "day": "Day", "evening": "Evening",
         "night": "Night"}
SHORT = {"dawn": "Morning", "classes": "Class", "lunch": "Lunch", "after_school": "After", "day": "Day", "evening": "Evening",
         "night": "Night"}
ICON = {"dawn": "leaf", "classes": "book", "lunch": "bowl", "after_school": "clock", "day": "tree", "evening": "star", "night": "moon"}
DID = {"study": "studied", "study_at_lunch": "studied", "practice_skill": "worked on it", "train": "lifted", "hobby": "hobby time",
       "rest": "rested", "sit_alone": "headphones", "attend_practice": "practice", "practice": "practice", "game": "game",
       "work_shift": "work", "job": "work", "pet_walk": "walked the dog", "pet_park": "dog park", "pet_play": "pet time",
       "pet_time": "pet time", "pet_train": "pet tricks", "exam": "quiz", "tryout": "tryouts", "show": "show"}
# actions you can save for later today
LATER_OK = {"study", "hobby", "rest", "practice_skill", "train", "pet_time", "pet_walk", "pet_park", "pet_play", "pet_train",
            "family_time", "chat_online", "hang_out", "date", "help_friend", "apologize"}
DUTY_ACTION = {"walk": "pet_walk", "play": "pet_play", "exercise": "pet_walk"}
CHORE = {"feed_am": "{pet} needs breakfast", "feed_pm": "{pet} needs dinner", "walk": "{pet} needs a walk", "bath": "{pet} needs a bath",
         "litter": "{pet}'s litter box", "brush": "{pet} needs brushing", "cage": "{pet}'s cage needs cleaning"}
RISKY = {"confront", "spread_rumor", "prank", "sneak_out", "tease", "gossip", "break_up"}


def _when(n: int, day: int) -> str:
    if n <= 0:
        return "today"
    if n == 1:
        return "tomorrow"
    if n < 7:
        return calm.date_of(day + n).strftime("%A")
    return f"in {n} days"


def _me(sim):
    w = sim.w
    return w.chars[w.meta["protagonist"]]


def _teams(sim, me) -> list:
    w = sim.w
    return [g for g in me.memberships if w.groups.get(g, {}).get("kind") in ("team", "production")]


def _in_season(sim, g) -> bool:
    try:
        return bool(sim.institutions.in_season(sim.w.groups[g]))
    except Exception:  # noqa: BLE001  a group without a season
        return sim.w.groups[g].get("kind") == "production"


def _close(sim, me, cid, need=50) -> bool:
    w = sim.w
    r = w.rels.get((me.id, cid))
    return cid in sim.siblings(me.id) or (r is not None and r.affection >= need)


def _birthday_in(w, c, n) -> bool:
    return (w.day + n - c.birth_day) % 365 == 0


def _calendar(sim, me, lo, hi, upcoming=False) -> list:
    """What's on the calendar that's yours, from lo to hi days out: your games and shows, school tests and dances, tryouts
    you'd care about, breaks, and the birthdays of people close to you."""
    w = sim.w
    cal = sim.cat.world["calendar"]
    mine = set(me.memberships)
    phases = sim.phases()
    out = []
    for i in w.calendar:
        n = i["day"] - w.day
        if not lo <= n <= hi:
            continue
        if upcoming and n == 0 and i.get("slot") in phases and phases.index(i["slot"]) < w.phase:
            continue  # already happened today
        k = i["kind"]
        g = i.get("group")
        if k in ("game", "show", "season_end") and g not in mine:
            continue
        if k == "season_end":
            continue
        if k == "exam" and i.get("school", "hchs") != me.school:
            continue
        if k in ("tryout", "audition"):
            grp = w.groups.get(g) if g else None
            skill = (grp or {}).get("skill")
            if g in mine or (skill and me.interests.get(skill, 0) < 55 and k == "tryout") or (k == "audition" and me.interests.get("drama", 0) < 55):
                continue
            if k == "tryout" and grp and grp["kind"] == "team":
                from . import sports
                if not sports.can_play(me, grp) or sports.clash(w, me, grp):
                    continue  # the other side's team, or a second sport the same season
        if k in ("dance", "graduation") and (me.grade or 0) > 12:
            continue
        icon = {"game": "trophy", "show": "star", "exam": "book", "dance": "sparkle", "tryout": "ball", "audition": "star",
                "election": "people", "graduation": "grad", "date": "heart"}.get(k, "clock")
        name = i.get("name") or k
        if k == "game" and g in w.groups:
            try:
                from .sports import opponent_name
                last = str(i.get("key", "")).split(":")[-1]
                name = f"Game vs {opponent_name(sim, w.groups[g], int(last) if last.isdigit() else 1)}"
            except Exception:  # noqa: BLE001  fall back to the calendar's own name
                pass
        if k == "exam" and i.get("weight", 1) >= 2:
            name = name if any(x in name.lower() for x in ("midterm", "final")) else f"{name} (big test)"
        out.append({"n": n, "day": i["day"], "kind": k, "icon": icon, "label": name, "group": g, "weight": i.get("weight", 1)})
    for n in range(lo, hi + 1):
        d = w.day + n
        b = calm.break_name(d, cal)
        if b and calm.break_name(d - 1, cal) != b:
            out.append({"n": n, "day": d, "kind": "break", "icon": "tree", "label": f"{b} starts"})
    people = [o for o in w.out.get(me.id, {}) if o in w.chars and w.chars[o].status == "active" and w.chars[o].role != "staff"]
    for o in people:
        if not _close(sim, me, o):
            continue
        for n in range(lo, hi + 1):
            if _birthday_in(w, w.chars[o], n):
                out.append({"n": n, "day": w.day + n, "kind": "birthday", "icon": "sparkle", "label": f"{w.chars[o].first}'s birthday", "who": o})
    out.sort(key=lambda x: (x["n"], x["kind"] != "game"))
    return out


# ---------------------------------------------------------------------------------------- the day

def strip(sim, me) -> list:
    """Today's parts of the day: what you did, where you are, and what's coming."""
    w = sim.w
    from .calendar import DECISION_SLOTS
    phases = sim.phases()
    now = w.phase
    evs = [w.history.events[e] for e in w.history.by_char.get(me.id, [])[-60:] if e in w.history.events]
    evs = [e for e in evs if e["day"] == w.day]
    mine = set(me.memberships)
    today_cal = [i for i in w.calendar if i["day"] == w.day and (
        (i["kind"] in ("game", "show") and i.get("group") in mine) or (i["kind"] == "exam" and i.get("school", "hchs") == me.school))]
    practice = [g for g in _teams(sim, me) if _in_season(sim, g)] and calm.is_school_day(w.day, sim.cat.world["calendar"])
    q = w.meta.get("control", {}).get("queued") or {}
    out = []
    for i, ph in enumerate(phases):
        s = {"phase": ph, "label": SHORT.get(ph, ph), "icon": ICON.get(ph, "clock"), "decide": ph in DECISION_SLOTS, "note": ""}
        if i < now:
            s["state"] = "done"
            did = [e for e in evs if e.get("slot") == ph and e["type"] not in ("milestone", "text")]
            if did:
                e = max(did, key=lambda e: e["importance"])
                other = next((x for x in e["actors"] + e["targets"] if x != me.id and x in w.chars), None)
                key = e["type"].split(".")[-1] if e["type"].startswith("interact.") else e["type"]
                s["note"] = f"w/ {w.chars[other].first}" if other and w.chars[other].role != "staff" else DID.get(key, "")
        else:
            s["state"] = "now" if i == now else "later"
            hit = next((x for x in today_cal if x.get("slot") == ph), None)
            if hit:
                s.update(note={"game": "game", "show": "show", "exam": "quiz"}.get(hit["kind"], hit["kind"]),
                         icon={"game": "trophy", "show": "star", "exam": "book"}.get(hit["kind"], "clock"), kind="event", plan=hit.get("name"))
            elif ph == "after_school" and practice:
                s.update(note="practice", icon="ball", kind="practice")
            elif ph == "classes":
                s["note"] = "class"
            elif ph == "night":
                s["note"] = "sleep"
            elif q and q.get("day") == w.day and q.get("slot") == ph:
                s.update(note="planned", kind="planned", plan=plan_label(sim, q))
            elif s["decide"] and ph == "lunch" and i != now and w.meta.get("control", {}).get("auto_lunch", False):
                s["note"] = "usual table"  # lunch runs on autopilot
            elif s["decide"]:
                s["note"] = "now" if i == now else "open"
            if i == now and s["note"] in ("open", ""):
                s["note"] = "now"
        out.append(s)
    return out


def plate(sim, me) -> list:
    """Everything that needs you right now, from every corner of the game, most pressing first."""
    from . import messages, pets
    w = sim.w
    items = []
    # texts waiting on an answer
    if "phone" in w.meta:
        for t in [t for t in messages.threads_view(sim) if t["needs_reply"]][:3]:
            cid = t["id"][3:] if t["id"].startswith("dm:") else None
            if cid in w.chars:
                title = f"{w.chars[cid].first}'s waiting on you"
            elif t["id"] == "family":
                title = "The family chat wants an answer"
            else:
                title = f"{t['title']} chat wants an answer"
            last = t["last"] if len(t["last"]) <= 46 else t["last"][:44] + "…"
            items.append({"id": f"text:{t['id']}", "kind": "text", "icon": "chat", "title": title, "sub": f"“{last}” · {t['at']}",
                          "go": f"phone/thread/{t['id']}", "cta": "Reply", "rank": 0})
    # pet chores that are yours today and not done
    for p in pets.pets(w).values():
        if p.get("household") != me.household_id or p.get("status") != "home" or me.location == "away":
            continue
        v = pets.view(sim, p)
        for d in v["duties"]:
            if d["due"] and d["today"] == me.id and not d["done"]:
                items.append({"id": f"pet:{p['id']}:{d['id']}", "kind": "pet", "icon": "paw", "title": CHORE.get(d["id"], "{pet}: " + d["label"].lower()).format(pet=p["name"]),
                              "sub": f"Your chore today. A quick tap on Home, it doesn't use up your time", "go": "home", "cta": "Do it", "rank": 1})
    # your group's plans for later today (yours to join or skip)
    from . import squad
    sp = squad.plan(sim)
    if sp and not sp.get("joined"):
        sq = squad.state(sim)
        when = {"evening": "tonight", "after_school": "after school", "day": "today"}.get(sp["slot"], "later")
        items.append({"id": f"squad:{w.day}", "kind": "people", "icon": "people",
                      "title": f"{sq['name'].capitalize()}: {squad.label(sim, sp['act'], sq).split(' with ')[0].lower()} {when}",
                      "sub": "It'll be in your choices then. Join or skip, no pressure", "rank": 3})
    # tests, games, tryouts and dances coming right up
    for c in _calendar(sim, me, 0, 3, upcoming=True):
        when = _when(c["n"], w.day)
        if c["kind"] == "exam" and (c["n"] <= 1 or c["weight"] >= 2):
            items.append({"id": f"cal:{c['kind']}:{c['day']}", "kind": "school", "icon": "book", "title": f"{c['label']} {when}",
                          "sub": f"GPA {me.gpa:.2f}" + (" · study tonight" if c["n"] == 1 else ""), "go": "me", "cta": "Classes", "rank": 2})
        elif c["kind"] in ("game", "show") and c["n"] <= 1:
            items.append({"id": f"cal:{c['kind']}:{c['day']}", "kind": "game", "icon": c["icon"], "title": f"{c['label']} {when}",
                          "sub": "Get some rest the night before" if c["n"] == 1 else "Today's the day", "rank": 2})
        elif c["kind"] in ("tryout", "audition") and c["n"] <= 3:
            items.append({"id": f"cal:{c['kind']}:{c['day']}", "kind": "game", "icon": c["icon"], "title": f"{c['label']} {when}",
                          "sub": "Sign up after school if you want a spot", "rank": 2})
        elif c["kind"] == "birthday" and c["n"] <= 1:
            items.append({"id": f"bday:{c['who']}", "kind": "people", "icon": "sparkle", "title": f"{c['label']} {when}",
                          "sub": "Send them something", "go": f"phone/contact/{c['who']}", "cta": "Text", "rank": 1})
    dance = next((i for i in w.calendar if i["kind"] == "dance" and i.get("ask_from", 10**9) <= w.day < i["day"]), None)
    if dance and (me.grade or 0) <= 12 and not (w.dance_dates.get(dance.get("key"), {}) or {}).get(me.id):
        items.append({"id": f"dance:{dance['day']}", "kind": "people", "icon": "heart", "title": f"{dance['name']} {_when(dance['day'] - w.day, w.day)}",
                      "sub": "You don't have a date yet", "rank": 3})
    # the person you're with, when it's been a few days
    partner = me.flags.get("partner")
    pr = w.rels.get((me.id, partner)) if partner in w.chars else None
    if pr and pr.last_day >= 0 and w.day - pr.last_day >= 3:
        gap = w.day - pr.last_day
        items.append({"id": f"partner:{partner}", "kind": "people", "icon": "heart", "title": f"{w.chars[partner].first} misses you",
                      "sub": f"{gap} days since you two talked", "go": f"phone/thread/dm:{partner}", "cta": "Text", "rank": 2})
    # friends you've lost touch with
    drift = []
    fam = set(sim.siblings(me.id))
    for o, r in w.out.get(me.id, {}).items():
        c = w.chars.get(o)
        if not c or c.status != "active" or c.role == "staff" or o in fam or o == partner or r.affection < 45 or r.last_day < 0:
            continue
        gap = w.day - r.last_day
        if gap >= 7:
            drift.append((r.affection, o, gap, r.peak_affection - r.affection >= 10))
    for _, o, gap, slipping in sorted(drift, reverse=True)[:2]:
        items.append({"id": f"drift:{o}", "kind": "people", "icon": "heart", "title": f"{w.chars[o].first}, {gap} days",
                      "sub": "You two are drifting" if slipping else "You haven't talked in a while", "go": f"phone/contact/{o}", "cta": "Text", "rank": 4})
    if me.needs.get("energy", 100) < 20:
        items.append({"id": "energy", "kind": "you", "icon": "bolt", "title": "You're running on empty", "sub": f"Energy {round(me.needs['energy'])}%. Rest soon.", "rank": 3})
    items.sort(key=lambda x: x["rank"])
    for x in items:
        x.pop("rank", None)
    return items


def week(sim, me) -> list:
    """The next seven days, starting today, with what's on each."""
    w = sim.w
    cal = _calendar(sim, me, 0, 6)
    out = []
    for n in range(7):
        d = calm.date_of(w.day + n)
        out.append({"n": n, "dow": d.strftime("%a").upper(), "num": d.day, "date": calm.label(w.day + n),
                    "school": calm.is_school_day(w.day + n, sim.cat.world["calendar"]),
                    "items": [{"icon": c["icon"], "label": c["label"], "kind": c["kind"]} for c in cal if c["n"] == n]})
    return out


def today(sim) -> dict:
    me = _me(sim)
    return {"strip": strip(sim, me), "plate": plate(sim, me), "week": week(sim, me)}


# ---------------------------------------------------------------------------------------- plans

def plan_label(sim, q) -> str | None:
    """A plan in plain words: what, with whom, and when ("Hanging out with Danny, next time you're free")."""
    if not q:
        return None
    w = sim.w
    verb = {"hang_out": "Hanging out", "date": "Going out", "family_time": "Time"}
    who, act = q.get("target"), q.get("action")
    if q.get("invite"):
        inv = next((i for i in w.meta.get("inbox", []) if i["id"] == q["invite"]), None)
        if inv:
            who, act = inv.get("from"), inv.get("action")
    if q.get("slot") and q.get("day") == w.day:
        when = "tonight" if q["slot"] == "evening" else LABEL.get(q["slot"], q["slot"]).lower()
    else:
        when = "next time you're free"
    if who in w.chars and act in verb:
        return f"{verb[act]} with {w.chars[who].first}, {when}"
    if who in w.chars and act == "ask_out":
        return f"Asking {w.chars[who].first} out, next time you see them"
    if q.get("label"):
        return q["label"] if q.get("slot") else f"{q['label']}, {when}"
    if who in w.chars:
        return f"Plans with {w.chars[who].first}, {when}"
    return None


# ---------------------------------------------------------------------------------------- choices with reasons

def _next_slot(sim) -> str | None:
    """Your next free time today (practice and games don't count: you're busy then)."""
    from .calendar import DECISION_SLOTS
    ph = sim.phases()
    me = sim.w.meta.get("protagonist")
    return next((p for p in ph[sim.w.phase + 1:] if p in DECISION_SLOTS and not (me and sim.committed(me, p))), None)


def annotate(sim, me, opts: list) -> list:
    """Give each choice a group (should / want / could), the reason it's there, and whether it can wait till later today."""
    from . import pets
    w = sim.w
    soon = _calendar(sim, me, 0, 6, upcoming=True)
    exam = next((c for c in soon if c["kind"] == "exam" and c["n"] <= 2), None)
    games = {c["group"]: c for c in soon if c["kind"] == "game"}
    energy = me.needs.get("energy", 100)
    partner = me.flags.get("partner")
    inviters = {i.get("from") for i in w.meta.get("inbox", []) if i.get("status") == "pending"}
    duty_acts = {}
    for p in pets.pets(w).values():
        if p.get("household") == me.household_id and p.get("status") == "home":
            for d in pets.view(sim, p)["duties"]:
                if d["due"] and d["today"] == me.id and not d["done"] and d["id"] in DUTY_ACTION:
                    duty_acts[DUTY_ACTION[d["id"]]] = p["name"]
    nxt = _next_slot(sim)
    own = next((o for o in opts if o.get("own")), None)  # your game or your show is in this part of the day
    busy_next = nxt and any(i.get("slot") == nxt and i["kind"] in ("game", "show") and i.get("group") in me.memberships for i in sim._today)
    for o in opts:
        a, t = o["action"], o.get("target")
        r = w.rels.get((me.id, t)) if t else None
        first = w.chars[t].first if t in w.chars else ""
        grp, why = "could", ""
        if a == "attend_practice":
            grp = "should"
            g = next((g for g in me.memberships if w.groups.get(g, {}).get("name") and w.groups[g]["name"] in (o.get("target_name") or "")), None)
            gm = games.get(g) or next(iter(games.values()), None)
            why = "Coach takes attendance" + (f" · game {_when(gm['n'], w.day)}" if gm else "")
        elif a == "work_shift":
            grp, why = "should", "You're on the schedule"
        elif a in ("study", "study_at_lunch"):
            if exam:
                grp, why = "should", f"{exam['label']} {_when(exam['n'], w.day)}"
            elif me.gpa < 2.6:
                grp, why = "should", f"Your GPA's at {me.gpa:.2f}"
            else:
                why = f"GPA {me.gpa:.2f}"
        elif a in duty_acts:
            grp, why = "should", f"Your chore today · {duty_acts[a]}"
        elif a.startswith("pet_"):
            why = "Time with your pet"
        elif a == "rest":
            grp, why = ("should", f"Energy {round(energy)}%") if energy < 30 else ("could", f"Energy {round(energy)}%")
        elif a == "reply_invite":
            grp, why = "want", "They asked you"
        elif a in ("flirt", "ask_out", "ask_to_dance") and t in w.chars:
            from . import chat
            rd, st = chat.read(sim, t), chat.stage(sim, t)
            if a == "ask_out":
                grp, why = ("want", "They flirt back") if st >= 3 and rd["level"] >= 3 else ("could", f"Risky: {rd['label'].lower()}")
            else:
                grp, why = ("want", rd["label"]) if rd["level"] >= 3 else ("could", "Some signs") if rd["level"] == 2 else \
                    ("could", "Risky: you barely know them" if rd["level"] == -1 else f"Risky: {rd['label'].lower()}")
        elif a in RISKY:
            why = "Risky" if o.get("risk", 0) >= 0.3 else "Could start drama"
        elif a == "sign_up":
            tc = next((c for c in soon if c["kind"] in ("tryout", "audition")), None)
            grp, why = ("want", f"{tc['label']} {_when(tc['n'], w.day)}") if tc else ("could", "Something new")
        elif a in ("go_to_party", "attend_event", "throw_party"):
            grp, why = "want", "Everyone's going" if a == "go_to_party" else "A night out"
        elif t and r is not None:
            gap = w.day - r.last_day if r.last_day >= 0 else 0
            if t == partner:
                grp, why = "want", "You're dating"
            elif t in inviters:
                grp, why = "want", f"{first} asked you"
            elif t in sim.siblings(me.id):
                why = "Family"
            elif r.affection >= 45 and gap >= 7:
                grp, why = "want", f"{gap} days since you talked"
            elif r.attraction >= 50:
                grp, why = "want", "You're into them"
            elif r.affection >= 60:
                grp, why = "want", "Close friend"
            elif r.familiarity < 25:
                why = "You barely know them"
            elif r.rivalry >= 40:
                why = "Your rival"
            else:
                why = "Friend" if r.affection >= 30 else "Someone you know"
        if not why:
            why = {"social": "Friends", "romance": "Romance", "academic": "School", "leisure": "Downtime", "family": "Family",
                   "activity": "Getting better", "obligation": "Commitment", "achievement": "Big move", "risk": "Risky"}.get(o.get("category"), "")
        if own is not None:
            if o is own:
                grp, why = "should", (f"Your game vs {o['opponent']}" if o.get("opponent") else "Your game today") if o["own"] == "game" else "You're in the show"
            else:
                grp, why = "could", "You'd miss your game" if own["own"] == "game" else "You'd miss the show"
        o["group"], o["reason"] = grp, why
        o["later"] = f"Save for {LABEL.get(nxt, 'later').lower()}" if nxt and a in LATER_OK and not busy_next else None
    for o in opts:
        o["section"] = section_of(o["action"])
    rank = {"should": 0, "want": 1, "could": 2}
    return sorted(opts, key=lambda o: (rank[o["group"]], o is not own))


SECTIONS = {
    "people": ("hang_group", "hang_out", "date", "sit_with", "family_time", "reply_invite", "flirt", "ask_out", "ask_to_dance", "help_friend",
               "introduce", "mentor", "staff_chat", "apologize"),
    "out": ("attend_event", "go_to_party", "spectate", "throw_party", "sign_up"),
    "trouble": ("confront", "prank", "tease", "gossip", "spread_rumor", "sneak_out", "break_up", "quit_group"),
}


def section_of(action: str) -> str:
    """Where a choice goes on the phone: with friends, on your own, go somewhere, or the trouble (behind More)."""
    for k, acts in SECTIONS.items():
        if action in acts:
            return k
    return "solo"


def save_for_later(sim, opt: dict) -> dict:
    """Plan a choice for the next part of today you get to decide in. It's picked for you then."""
    w = sim.w
    nxt = _next_slot(sim)
    if not nxt:
        raise ValueError("there's no more free time today")
    q = w.meta.get("control", {}).get("queued")
    if q and (q.get("invite") or q.get("agreed")):
        raise ValueError(f"you already have plans: {q.get('label') or 'saying yes to an invite'}")
    plan = {"action": opt["action"], "day": w.day, "slot": nxt, "label": f"{opt['text']} ({LABEL[nxt].lower()})"}
    if opt.get("target"):
        plan["target"] = opt["target"]
    if opt.get("pet"):
        plan["pet"] = opt["pet"]
    w.meta.setdefault("control", {})["queued"] = plan
    return plan
