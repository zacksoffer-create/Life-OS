"""Real MLB in LIFE OS: the history since 1990, the what-ifs, and live seasons running in the background.

The data (data/mlb.json, built by tools/build_mlb_data.py from the Lahman database): every team-season, postseason series
and major award from 1990 through the last real season (2025), and every regular's season with a value in wins (a WAR-style
estimate). The story starts on Sept 1, 2025, so the real 2025 finish plays out on its real dates.

What-ifs (WHATIFS): real moves that almost happened. Each is a list of moves: a player's seasons going to another team (or
to nowhere: "he signs somewhere else"), and flat changes in a team's wins (the guy who loses his job, the player a team signs
instead). Turn some on and history replays:
- each team-season's wins move by the value that moved; its opponents give those wins back (division rivals the most)
- the playoff field is rebuilt with that year's format (two divisions through 1993, none in 1994, three divisions and a wild
  card from 1995, a second wild card from 2012, sixteen teams in 2020, six a league from 2022)
- October replays with as little change as possible: when the same two teams meet as really met, the real result stands
  unless the change in their odds flips it (a team that got better and really lost wins with chance (p1 - p0) / (1 - p0); a
  team that got worse and really won keeps it with chance p1 / p0); a matchup that never happened is played fresh
- each world rolls its October once (seeded), so it's the same every time you look, and the odds sit next to what happened

Live seasons (2026 on): rosters from where everyone finished 2025 (a what-if moves active players: Harper's a Yankee if he
signed there), talent from each player's last three seasons, team strength from the roster, a 162-game season played
series by series, the postseason in the current format, awards, then the offseason: aging, retirements, free agency and
rookies. It all happens in the background; catch_up() brings it to today and is safe to call any time.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import random
from collections import defaultdict
from functools import lru_cache

from . import calendar as calm
from .catalogs import DATA_DIR

ROUND_ORDER = {"WC": 0, "DS": 1, "CS": 2, "WS": 3}
ROUND_LABEL = {"WC": "Wild Card Series", "DS": "Division Series", "CS": "Championship Series", "WS": "World Series"}
LEAGUE_LABEL = {"AL": "American League", "NL": "National League"}
DIV_LABEL = {"E": "East", "C": "Central", "W": "West"}
RIVALS = {"NYY": ["BOS"], "BOS": ["NYY"], "NYM": ["PHI", "ATL"], "LAD": ["SFG"], "SFG": ["LAD"], "CHC": ["STL"], "STL": ["CHC"]}
FIRST_LIVE = 2026  # data runs through 2025: everything after is simulated


# ---------------------------------------------------------------------------------------------------- the what-ifs
# p: the player's Lahman id; to: the franchise he goes to (None: he signs somewhere else); years: the seasons that move
# (9999 = through the last real season and on into the live world); from: only his seasons with these teams.
# flat: a change in a team's wins for those seasons, with the reason.
WHATIFS = [
    {"id": "beltran_2005", "group": "Yours", "when": "January 2005", "title": "The Yankees sign Carlos Beltrán",
     "real": "Beltrán's side offered him to the Yankees at a discount that winter. They'd just traded for Randy Johnson and "
             "passed, and he signed with the Mets for 7 years and $119 million.",
     "moves": [{"p": "beltrca01", "to": "NYY", "years": [2005, 2011]}],
     "flat": [{"team": "NYY", "years": [2005, 2011], "wins": -1.0, "why": "the outfielder who loses his spot"},
              {"team": "NYM", "years": [2005, 2011], "wins": 1.0, "why": "the center fielder the Mets play instead"}]},
    {"id": "lee_trade_2010", "group": "Yours", "when": "July 2010", "title": "The Yankees trade for Cliff Lee",
     "real": "Seattle had a deal in place to send Lee to the Yankees for Jesús Montero, then took Texas's offer built around "
             "Justin Smoak. Lee pitched the Rangers past the Yankees in the ALCS.",
     "moves": [{"p": "leecl02", "to": "NYY", "years": [2010, 2010], "from": ["TEX"]}],
     "flat": [{"team": "NYY", "years": [2010, 2010], "wins": -0.4, "why": "the starter he bumps"},
              {"team": "TEX", "years": [2010, 2010], "wins": 0.4, "why": "the starter Texas runs out instead"}]},
    {"id": "cano_2014", "group": "Yours", "when": "December 2013", "title": "The Yankees re-sign Robinson Canó",
     "real": "The Yankees offered 7 years and $175 million. Seattle offered 10 years and $240 million, and he left. Two weeks "
             "later the Yankees signed Carlos Beltrán.",
     "moves": [{"p": "canoro01", "to": "NYY", "years": [2014, 2023]},
               {"p": "beltrca01", "to": None, "years": [2014, 2016], "from": ["NYY"]}],
     "flat": [{"team": "NYY", "years": [2014, 2018], "wins": -0.8, "why": "the second basemen they really played"},
              {"team": "SEA", "years": [2014, 2018], "wins": 1.0, "why": "the second baseman Seattle plays instead"}]},
    {"id": "harper_2019", "group": "Yours", "when": "February 2019", "title": "The Yankees sign Bryce Harper",
     "real": "The Yankees never really got in. Harper signed with the Phillies for 13 years and $330 million, the biggest "
             "deal in the sport at the time.",
     "moves": [{"p": "harpebr03", "to": "NYY", "years": [2019, 9999]}],
     "flat": [{"team": "NYY", "years": [2019, 2025], "wins": -1.2, "why": "the corner outfielder or DH who sits"},
              {"team": "PHI", "years": [2019, 2025], "wins": 1.0, "why": "the right fielder the Phillies play instead"}]},
    {"id": "maddux_1993", "group": "Arms", "when": "December 1992", "title": "The Yankees sign Greg Maddux",
     "real": "Fresh off his first Cy Young, Maddux had a bigger offer from the Yankees and took less to go to Atlanta, where "
             "he won the next three too.",
     "moves": [{"p": "maddugr01", "to": "NYY", "years": [1993, 2003]}],
     "flat": [{"team": "NYY", "years": [1993, 2003], "wins": -0.8, "why": "the starter he bumps"},
              {"team": "ATL", "years": [1993, 2003], "wins": 1.0, "why": "the starter Atlanta signs instead"}]},
    {"id": "lee_fa_2011", "group": "Arms", "when": "December 2010", "title": "Cliff Lee signs with the Yankees",
     "real": "The Yankees offered 7 years and about $148 million. Lee took less, 5 years and $120 million, to go back to "
             "Philadelphia.",
     "moves": [{"p": "leecl02", "to": "NYY", "years": [2011, 2014]}],
     "flat": [{"team": "NYY", "years": [2011, 2014], "wins": -0.8, "why": "the starter he bumps"},
              {"team": "PHI", "years": [2011, 2014], "wins": 0.8, "why": "the starter the Phillies sign instead"}]},
    {"id": "santana_2008", "group": "Arms", "when": "Winter 2007-08", "title": "The Yankees trade for Johan Santana",
     "real": "Minnesota wanted Phil Hughes, Melky Cabrera and a prospect. The Yankees wouldn't move Hughes, and the Twins "
             "sent Santana to the Mets for Carlos Gómez and three others.",
     "moves": [{"p": "santajo01", "to": "NYY", "years": [2008, 2012]},
               {"p": "hugheph01", "to": "MIN", "years": [2008, 2012], "from": ["NYY"]},
               {"p": "cabreme01", "to": "MIN", "years": [2008, 2008], "from": ["NYY"]},
               {"p": "gomezca01", "to": "NYM", "years": [2008, 2009], "from": ["MIN"]}],
     "flat": [{"team": "NYM", "years": [2008, 2012], "wins": 1.0, "why": "the starter the Mets get instead"}]},
    {"id": "cole_2008", "group": "Arms", "when": "August 2008", "title": "Gerrit Cole signs out of high school",
     "real": "The Yankees took Cole in the first round out of high school. He went to UCLA instead, went first overall to "
             "Pittsburgh in 2011, and didn't get to the Bronx until 2020.",
     "moves": [{"p": "colege01", "to": "NYY", "years": [2013, 2019]}],
     "flat": [{"team": "NYY", "years": [2013, 2019], "wins": -0.8, "why": "the starter he bumps"},
              {"team": "PIT", "years": [2013, 2017], "wins": 1.0, "why": "the starter Pittsburgh has instead"},
              {"team": "HOU", "years": [2018, 2019], "wins": 1.0, "why": "the starter Houston trades for instead"}]},
    {"id": "machado_2019", "group": "Bats", "when": "February 2019", "title": "The Yankees sign Manny Machado",
     "real": "Machado visited the Yankees that winter, but they'd already signed DJ LeMahieu and never made a real offer. "
             "He went to San Diego for 10 years and $300 million.",
     "moves": [{"p": "machama01", "to": "NYY", "years": [2019, 9999]}],
     "flat": [{"team": "NYY", "years": [2019, 2025], "wins": -1.2, "why": "the infielder who sits"},
              {"team": "SDP", "years": [2019, 2025], "wins": 1.0, "why": "the third baseman San Diego plays instead"}]},
    {"id": "soto_2025", "group": "Bats", "when": "December 2024", "title": "The Yankees keep Juan Soto",
     "real": "The Yankees offered 16 years and $760 million. The Mets went to 15 years and $765 million and got him. The "
             "Yankees pivoted to Max Fried, Cody Bellinger and Paul Goldschmidt.",
     "moves": [{"p": "sotoju01", "to": "NYY", "years": [2025, 9999]},
               {"p": "bellico01", "to": "CHC", "years": [2025, 9999], "from": ["NYY"]}],
     "flat": [{"team": "NYM", "years": [2025, 2025], "wins": 1.5, "why": "what the Mets do with the money instead"}]},
    {"id": "crawford_2011", "group": "Bats", "when": "December 2010", "title": "The Yankees sign Carl Crawford",
     "real": "The Yankees met with Crawford, but Boston swooped in with 7 years and $142 million. It went badly, and by "
             "August 2012 he was in the Dodgers trade.",
     "moves": [{"p": "crawfca02", "to": "NYY", "years": [2011, 2016]}],
     "flat": [{"team": "NYY", "years": [2011, 2016], "wins": -0.8, "why": "the outfielder who sits"},
              {"team": "BOS", "years": [2011, 2012], "wins": 0.8, "why": "the left fielder Boston plays instead"},
              {"team": "LAD", "years": [2012, 2016], "wins": 0.5, "why": "the outfielder the Dodgers play instead"}]},
    {"id": "arod_2004", "group": "Bats", "when": "December 2003", "title": "A-Rod's Boston deal goes through",
     "real": "Boston and Texas agreed to swap A-Rod for Manny Ramírez, but the players' union wouldn't let him cut his salary "
             "to make it work. Two months later the Yankees got him for Alfonso Soriano.",
     "moves": [{"p": "rodrial01", "to": "BOS", "years": [2004, 2010], "from": ["NYY"]},
               {"p": "rodrial01", "to": None, "years": [2011, 2016], "from": ["NYY"]},
               {"p": "soriaal01", "to": "NYY", "years": [2004, 2005], "from": ["TEX"]},
               {"p": "ramirma02", "to": "TEX", "years": [2004, 2008], "from": ["BOS"]},
               {"p": "garcino01", "to": "CHW", "years": [2004, 2004], "from": ["BOS"]},
               {"p": "ordonma01", "to": "BOS", "years": [2004, 2004], "from": ["CHW"]}],
     "flat": [{"team": "NYY", "years": [2004, 2016], "wins": 1.5, "why": "the third baseman they find instead"}]},
]
WHATIF = {x["id"]: x for x in WHATIFS}


# ---------------------------------------------------------------------------------------------------- the data
class Data:
    def __init__(self, d: dict):
        self.first, self.last = d["first"], d["last"]
        self.teams = d["teams"]
        self.people = d["people"]
        self.pidx = {p[0]: i for i, p in enumerate(d["people"])}
        self.BL = {k: i + 5 for i, k in enumerate(d["bat_line"])}   # bat row: [p, year, team, pos, wins, *line]
        self.PL = {k: i + 4 for i, k in enumerate(d["pit_line"])}   # pit row: [p, year, team, wins, *line]
        self.bat = defaultdict(list)
        self.pit = defaultdict(list)
        self.bat_y = defaultdict(list)
        self.pit_y = defaultdict(list)
        for r in d["bat"]:
            self.bat[r[0]].append(r)
            self.bat_y[r[1]].append(r)
        for r in d["pit"]:
            self.pit[r[0]].append(r)
            self.pit_y[r[1]].append(r)
        self.seasons = defaultdict(dict)
        for s in d["seasons"]:
            self.seasons[s[0]][s[1]] = s   # [year, team, lg, div, W, L, R, RA, rank, how]
        self.post = defaultdict(list)
        for p in d["post"]:
            self.post[p[0]].append(p)      # [year, round, winner, loser, wins, losses]
        self.awards = defaultdict(list)
        for a in d["awards"]:
            self.awards[a[0]].append(a)    # [year, award, lg, p]
        self.rosters = d["rosters"]
        self.names = d.get("names", {})  # franchise -> [[first year, name], ...]

    def name(self, p: int) -> str:
        x = self.people[p]
        return f"{x[1]} {x[2]}".strip()

    def rows_raw(self, p: int, y: int) -> list:
        return [r for r in self.bat[p] if r[1] == y] + [r for r in self.pit[p] if r[1] == y]

    def rows(self, p: int, y: int) -> list:
        """(team, wins, share of his season, starter?) for each team he played for that year."""
        out = []
        bg = sum(r[self.BL["G"]] for r in self.bat[p] if r[1] == y)
        po = sum(r[self.PL["IPOuts"]] for r in self.pit[p] if r[1] == y)
        for r in self.bat[p]:
            if r[1] == y:
                out.append((r[2], r[4], r[self.BL["G"]] / bg if bg else 1.0, False))
        for r in self.pit[p]:
            if r[1] == y:
                sp = r[self.PL["GS"]] >= 0.5 * r[self.PL["G"]]
                out.append((r[2], r[3], r[self.PL["IPOuts"]] / po if po else 1.0, sp))
        return out


@lru_cache(maxsize=1)
def data() -> Data:
    with open(os.path.join(DATA_DIR, "mlb.json"), "r", encoding="utf-8") as f:
        return Data(json.load(f))


def _nick(name: str) -> str:
    parts = name.split()
    return " ".join(parts[-2:]) if len(parts) > 1 and parts[-2] in ("Red", "White", "Blue", "Devil") else parts[-1]


def team_name(t: str, short=True, y: int | None = None) -> str:
    """A team's name (or nickname), as it was in season y: the Florida Marlins in 2010, the Miami Marlins from 2012."""
    D = data()
    x = D.teams.get(t) or {}
    if y is not None and t in D.names:
        nm = [n for (y0, n) in D.names[t] if y0 <= y]
        nm = nm[-1] if nm else D.names[t][0][1]
        return _nick(nm) if short else nm
    return (x.get("nick") if short else x.get("name")) or t


