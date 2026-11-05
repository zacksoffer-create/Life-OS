"""Time: days, phases and the yearly institutional calendar.

Day 0 is the first day of the first school year. Each day runs a fixed list of phases.
School days:   dawn -> classes -> lunch* -> after_school* -> night
Other days:    dawn -> day* -> evening* -> night
(* = decision slots where every character chooses an action)
Weekly, term and yearly processing hang off 'night'.
"""
from __future__ import annotations

import datetime as dt
import functools

SCHOOL_PHASES = ["dawn", "classes", "lunch", "after_school", "evening", "night"]  # after school: practice if you're on a team; evening: yours
FREE_PHASES = ["dawn", "day", "evening", "night"]
DECISION_SLOTS = {"lunch", "after_school", "day", "evening"}
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

START = dt.date(2010, 9, 1)  # a Wednesday: the first day of school, fall 2010


@functools.lru_cache(maxsize=None)
def date_of(day: int) -> dt.date:
    return START + dt.timedelta(days=day)  # (cached: the scheduler asks about the same days millions of times)


def weekday(day: int) -> int:
    return date_of(day).weekday()


def day_of(date: dt.date) -> int:
    return (date - START).days


def school_year_of(day: int) -> int:
    d = date_of(day)
    return d.year - START.year if (d.month, d.day) >= (9, 1) else d.year - START.year - 1


def md_to_day(year: int, md) -> int:
    m, d = md
    y = START.year + year if m >= 9 else START.year + year + 1
    try:
        date = dt.date(y, m, d)
    except ValueError:
        date = dt.date(y, m, 28)
    return day_of(date)


def in_range(day: int, year: int, start_md, end_md) -> bool:
    a = md_to_day(year, start_md)
    b = md_to_day(year, end_md)
    if b < a:
        b = md_to_day(year + 1, end_md) if start_md[0] < 9 else b
    return a <= day <= b


def break_name(day: int, cal: dict) -> str | None:
    y = school_year_of(day)
    for b in cal["breaks"]:
        a = md_to_day(y, b["from"])
        z = md_to_day(y, b["to"])
        if z < a:
            z = md_to_day(y + 1, b["to"]) if b["from"][0] >= 9 and b["to"][0] < 9 else z
        if a <= day <= z:
            return b["name"]
    return None


def is_school_day(day: int, cal: dict) -> bool:
    return weekday(day) < 5 and break_name(day, cal) is None


def phases_for(day: int, cal: dict) -> list[str]:
    return SCHOOL_PHASES if is_school_day(day, cal) else FREE_PHASES


def term_label(day: int, cal: dict) -> str:
    b = break_name(day, cal)
    if b:
        return b
    d = date_of(day)
    return "Fall term" if d.month >= 9 else "Spring term"


def label(day: int) -> str:
    d = date_of(day)
    return f"{WEEKDAYS[d.weekday()]}, {d.strftime('%b')} {d.day}, {d.year}"


def next_school_day(day: int, cal: dict) -> int:
    for k in range(0, 21):
        if is_school_day(day + k, cal):
            return day + k
    return day


def next_weekday(day: int, wd: int) -> int:
    return day + ((wd - weekday(day)) % 7)


