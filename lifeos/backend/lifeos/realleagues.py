"""The rest of the sports world behind your story, as it really happened: the NFL, the NBA and college sports.

The story starts in fall 2010, and every one of these leagues plays out on its real dates: the games, the standings, the
polls, the playoffs and the champions, a day at a time (you never see past today). MLB has its own module (mlb.py, with the
what-ifs); this is everything else.

- Game leagues (data/leagues/<league>/, built by tools/build_league_data.py from public data): the NFL, the NBA, college
  football, and men's and women's college basketball. Every game with its date and score; conference and division
  standings; the playoffs, bowls and the NCAA tournament; a weekly top 25 for college (ours, from results: an Elo rating with
  margin of victory, not the AP poll).
- European soccer: the Premier League, La Liga, Serie A, the Bundesliga and Ligue 1, every league game, the table by points
  (then goal difference), the champion on the last day; the Champions League finals; the Ballon d'Or winners (and the
  women's from 2018).
- Title-only sports (data/leagues/titles.json): college baseball (the College World Series) and men's and women's college
  soccer (the College Cups). No public game data exists for them, so they carry the real finals: who won, who lost, when.
- Past the data (the 2026 seasons and on), each league keeps going in this world: a champion every year, drawn from the
  programs that were good when the data ran out.

You follow a team in each: the Giants and the Knicks to start (it's Connecticut: plenty of Patriots and Celtics fans around
too), and UConn in college until you go to college yourself, then your school. Everyone in town has their teams; a title is
a memory and a good week for its fans, an exit stings, and storylines can ask about any of it (pro.py).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import random
from collections import defaultdict
from functools import lru_cache

from . import calendar as calm
from .catalogs import DATA_DIR

EPOCH = dt.date(2000, 1, 1)
DIR = os.path.join(DATA_DIR, "leagues")

LEAGUES = {
    "nfl": {"label": "NFL", "short": "NFL", "kind": "pro", "title": "the Super Bowl", "post": "the playoffs",
            "rounds": {"WC": "Wild Card round", "DIV": "Divisional round", "CON": "Conference Championship", "SB": "Super Bowl"}},
    "nba": {"label": "NBA", "short": "NBA", "kind": "pro", "title": "the NBA Finals", "post": "the playoffs", "series": True,
            "rounds": {"R1": "First round", "CSF": "Conference semifinals", "CF": "Conference finals", "F": "NBA Finals"}},
    "cfb": {"label": "College football", "short": "Football", "kind": "college", "title": "the national championship",
            "post": "the playoff",
            "rounds": {"R1": "Playoff first round", "QF": "Playoff quarterfinal", "SF": "Playoff semifinal", "NC": "National championship"}},
    "mbb": {"label": "Men's college basketball", "short": "Men's hoops", "kind": "college", "title": "the national championship",
            "post": "the NCAA tournament",
            "rounds": {"FF": "First Four", "R64": "Round of 64", "R32": "Round of 32", "S16": "Sweet 16", "E8": "Elite Eight",
                       "F4": "Final Four", "NC": "National championship"}},
    "wbb": {"label": "Women's college basketball", "short": "Women's hoops", "kind": "college", "title": "the national championship",
            "post": "the NCAA tournament",
            "rounds": {"FF": "First Four", "R64": "Round of 64", "R32": "Round of 32", "S16": "Sweet 16", "E8": "Elite Eight",
                       "F4": "Final Four", "NC": "National championship"}},
    "epl": {"label": "Premier League", "short": "Premier League", "kind": "soccer", "title": "the Premier League"},
    "laliga": {"label": "La Liga", "short": "La Liga", "kind": "soccer", "title": "La Liga"},
    "seriea": {"label": "Serie A", "short": "Serie A", "kind": "soccer", "title": "Serie A"},
    "bund": {"label": "Bundesliga", "short": "Bundesliga", "kind": "soccer", "title": "the Bundesliga"},
    "ligue1": {"label": "Ligue 1", "short": "Ligue 1", "kind": "soccer", "title": "Ligue 1"},
    "ucl": {"label": "Champions League", "short": "Champions League", "kind": "soccer", "titles_only": True},
    "ballon": {"label": "Ballon d'Or", "short": "Ballon d'Or", "kind": "soccer", "titles_only": True, "award": True},
    "cbase": {"label": "College baseball", "short": "Baseball", "kind": "college", "titles_only": True},
    "msoc": {"label": "Men's college soccer", "short": "Men's soccer", "kind": "college", "titles_only": True},
    "wsoc": {"label": "Women's college soccer", "short": "Women's soccer", "kind": "college", "titles_only": True},
}
PRO = ("nfl", "nba")
COLLEGE = ("cfb", "mbb", "wbb", "cbase", "msoc", "wsoc")
SOCCER = ("epl", "laliga", "seriea", "bund", "ligue1")
GAME_LEAGUES = ("nfl", "nba", "cfb", "mbb", "wbb") + SOCCER
DISPLAY = {"Connecticut": "UConn"}  # college football's name for UConn
SCHOOL = {"uconn": "UConn", "stanford": "Stanford", "ucla": "UCLA", "lsu": "LSU", "unc": "North Carolina", "texas": "Texas",
          "oklahoma": "Oklahoma", "fsu": "Florida State", "miami": "Miami", "michigan": "Michigan"}
DEFAULT_FOLLOW = {"nfl": "NYG", "nba": "New York Knicks", "college": "UConn", "epl": "Man United", "laliga": "Barcelona",
                  "seriea": "Juventus", "bund": "Bayern Munich", "ligue1": "Paris SG"}
FANS = {  # the shoreline: who people root for
    "nfl": [("NYG", 34), ("NE", 34), ("NYJ", 14), ("", 18)],
    "nba": [("New York Knicks", 36), ("Boston Celtics", 34), ("Brooklyn Nets", 6), ("", 24)],
    "college": [("UConn", 100)],
}


# ---------------------------------------------------------------------------------------------------- the data
def _offset() -> int:
    return (calm.START - EPOCH).days


@lru_cache(maxsize=8)
def index(lg: str) -> dict:
    with open(os.path.join(DIR, lg, "index.json"), encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=8)
def teams(lg: str) -> list:
    with open(os.path.join(DIR, lg, "teams.json"), encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def titles_data() -> dict:
    with open(os.path.join(DIR, "titles.json"), encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=12)
def season(lg: str, key: str) -> dict:
    """A season with its games in story days: (day, home, away, home pts, away pts, kind, round), and who played whom."""
    with open(os.path.join(DIR, lg, f"{key}.json"), encoding="utf-8") as f:
        s = json.load(f)
    off = _offset()
    games = [(g[0] - off, g[1], g[2], g[3], g[4], g[5], g[6] if len(g) > 6 else "") for g in s["games"]]
    by = defaultdict(list)
    for i, g in enumerate(games):
        by[g[1]].append(i)
        by[g[2]].append(i)
    s["games"] = games
    s["by"] = dict(by)
    s["conf"] = {t: c for c, ts in s.get("groups", {}).items() for t in ts}
    s["polls"] = [(d - off, ts) for d, ts in s.get("polls", [])]
    return s


def name(lg: str, t: int, key: str | None = None, short=True) -> str:
    row = teams(lg)[t]
    nm = row[0]
    if key is not None:
        nm = ((index(lg).get(key) or {}).get("names") or {}).get(str(t), nm)  # its name that season
    if LEAGUES[lg]["kind"] == "soccer":
        return nm
    if short:
        if LEAGUES[lg]["kind"] == "college":
            return DISPLAY.get(row[1], row[1])
        return nm.split()[-1] if not nm.endswith("Team") else "Washington"
    return DISPLAY.get(nm, nm)


SPORT_NOUN = {"cfb": "football", "mbb": "men's basketball", "wbb": "women's basketball", "cbase": "baseball",
              "msoc": "men's soccer", "wsoc": "women's soccer"}


def who(lg: str, t: int, key: str | None = None) -> str:
    """'UConn men's basketball', 'the New York Giants'."""
    if LEAGUES[lg]["kind"] == "college":
        return f"{name(lg, t, key)} {SPORT_NOUN[lg]}"
    return f"the {name(lg, t, key, False)}"