# ---------------------------------------------------------------------------------------------------- state
def state(sim) -> dict:
    m = sim.w.meta.setdefault("mlb", {})
    if "seed" not in m:
        m.update({"v": 1, "seed": int(sim.w.seed) % 1_000_003 if isinstance(sim.w.seed, int) else 7, "whatifs": [],
                  "fans": {}, "arch": {}, "news": []})
    return m


def whatifs(sim) -> list:
    return list(state(sim).get("whatifs") or [])


# ---------------------------------------------------------------------------------------------------- the calendar
def _last_weekday(year, month, weekday) -> dt.date:
    d = dt.date(year, month + 1, 1) - dt.timedelta(days=1) if month < 12 else dt.date(year, 12, 31)
    while d.weekday() != weekday:
        d -= dt.timedelta(days=1)
    return d


@lru_cache(maxsize=128)
def season_days(year: int) -> dict:
    """Game-day numbers for a season: Opening Day, the last day of the regular season (the last Sunday on or before Oct 4),
    each round of October as that era spaced them, and the offseason (Nov 15). 2020 was its own thing."""
    if year == 2020:
        od, end = calm.day_of(dt.date(2020, 7, 23)), calm.day_of(dt.date(2020, 9, 27))
    else:
        first_monday = dt.date(year, 4, 1) + dt.timedelta(days=(7 - dt.date(year, 4, 1).weekday()) % 7)
        od = calm.day_of(_last_weekday(year, 3, 3) if year >= 2018 else first_monday)
        end_d = dt.date(year, 10, 4)
        while end_d.weekday() != 6:
            end_d -= dt.timedelta(days=1)
        end = calm.day_of(end_d)
    if year <= 2011:
        r = {"WC": end + 2, "DS": end + 3, "CS": end + 12, "WS": end + 24}
    elif year <= 2021:
        r = {"WC": end + 2, "DS": end + 4, "CS": end + 11, "WS": end + 22}
    else:
        r = {"WC": end + 2, "DS": end + 6, "CS": end + 14, "WS": end + 26}
    return {"od": od, "end": end, **r, "off": calm.day_of(dt.date(year, 11, 15))}


# the draft, era by era: (first day, rounds)
DRAFTS = {2010: ((6, 7), 50), 2011: ((6, 6), 50), 2012: ((6, 4), 40), 2013: ((6, 6), 40), 2014: ((6, 5), 40),
          2015: ((6, 8), 40), 2016: ((6, 9), 40), 2017: ((6, 12), 40), 2018: ((6, 4), 40), 2019: ((6, 3), 40),
          2020: ((6, 10), 5), 2021: ((7, 11), 20), 2022: ((7, 17), 20), 2023: ((7, 9), 20), 2024: ((7, 14), 20),
          2025: ((7, 13), 20)}


def draft_info(year: int) -> tuple:
    """((month, day), rounds) for the MLB draft in a year (mid-July and 20 rounds from 2021 on)."""
    return DRAFTS.get(year, ((7, 13), 20) if year > 2025 else ((6, 7), 50))


def game_day(start: int, k: int, n: int) -> int:
    """The day of game k (0-based) of a best-of-n starting on `start` (2-3-2 for seven, 2-2-1 for five, travel days)."""
    if n == 7:
        return start + k + (k >= 2) + (k >= 5)
    if n == 5:
        return start + k + (k >= 2) + (k >= 4)
    return start + k


def completed(sim) -> int:
    """The last season that's over (its World Series played) as of today: nothing after it shows, no spoilers."""
    day = sim.w.day
    y = season_of_day(day)
    sd = season_days(y)
    ws_done = day > sd["WS"] + 10
    return y if ws_done else y - 1


def season_of_day(day: int) -> int:
    """The MLB season a day belongs to: before Opening Day is still last season's winter."""
    y = calm.date_of(day).year
    return y if day >= season_days(y)["od"] - 45 else y - 1


# ---------------------------------------------------------------------------------------------------- odds
def pyth(r, ra) -> float:
    return r ** 1.83 / (r ** 1.83 + ra ** 1.83) if r + ra else 0.5


def log5(a: float, b: float) -> float:
    d = a + b - 2 * a * b
    return (a - a * b) / d if d else 0.5


def series_p(p: float, n: int) -> float:
    k = n // 2 + 1
    return sum(math.comb(k - 1 + j, j) * p ** k * (1 - p) ** j for j in range(k))


def series_len(y: int, rnd: str) -> int:
    if rnd == "WC":
        return 3 if y == 2020 or y >= 2022 else 1
    if rnd == "DS":
        return 5
    return 7


def _rkey(r: str) -> str:
    """'ALDS1' -> 'DS'; 'WS' -> 'WS'; 'ALWC' -> 'WC'."""
    return "WS" if r == "WS" else r[2:4]


# ---------------------------------------------------------------------------------------------------- what-if deltas
@lru_cache(maxsize=32)
def deltas(ids: tuple) -> dict:
    """{year: {team: [regular-season wins, October wins]}} for a set of what-ifs (don't change what it returns)."""
    D = data()
    out = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    for wid in ids:
        wi = WHATIF.get(wid)
        if not wi:
            continue
        for m in wi.get("moves", []):
            p = D.pidx.get(m["p"])
            if p is None:
                continue
            for y in range(m["years"][0], min(m["years"][1], D.last) + 1):
                rows = [r for r in D.rows(p, y) if r[0] != m.get("to") and (not m.get("from") or r[0] in m["from"])]
                if not rows:
                    continue
                gain, share, sp = 0.0, 0.0, False
                for team, v, frac, starter in rows:
                    k = 1.3 if starter else 1.0
                    out[y][team][0] -= v
                    out[y][team][1] -= v / max(frac, 0.35) * k  # his October value: his full-season rate
                    gain += v
                    share += frac
                    sp = sp or starter
                if m.get("to"):
                    out[y][m["to"]][0] += gain
                    out[y][m["to"]][1] += gain / max(share, 0.35) * (1.3 if sp else 1.0)
        for f in wi.get("flat", []):
            for y in range(f["years"][0], min(f["years"][1], D.last) + 1):
                out[y][f["team"]][0] += f["wins"]
                out[y][f["team"]][1] += f["wins"]
    return {y: {t: v for t, v in d.items() if abs(v[0]) > 1e-9 or abs(v[1]) > 1e-9} for y, d in out.items()}


def _standings(y: int, dy: dict) -> dict:
    """{team: wins (float)} with the deltas in, and each team's gain taken back from its opponents (division rivals most)."""
    rows = data().seasons[y]
    adj = {t: 0.0 for t in rows}
    for t, (reg, _) in dy.items():
        if t not in rows:
            continue
        adj[t] += reg
        me = rows[t]
        wts = {o: 3.0 if (r[2], r[3]) == (me[2], me[3]) else 1.5 if r[2] == me[2] else 0.5 for o, r in rows.items() if o != t}
        tot = sum(wts.values())
        for o, x in wts.items():
            adj[o] -= reg * x / tot
    return {t: rows[t][4] + adj[t] for t in rows}