def build_year(world, cat, year: int, only: set | None = None) -> list[dict]:
    """Every scheduled institutional event for one school year (or just for the groups in `only`)."""
    cal = cat.world["calendar"]
    items: list[dict] = []
    y0 = md_to_day(year, cal["school_year_start"])
    y1 = md_to_day(year + 1, cal["school_year_start"]) - 1

    def slot_for(d: int) -> str:
        return "after_school" if is_school_day(d, cal) else ("evening" if weekday(d) >= 5 else "day")

    for g in world.groups.values():
        if only is not None and g["id"] not in only:
            continue
        if only is None and g.get("school") == "college":
            continue
        if g["kind"] == "team":
            s_start = md_to_day(year, g["season"]["start"])
            s_end = md_to_day(year, g["season"]["end"])
            if s_end < s_start:
                s_end = md_to_day(year + 1, g["season"]["end"]) if g["season"]["start"][0] >= 9 else s_end
            t = next_school_day(md_to_day(year, g["tryout"]), cal)
            items.append({"day": t, "kind": "tryout", "group": g["id"], "slot": "after_school",
                          "name": f"{g['name']} tryouts", "key": f"tryout:{g['id']}:{year}",
                          "signup_from": max(y0, t - 21) if t - 21 >= y0 else y0})
            items.append({"day": s_end, "kind": "season_end", "group": g["id"], "slot": None,
                          "name": f"{g['name']} season ends", "key": f"season_end:{g['id']}:{year}"})
            gd = next_weekday(t + 6, g["game_day"])
            n = 0
            while gd <= s_end:
                if break_name(gd, cal) is None:
                    n += 1
                    items.append({"day": gd, "kind": "game", "group": g["id"], "slot": slot_for(gd) if g["game_day"] < 5 else "day",
                                  "name": f"{g['name']} game {n}", "key": f"game:{g['id']}:{year}:{n}"})
                gd += 7
        elif g["kind"] == "production":
            for p in g["productions"]:
                a = next_school_day(md_to_day(year, p["audition"]), cal)
                s = md_to_day(year, p["show"])
                s = s if weekday(s) == 4 else next_weekday(s, 4)
                items.append({"day": a, "kind": "audition", "group": g["id"], "slot": "after_school",
                              "name": f"Auditions for {p['name']}", "production": p["id"], "production_name": p["name"],
                              "key": f"audition:{p['id']}:{year}", "signup_from": max(y0, a - 14)})
                items.append({"day": s, "kind": "show", "group": g["id"], "slot": slot_for(s),
                              "name": f"Opening night of {p['name']}", "production": p["id"],
                              "production_name": p["name"], "key": f"show:{p['id']}:{year}"})
        elif g["kind"] == "council":
            e = next_school_day(md_to_day(year, g["election"]), cal)
            items.append({"day": e, "kind": "election", "group": g["id"], "slot": "lunch",
                          "name": "Student Council election", "key": f"election:{g['id']}:{year}",
                          "signup_from": md_to_day(year, g["signup_open"])})
    for ev in (cal["events"] if only is None else []):
        d = md_to_day(year, ev["date"])
        if ev["kind"] == "dance":
            d = next_weekday(d, 5)
            items.append({"day": d, "kind": "dance", "slot": "evening", "name": ev["name"], "id": ev["id"],
                          "grades": ev.get("grades"), "ask_from": d - ev.get("ask_window", 14),
                          "key": f"dance:{ev['id']}:{year}"})
        elif ev["kind"] in ("exam", "report_card"):
            d = next_school_day(d, cal) if not is_school_day(d, cal) else d
            items.append({"day": d, "kind": ev["kind"], "slot": "classes", "name": ev["name"], "id": ev["id"],
                          "weight": ev.get("weight", 1), "key": f"{ev['kind']}:{ev['id']}:{year}"})
        elif ev["kind"] == "graduation":
            items.append({"day": d, "kind": "graduation", "slot": "night", "name": ev["name"], "id": ev["id"],
                          "key": f"graduation:{year}"})
        elif ev["kind"] in ("admissions", "decision_day", "college_decision"):
            items.append({"day": d, "kind": ev["kind"], "slot": None, "name": ev["name"], "id": ev["id"],
                          "key": f"{ev['kind']}:{year}"})
    q = cal.get("quiz_every_days", 14)
    d = next_weekday(y0 + 10, 4)
    n = 0
    while d < y1 and only is None:
        if is_school_day(d, cal) and not any(i["day"] == d and i["kind"] == "exam" for i in items):
            n += 1
            items.append({"day": d, "kind": "exam", "slot": "classes", "name": f"Quiz {n}", "id": f"quiz{n}",
                          "weight": 1, "key": f"exam:quiz{n}:{year}"})
        d += q
    items.sort(key=lambda i: (i["day"], i["kind"], i.get("group") or "", i["key"]))
    return items


# ---------------------------------------------------------------------------------------------------- named days
# Holidays that move (Thanksgiving, Easter...), the real Super Bowl Sundays, and the school calendar's own days (homecoming,
# prom, finals week, the first and last day of school, the breaks). A scene's dates can name any of these.

SUPER_BOWL = {2011: (2, 6), 2012: (2, 5), 2013: (2, 3), 2014: (2, 2), 2015: (2, 1), 2016: (2, 7), 2017: (2, 5), 2018: (2, 4),
              2019: (2, 3), 2020: (2, 2), 2021: (2, 7), 2022: (2, 13), 2023: (2, 12), 2024: (2, 11), 2025: (2, 9), 2026: (2, 8)}