def find(lg: str, label: str) -> int | None:
    """A team by its name, nickname, school or abbreviation."""
    for i, (nm, short, abbr) in enumerate(teams(lg)):
        if label in (nm, short, abbr) or DISPLAY.get(short) == label:
            return i
    return None


# ---------------------------------------------------------------------------------------------------- which season
def season_key(lg: str, day: int) -> str | None:
    """The season on today: the last one whose first game is at most three weeks off (so the offseason keeps showing the
    season that just ended)."""
    off = _offset()
    keys = sorted(index(lg), key=int)
    cur = None
    for k in keys:
        if index(lg)[k]["first"] - off - 21 <= day:
            cur = k
    return cur


def past_data(lg: str, day: int) -> bool:
    keys = sorted(index(lg), key=int)
    last = index(lg)[keys[-1]]
    return day > last["last"] - _offset() + 120


# ---------------------------------------------------------------------------------------------------- records
def _wl(g, t) -> int:
    """1 win, 0 loss, -1 tie (from t's side)."""
    mine, theirs = (g[3], g[4]) if g[1] == t else (g[4], g[3])
    return 1 if mine > theirs else 0 if mine < theirs else -1


def record(lg: str, key: str, t: int, day: int, conf=False, regular=None) -> list:
    """[wins, losses, ties] through today. regular: only the regular season (the pros), conf: only conference games."""
    s = season(lg, key)
    reg = LEAGUES[lg]["kind"] == "pro" if regular is None else regular
    w = l_ = ti = 0
    for i in s["by"].get(t, []):
        g = s["games"][i]
        if g[0] > day:
            break
        if conf and g[5] != 1:
            continue
        if reg and g[5] >= 3:
            continue
        r = _wl(g, t)
        w += r == 1
        l_ += r == 0
        ti += r == -1
    return [w, l_, ti]