def _field(y: int, lg: str, wins: dict) -> list:
    """The playoff teams of one league in seed order, by that year's format ([] in 1994)."""
    S = data().seasons[y]
    if y == 1994:
        return []
    teams = [t for t, r in S.items() if r[2] == lg]
    key = lambda t: (-wins[t], S[t][8], -S[t][4], t)  # noqa: E731  (a tie goes the way it really went)
    divs = defaultdict(list)
    for t in teams:
        divs[S[t][3]].append(t)
    for d in divs.values():
        d.sort(key=key)
    winners = sorted((d[0] for d in divs.values()), key=key)
    rest = sorted((t for t in teams if t not in winners), key=key)
    if y <= 1993:
        return sorted(winners, key=lambda t: S[t][3])  # East, West
    if y <= 2011:
        return winners + rest[:1]
    if y == 2020:
        second = sorted((d[1] for d in divs.values() if len(d) > 1), key=key)
        others = sorted((t for t in teams if t not in winners and t not in second), key=key)
        return winners + second + others[:2]
    if y <= 2021:
        return winners + rest[:2]
    return winners + rest[:3]


def _rule_bracket(y: int, lg: str, seeds: list, S: dict):
    """A league's bracket from its seeds, as a tree: a team, or (round, left, right)."""
    if not seeds:
        return None
    if y <= 1993:
        return ("CS", seeds[0], seeds[1])
    if y <= 2011:
        w1, w2, w3, wc = seeds
        if S[w1][3] == S[wc][3]:
            return ("CS", ("DS", w1, w3), ("DS", w2, wc))
        return ("CS", ("DS", w1, wc), ("DS", w2, w3))
    if y == 2020:
        s = seeds
        return ("CS", ("DS", ("WC", s[0], s[7]), ("WC", s[3], s[4])), ("DS", ("WC", s[1], s[6]), ("WC", s[2], s[5])))
    if y <= 2021:
        return ("CS", ("DS", seeds[0], ("WC", seeds[3], seeds[4])), ("DS", seeds[1], seeds[2]))
    return ("CS", ("DS", seeds[0], ("WC", seeds[3], seeds[4])), ("DS", seeds[1], ("WC", seeds[2], seeds[5])))


def _real_bracket(y: int, lg: str):
    """The bracket that really happened, rebuilt from the series."""
    series = [s for s in data().post[y] if s[1] != "WS" and s[1].startswith(lg)]
    if not series:
        return None

    def node(team, rnd):
        """The series this team won in an earlier round (and what's under it), or the team itself."""
        for r in sorted((r for r in ROUND_ORDER if ROUND_ORDER[r] < ROUND_ORDER[rnd]), key=lambda r: -ROUND_ORDER[r]):
            for x in series:
                if _rkey(x[1]) == r and x[2] == team:
                    return (r, node(x[2], r), node(x[3], r))
        return team

    top = max(series, key=lambda x: ROUND_ORDER[_rkey(x[1])])
    r = _rkey(top[1])
    return (r, node(top[2], r), node(top[3], r))


def _teams_in(tree) -> list:
    if tree is None:
        return []
    if isinstance(tree, str):
        return [tree]
    return _teams_in(tree[1]) + _teams_in(tree[2])


def _dist(tree, strength, y) -> dict:
    """{team: chance it wins this part of the bracket}."""
    if isinstance(tree, str):
        return {tree: 1.0}
    rnd, a, b = tree
    da, db = _dist(a, strength, y), _dist(b, strength, y)
    n = series_len(y, rnd)
    out = defaultdict(float)
    for ta, pa in da.items():
        for tb, pb in db.items():
            p = series_p(log5(strength[ta], strength[tb]), n)
            out[ta] += pa * pb * p
            out[tb] += pa * pb * (1 - p)
    return dict(out)


def _games(rng, winner_wins: int, loser_wins: int) -> str:
    """A believable order of games: 'W'/'L' from the winner's side, ending on a win."""
    seq = ["W"] * (winner_wins - 1) + ["L"] * loser_wins
    rng.shuffle(seq)
    return "".join(seq) + "W"


def _play(rng, p: float, n: int) -> tuple[bool, int, int]:
    """Play a best-of-n: (did A win, A's wins, B's wins)."""
    k = n // 2 + 1
    a = b = 0
    while a < k and b < k:
        if rng.random() < p:
            a += 1
        else:
            b += 1
    return a == k, a, b


# ---------------------------------------------------------------------------------------------------- replaying a season
def _form(y: int) -> dict:
    """How each team really played that October: +0.02 a game for each series it won, -0.02 for each it lost. A matchup
    that never happened carries it, so a team that got hot keeps its heat and one change doesn't reshuffle every title."""
    f = defaultdict(float)
    for s in data().post[y]:
        f[s[2]] += 0.02
        f[s[3]] -= 0.02
    return f


def _strengths(y: int, dy: dict) -> tuple[dict, dict]:
    """(real, this world) game-winning strength per team in October: Pythagorean record, plus the October value moved."""
    S = data().seasons[y]
    real = {t: pyth(r[6], r[7]) for t, r in S.items()}
    alt = {t: min(0.75, max(0.25, real[t] + dy.get(t, [0, 0])[1] / 162)) for t in S}
    return real, alt


def replay(seed: int, ids: tuple, y: int) -> dict:
    """One season in a world: standings, the playoff field, every series and the champion, plus the odds both ways."""
    D = data()
    S = D.seasons[y]
    dy = deltas(tuple(ids)).get(y, {})
    real_series = {(s[1] if s[1] == "WS" else s[1][:2] + _rkey(s[1]), frozenset((s[2], s[3]))): s for s in D.post[y]}
    wins = _standings(y, dy) if dy else {t: float(r[4]) for t, r in S.items()}
    real_w = {t: float(r[4]) for t, r in S.items()}
    real_s, alt_s = _strengths(y, dy)
    form = _form(y)
    out = {"year": y, "changed": bool(dy), "wins": {t: round(v, 1) for t, v in wins.items()}, "series": [], "champ": None,
           "real_champ": next((s[2] for s in D.post[y] if s[1] == "WS"), None), "fields": {}, "odds": {}}
    if y == 1994:
        return out
    trees, real_trees = {}, {}
    for lg in ("AL", "NL"):
        real_tree = _real_bracket(y, lg)
        f_real, f_alt = _field(y, lg, real_w), _field(y, lg, wins)
        out["fields"][lg] = f_alt
        if f_real == f_alt and real_tree is not None:
            trees[lg] = real_tree
        else:
            trees[lg] = _rule_bracket(y, lg, f_alt, S)
        real_trees[lg] = real_tree

    def run(tree, lg):
        if isinstance(tree, str):
            return tree
        rnd, a, b = tree
        ta, tb = run(a, lg), run(b, lg)
        n = series_len(y, rnd)
        key = ("WS" if rnd == "WS" else lg + rnd, frozenset((ta, tb)))
        rng = random.Random(f"{seed}:{y}:{key[0]}:{min(ta, tb)}:{max(ta, tb)}")
        real = real_series.get(key)
        if real:
            win, lose = real[2], real[3]
            p0 = series_p(log5(real_s[win], real_s[lose]), n)
            p1 = series_p(log5(alt_s[win], alt_s[lose]), n)
            small = abs(dy.get(win, [0, 0])[1]) < 0.25 and abs(dy.get(lose, [0, 0])[1]) < 0.25
            if small or p1 >= p0 or rng.random() < p1 / p0:
                how, ww, ll = "real", real[4], real[5]
            else:  # the odds moved enough to flip it
                how, win, lose = "flipped", lose, win
                ww, ll = n // 2 + 1, rng.randrange(n // 2 + 1)
        else:
            won, aw, bw = _play(rng, log5(alt_s[ta] + form[ta], alt_s[tb] + form[tb]), n)
            how, win, lose = "new", (ta if won else tb), (tb if won else ta)
            ww, ll = (aw, bw) if won else (bw, aw)
        g = _games(rng, ww, ll)
        out["series"].append({"round": rnd, "lg": lg if rnd != "WS" else "MLB", "winner": win, "loser": lose,
                              "w": ww, "l": ll, "games": g, "how": how})
        return win

    champs = {lg: run(trees[lg], lg) for lg in ("AL", "NL") if trees[lg]}
    if len(champs) == 2:
        out["champ"] = run(("WS", champs["AL"], champs["NL"]), "WS")
    # the odds, both ways, for the teams the what-ifs touched the most
    if dy and all(trees.get(lg) for lg in ("AL", "NL")) and all(real_trees.get(lg) for lg in ("AL", "NL")):
        alt_tree = ("WS", trees["AL"], trees["NL"])
        real_tree = ("WS", real_trees["AL"], real_trees["NL"])
        pa, pr = _dist(alt_tree, alt_s, y), _dist(real_tree, real_s, y)
        for t, v in dy.items():
            if abs(v[0]) >= 1.0 or abs(v[1]) >= 1.0:
                out["odds"][t] = {"real": round(pr.get(t, 0.0), 3), "alt": round(pa.get(t, 0.0), 3),
                                  "in_real": t in _teams_in(real_tree), "in_alt": t in _teams_in(alt_tree)}
    return out


# ---------------------------------------------------------------------------------------------------- history in a world
_CACHE: dict = {}


def history(sim) -> dict:
    """{year: replayed season} for every season the world's what-ifs touch (the rest is just what happened)."""
    st = state(sim)
    ids = tuple(sorted(st.get("whatifs") or []))
    key = (st["seed"], ids)
    if key not in _CACHE:
        if len(_CACHE) > 16:
            _CACHE.clear()
        d = deltas(tuple(ids))
        _CACHE[key] = {y: replay(st["seed"], ids, y) for y in sorted(d) if d[y]}
    return _CACHE[key]


def season(sim, y: int) -> dict:
    """A real season (1990-2025) as it went in this world."""
    h = history(sim)
    if y in h:
        return h[y]
    D = data()
    S = D.seasons[y]
    ser = []
    for s in sorted(D.post[y], key=lambda s: ROUND_ORDER[_rkey(s[1])]):
        rng = random.Random(f"real:{y}:{s[1]}")
        ser.append({"round": _rkey(s[1]), "lg": "MLB" if s[1] == "WS" else s[1][:2], "winner": s[2], "loser": s[3],
                    "w": s[4], "l": s[5], "games": _games(rng, s[4], s[5]), "how": "real"})
    champ = next((s[2] for s in D.post[y] if s[1] == "WS"), None)
    return {"year": y, "changed": False, "wins": {t: float(r[4]) for t, r in S.items()}, "series": ser, "champ": champ,
            "real_champ": champ, "fields": {}, "odds": {}}