NAMED_DAYS = {  # name -> what it is (for the guide and the checker)
    "thanksgiving": "Thanksgiving (the fourth Thursday of November)", "black_friday": "the day after Thanksgiving",
    "easter": "Easter Sunday", "mothers_day": "Mother's Day (second Sunday of May)", "fathers_day": "Father's Day (third Sunday of June)",
    "memorial_day": "Memorial Day", "labor_day": "Labor Day", "mlk_day": "Martin Luther King Jr. Day", "presidents_day": "Presidents' Day",
    "columbus_day": "Columbus Day", "super_bowl": "Super Bowl Sunday (the real date each year)",
    "first_day_of_school": "the first day of the school year", "last_day_of_school": "the last day before summer",
    "homecoming": "the homecoming dance", "homecoming_week": "homecoming week (the week before it)",
    "snow_ball": "the Snow Ball (winter dance)", "prom": "prom night", "prom_week": "the week before prom",
    "graduation": "graduation day", "midterms": "a midterm exam day (fall or spring)", "midterms_week": "the week before midterms",
    "finals": "a final exam day (fall or spring)", "finals_week": "the week before finals", "report_cards": "report card day",
    "thanksgiving_break": "Thanksgiving break", "winter_break": "winter break", "spring_break": "spring break",
}
APPROX_MD = {"thanksgiving": "11-25", "black_friday": "11-26", "easter": "04-08", "mothers_day": "05-10", "fathers_day": "06-17",
             "memorial_day": "05-28", "labor_day": "09-05", "mlk_day": "01-17", "presidents_day": "02-18", "columbus_day": "10-10",
             "super_bowl": "02-06", "first_day_of_school": "09-01", "last_day_of_school": "06-12", "homecoming": "10-18",
             "homecoming_week": "10-12", "snow_ball": "02-14", "prom": "05-16", "prom_week": "05-10", "graduation": "06-14",
             "midterms": "10-24", "midterms_week": "10-18", "finals": "12-18", "finals_week": "12-12", "report_cards": "11-07",
             "thanksgiving_break": "11-26", "winter_break": "12-20", "spring_break": "04-04"}
_EVENT_NAMES = {"midterms_fall": "midterms", "midterms_spring": "midterms", "finals_fall": "finals", "finals_spring": "finals",
                "rc1": "report_cards", "rc2": "report_cards", "rc3": "report_cards", "rc4": "report_cards"}
_WEEKS = {"homecoming", "prom", "midterms", "finals"}
_named_cache: dict = {}


def _nth(y, m, wd, n) -> dt.date:
    first = dt.date(y, m, 1)
    return first + dt.timedelta(days=(wd - first.weekday()) % 7 + 7 * (n - 1))


def _last(y, m, wd) -> dt.date:
    d = dt.date(y, m + 1, 1) - dt.timedelta(days=1) if m < 12 else dt.date(y, 12, 31)
    return d - dt.timedelta(days=(d.weekday() - wd) % 7)


def _easter(y) -> dt.date:
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    L = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * L) // 451
    month = (h + L - 7 * m + 114) // 31
    return dt.date(y, month, ((h + L - 7 * m + 114) % 31) + 1)


def named_days(day: int, cal: dict) -> frozenset:
    """Every named day that falls on this day."""
    key = (day, id(cal))
    hit = _named_cache.get(key)
    if hit is not None:
        return hit
    if len(_named_cache) > 20000:
        _named_cache.clear()
    d = date_of(day)
    y = d.year
    out = set()
    thx = _nth(y, 11, 3, 4)
    fixed = {"thanksgiving": thx, "black_friday": thx + dt.timedelta(days=1), "easter": _easter(y),
             "mothers_day": _nth(y, 5, 6, 2), "fathers_day": _nth(y, 6, 6, 3), "memorial_day": _last(y, 5, 0),
             "labor_day": _nth(y, 9, 0, 1), "mlk_day": _nth(y, 1, 0, 3), "presidents_day": _nth(y, 2, 0, 3),
             "columbus_day": _nth(y, 10, 0, 2),
             "super_bowl": dt.date(y, *SUPER_BOWL[y]) if y in SUPER_BOWL else _nth(y, 2, 6, 2 if y > 2021 else 1)}
    out |= {k for k, v in fixed.items() if v == d}
    sy = school_year_of(day)
    for e in cal.get("events") or []:
        if not isinstance(e.get("date"), (list, tuple)):
            continue
        name = _EVENT_NAMES.get(e["id"], e["id"])
        ed = md_to_day(sy, e["date"])
        if day == ed:
            out.add(name)
        if name in _WEEKS and ed - 6 <= day < ed:
            out.add(name + "_week")
    for b in cal.get("breaks") or []:
        nm = b["name"].lower().replace(" ", "_")
        if nm in ("thanksgiving_break", "winter_break", "spring_break") and break_name(day, cal) == b["name"]:
            out.add(nm)
    start = md_to_day(sy, cal.get("school_year_start", (9, 1)))
    if is_school_day(day, cal) and day >= start and not any(is_school_day(x, cal) for x in range(start, day)):
        out.add("first_day_of_school")
    summer = next((b for b in cal.get("breaks") or [] if b["name"] == "Summer"), None)
    if summer and is_school_day(day, cal):
        nxt = next((x for x in range(day + 1, day + 6) if weekday(x) < 5), day + 1)
        if break_name(nxt, cal) == "Summer":
            out.add("last_day_of_school")
    hit = _named_cache[key] = frozenset(out)
    return hit


def date_matches(day: int, dates, cal: dict) -> bool:
    """A scene's dates ("10-31", or named days like "thanksgiving") against a day."""
    d = date_of(day)
    md = f"{d.month:02d}-{d.day:02d}"
    named = None
    for x in dates:
        if x == md:
            return True
        if x in NAMED_DAYS:
            named = named_days(day, cal) if named is None else named
            if x in named:
                return True
    return False