def rec_text(r, soccer=False) -> str:
    """'10-6', '10-5-1' with a tie, and wins-draws-losses in soccer: '21-9-8'."""
    if soccer:
        return f"{r[0]}-{r[2]}-{r[1]}"
    return f"{r[0]}-{r[1]}" + (f"-{r[2]}" if r[2] else "")


def _soccer(lg) -> bool:
    return LEAGUES[lg]["kind"] == "soccer"


def table_points(lg: str, key: str, day: int) -> dict:
    """{club: (points, goal difference, goals for, played)} through today."""
    s = season(lg, key)
    out = defaultdict(lambda: [0, 0, 0, 0])
    for g in s["games"]:
        if g[0] > day:
            break
        for t, f, a in ((g[1], g[3], g[4]), (g[2], g[4], g[3])):
            x = out[t]
            x[0] += 3 if f > a else 1 if f == a else 0
            x[1] += f - a
            x[2] += f
            x[3] += 1
    return out


def poll(lg: str, key: str, day: int) -> list:
    """This week's top 25 (college), or [] before the first one."""
    ps = [p for p in season(lg, key)["polls"] if p[0] <= day]
    return ps[-1][1] if ps else []


def standings(lg: str, key: str, day: int, only: set | None = None) -> list:
    """Conference or division tables through today."""
    s = season(lg, key)
    out = []
    college = LEAGUES[lg]["kind"] == "college"
    for grp, ts in sorted(s.get("groups", {}).items()):
        if only is not None and grp not in only:
            continue
        rows = []
        for t in ts:
            r = record(lg, key, t, day)
            c = record(lg, key, t, day, conf=True)
            rows.append({"team": t, "name": name(lg, t, key), "w": r[0], "l": r[1], "t": r[2],
                         "cw": c[0], "cl": c[1], "pct": (r[0] + r[2] / 2) / max(1, sum(r))})
        if _soccer(lg):
            tp = table_points(lg, key, day)
            for x in rows:
                x["pts"], x["gd"] = tp[x["team"]][0], tp[x["team"]][1]
            rows.sort(key=lambda x: (-x["pts"], -x["gd"], -tp[x["team"]][2], x["name"]))
        elif college:
            rows.sort(key=lambda x: (-(x["cw"] / max(1, x["cw"] + x["cl"])), -x["cw"], -x["pct"], x["name"]))
        else:
            rows.sort(key=lambda x: (-x["pct"], -x["w"], x["name"]))
        conf, div = (grp.split("|") + [""])[:2]
        out.append({"group": grp, "label": f"{conf} {div}".strip(), "rows": rows})
    return out


