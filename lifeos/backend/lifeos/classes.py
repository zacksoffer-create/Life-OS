"""Your classes: a real schedule each school year, teachers, per-class grades, and playable quizzes and tests.

The engine already runs quizzes (every two weeks), midterms and finals for everyone, scored from academic skill,
aptitude, recent studying, mood and stress. For the protagonist, a quiz day brings a "class_quiz" moment: take it yourself
(a trivia round in that class's subject) or let it ride. A played round counts toward that test: the exam score blends
your round with your character's preparation (institutions.exam), and the class's grade remembers it.
"""
from __future__ import annotations

import json
import os
import zlib

from . import calendar as calm
from .catalogs import DATA_DIR, _base

_DATA = None
LETTERS = [(93, "A"), (90, "A-"), (87, "B+"), (83, "B"), (80, "B-"), (77, "C+"), (73, "C"), (70, "C-"), (67, "D+"), (60, "D"), (0, "F")]


def data() -> dict:
    global _DATA
    if _DATA is None:
        with open(os.path.join(DATA_DIR, "classes.json"), encoding="utf-8") as f:
            _DATA = json.load(f)
    return _DATA


def _h(*p) -> int:
    return zlib.crc32(":".join(str(x) for x in p).encode())


def letter(pct: float) -> str:
    return next(l for t, l in LETTERS if pct >= t)


def store(w) -> dict:
    s = w.meta.setdefault("classes", {})
    s.setdefault("sched", {})
    s.setdefault("quizzes", {})
    return s


def _year_key(sim, c) -> str:
    d = calm.date_of(sim.w.day)
    year = d.year if d.month >= 8 else d.year - 1
    return f"{c.grade or 9}:{year}"


def _teacher(sim, cls_id, key, taken=None) -> str:
    names = _base("people.json")["names"]["last"]
    i = _h(sim.w.gen_seed, key, cls_id) % len(names)
    while taken is not None and names[i] in taken and len(taken) < len(names):
        i = (i + 7) % len(names)
    if taken is not None:
        taken.add(names[i])
    title = ["Mr.", "Ms.", "Mrs.", "Dr."][_h(sim.w.gen_seed, "t", key, cls_id) % 4]
    return f"{title} {names[i]}"


def schedule(sim, c) -> list:
    """This school year's classes (made once a year, then kept)."""
    w = sim.w
    st = store(w)
    key = _year_key(sim, c)
    if key in st["sched"]:
        return st["sched"][key]
    d = data()
    grade = c.grade or 9
    rows = d["grades"]["college" if grade >= 13 else str(min(12, max(9, grade)))]
    honors = c.aptitudes.get("academic", 50) >= d["honors_bar"]["academic"] or c.gpa >= d["honors_bar"]["gpa"]
    out = []
    taken: set = set()
    for r in rows:
        spec = r["hon"] if honors else r["std"]
        cid = f"{r['slot']}"
        out.append({"id": cid, "name": spec[0], "subject": spec[1], "math": spec[2] if len(spec) > 2 else None,
                    "teacher": _teacher(sim, cid, key, taken), "honors": honors and r["hon"] != r["std"]})
    if grade <= 12:
        picks = [e for e in d["electives"] if e["if"] and max(c.skills.get(e["if"], 0), c.interests.get(e["if"], 0)) >= 40]
        picks.sort(key=lambda e: -max(c.skills.get(e["if"], 0), c.interests.get(e["if"], 0)))
        e = picks[0] if picks else next(e for e in d["electives"] if e["if"] is None)
        out.append({"id": "elective", "name": e["class"][0], "subject": e["class"][1], "math": None,
                    "teacher": _teacher(sim, "elective", key, taken), "honors": False})
    st["sched"][key] = out
    keep = sorted(st["sched"])[-8:]
    st["sched"] = {k: st["sched"][k] for k in keep}
    return out