def titles(sim, team: str) -> dict:
    """A team's World Series titles, real and in this world, through the last season that's over by today."""
    D = data()
    upto = min(D.last, completed(sim))
    real = [y for y in range(D.first, upto + 1) if any(s[1] == "WS" and s[2] == team for s in D.post[y])]
    alt = [y for y in range(D.first, upto + 1) if season(sim, y)["champ"] == team]
    live = [int(y) for y, a in sorted(state(sim)["arch"].items()) if a.get("champ") == team]
    return {"real": real, "world": alt + live}


# ---------------------------------------------------------------------------------------------------- live seasons
FULL = {"H": 600, "SP": 540, "RP": 195}    # a full season: plate appearances / outs for a starter / outs for a reliever
MU = {"H": 1.0, "SP": 1.5, "RP": 0.3}      # what an unknown player regresses toward (wins per full season)
SERIES = 54                                 # 54 three-game series = 162 games
MARKET = {"NYY": 3.0, "LAD": 3.0, "NYM": 2.6, "BOS": 2.2, "PHI": 2.0, "CHC": 1.8, "SFG": 1.8, "TOR": 1.7, "ATL": 1.6,
          "TEX": 1.6, "SDP": 1.5, "ANA": 1.4, "HOU": 1.4, "SEA": 1.2, "STL": 1.1, "ARI": 1.1, "DET": 1.0, "BAL": 1.0,
          "MIL": 0.9, "MIN": 0.9, "WSN": 0.9, "CHW": 0.8, "CIN": 0.8, "KCR": 0.8, "COL": 0.8, "CLE": 0.7, "PIT": 0.6,
          "TBD": 0.6, "FLA": 0.6, "OAK": 0.6}
KNOWN_THROUGH = {  # long deals that were already signed when the story starts (approximate)
    "judgeaa01": 2031, "ohtansh01": 2033, "sotoju01": 2039, "harpebr03": 2031, "machama01": 2033, "troutmi01": 2030,
    "bettsmo01": 2032, "lindofr01": 2031, "seageco01": 2031, "tatisfe02": 2034, "wittbo02": 2034, "colege01": 2028,
    "stantmi03": 2027, "yamamyo01": 2035, "deverra01": 2033, "guerrvl02": 2039, "freemfr01": 2027, "friedma01": 2032,
    "burneco01": 2030, "wheelza01": 2027, "rodriju01": 2034}
LUCK_SD = 1.1                               # a regular's season can run about a win above or below his talent
SPREAD = 1.4                                # roster wins -> team wins (the depth chart misses the bench churn and defense)


def _project(D: Data, p: int):
    """(role, talent in wins per full season, position) from his last three real seasons (5/4/3 weights), regressed."""
    W = {D.last: 5, D.last - 1: 4, D.last - 2: 3}
    b = [r for r in D.bat[p] if r[1] in W]
    q = [r for r in D.pit[p] if r[1] in W]
    pa = sum(W[r[1]] * r[D.BL["PA"]] for r in b)
    outs = sum(W[r[1]] * r[D.PL["IPOuts"]] for r in q)
    th = (sum(W[r[1]] * r[4] for r in b) + 3 * MU["H"]) / (pa / 600 + 3) if pa else None
    tp, role = None, None
    if outs:
        g = sum(W[r[1]] * r[D.PL["G"]] for r in q)
        gs = sum(W[r[1]] * r[D.PL["GS"]] for r in q)
        role = "SP" if gs >= 0.5 * g else "RP"
        tp = (sum(W[r[1]] * r[3] for r in q) + 3 * MU[role]) / (outs / FULL[role] + 3)
    pos = max(b, key=lambda r: (r[1], r[D.BL["PA"]]))[3] if b else (role or "P")
    if th is not None and tp is not None and pa >= 600 and outs >= 0.8 * 540:
        return "H", th + 0.7 * tp, "TWP"  # a two-way player
    if tp is not None and outs * 600 / 540 >= pa:
        return role, tp, role
    if th is not None:
        return "H", th, pos
    return None


def _years(rng, age: int, v: float) -> int:
    if v >= 4:
        return max(1, min(10, 35 - age + rng.randint(-1, 2)))
    if v >= 2:
        return rng.randint(2, 5) if age < 32 else rng.randint(1, 3)
    return rng.randint(1, 2)


def _luck(seed, y, key) -> float:
    return random.Random(f"{seed}:{y}:luck:{key}").gauss(0, LUCK_SD)


def player_name(sim, key: str) -> str:
    x = state(sim).get("live", {}).get("pl", {}).get(key)
    if x and x.get("n"):
        return x["n"]
    p = data().pidx.get(key)
    return data().name(p) if p is not None else key


def _depth(L: dict, team: str) -> dict:
    """{player: share of a full season he plays}: nine regulars and four bench bats, five starters, eight relievers."""
    pl = L["pl"]
    mine = [(k, x) for k, x in pl.items() if x["t"] == team]
    out = {}
    hs = sorted((kx for kx in mine if kx[1]["r"] == "H"), key=lambda kx: (-kx[1]["v"], kx[0]))
    for i, (k, _) in enumerate(hs[:13]):
        out[k] = 0.92 if i < 9 else 0.3
    sp = sorted((kx for kx in mine if kx[1]["r"] == "SP"), key=lambda kx: (-kx[1]["v"], kx[0]))
    for i, (k, _) in enumerate(sp[:5]):
        out[k] = 0.9
    rp = sorted((kx for kx in mine if kx[1]["r"] == "RP"), key=lambda kx: (-kx[1]["v"], kx[0]))
    for i, (k, _) in enumerate(rp[:8]):
        out[k] = 0.9 if i < 6 else 0.5
    return out


def _team_war(sim, L: dict, y: int, with_luck=True) -> dict:
    seed = state(sim)["seed"]
    out = {}
    for t in data().teams:
        d = _depth(L, t)
        out[t] = sum((L["pl"][k]["v"] + (_luck(seed, y, k) if with_luck else 0)) * s for k, s in d.items())
    return out


def _build_live(sim):
    """The live world, from where everyone finished the last real season (what-ifs move the players they cover)."""
    D = data()
    st = state(sim)
    rng = random.Random(f"{st['seed']}:build")
    present = {}
    for wid in st.get("whatifs") or []:
        for m in WHATIF[wid]["moves"]:
            if m["years"][1] >= D.last and m.get("to"):
                present[m["p"]] = (m["to"], m.get("from"))
    pl = {}
    for t, ps in D.rosters.items():
        for p in ps:
            proj = _project(D, p)
            if not proj:
                continue
            role, v, pos = proj
            key = D.people[p][0]
            if key in present and (not present[key][1] or t in present[key][1]):
                t2 = present[key][0]
            else:
                t2 = t
            birth = D.people[p][3] or D.last - 28
            debut = D.people[p][6] or D.last
            age = D.last + 1 - birth
            if key in KNOWN_THROUGH:
                c = KNOWN_THROUGH[key]
            elif D.last - debut < 6:
                c = max(D.last, debut + 6)  # still under team control
            else:
                c = D.last + rng.choice([0, 0, 1, 1, 2, 3]) if v < 2 else D.last + _years(rng, age, v) - 1
            pl[key] = {"t": t2, "v": round(v, 2), "v0": round(v, 2), "r": role, "pos": pos, "b": birth, "c": c, "d": debut}
    st["live"] = {"year": D.last, "pl": pl, "gen": 0, "rec": {}, "l10": {}, "done": SERIES, "post": [], "str": {},
                  "proj": {}, "reacted": []}


def _gen_player(sim, L, rng, team: str, role: str, y: int, star=False) -> str:
    D = data()
    a, b = rng.randrange(len(D.people)), rng.randrange(len(D.people))
    first, last = D.people[a][1] or "Alex", D.people[b][2] or "Smith"
    L["gen"] += 1
    key = f"g{L['gen']}"
    mu = {"H": 0.4, "SP": 0.5, "RP": 0.1}[role]
    sd = {"H": 1.0, "SP": 1.0, "RP": 0.45}[role]
    v = rng.gauss(3.2, 0.9) if star else rng.gauss(mu, sd)
    pos = rng.choice(["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"]) if role == "H" else role
    L["pl"][key] = {"t": team, "v": round(v, 2), "v0": round(v, 2), "r": role, "pos": pos, "b": y - rng.randint(22, 25),
                    "c": y + 5, "d": y, "n": f"{first} {last}"}
    return key


def _news(sim, text: str, team: str | None = None, kind: str = "news", day: int | None = None):
    st = state(sim)
    st["news"].append({"day": sim.w.day if day is None else day, "text": text, "team": team, "kind": kind})
    del st["news"][:-120]


def _aging(age: int) -> float:
    return 0.6 if age <= 23 else 0.3 if age <= 26 else 0.0 if age <= 29 else -0.3 if age <= 31 else -0.5 if age <= 33 \
        else -0.8 if age <= 35 else -1.0


def _offseason(sim, y: int):
    """After season y: everyone ages a year, some retire, free agents sign, and rookies come up for y + 1."""
    D = data()
    st = state(sim)
    L = st["live"]
    rng = random.Random(f"{st['seed']}:{y}:off")
    nxt = y + 1
    day = season_days(y)["off"]
    pl = L["pl"]
    for key in sorted(pl):
        x = pl[key]
        age = nxt - x["b"]
        p_ret = (0.01 if age < 30 else 0.04 if age < 34 else 0.12 if age < 36 else 0.25 if age < 38 else 0.45 if age < 40 else 0.75)
        p_ret *= 2.0 if x["v"] < 0.5 else 0.35 if x["v"] > 3 else 1.0
        if rng.random() < p_ret:
            if x["v"] >= 2.0 or (key in D.pidx and _career(D, D.pidx[key]) >= 30):
                _news(sim, f"{player_name(sim, key)} retires at {age - 1}.", x["t"], "retire", day)
            del pl[key]
            continue
        k = 0.4 if x["r"] == "RP" else 1.0
        x["v"] = round(x["v"] + k * (_aging(age) + rng.gauss(0, 0.45)), 2)
    # free agency: the best sign first
    fa = sorted((k for k, x in pl.items() if x["c"] <= y), key=lambda k: (-pl[k]["v"], k))
    war = _team_war(sim, L, nxt, with_luck=False)
    avg = sum(war.values()) / len(war)
    for key in fa:
        x = pl[key]
        age = nxt - x["b"]
        if x["v"] < 0.0 and age >= 30 and rng.random() < 0.6:
            del pl[key]
            continue
        old = x["t"]
        if rng.random() < 0.42:
            t = old
        else:
            teams = sorted(D.teams)
            wts = [max(0.2, 1 + (avg - war[t]) / 12) * (MARKET.get(t, 1.0) ** (2 if x["v"] >= 3 else 0.5)) for t in teams]
            t = rng.choices(teams, wts)[0]
        n = _years(rng, age, x["v"])
        x["t"], x["c"] = t, y + n
        if t != old:
            war[old] -= x["v"] * 0.9
            war[t] += x["v"] * 0.9
            if x["v"] >= 2.5:
                _news(sim, f"{player_name(sim, key)} leaves the {team_name(old)} and signs with the {team_name(t)}: "
                           f"{n} year{'s' if n > 1 else ''}.", t, "signing", day)
    # rookies and call-ups: every team fills its holes, and adds a prospect or two
    for t in sorted(D.teams):
        mine = [x for x in pl.values() if x["t"] == t]
        need = {"H": 13 - sum(1 for x in mine if x["r"] == "H"), "SP": 6 - sum(1 for x in mine if x["r"] == "SP"),
                "RP": 8 - sum(1 for x in mine if x["r"] == "RP")}
        for role, k in need.items():
            for _ in range(max(0, k)):
                _gen_player(sim, L, rng, t, role, nxt)
        for _ in range(rng.choice([1, 2, 2, 3])):
            star = rng.random() < 0.035
            key = _gen_player(sim, L, rng, t, rng.choice(["H", "H", "SP", "RP"]), nxt, star)
            if star:
                _news(sim, f"The {team_name(t)} have a big one coming: {pl[key]['n']}, the top prospect in their system, "
                           f"makes the club out of camp.", t, "prospect", day)
        # a team only carries so many: the rest go down to the minors
        mine = sorted((k for k, x in pl.items() if x["t"] == t), key=lambda k: (-pl[k]["v"], k))
        for k in mine[34:]:
            if pl[k].get("n"):
                del pl[k]