# ---------------------------------------------------------------------------------------------------- the postseason
def postseason(lg: str, key: str, day: int) -> list:
    """The playoff / tournament games (or series, in the NBA) played through today, by round."""
    s = season(lg, key)
    rounds = LEAGUES[lg].get("rounds", {})
    order = list(rounds)
    if LEAGUES[lg].get("series"):
        ser = {}
        for g in s["games"]:
            if g[5] < 3 or g[0] > day:
                continue
            k = (g[6], frozenset((g[1], g[2])))
            x = ser.setdefault(k, {"round": g[6], "teams": sorted((g[1], g[2])), "wins": defaultdict(int), "last": g[0]})
            x["wins"][g[1] if g[3] > g[4] else g[2]] += 1
            x["last"] = g[0]
        out = []
        for x in ser.values():
            a, b = x["teams"]
            wa, wb = x["wins"][a], x["wins"][b]
            done = max(wa, wb) == 4
            out.append({"round": x["round"], "label": rounds.get(x["round"], x["round"]), "teams": [a, b],
                        "names": [name(lg, a, key), name(lg, b, key)], "score": [wa, wb], "done": done,
                        "winner": (a if wa > wb else b) if done else None, "day": x["last"]})
        return sorted(out, key=lambda x: (order.index(x["round"]) if x["round"] in order else 9, x["day"]))
    out = []
    for g in s["games"]:
        if g[5] < 3 or g[0] > day or g[5] == 4:
            continue
        win = g[1] if g[3] > g[4] else g[2]
        out.append({"round": g[6], "label": rounds.get(g[6], "Postseason"), "teams": [g[1], g[2]],
                    "names": [name(lg, g[1], key), name(lg, g[2], key)], "score": [g[3], g[4]], "done": True,
                    "winner": win, "day": g[0]})
    return out


def title_game(lg: str, key: str):
    return next((g for g in reversed(season(lg, key)["games"]) if g[5] == 5), None)


def champion(lg: str, key: str, day: int) -> int | None:
    """Whoever won it, once the title's been decided by today."""
    ix = index(lg).get(key)
    if ix and ix["title"] and ix["title"][0] - _offset() <= day:
        return ix["champ"]  # (decided: no need to open the season)
    if ix and ix["title"] and int(key) < int(season_key(lg, day) or key):
        return ix["champ"]
    if not os.path.exists(os.path.join(DIR, lg, f"{key}.json")):
        return None
    if LEAGUES[lg].get("series"):
        f = [x for x in postseason(lg, key, day) if x["round"] == "F" and x["done"]]
        return f[0]["winner"] if f else None
    g = title_game(lg, key)
    if g and g[0] <= day:
        return g[1] if g[3] > g[4] else g[2]
    return None


def in_postseason(lg: str, key: str, t: int, day: int) -> bool:
    return any(t in x["teams"] for x in postseason(lg, key, day))


def alive(lg: str, key: str, t: int, day: int) -> bool:
    """In the postseason and not knocked out (as of today)."""
    ps = postseason(lg, key, day)
    if not any(t in x["teams"] for x in ps):
        return False
    return not any(t in x["teams"] and x["done"] and x["winner"] != t for x in ps) and champion(lg, key, day) is None


# ---------------------------------------------------------------------------------------------------- title-only sports
def finals(lg: str, day: int) -> list:
    """The finals decided by today: [{season, date, champ, runner_up, score, note}]."""
    T = titles_data()[lg]
    if T.get("award"):
        return []
    out = []
    for yr, date, champ, ru, score, note in T["rows"]:
        if date is None:
            if calm.day_of(dt.date(yr, 6, 30)) <= day:
                out.append({"season": yr, "date": None, "champ": None, "runner_up": None, "score": None, "note": note})
            continue
        d = calm.day_of(dt.date.fromisoformat(date))
        if d <= day:
            out.append({"season": yr, "date": calm.label(d), "day": d, "champ": champ, "runner_up": ru, "score": score, "note": note})
    out = out + _sim_finals(lg, day, T)
    for f in out:
        f["label"] = f"{f['season'] - 1}-{f['season'] % 100:02d}" if T.get("split") else str(f["season"])
    return out


def awards(lg: str, day: int) -> list:
    """The Ballon d'Or winners announced by today: [{year, date, winner, club, women, women_club}]."""
    out = []
    for yr, date, who_, club, women, wclub in titles_data()[lg]["rows"]:
        if date is None:
            if calm.day_of(dt.date(yr, 12, 15)) <= day:
                out.append({"year": yr, "date": None, "winner": None, "club": None, "women": None, "women_club": None,
                            "note": "Not awarded (COVID-19)"})
            continue
        d = calm.day_of(dt.date.fromisoformat(date))
        if d <= day:
            out.append({"year": yr, "date": calm.label(d), "day": d, "winner": who_, "club": club, "women": women, "women_club": wclub})
    return out


def _sim_finals(lg: str, day: int, T: dict) -> list:
    """After the real list runs out, this world keeps crowning champions, from the programs that were winning."""
    rows = [r for r in T["rows"] if r[1]]
    last = rows[-1]
    recent = [r[2] for r in rows[-12:]] + [r[3] for r in rows[-12:]]
    out = []
    y = last[0] + 1
    while True:
        md = dt.date.fromisoformat(last[1])
        d = calm.day_of(dt.date(md.year + (y - last[0]), md.month, min(md.day, 28)))
        if d > day:
            break
        rng = random.Random(f"{lg}:{y}")
        a = rng.choice(recent)
        b = rng.choice([x for x in recent if x != a])
        out.append({"season": y, "date": calm.label(d), "day": d, "champ": a, "runner_up": b, "score": None,
                    "note": "this world's"})
        y += 1
    return out