def quiz_context(sim, c, item) -> dict:
    """Which class a quiz is in (quizzes rotate through your schedule), or every class for a midterm or final."""
    sched = schedule(sim, c)
    core = [x for x in sched if x["subject"] != "health"] or sched
    weight = item.get("weight", 1)
    if weight >= 2:
        subs = [x["subject"] for x in core]
        maths = [x["math"] for x in core if x["math"]] or ["algebra1"]
        return {"exam": item["name"], "class_id": "all", "class_name": "all your classes", "teacher": "", "subjects": subs,
                "math_courses": maths, "n": 6 + 2 * min(2, weight - 1), "weight": weight,
                "quiz_line": f"It covers all your classes: {len(subs)} subjects, {6 + 2 * min(2, weight - 1)} questions."}
    num = int("".join(ch for ch in str(item.get("id", "")) if ch.isdigit()) or 0)
    cls = core[num % len(core)]
    return {"exam": item["name"], "class_id": cls["id"], "class_name": cls["name"], "teacher": cls["teacher"],
            "subjects": [cls["subject"]], "math_courses": [cls["math"] or "algebra1"], "n": 5, "weight": weight,
            "quiz_line": "Five questions, fifteen seconds each."}


def record(w, class_id, pct, exam=None):
    q = store(w)["quizzes"]
    if class_id == "all":
        for k in list(q) or []:
            q[k] = (q[k] + [pct])[-12:]
        q.setdefault("_tests", []).append(pct)
        return
    q[class_id] = (q.get(class_id, []) + [pct])[-12:]


def grades(sim, c) -> list:
    """Each class's grade: your GPA, how well your talents fit the subject, the quizzes you played in it, and its class games."""
    w = sim.w
    q = store(w)["quizzes"]
    games = store(w).get("games", {})
    yk = _year_key(sim, c)
    base = 55 + c.gpa * 10.5
    fit = {"math": ("academic", "technical"), "biology": ("academic",), "chemistry": ("academic", "technical"),
           "physics": ("academic", "technical"), "english": ("academic", "creativity"), "us_history": ("academic",),
           "world_history": ("academic",), "government": ("academic",), "spanish": ("academic", "charisma"),
           "health": ("athletic",), "art": ("creativity",), "music": ("creativity",), "tech": ("technical",),
           "psychology": ("academic", "charisma"), "economics": ("academic",)}
    out = []
    for cls in schedule(sim, c):
        apts = fit.get(cls["subject"], ("academic",))
        lean = sum(c.aptitudes.get(a, 50) - 50 for a in apts) / len(apts) * 0.08
        noise = (_h(w.gen_seed, c.id, cls["name"]) % 50) / 10 - 2.5
        pct = base + max(-6, min(6, lean)) + noise
        played = q.get(cls["id"], [])
        if played:
            avg = sum(played) / len(played) * 100
            pct = pct * 0.7 + avg * 0.3
        cg = games.get(f"{yk}|{cls['id']}", [])
        if cg:  # the quick class games you went for: a small nudge, up to +3 or -2
            pct += max(-2.0, min(3.0, (sum(cg) / len(cg) - 0.5) * 8))
        if cls["subject"] == "health":
            pct = max(pct, 85 + (c.aptitudes.get("athletic", 50) - 50) * 0.2)
        pct = round(max(40, min(100, pct)), 1)
        out.append({**cls, "pct": pct, "letter": letter(pct), "quizzes": len(played),
                    "quiz_avg": round(sum(played) / len(played) * 100) if played else None,
                    "games": len(cg), "games_won": sum(1 for x in cg if x >= 0.8)})
    return out


def blend_exam(c, day, model_score) -> tuple[float, list] | None:
    """If you played today's quiz yourself, the score is your round blended with your preparation."""
    qp = c.flags.get("quiz_played")
    if not qp or qp.get("day") != day:
        return None
    mine = qp["pct"] * 100
    s = round(0.55 * mine + 0.45 * model_score, 1)
    return s, [("your quiz round", round(0.55 * mine, 2)), ("your preparation", round(0.45 * model_score, 2))]