def _career(D: Data, p: int) -> float:
    return sum(r[4] for r in D.bat[p]) + sum(r[3] for r in D.pit[p])


def _start_season(sim, y: int):
    st = state(sim)
    L = st["live"]
    war = _team_war(sim, L, y)
    base = _team_war(sim, L, y, with_luck=False)
    mean = sum(war.values()) / len(war)
    mean0 = sum(base.values()) / len(base)
    L.update({"year": y, "done": 0, "post": [], "reacted": [],
              "rec": {t: [0, 0] for t in war}, "l10": {t: "" for t in war},
              "str": {t: round(min(0.65, max(0.35, (81 + SPREAD * (war[t] - mean)) / 162)), 4) for t in war},
              "proj": {t: round(81 + SPREAD * (base[t] - mean0)) for t in base}})


def _series_day(y: int, k: int) -> int:
    sd = season_days(y)
    return sd["od"] + round(k * (sd["end"] - 2 - sd["od"]) / (SERIES - 1))


def _play_series(sim, k: int):
    D = data()
    st = state(sim)
    L = st["live"]
    y = L["year"]
    rng = random.Random(f"{st['seed']}:{y}:s{k}")
    al = sorted(t for t, x in D.teams.items() if x["lg"] == "AL")
    nl = sorted(t for t, x in D.teams.items() if x["lg"] == "NL")
    rng.shuffle(al)
    rng.shuffle(nl)
    if k % 6 == 5:
        pairs = list(zip(al, nl))
    else:
        pairs = [(al[i], al[i + 1]) for i in range(0, len(al) - 1, 2)] + [(nl[i], nl[i + 1]) for i in range(0, len(nl) - 1, 2)]
        if len(al) % 2:
            pairs.append((al[-1], nl[-1]))
    S = L["str"]
    for a, b in pairs:
        for g in range(3):
            p = log5(S[a], S[b]) + (0.02 if (k + g) % 2 == 0 else -0.02)
            w, l_ = (a, b) if rng.random() < p else (b, a)
            L["rec"][w][0] += 1
            L["rec"][l_][1] += 1
            L["l10"][w] = (L["l10"][w] + "W")[-10:]
            L["l10"][l_] = (L["l10"][l_] + "L")[-10:]


def _live_field(L: dict, lg: str) -> list:
    D = data()
    rec, S = L["rec"], L["str"]
    teams = [t for t, x in D.teams.items() if x["lg"] == lg]
    key = lambda t: (-rec[t][0], -S[t], t)  # noqa: E731
    divs = defaultdict(list)
    for t in teams:
        divs[D.teams[t]["div"]].append(t)
    winners = sorted((sorted(d, key=key)[0] for d in divs.values()), key=key)
    rest = sorted((t for t in teams if t not in winners), key=key)
    return winners + rest[:3]


def _postseason(sim):
    """October in the current format, all played now (seeded) and shown day by day as the dates come."""
    st = state(sim)
    L = st["live"]
    y = L["year"]
    sd = season_days(y)
    rng = random.Random(f"{st['seed']}:{y}:october")
    S = L["str"]
    seeds = {lg: _live_field(L, lg) for lg in ("AL", "NL")}
    L["fields"] = seeds
    rank = {t: i for lg in seeds for i, t in enumerate(seeds[lg])}
    out = []

    def run(tree, lg):
        if isinstance(tree, str):
            return tree
        rnd, a, b = tree
        ta, tb = run(a, lg), run(b, lg)
        if rnd == "WS":
            hi, lo = sorted((ta, tb), key=lambda t: (-L["rec"][t][0], t))
        else:
            hi, lo = sorted((ta, tb), key=lambda t: rank[t])
        n = series_len(y, rnd)
        need = n // 2 + 1
        aw = bw = 0
        seq = ""
        while aw < need and bw < need:
            home_hi = len(seq) in ((0, 1, 5, 6) if n == 7 else (0, 1, 4) if n == 5 else (0, 1, 2))
            p = log5(S[hi], S[lo]) + (0.02 if home_hi else -0.02)
            if rng.random() < p:
                aw += 1
                seq += "H"
            else:
                bw += 1
                seq += "L"
        win, lose = (hi, lo) if aw == need else (lo, hi)
        games = "".join(("W" if (c == "H") == (win == hi) else "L") for c in seq)
        out.append({"round": rnd, "lg": lg if rnd != "WS" else "MLB", "winner": win, "loser": lose,
                    "w": max(aw, bw), "l": min(aw, bw), "games": games, "how": "live", "high": hi, "start": sd[rnd]})
        return win

    champs = {lg: run(_rule_bracket(2022, lg, seeds[lg], {}), lg) for lg in ("AL", "NL")}
    L["champ"] = run(("WS", champs["AL"], champs["NL"]), "WS")
    L["post"] = out


def _awards(sim, y: int) -> list:
    st = state(sim)
    L = st["live"]
    seed = st["seed"]
    D = data()
    inpost = {t for f in (L.get("fields") or {}).values() for t in f}
    out = []
    for lg in ("AL", "NL"):
        cands = []
        for t in (t for t, x in D.teams.items() if x["lg"] == lg):
            for k, s in _depth(L, t).items():
                x = L["pl"][k]
                val = (x["v"] + _luck(seed, y, k)) * s
                cands.append((val, k, t, x))
        mvp = max(cands, key=lambda c: (c[0] + (0.8 if c[2] in inpost else 0), c[1]))
        cy = max((c for c in cands if c[3]["r"] == "SP"), key=lambda c: (c[0], c[1]))
        rook = [c for c in cands if c[3].get("d") == y]
        out.append({"award": "mvp", "lg": lg, "key": mvp[1], "name": player_name(sim, mvp[1]), "team": mvp[2]})
        out.append({"award": "cy", "lg": lg, "key": cy[1], "name": player_name(sim, cy[1]), "team": cy[2]})
        if rook:
            r = max(rook, key=lambda c: (c[0], c[1]))
            out.append({"award": "roy", "lg": lg, "key": r[1], "name": player_name(sim, r[1]), "team": r[2]})
    return out


AWARD_LABEL = {"mvp": "MVP", "cy": "Cy Young", "roy": "Rookie of the Year", "wsmvp": "World Series MVP"}


def _close_season(sim):
    st = state(sim)
    L = st["live"]
    y = L["year"]
    aw = _awards(sim, y)
    st["arch"][str(y)] = {"rec": {t: list(v) for t, v in L["rec"].items()}, "post": L["post"], "champ": L.get("champ"),
                          "fields": L.get("fields"), "awards": aw}
    day = season_days(y)["off"] - 1
    for a in aw:
        _news(sim, f"{a['name']} ({team_name(a['team'])}) wins the {a['lg']} {AWARD_LABEL[a['award']]}.", a["team"], "award", day)


def catch_up(sim):
    """Bring the MLB world to today. Safe to call any time: everything is seeded, so it comes out the same."""
    st = state(sim)
    day = sim.w.day
    D = data()
    if day < season_days(D.last)["off"]:
        return
    if "live" not in st:
        _build_live(sim)
        _offseason(sim, D.last)
        _start_season(sim, D.last + 1)
    L = st["live"]
    for _ in range(40):
        y = L["year"]
        while L["done"] < SERIES and _series_day(y, L["done"]) <= day:
            _play_series(sim, L["done"])
            L["done"] += 1
        if L["done"] < SERIES:
            break
        if not L["post"]:
            _postseason(sim)
        if day < season_days(y)["off"]:
            break
        _close_season(sim)
        _offseason(sim, y)
        _start_season(sim, y + 1)


def set_whatif(sim, wid: str, on: bool) -> dict:
    """Turn a what-if on or off. History replays; a player it covers who's still playing moves now."""
    if wid not in WHATIF:
        raise ValueError(f"no what-if called {wid}")
    st = state(sim)
    ids = set(st.get("whatifs") or [])
    (ids.add if on else ids.discard)(wid)
    st["whatifs"] = sorted(ids)
    moved = []
    L = st.get("live")
    if L:
        D = data()
        for m in WHATIF[wid]["moves"]:
            x = L["pl"].get(m["p"])
            if not x or m["years"][1] < D.last or not m.get("to"):
                continue
            p = D.pidx[m["p"]]
            real_team = next((t for t, ps in D.rosters.items() if p in ps), x["t"])
            new = m["to"] if on else real_team
            if x["t"] != new and (on or x["t"] == m["to"]):
                x["t"] = new
                moved.append(f"{player_name(sim, m['p'])} is a {team_name(new)} now.")
    return {"whatifs": st["whatifs"], "moved": moved}


# ---------------------------------------------------------------------------------------------------- today
def _reveal(series: list, day: int, y: int, starts: dict, fields: dict | None = None) -> list:
    """The series you can see on a day (from the day before they start), each with the games played so far."""
    seed_of = {t: i for f in (fields or {}).values() for i, t in enumerate(f)}
    out = []
    for s in sorted(series, key=lambda s: (ROUND_ORDER[s["round"]], s["lg"])):
        start = s.get("start", starts.get(s["round"]))
        if start is None or day < start - 1:
            continue
        n = series_len(y, s["round"])
        played = sum(1 for k in range(len(s["games"])) if game_day(start, k, n) <= day)
        g = s["games"][:played]
        done = played == len(s["games"])
        a, b = sorted((s["winner"], s["loser"]), key=lambda t: (seed_of.get(t, 99), t))
        wins = {s["winner"]: g.count("W"), s["loser"]: g.count("L")}
        nxt = next((game_day(start, k, n) for k in range(played, len(s["games"]))), None)
        out.append({"round": s["round"], "label": ROUND_LABEL[s["round"]], "lg": s["lg"], "teams": [a, b],
                    "wins": [wins[a], wins[b]], "done": done, "winner": s["winner"] if done else None,
                    "how": s.get("how", "real"), "next": calm.label(nxt) if nxt is not None and not done else None,
                    "ended": game_day(start, len(s["games"]) - 1, n)})
    return out