# ---------------------------------------------------------------------------------------------------- following and fans
def state(sim) -> dict:
    st = sim.w.meta.setdefault("leagues", {})
    st.setdefault("follow", {})
    st.setdefault("fans", {})
    st.setdefault("news", [])
    st.setdefault("seen", [])
    return st


def my_college(sim) -> str:
    """Your school once you're in college (if it plays), else whoever you picked, else UConn."""
    st = state(sim)
    if st["follow"].get("college_pick"):
        return st["follow"]["college_pick"]
    prot = sim.w.meta.get("protagonist")
    c = sim.w.chars.get(prot) if prot else None
    if c and (c.path or {}).get("kind") == "college" and c.path.get("college") in SCHOOL:
        return SCHOOL[c.path["college"]]
    return DEFAULT_FOLLOW["college"]


def followed(sim, lg: str):
    """The team you follow: a team number for the game leagues, a school name for the title-only sports."""
    st = state(sim)
    if lg in PRO or lg in SOCCER:
        label = st["follow"].get(lg) or DEFAULT_FOLLOW[lg]
        return find(lg, label)
    if lg == "ucl":
        return my_clubs(sim)
    school = my_college(sim)
    if LEAGUES[lg].get("titles_only"):
        return school
    t = find(lg, school)
    return t if t is not None else find(lg, "UConn") if lg != "cfb" else find(lg, "Connecticut")


def my_clubs(sim) -> list:
    """The clubs you follow, one in each league (full names)."""
    return [name(lg, followed(sim, lg)) for lg in SOCCER if followed(sim, lg) is not None]


def set_follow(sim, lg: str, label: str):
    st = state(sim)
    if lg in ("ucl", "ballon"):
        raise ValueError("follow a club in its league; the Champions League follows your clubs")
    if lg in PRO or lg in SOCCER:
        if find(lg, label) is None:
            raise ValueError(f"no {LEAGUES[lg]['label']} team called {label}")
        st["follow"][lg] = label
    else:
        st["follow"]["college_pick"] = label or None


def fans(sim, group: str) -> dict:
    """{person: [team label, how much they care 0-2]} for 'nfl', 'nba' or 'college'."""
    st = state(sim)
    f = st["fans"].setdefault(group, {})
    prot = sim.w.meta.get("protagonist")
    for c in sim.w.chars.values():
        if c.id in f:
            continue
        rng = random.Random(f"{sim.w.seed}:{group}:{c.id}")
        if c.id == prot:
            f[c.id] = ["", 2]  # (yours follows what you follow)
            continue
        t = rng.choices([x[0] for x in FANS[group]], [x[1] for x in FANS[group]])[0]
        f[c.id] = [t, rng.choices([0, 1, 2], [38, 44, 18])[0] if t else 0]
    return f


def _fan_team(sim, group: str, cid: str):
    if cid == sim.w.meta.get("protagonist"):
        return "you"
    return fans(sim, group).get(cid, ["", 0])


def _news(sim, lg: str, text: str, mine: bool, day: int):
    st = state(sim)
    st["news"].append({"lg": lg, "day": day, "text": text, "mine": mine})
    del st["news"][:-200]


def weekly(sim):
    """Once a week: the titles decided and your teams' playoff results since last time become news, and the fans feel them."""
    from .history import Effects
    st = state(sim)
    seen = set(st["seen"])
    day = sim.w.day
    w = sim.w
    prot = w.meta.get("protagonist")
    fx = None
    for lg in GAME_LEAGUES:
        key = season_key(lg, day)
        if not key:
            continue
        me = followed(sim, lg)
        group = lg if lg in PRO else "college"
        for x in postseason(lg, key, day):
            if not x["done"]:
                continue
            tag = f"{lg}:{key}:{x['round']}:{min(x['teams'])}:{max(x['teams'])}"
            if tag in seen:
                continue
            seen.add(tag)
            win = x["winner"]
            lose = [t for t in x["teams"] if t != win][0]
            final = x["round"] in ("SB", "F", "NC")
            if not final and me not in x["teams"]:
                continue
            i, j = x["teams"].index(win), x["teams"].index(lose)
            score = f"{x['score'][i]}-{x['score'][j]}"
            what = f"to win {LEAGUES[lg]['title']}" if final else f"in the {x['label']}"
            _news(sim, lg, f"{name(lg, win, key, False)} beat {name(lg, lose, key, False)} {score} {what}.", me in x["teams"], x["day"])
            if not final and me != lose:
                continue
            fx = fx or Effects(w, None)
            for cid, info in list(fans(sim, group).items()):
                if cid not in w.chars or w.chars[cid].status != "active":
                    continue
                if cid == prot:
                    team, care = me, 2
                else:
                    label, care = info
                    team = find(lg, label) if label else None
                    if group == "college" and label:
                        team = find(lg, label if lg != "cfb" else "Connecticut") if label == "UConn" else find(lg, label)
                if not care or team is None:
                    continue
                if final and team == win:
                    fx.mood(cid, 6 * care, f"{name(lg, win, key)} won it all")
                    fx.memory(cid, "pro_title", [], 0.35 * care, 25 * care,
                              f"{who(lg, win, key)[:1].upper() + who(lg, win, key)[1:]} won {LEAGUES[lg]['title']} ({index(lg)[key]['label']})")
                elif team == lose:
                    fx.mood(cid, -(5 if final else 3) * care, f"{name(lg, lose, key)} lost")
                    if final or care == 2:
                        fx.memory(cid, "pro_heartbreak", [], -0.2 * care, 12 * care,
                                  f"{who(lg, lose, key)[:1].upper() + who(lg, lose, key)[1:]} lost in the {x['label']} "
                                  f"({index(lg)[key]['label']})")
    for lg in SOCCER:  # a league title, decided on the last day
        key = season_key(lg, day)
        c = champion(lg, key, day) if key else None
        tag = f"{lg}:{key}:title"
        if c is None or tag in seen:
            continue
        seen.add(tag)
        mine = c == followed(sim, lg)
        picked = bool(st["follow"].get(lg))  # (a club you chose yourself is one you feel; the starting ones are just news)
        _news(sim, lg, f"{name(lg, c, key)} win {LEAGUES[lg]['title']} ({index(lg)[key]['label']}).", mine, index(lg)[key]["title"][0] - _offset())
        if mine and picked and prot in w.chars:
            fx = fx or Effects(w, None)
            fx.mood(prot, 4, f"{name(lg, c, key)} won the league")
            fx.memory(prot, "pro_title", [], 0.25, 18, f"{name(lg, c, key)} won {LEAGUES[lg]['title']} ({index(lg)[key]['label']})")
    for f in finals("ucl", day):
        tag = f"ucl:{f['season']}"
        if tag in seen or not f.get("champ"):
            continue
        seen.add(tag)
        if f.get("day", day) < day - 60:
            continue
        mine = f["champ"] in my_clubs(sim)
        picked = any(st["follow"].get(x) and name(x, followed(sim, x)) == f["champ"] for x in SOCCER)
        _news(sim, "ucl", f"{f['champ']} beat {f['runner_up']}" + (f" {f['score']}" if f.get("score") else "") +
              (f" {f['note']}" if f.get("note") and f["note"] != "this world's" else "") + " in the Champions League final.",
              mine or f["runner_up"] in my_clubs(sim), f.get("day", day))
        if mine and picked and prot in w.chars:
            fx = fx or Effects(w, None)
            fx.mood(prot, 5, f"{f['champ']} won the Champions League")
            fx.memory(prot, "pro_title", [], 0.3, 20, f"{f['champ']} won the Champions League ({f['label']})")
    for a in awards("ballon", day):
        tag = f"ballon:{a['year']}"
        if tag in seen or not a.get("winner"):
            continue
        seen.add(tag)
        if a.get("day", day) < day - 60:
            continue
        _news(sim, "ballon", f"{a['winner']} ({a['club']}) wins the {a['year']} Ballon d'Or" +
              (f"; {a['women']} ({a['women_club']}) wins the women's." if a.get("women") else "."), False, a.get("day", day))
    for lg in ("cbase", "msoc", "wsoc"):
        for f in finals(lg, day):
            tag = f"{lg}:{f['season']}"
            if tag in seen or not f.get("champ"):
                continue
            seen.add(tag)
            if f.get("day", day) < day - 60:
                continue  # (long before the story)
            mine = my_college(sim) in (f["champ"], f["runner_up"])
            _news(sim, lg, f"{f['champ']} beat {f['runner_up']}" + (f" {f['score']}" if f.get("score") else "") +
                  (f" {f['note']}" if f.get("note") and f["note"] != "this world's" else "") +
                  f" to win the {titles_data()[lg]['event']}.", mine, f.get("day", day))
    st["seen"] = sorted(seen)[-800:]