_CUR: dict = {}


def current(sim) -> dict:
    """The MLB season as of today: phase, records, the October you can see so far, the champion once it's decided."""
    catch_up(sim)
    st = state(sim)
    D = data()
    day = sim.w.day
    y = season_of_day(day)
    L = st.get("live") or {}
    key = (id(sim.w), day, tuple(st.get("whatifs") or []), L.get("year"), L.get("done"), len(st["arch"]))
    if _CUR.get("key") == key:
        return _CUR["val"]
    sd = season_days(y)
    out = {"year": y, "live": y > D.last, "l10": {}, "proj": {}}
    if y <= D.last:
        s = season(sim, y)
        frac = min(1.0, max(0.0, (day - sd["od"]) / (sd["end"] - sd["od"])))
        G = {t: r[4] + r[5] for t, r in D.seasons[y].items()}
        out["rec"] = {t: [round(w * frac), round((G[t] - w) * frac)] for t, w in s["wins"].items()}
        out["final_rec"] = {t: [round(w), G[t] - round(w)] for t, w in s["wins"].items()}
        series, fields = s["series"], s.get("fields") or {}
        if not fields:
            fields = {lg: [t for t in s["wins"] if t in {x["winner"] for x in series if x["lg"] == lg} | {x["loser"] for x in series if x["lg"] == lg}]
                      for lg in ("AL", "NL")}
        champ = s["champ"]
    elif str(y) in st["arch"]:
        a = st["arch"][str(y)]
        out["rec"] = a["rec"]
        out["final_rec"] = a["rec"]
        series, fields, champ = a["post"], a.get("fields") or {}, a.get("champ")
    else:
        out["rec"] = L.get("rec", {})
        out["final_rec"] = L.get("rec", {}) if L.get("done") == SERIES else None
        out["l10"] = L.get("l10", {})
        out["proj"] = L.get("proj", {})
        series, fields, champ = L.get("post") or [], L.get("fields") or {}, L.get("champ")
    starts = {r: sd[r] for r in ROUND_ORDER}
    out["october"] = _reveal(series, day, y, starts, fields) if day > sd["end"] else []
    ws = next((s for s in out["october"] if s["round"] == "WS" and s["done"]), None)
    out["champ"] = ws["winner"] if ws else None
    out["fields"] = fields if day > sd["end"] else {}
    out["phase"] = ("preseason" if day < sd["od"] else "regular" if day <= sd["end"]
                    else "october" if not ws else "offseason")
    out["eliminated"] = {}
    for s in out["october"]:
        if s["done"]:
            out["eliminated"][[t for t in s["teams"] if t != s["winner"]][0]] = s["ended"]
    _CUR.update(key=key, val=out)
    del champ
    return out


# ---------------------------------------------------------------------------------------------------- fans
FAN_SHARE = [("NYY", 44), ("BOS", 34), ("NYM", 12), ("", 10)]  # the shoreline: Yankees and Red Sox country, split


def fans(sim) -> dict:
    """{person: [team, how much they care: 0 not at all, 1 a fan, 2 die-hard]}. Everyone gets one the first time it's asked."""
    st = state(sim)
    f = st["fans"]
    prot = sim.w.meta.get("protagonist")
    for c in sim.w.chars.values():
        if c.id in f:
            continue
        rng = random.Random(f"{st['seed']}:fan:{c.id}")
        if c.id == prot:
            f[c.id] = ["NYY", 2]
            continue
        t = rng.choices([x[0] for x in FAN_SHARE], [x[1] for x in FAN_SHARE])[0] or rng.choice(sorted(data().teams))
        f[c.id] = [t, rng.choices([0, 1, 2], [40, 42, 18])[0]]
    return f


def my_team(sim) -> str:
    prot = sim.w.meta.get("protagonist")
    f = state(sim)["fans"].get(prot) if prot else None
    return f[0] if f else "NYY"


def set_team(sim, team: str):
    if team not in data().teams:
        raise ValueError(f"no MLB team {team}")
    prot = sim.w.meta.get("protagonist")
    if prot:
        fans(sim)[prot] = [team, 2]


def _react(sim):
    """When October settles something, the fans feel it: a title is a memory, a rival's title stings, an exit hurts."""
    from .history import Effects
    st = state(sim)
    cur = current(sim)
    y = cur["year"]
    done = set(st.setdefault("reacted", []))
    if not cur["october"]:
        return
    f = fans(sim)
    w = sim.w
    fx = None
    for s in cur["october"]:
        if not s["done"]:
            continue
        loser = [t for t in s["teams"] if t != s["winner"]][0]
        tag = f"{y}:{s['round']}:{s['winner']}:{loser}"
        if tag in done:
            continue
        done.add(tag)
        fx = fx or Effects(w, None)
        ws = s["round"] == "WS"
        for cid, (team, care) in sorted(f.items()):
            if not care or cid not in w.chars or w.chars[cid].status != "active":
                continue
            if ws and team == s["winner"]:
                fx.mood(cid, 6 * care, "their team won the World Series")
                fx.memory(cid, "pro_title", [], 0.35 * care, 25 * care, f"The {team_name(team, True, y)} won the {y} World Series")
            elif team == loser:
                fx.mood(cid, -(3 if not ws else 5) * care, f"the {team_name(team, True, y)} got knocked out")
                if ws or care == 2:
                    fx.memory(cid, "pro_heartbreak", [], -0.2 * care, 12 * care,
                              f"The {team_name(team, True, y)} lost the {y} {ROUND_LABEL[s['round']]} to the "
                              f"{team_name(s['winner'], True, y)}")
            elif ws and team in RIVALS.get(s["winner"], []):
                fx.mood(cid, -2 * care, f"the {team_name(s['winner'], True, y)} won it all")
        if ws or my_team(sim) in s["teams"]:
            _news(sim, f"The {team_name(s['winner'], True, y)} beat the {team_name(loser, True, y)} {s['wins'][s['teams'].index(s['winner'])]}-"
                       f"{s['wins'][s['teams'].index(loser)]}" + (f" to win the {y} World Series." if ws else f" in the {s['label']}."),
                  s["winner"], "october", s["ended"])
    st["reacted"] = sorted(done)[-60:]


def weekly(sim):
    """The engine's weekly step: play the background season up to today and let the fans react."""
    catch_up(sim)
    _react(sim)


# ---------------------------------------------------------------------------------------------------- the draft
def draft_order(sim, year: int) -> list:
    """The MLB draft order in July of `year`: worst record last season picks first (no lottery). Full team names."""
    D = data()
    prev = year - 1
    if prev <= D.last:
        wins = season(sim, prev)["wins"]
    elif str(prev) in state(sim)["arch"]:
        wins = {t: r[0] for t, r in state(sim)["arch"][str(prev)]["rec"].items()}
    else:
        return []
    return [team_name(t, False, prev) for t in sorted(wins, key=lambda t: (wins[t], t))]


# ---------------------------------------------------------------------------------------------------- stat lines
_RATES: dict = {}


def _rates(key: str, x: dict) -> dict:
    """Per-PA (hitters) or per-out (pitchers) rates from his last three real seasons; a line that fits his talent otherwise."""
    if key in _RATES:
        return _RATES[key]
    D = data()
    p = D.pidx.get(key)
    v = x.get("v0", x["v"])
    if x["r"] == "H":
        rows = [r for r in D.bat[p] if r[1] >= D.last - 2] if p is not None and not x.get("n") else []
        pa = sum(r[D.BL["PA"]] for r in rows)
        if pa >= 120:
            out = {k: sum(r[D.BL[k]] for r in rows) / pa for k in ("AB", "H", "2B", "3B", "HR", "RBI", "R", "SB", "BB", "SO")}
        else:
            ab = 0.885
            out = {"AB": ab, "H": ab * (0.238 + 0.006 * v), "2B": 0.045, "3B": 0.004, "HR": 0.026 + 0.006 * v,
                   "RBI": 0.11 + 0.012 * v, "R": 0.115 + 0.01 * v, "SB": 0.015, "BB": 0.08 + 0.004 * v, "SO": 0.22 - 0.01 * v}
    else:
        rows = [r for r in D.pit[p] if r[1] >= D.last - 2] if p is not None and not x.get("n") else []
        outs = sum(r[D.PL["IPOuts"]] for r in rows)
        if outs >= 90:
            out = {k: sum(r[D.PL[k]] for r in rows) / outs for k in ("H", "ER", "HR", "BB", "SO")}
        else:
            era = (4.25 - 0.35 * v) if x["r"] == "SP" else (4.0 - 0.9 * v)
            out = {"H": 0.29, "ER": max(1.5, era) / 27, "HR": 0.037, "BB": 0.11, "SO": 0.33 + 0.03 * v}
    _RATES[key] = out
    return out


def line(sim, key: str, y: int, share: float, frac: float, team_pct: float = 0.5, closer: bool = False) -> dict:
    """His season so far (frac of it played), from his rates moved by how his season is going against his talent."""
    st = state(sim)
    x = st["live"]["pl"][key]
    r = _rates(key, x)
    d = x["v"] + _luck(st["seed"], y, key) - x.get("v0", x["v"])
    if x["r"] == "H":
        f = min(1.3, max(0.75, 1 + 0.06 * d))
        pa = round(650 * share * frac)
        ab = round(pa * r["AB"])
        h = round(ab * r["H"] / r["AB"] * f ** 0.5) if ab else 0
        hr = round(pa * r["HR"] * f)
        bb = round(pa * r["BB"])
        tb = h + round(pa * r["2B"]) + 2 * round(pa * r["3B"]) + 3 * hr
        return {"pa": pa, "avg": round(h / ab, 3) if ab else 0.0, "hr": hr, "rbi": round(pa * r["RBI"] * f ** 0.7),
                "r": round(pa * r["R"] * f ** 0.7), "sb": round(pa * r["SB"]), "bb": bb,
                "ops": round((h + bb) / pa + tb / ab, 3) if pa and ab else 0.0}
    outs = round(FULL[x["r"]] * share * frac)
    era = min(7.5, max(1.2, r["ER"] * 27 - (0.35 if x["r"] == "SP" else 0.9) * d))
    so = round(outs * r["SO"] * (1 + 0.03 * d))
    out = {"ip": f"{outs // 3}.{outs % 3}", "outs": outs, "era": round(era, 2), "so": so}
    if x["r"] == "SP":
        dec = 32 * share * frac * 0.66
        wshare = min(0.8, max(0.25, team_pct + 0.03 * (x["v"] + d - 2)))
        out["w"] = round(dec * wshare)
        out["l"] = round(dec) - out["w"]
    elif closer:
        out["sv"] = round(162 * frac * team_pct * 0.42)
    return out