# ---------------------------------------------------------------------------------------------------- views
def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _game_line(lg, key, g, t) -> dict:
    home = g[1] == t
    opp = g[2] if home else g[1]
    rnd = (LEAGUES[lg].get("rounds", {}).get(g[6], "") if g[5] in (3, 5) else "Bowl game" if g[5] == 4 and lg == "cfb" else
           "Postseason" if g[5] == 4 else "Conference tournament" if g[5] == 2 else "")
    out = {"date": calm.label(g[0]), "opp": name(lg, opp, key), "home": home, "label": rnd,
           "conf": g[5] == 1 and not _soccer(lg)}
    return out


def team_card(sim, lg: str, key: str, t: int, day: int) -> dict:
    s = season(lg, key)
    r = record(lg, key, t, day)
    c = record(lg, key, t, day, conf=True)
    grp = s["conf"].get(t)
    place = None
    if grp:
        tab = next((x for x in standings(lg, key, day, {grp}) if x["group"] == grp), None)
        if tab and sum(r):
            pos = next(i for i, x in enumerate(tab["rows"]) if x["team"] == t)
            place = f"{_ordinal(pos + 1)} in {LEAGUES[lg]['title'] if _soccer(lg) else 'the ' + tab['label']}"
    rank = None
    if LEAGUES[lg]["kind"] == "college":
        p = poll(lg, key, day)
        rank = p.index(t) + 1 if t in p else None
    games = [s["games"][i] for i in s["by"].get(t, [])]
    played = [g for g in games if g[0] <= day]
    last = []
    for g in reversed(played[-5:]):
        x = _game_line(lg, key, g, t)
        mine, theirs = (g[3], g[4]) if g[1] == t else (g[4], g[3])
        x.update({"score": f"{mine}-{theirs}", "result": "W" if mine > theirs else "L" if mine < theirs else "T"})
        last.append(x)
    nxt = next((g for g in games if g[0] > day), None)
    champ = champion(lg, key, day)
    status = None
    ps = postseason(lg, key, day)
    mine_ps = [x for x in ps if t in x["teams"]]
    if champ == t:
        status = f"Champions: won {LEAGUES[lg]['title']}."
    elif mine_ps:
        lost = next((x for x in mine_ps if x["done"] and x["winner"] != t), None)
        if lost:
            other = [o for o in lost["teams"] if o != t][0]
            status = f"Out in the {lost['label'].lower()}: lost to {name(lg, other, key)}."
        else:
            status = f"Still alive in {LEAGUES[lg]['post']}."
    elif _soccer(lg) and not games:
        status = f"Not in {LEAGUES[lg]['label']} this season."
    elif not played and nxt:
        status = f"Season starts {calm.label(nxt[0]).replace(', ' + str(calm.date_of(nxt[0]).year), '')}."
    elif champ is not None:
        status = "Season over."
    pts = table_points(lg, key, day)[t][0] if _soccer(lg) else None
    if _soccer(lg) and champ == t:
        status = f"Champions of {LEAGUES[lg]['title']}."
    return {"team": t, "name": name(lg, t, key, False), "short": name(lg, t, key), "record": rec_text(r, _soccer(lg)) if sum(r) else None,
            "conf_record": None if _soccer(lg) else rec_text(c) if sum(c) else None, "points": pts,
            "conf": grp.replace("|", " ") if grp else None, "place": place,
            "rank": rank, "last": last, "status": status,
            "next": ({**_game_line(lg, key, nxt, t)} if nxt else None)}


def view(sim, lg: str) -> dict:
    """One league's page: your team, the table (or the top 25), the postseason so far, the champions, the news."""
    if lg not in LEAGUES:
        raise ValueError(f"no league {lg}")
    day = sim.w.day
    st = state(sim)
    L = LEAGUES[lg]
    news = [{"date": calm.label(n["day"]), "text": n["text"], "mine": n["mine"]}
            for n in reversed(st["news"]) if n["lg"] == lg and n["day"] <= day][:12]
    base = {"league": lg, "label": L["label"], "kind": L["kind"], "news": news, "today": calm.label(day)}
    if L.get("award"):
        aw = list(reversed(awards(lg, day)))
        nxt = next((r for r in titles_data()[lg]["rows"] if r[1] and calm.day_of(dt.date.fromisoformat(r[1])) > day), None)
        return {**base, "titles_only": True, "award": True, "winners": aw[:25],
                "next": (f"The next one is given out around {calm.label(calm.day_of(dt.date.fromisoformat(nxt[1])))[5:]}." if nxt else None),
                "note": "The real winners (2010-15 it was the FIFA Ballon d'Or; the women's award started in 2018)."}
    if L.get("titles_only"):
        fin = finals(lg, day)
        school = followed(sim, lg)
        T = titles_data()[lg]
        if lg == "ucl":
            mine = [f"{f['label']} ({f['champ']})" for f in fin if f.get("champ") in school]
            school = ", ".join(school)
        else:
            mine = [str(f["season"]) for f in fin if f.get("champ") == school]
        nxt_row = next((r for r in T["rows"] if r[1] and calm.day_of(dt.date.fromisoformat(r[1])) > day), None)
        return {**base, "titles_only": True, "event": T["event"], "school": school,
                "school_titles": mine, "finals": list(reversed(fin))[:20],
                "next": (f"The {T['event']} final is around {calm.label(calm.day_of(dt.date.fromisoformat(nxt_row[1])))[5:]}."
                         if nxt_row else None),
                "note": ("Every final, with your clubs' titles (follow clubs in their leagues)." if lg == "ucl" else
                         "No game-by-game data is public for this sport: you see the real finals, and your school's titles.")}
    key = season_key(lg, day)
    if not key:
        return {**base, "season": None}
    t = followed(sim, lg)
    s = season(lg, key)
    card = team_card(sim, lg, key, t, day) if t is not None else None
    tables = standings(lg, key, day, None if L["kind"] in ("pro", "soccer") else ({s["conf"].get(t)} if t is not None else set()))
    top = [{"rank": i + 1, "team": x, "name": name(lg, x, key), "record": rec_text(record(lg, key, x, day))}
           for i, x in enumerate(poll(lg, key, day))] if L["kind"] == "college" else []
    champs = []
    for k in sorted(index(lg), key=int):
        ix = index(lg)[k]
        if ix["title"] and ix["title"][0] - _offset() <= day and ix["champ"] is not None:
            g = ix["title"]
            win = ix["champ"]
            lose = g[2] if g[1] == win else g[1]
            champs.append({"season": ix["label"], "champ": name(lg, win, k, False),
                           "runner_up": name(lg, lose, k, False) if lose is not None else None, "mine": win == t})
    picks = sorted({x for grp in s.get("groups", {}).values() for x in grp}, key=lambda x: name(lg, x, key))
    return {**base, "season": index(lg)[key]["label"], "my_team": card, "standings": tables, "top25": top,
            "postseason": postseason(lg, key, day), "champ": (name(lg, champion(lg, key, day), key, False)
                                                             if champion(lg, key, day) is not None else None),
            "champions": list(reversed(champs))[:20],
            "teams": [{"team": x, "name": name(lg, x, key, L["kind"] == "college")} for x in picks],
            "note": ("The real results run out here; from now on it's this world's." if past_data(lg, day) else
                     "Every game as it really happened, on its real date." +
                     (" (Bowl games before the 2023 season aren't in the public data; the title games are.)" if lg == "cfb" else "") +
                     (" The top 25 is ours, from results, not the AP poll." if L["kind"] == "college" else ""))}


def summary(sim) -> list:
    """A line per league for the Pro / College menus: your team's record or status right now."""
    out = []
    day = sim.w.day
    for lg, L in LEAGUES.items():
        if L.get("award"):
            aw = awards(lg, day)
            out.append({"league": lg, "label": L["short"], "kind": L["kind"],
                        "line": f"Last: {aw[-1]['winner']}" if aw and aw[-1].get("winner") else None})
            continue
        if L.get("titles_only"):
            fin = finals(lg, day)
            out.append({"league": lg, "label": L["short"], "kind": L["kind"],
                        "line": f"Last champion: {fin[-1]['champ']}" if fin and fin[-1].get("champ") else None})
            continue
        key = season_key(lg, day)
        t = followed(sim, lg)
        if not key or t is None:
            out.append({"league": lg, "label": L["short"], "kind": L["kind"], "line": None})
            continue
        r = record(lg, key, t, day)
        ix = index(lg)[key]
        out.append({"league": lg, "label": L["short"], "kind": L["kind"],
                    "in_season": ix["first"] - _offset() - 7 <= day <= ix["last"] - _offset(),
                    "line": f"{name(lg, t, key)} {rec_text(r, _soccer(lg))}" if sum(r) else name(lg, t, key)})
    return out