def _lines(sim, y: int, frac: float) -> list:
    """Every player who plays, with his line: [(key, team, line, share)]."""
    st = state(sim)
    L = st["live"]
    rec = L["rec"]
    out = []
    for t in sorted(data().teams):
        d = _depth(L, t)
        w, l_ = rec.get(t, [0, 0])
        pct = w / (w + l_) if w + l_ else 0.5
        rps = sorted((k for k in d if L["pl"][k]["r"] == "RP"), key=lambda k: (-L["pl"][k]["v"], k))
        for k, s in d.items():
            out.append((k, t, line(sim, k, y, s, frac, pct, closer=bool(rps) and k == rps[0]), s))
    return out


LEADER_STATS = [("hr", "Home runs", "H", False), ("avg", "Batting average", "H", False), ("rbi", "RBI", "H", False),
                ("sb", "Stolen bases", "H", False), ("era", "ERA", "P", True), ("so", "Strikeouts", "P", False),
                ("w", "Wins", "P", False), ("sv", "Saves", "P", False)]


def leaders(sim, n=5) -> list:
    """The live season's leaders so far (each league), or [] before there's a live season."""
    st = state(sim)
    L = st.get("live")
    if not L or L["done"] == 0 and not st["arch"]:
        return []
    y = L["year"]
    frac = L["done"] / SERIES
    if frac == 0:
        return []
    rows = _lines(sim, y, frac)
    games = 162 * frac
    out = []
    for key, label, kind, low in LEADER_STATS:
        for lg in ("AL", "NL"):
            pool = []
            for k, t, ln, _ in rows:
                if data().teams[t]["lg"] != lg or key not in ln:
                    continue
                if key == "avg" and ln["pa"] < 3.1 * games:
                    continue
                if key == "era" and ln["outs"] < 2.4 * games:  # 0.8 innings a game (the sim's starters throw ~160)
                    continue
                pool.append((ln[key], k, t))
            pool.sort(key=lambda r: (r[0] if low else -r[0], r[1]))
            out.append({"stat": key, "label": label, "lg": lg,
                        "rows": [{"name": player_name(sim, k), "team": t, "abbr": data().teams[t]["abbr"],
                                  "value": (f"{v:.3f}".lstrip("0") if key == "avg" else f"{v:.2f}" if key == "era" else v)}
                                 for v, k, t in pool[:n]]})
    return out


# ---------------------------------------------------------------------------------------------------- views
def _moved_team(ids, key: str, y: int, real: str) -> str:
    for wid in ids:
        for m in WHATIF[wid]["moves"]:
            if m["p"] == key and m["years"][0] <= y <= m["years"][1] and real != m.get("to") and (not m.get("from") or real in m["from"]):
                return m.get("to") or ""
    return real


def _stars(sim, team: str, y: int, n=4) -> list:
    """The team's best players right now, with their lines."""
    D = data()
    st = state(sim)
    if y > D.last and st.get("live"):
        L = st["live"]
        frac = L["done"] / SERIES if L["year"] == y else 1.0
        d = _depth(L, team)
        w, l_ = L["rec"].get(team, [0, 0])
        pct = w / (w + l_) if w + l_ else 0.5
        top = sorted(d, key=lambda k: (-L["pl"][k]["v"], k))[:n]
        here = {m["p"] for wid in st.get("whatifs") or [] for m in WHATIF[wid]["moves"]
                if m.get("to") == team and m["years"][1] >= D.last}
        top += [k for k in sorted(here) if k in d and k not in top]  # a what-if's player always shows
        return [{"name": player_name(sim, k), "pos": L["pl"][k]["pos"], "age": y - L["pl"][k]["b"],
                 "talent": round(L["pl"][k]["v"], 1), "moved": k in here,
                 "line": _line_text(line(sim, k, y, d[k], frac, pct)) if frac else None} for k in top]
    ids = tuple(st.get("whatifs") or [])
    vals = defaultdict(float)
    for rows, vi in ((D.bat, 4), (D.pit, 3)):
        for p, rs in rows.items():
            for r in rs:
                if r[1] == y and _moved_team(ids, D.people[p][0], y, r[2]) == team:
                    vals[p] += r[vi]
    top = sorted(vals, key=lambda p: -vals[p])[:n]
    frac = _frac(sim, y)
    moved = [p for p in vals if any(_moved_team(ids, D.people[p][0], y, r[2]) == team != r[2] for r in D.rows_raw(p, y))]
    top += [p for p in moved if p not in top]
    return [{"name": D.name(p), "pos": _pos_of(D, p, y), "age": y - (D.people[p][3] or y - 28), "talent": round(vals[p], 1),
             "line": _real_line(D, p, y, frac) if frac > 0 else None, "moved": p in moved} for p in top]


def _frac(sim, y: int) -> float:
    """How much of season y has been played by today (0 before Opening Day, 1 once it's over)."""
    sd = season_days(y)
    return min(1.0, max(0.0, (sim.w.day - sd["od"]) / (sd["end"] - sd["od"])))


def _real_line(D: Data, p: int, y: int, frac: float) -> str | None:
    """His real season so far (counting stats scaled to today; rates as they finished)."""
    b = [r for r in D.bat[p] if r[1] == y]
    q = [r for r in D.pit[p] if r[1] == y]
    if b and sum(r[D.BL["PA"]] for r in b) >= sum(r[D.PL["IPOuts"]] for r in q):
        tot = {k: sum(r[D.BL[k]] for r in b) for k in ("AB", "H", "HR", "RBI")}
        avg = f"{tot['H'] / tot['AB']:.3f}".lstrip("0") if tot["AB"] else ".000"
        return f"{avg}, {round(tot['HR'] * frac)} HR, {round(tot['RBI'] * frac)} RBI"
    if q:
        tot = {k: sum(r[D.PL[k]] for r in q) for k in ("W", "L", "ER", "IPOuts", "SO", "SV", "GS")}
        era = tot["ER"] * 27 / tot["IPOuts"] if tot["IPOuts"] else 0
        out = f"{era:.2f} ERA, {round(tot['SO'] * frac)} K"
        if tot["GS"]:
            out = f"{round(tot['W'] * frac)}-{round(tot['L'] * frac)}, " + out
        if tot["SV"] >= 5:
            out += f", {round(tot['SV'] * frac)} saves"
        return out
    return None


def _real_leaders(sim, cur: dict, n=5) -> list:
    """A real season's leaders so far: counting stats scaled to today, rates for the qualified (as the year finished)."""
    D = data()
    y = cur["year"]
    if y > D.last or y not in D.seasons:
        return []
    frac = _frac(sim, y)
    if frac <= 0:
        return []
    S = D.seasons[y]
    ids = tuple(state(sim).get("whatifs") or [])
    G = 162 * frac
    pool = defaultdict(list)
    for r in D.bat_y[y]:
        t = _moved_team(ids, D.people[r[0]][0], y, r[2])
        if t not in S:
            continue
        lg = S[t][2]
        ab, h, pa = r[D.BL["AB"]], r[D.BL["H"]], r[D.BL["PA"]]
        for k, v in (("hr", r[D.BL["HR"]] * frac), ("rbi", r[D.BL["RBI"]] * frac), ("sb", r[D.BL["SB"]] * frac)):
            pool[(k, lg)].append((round(v), r[0], t))
        if ab and pa * frac >= 3.1 * G * 0.98:
            pool[("avg", lg)].append((h / ab, r[0], t))
    for r in D.pit_y[y]:
        t = _moved_team(ids, D.people[r[0]][0], y, r[2])
        if t not in S:
            continue
        lg = S[t][2]
        outs = r[D.PL["IPOuts"]]
        for k, v in (("so", r[D.PL["SO"]] * frac), ("w", r[D.PL["W"]] * frac), ("sv", r[D.PL["SV"]] * frac)):
            pool[(k, lg)].append((round(v), r[0], t))
        if outs and outs * frac >= 3 * G * 0.98:
            pool[("era", lg)].append((r[D.PL["ER"]] * 27 / outs, r[0], t))
    out = []
    for key, label, kind, low in LEADER_STATS:
        for lg in ("AL", "NL"):
            rows = sorted(pool[(key, lg)], key=lambda x: (x[0] if low else -x[0], x[1]))[:n]
            out.append({"stat": key, "label": label, "lg": lg,
                        "rows": [{"name": D.name(p), "team": t, "abbr": D.teams[t]["abbr"],
                                  "value": (f"{v:.3f}".lstrip("0") if key == "avg" else f"{v:.2f}" if key == "era" else v)}
                                 for v, p, t in rows]})
    return out


def _team_of(D: Data, p: int, y: int) -> str:
    rows = D.rows(p, y)
    return max(rows, key=lambda r: r[2])[0] if rows else ""


def _pos_of(D: Data, p: int, y: int) -> str:
    b = [r for r in D.bat[p] if r[1] == y]
    if b:
        return max(b, key=lambda r: r[D.BL["PA"]])[3]
    q = [r for r in D.pit[p] if r[1] == y]
    return ("SP" if q and q[0][D.PL["GS"]] >= 0.5 * q[0][D.PL["G"]] else "RP") if q else ""


def _line_text(ln: dict) -> str:
    if "avg" in ln:
        return f"{ln['avg']:.3f}".lstrip("0") + f", {ln['hr']} HR, {ln['rbi']} RBI"
    s = f"{ln['era']:.2f} ERA, {ln['so']} K"
    if "w" in ln:
        s = f"{ln['w']}-{ln['l']}, " + s
    if ln.get("sv"):
        s += f", {ln['sv']} saves"
    return s


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def standings(sim, cur: dict | None = None) -> list:
    D = data()
    cur = cur or current(sim)
    me = my_team(sim)
    rec = cur["rec"]
    y = cur["year"]
    out = []
    divs = defaultdict(list)
    for t, x in D.teams.items():
        if y <= D.last:
            r = D.seasons[y].get(t)
            if not r:
                continue
            divs[(r[2], r[3])].append(t)
        else:
            divs[(x["lg"], x["div"])].append(t)
    real_rank = {t: r[8] for t, r in D.seasons[y].items()} if y <= D.last else {}
    for (lg, dv) in sorted(divs, key=lambda k: (k[0], "ECW".index(k[1]) if k[1] in "ECW" else 9)):
        ts = sorted(divs[(lg, dv)], key=lambda t: (-rec.get(t, [0, 0])[0], rec.get(t, [0, 0])[1], real_rank.get(t, 0), t))
        lw, ll = rec.get(ts[0], [0, 0])
        rows = []
        for t in ts:
            w, l_ = rec.get(t, [0, 0])
            gb = ((lw - w) + (l_ - ll)) / 2
            l10 = cur["l10"].get(t, "")
            streak = ""
            if l10:
                c = l10[-1]
                k = len(l10) - len(l10.rstrip(c))
                streak = f"{c}{k}"
            rows.append({"team": t, "nick": team_name(t, True, y), "abbr": D.teams[t]["abbr"], "w": w, "l": l_,
                         "pct": f"{w / (w + l_):.3f}".lstrip("0") if w + l_ else ".000", "gb": "-" if gb <= 0 else f"{gb:g}",
                         "l10": f"{l10.count('W')}-{l10.count('L')}" if l10 else None, "streak": streak or None,
                         "proj": cur["proj"].get(t), "you": t == me,
                         "in": t in (cur.get("fields") or {}).get(lg, [])})
        out.append({"lg": lg, "div": dv, "label": f"{lg} {DIV_LABEL.get(dv, dv)}", "rows": rows})
    return out


def _team_card(sim, team: str, cur: dict, table: list) -> dict:
    D = data()
    y = cur["year"]
    div = next(d for d in table if any(r["team"] == team for r in d["rows"]))
    pos = next(i for i, r in enumerate(div["rows"]) if r["team"] == team)
    row = div["rows"][pos]
    w, l_ = row["w"], row["l"]
    place = (f"{_ordinal(pos + 1)} in the {div['label']}" + ("" if pos == 0 else f", {row['gb']} back")) if w + l_ else None
    status = None
    ph = cur["phase"]
    lg = div["lg"]
    if ph in ("october", "offseason") and cur["fields"]:
        if team not in cur["fields"].get(lg, []):
            status = f"Missed the playoffs ({cur['final_rec'][team][0]}-{cur['final_rec'][team][1]})." if cur.get("final_rec") else "Missed the playoffs."
        elif cur["champ"] == team:
            status = f"World Series champions, {y}."
        elif team in cur["eliminated"]:
            s = next(s for s in cur["october"] if s["done"] and team in s["teams"] and s["winner"] != team)
            status = f"Out in the {s['label']}: lost to the {team_name(s['winner'], True, y)} {max(s['wins'])}-{min(s['wins'])}."
        else:
            s = next((s for s in reversed(cur["october"]) if team in s["teams"]), None)
            if s:
                i = s["teams"].index(team)
                status = (f"In the {s['label']}: " + ("tied" if s["wins"][0] == s["wins"][1] else
                          ("up" if s["wins"][i] > s["wins"][1 - i] else "down")) + f" {max(s['wins'])}-{min(s['wins'])} "
                          f"with the {team_name(s['teams'][1 - i], True, y)}" + (f" · next game {s['next']}" if s["next"] else "") + ".")
            else:
                status = "In the playoffs."
    elif ph == "preseason":
        status = f"Projected for about {cur['proj'].get(team)} wins." if cur["proj"].get(team) else "Spring training."
    elif ph == "regular" and w + l_:
        status = "Holding a playoff spot." if team in _spots(cur, lg) else "Out of a playoff spot right now."
    t = titles(sim, team)
    return {"team": team, "name": team_name(team, False, y), "nick": team_name(team, True, y), "abbr": D.teams[team]["abbr"],
            "record": f"{w}-{l_}" if w + l_ else None, "place": place, "status": status, "l10": row["l10"],
            "streak": row["streak"], "stars": _stars(sim, team, y), "titles": t,
            "rival": [team_name(r, True, y) for r in RIVALS.get(team, [])]}


def _spots(cur: dict, lg: str) -> list:
    """Who'd be in if the season ended today."""
    y = cur["year"]
    if y <= data().last:
        return _field(y, lg, {t: float(r[0]) - 0.001 * r[1] for t, r in cur["rec"].items()})
    return _live_field({"rec": cur["rec"], "str": {t: 0.5 for t in cur["rec"]}}, lg)


def view(sim) -> dict:
    """The MLB page: your team, the standings, October, the leaders, the news, the what-ifs."""
    catch_up(sim)
    _react(sim)
    st = state(sim)
    fans(sim)
    cur = current(sim)
    table = standings(sim, cur)
    me = my_team(sim)
    D = data()
    news = [{"date": calm.label(n["day"]), "text": n["text"], "kind": n["kind"], "mine": n.get("team") == me}
            for n in reversed(st["news"]) if n["day"] <= sim.w.day][:14]
    on = set(st.get("whatifs") or [])
    return {"year": cur["year"], "phase": cur["phase"], "today": calm.label(sim.w.day),
            "my_team": _team_card(sim, me, cur, table), "standings": table, "october": cur["october"],
            "leaders": leaders(sim) if cur["live"] else _real_leaders(sim, cur), "news": news,
            "whatifs": [{"id": x["id"], "title": x["title"], "when": x["when"], "group": x["group"], "on": x["id"] in on}
                        for x in WHATIFS],
            "teams": sorted(({"team": t, "name": team_name(t, False, cur["year"]), "nick": team_name(t, True, cur["year"]),
                             "abbr": x["abbr"]} for t, x in D.teams.items()), key=lambda r: r["name"]),
            "years": list(range(D.first, completed(sim) + 1)),
            "source": "Real MLB through 2025 (Lahman database), as it happens day by day; everything after is this world's."}


def whatif_view(sim, wid: str) -> dict:
    """One what-if on its own: what moved, and season by season what changed (and the odds)."""
    wi = WHATIF[wid]
    D = data()
    st = state(sim)
    moves = []
    for m in wi["moves"]:
        p = D.pidx.get(m["p"])
        yrs = [y for y in range(m["years"][0], min(m["years"][1], D.last) + 1)]
        tot = sum(v for y in yrs for (t, v, _, _) in D.rows(p, y) if t != m.get("to") and (not m.get("from") or t in m["from"]))
        span = f"{yrs[0]}-{yrs[-1]}" if len(yrs) > 1 else str(yrs[0]) if yrs else ""
        moves.append({"name": D.name(p), "to": team_name(m["to"]) if m.get("to") else None, "years": span,
                      "wins": round(tot, 1), "now": m["years"][1] >= 9999})
    seasons = []
    d = deltas((wid,))
    focus = "NYY"
    done = completed(sim)
    later = [y for y in sorted(d) if y > done]
    for y in sorted(y for y in d if y <= done):
        r = replay(st["seed"], (wid,), y)
        real = season(sim, y) if False else None
        del real
        rs = D.seasons[y].get(focus)
        if not rs:
            continue
        def path(series, team):
            out = []
            for s in series:
                if team in (s["winner"], s["loser"]):
                    out.append(("Won" if s["winner"] == team else "Lost") + f" the {ROUND_LABEL[s['round']]}" +
                               ("" if s["round"] == "WS" else "") + f" {s['w']}-{s['l']}" +
                               ("" if s["winner"] == team else f" to the {team_name(s['winner'], True, y)}") +
                               (f" over the {team_name(s['loser'], True, y)}" if s["winner"] == team else ""))
            return out
        real_series = sorted(({"round": _rkey(x[1]), "winner": x[2], "loser": x[3], "w": x[4], "l": x[5]} for x in D.post[y]),
                             key=lambda x: ROUND_ORDER[x["round"]])
        alt_w = r["wins"].get(focus, rs[4])
        o = r["odds"].get(focus)
        seasons.append({"year": y, "real": f"{rs[4]}-{rs[5]}", "world": f"{round(alt_w)}-{rs[4] + rs[5] - round(alt_w)}",
                        "change": round(d[y].get(focus, [0, 0])[0], 1),
                        "real_path": path(real_series, focus) or ["Missed the playoffs"] if y != 1994 else ["The strike: no October"],
                        "world_path": path(r["series"], focus) or ["Missed the playoffs"] if y != 1994 else ["The strike: no October"],
                        "odds": {"real": o["real"], "world": o["alt"]} if o else None,
                        "champ": team_name(r["champ"], True, y) if r["champ"] else None,
                        "real_champ": team_name(r["real_champ"], True, y) if r["real_champ"] else None})
    t_real = [s["year"] for s in seasons if s["real_champ"] == team_name(focus)]
    t_world = [s["year"] for s in seasons if s["champ"] == team_name(focus)]
    return {"id": wid, "title": wi["title"], "when": wi["when"], "real": wi["real"], "group": wi["group"],
            "on": wid in (st.get("whatifs") or []), "moves": moves,
            "flat": [{"team": team_name(f["team"]), "years": f"{f['years'][0]}-{f['years'][1]}" if f["years"][0] != f["years"][1]
                      else str(f["years"][0]), "wins": f["wins"], "why": f["why"]} for f in wi.get("flat", [])],
            "seasons": seasons, "titles": {"real": t_real, "world": t_world},
            "later": ({"years": f"{later[0]}-{later[-1]}" if len(later) > 1 else str(later[0]),
                       "line": ("It hasn't happened yet: it's " + wi["when"] + "." if not seasons else
                                f"The rest ({later[0]} on) plays out as the story gets there.")} if later else None),
            "how": ("Each season, the Yankees' wins move by what the players were worth (an estimate in wins, like WAR), and "
                    "October replays: a series that really happened keeps its result unless the new odds flip it; a matchup "
                    "that never happened is played fresh. This world rolls it once, so it stays put.")}


def year_view(sim, y: int) -> dict:
    """A past season in this world: the final standings, October, the awards."""
    D = data()
    st = state(sim)
    if y > completed(sim) or y < D.first:
        raise ValueError(f"{y} hasn't been played yet")
    if y > D.last:
        a = st["arch"].get(str(y))
        if not a:
            raise ValueError(f"{y} hasn't been played yet")
        cur = {"year": y, "rec": a["rec"], "final_rec": a["rec"], "l10": {}, "proj": {}, "fields": a.get("fields") or {},
               "october": _reveal(a["post"], 10 ** 9, y, {}), "phase": "offseason", "champ": a.get("champ"), "eliminated": {}, "live": True}
        awards = [{"label": f"{x['lg']} {AWARD_LABEL[x['award']]}", "name": x["name"], "team": team_name(x["team"])} for x in a["awards"]]
        changed = False
    else:
        s = season(sim, y)
        G = {t: r[4] + r[5] for t, r in D.seasons[y].items()}
        rec = {t: [round(w), G[t] - round(w)] for t, w in s["wins"].items()}
        fields = s.get("fields") or {}
        cur = {"year": y, "rec": rec, "final_rec": rec, "l10": {}, "proj": {}, "fields": fields,
               "october": _reveal(s["series"], 10 ** 9, y, {r: 0 for r in ROUND_ORDER}, fields), "phase": "offseason",
               "champ": s["champ"], "eliminated": {}, "live": False}
        awards = [{"label": f"{a[2]} {AWARD_LABEL[a[1]]}" if a[1] != "wsmvp" else "World Series MVP", "name": D.name(a[3]),
                   "team": team_name(_team_of(D, a[3], y), True, y)} for a in D.awards[y]]
        changed = s["changed"]
    return {"year": y, "standings": standings(sim, cur), "october": cur["october"],
            "champ": team_name(cur["champ"], True, y) if cur["champ"] else None, "awards": awards, "changed": changed,
            "real_champ": team_name(next((x[2] for x in D.post[y] if x[1] == "WS"), ""), True, y) if y <= D.last and D.post[y] else None,
            "names": {t: team_name(t, True, y) for t in D.teams}}
