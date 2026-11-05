"""The sports world behind your story, and the hooks storylines use.

MLB (mlb.py: real history since 1990, the what-ifs, simulated seasons after 2025), and the NFL, the NBA and college sports
(realleagues.py: football, men's and women's basketball, baseball, men's and women's soccer), all playing out on their real
dates from fall 2010. Each league plugs in the same way: a weekly step, a page on the Sports tab, requirements scenes can
use, and placeholders scene text can say.

Storyline hooks (all about the protagonist's team: the Yankees unless you pick another):
- requires: pro:baseball_season, pro:october, pro:my_team_winning, pro:my_team_losing, pro:my_team_in_playoffs,
  pro:my_team_alive, pro:my_team_missed, pro:my_team_champs, and pro:whatif:<id> for a world where that what-if is on
  (pro:whatif:harper_2019 = Harper's a Yankee in this world)
- placeholders: {my_team} (Yankees), {my_team_record} (88-74), {my_team_star} (the best player on it right now),
  {mlb_champ} (whoever won the last World Series)
- the other leagues, as pro:<league>:<condition> with league nfl, nba, cfb (college football), mbb / wbb (men's / women's
  college basketball), cbase (college baseball), msoc / wsoc (college soccer); conditions in_season, my_team_winning,
  my_team_losing, my_team_in_postseason, my_team_alive, my_team_champs, and my_team_ranked for college (the title-only
  sports have my_team_champs). "Your team" is the Giants, the Knicks and UConn (your college, once you're at one).
- European soccer: pro:epl / laliga / seriea / bund / ligue1 : in_season, my_team_winning, my_team_losing, my_team_champs
  (your club in that league: Manchester United, Barcelona, Juventus, Bayern, PSG to start), and pro:ucl:my_team_champs
- placeholders: {my_nfl_team}, {my_nba_team}, {my_college}, {my_nfl_record} (and nba, cfb, mbb, wbb), {nfl_champ} (and nba,
  cfb, mbb, wbb), {my_club} (your Premier League club), {epl_champ}, {ucl_champ}, {ballon_dor}
- fans: everyone has a team and how much they care; a title is a memory and a good week, a playoff exit stings
"""
from __future__ import annotations

from . import mlb
from . import realleagues as RL

REQUIRES = {
    "pro:baseball_season": "The MLB regular season is on.",
    "pro:october": "It's the MLB postseason.",
    "pro:my_team_winning": "Your MLB team is over .500 (during the season).",
    "pro:my_team_losing": "Your MLB team is under .500 (during the season).",
    "pro:my_team_in_playoffs": "Your MLB team made the playoffs this year (from October to next spring).",
    "pro:my_team_alive": "Your MLB team is still alive in October.",
    "pro:my_team_missed": "Your MLB team missed the playoffs this year (from October to next spring).",
    "pro:my_team_champs": "Your MLB team won the last World Series.",
}
CONDS = {"in_season": "its season is on", "my_team_winning": "your team has a winning record (in season)",
         "my_team_losing": "your team has a losing record (in season)",
         "my_team_in_postseason": "your team made the postseason this year (until next season)",
         "my_team_alive": "your team is still alive in the postseason", "my_team_champs": "your team won the last title",
         "my_team_ranked": "your team is in this week's top 25"}
for _lg, _L in RL.LEAGUES.items():
    for _c, _txt in CONDS.items():
        if _L.get("award") or (_L.get("titles_only") and _c != "my_team_champs"):
            continue
        if _c == "my_team_ranked" and _L["kind"] != "college":
            continue
        if _L["kind"] == "soccer" and _c in ("my_team_in_postseason", "my_team_alive"):
            continue
        REQUIRES[f"pro:{_lg}:{_c}"] = f"{_L['label']}: {_txt}."
WHATIF_PREFIX = "pro:whatif:"
NAMES = {"my_team": "your MLB team (Yankees)", "my_team_record": "its record this season (88-74)",
         "my_team_star": "its best player right now", "mlb_champ": "whoever won the last World Series",
         "my_nfl_team": "your NFL team (Giants)", "my_nba_team": "your NBA team (Knicks)",
         "my_college": "your college team's school (UConn until you're at a college)",
         "my_nfl_record": "its record", "my_nba_record": "its record", "my_cfb_record": "your school's football record",
         "my_mbb_record": "your school's men's basketball record", "my_wbb_record": "your school's women's basketball record",
         "nfl_champ": "the last Super Bowl winner", "nba_champ": "the last NBA champion", "cfb_champ": "the last college football champion",
         "mbb_champ": "the last men's college basketball champion", "wbb_champ": "the last women's college basketball champion",
         "my_club": "your Premier League club (Manchester United)", "epl_champ": "the last Premier League champion",
         "ucl_champ": "the last Champions League winner", "ballon_dor": "the last Ballon d'Or winner"}


def known(r: str) -> bool:
    return r in REQUIRES or (r.startswith(WHATIF_PREFIX) and r[len(WHATIF_PREFIX):] in mlb.WHATIF)


def requirement(sim, me, r: str) -> bool:
    if r.startswith(WHATIF_PREFIX):
        return r[len(WHATIF_PREFIX):] in mlb.whatifs(sim)
    parts = r.split(":")
    if len(parts) == 3 and parts[1] in RL.LEAGUES:
        return league_requirement(sim, parts[1], parts[2])
    cur = mlb.current(sim)
    team = mlb.my_team(sim)
    lg = mlb.data().teams[team]["lg"]
    w, l_ = cur["rec"].get(team, [0, 0])
    ph = cur["phase"]
    after = ph in ("october", "offseason")
    made = team in (cur.get("fields") or {}).get(lg, [])
    if r == "pro:baseball_season":
        return ph == "regular"
    if r == "pro:october":
        return ph == "october"
    if r == "pro:my_team_winning":
        return ph == "regular" and w > l_
    if r == "pro:my_team_losing":
        return ph == "regular" and w < l_
    if r == "pro:my_team_in_playoffs":
        return after and made
    if r == "pro:my_team_missed":
        return after and bool(cur.get("fields")) and not made
    if r == "pro:my_team_alive":
        return ph == "october" and made and team not in cur["eliminated"]
    if r == "pro:my_team_champs":
        return last_champ(sim) == team
    return False


def league_requirement(sim, lg: str, cond: str) -> bool:
    day = sim.w.day
    if RL.LEAGUES[lg].get("award"):
        return False
    if RL.LEAGUES[lg].get("titles_only"):
        fin = [f for f in RL.finals(lg, day) if f.get("champ")]
        mine = RL.followed(sim, lg)
        return cond == "my_team_champs" and bool(fin) and (fin[-1]["champ"] in mine if lg == "ucl" else fin[-1]["champ"] == mine)
    key = RL.season_key(lg, day)
    t = RL.followed(sim, lg)
    if key is None or t is None:
        return False
    ix = RL.index(lg)[key]
    on = ix["first"] - RL._offset() <= day <= ix["last"] - RL._offset()
    if cond == "in_season":
        return on
    if cond in ("my_team_winning", "my_team_losing"):
        r = RL.record(lg, key, t, day)
        return on and sum(r) > 0 and (r[0] > r[1] if cond == "my_team_winning" else r[0] < r[1])
    if cond == "my_team_in_postseason":
        return RL.in_postseason(lg, key, t, day)
    if cond == "my_team_alive":
        return RL.alive(lg, key, t, day)
    if cond == "my_team_ranked":
        return t in RL.poll(lg, key, day)
    if cond == "my_team_champs":
        return league_champ(lg, day) == t
    return False


def league_champ(lg: str, day: int):
    """The latest champion decided by today (this season's, or last season's while this one's still going)."""
    key = RL.season_key(lg, day)
    if key is None:
        return None
    c = RL.champion(lg, key, day)
    if c is not None:
        return c
    prev = str(int(key) - 1)
    return RL.champion(lg, prev, day) if prev in RL.index(lg) else None


def last_champ(sim) -> str | None:
    """Whoever won the most recent World Series that's been decided by today."""
    cur = mlb.current(sim)
    if cur["champ"]:
        return cur["champ"]
    y = cur["year"] - 1
    if y <= mlb.data().last:
        return mlb.season(sim, y)["champ"]
    a = mlb.state(sim)["arch"].get(str(y))
    return a.get("champ") if a else None


def names(sim, me) -> dict:
    """What a scene's text can say about pro sports."""
    try:
        team = mlb.my_team(sim)
        cur = mlb.current(sim)
        w, l_ = cur["rec"].get(team, [0, 0])
        stars = mlb._stars(sim, team, cur["year"], n=1)
        champ = last_champ(sim)
        out = {"my_team": mlb.team_name(team, True, cur["year"]), "my_team_record": f"{w}-{l_}",
               "my_team_star": stars[0]["name"] if stars else f"the {mlb.team_name(team)}' best player",
               "mlb_champ": mlb.team_name(champ, True, cur["year"]) if champ else "the champs"}
    except Exception:  # never let the background leagues break a scene
        out = {"my_team": "Yankees", "my_team_record": "", "my_team_star": "the best player", "mlb_champ": "the champs"}
    try:
        day = sim.w.day
        out["my_college"] = RL.my_college(sim)
        for lg in RL.GAME_LEAGUES:
            key = RL.season_key(lg, day)
            t = RL.followed(sim, lg)
            if lg in RL.SOCCER and lg != "epl":
                continue
            if lg in RL.PRO:
                out[f"my_{lg}_team"] = RL.name(lg, t, key) if t is not None else ""
            r = RL.record(lg, key, t, day) if key and t is not None else [0, 0, 0]
            if lg != "epl":
                out[f"my_{lg}_record"] = RL.rec_text(r) if sum(r) else ""
            c = league_champ(lg, day)
            if lg in RL.SOCCER and lg != "epl":
                continue
            out[f"{lg}_champ"] = RL.name(lg, c, key) if c is not None else "the champs"
        t = RL.followed(sim, "epl")
        out["my_club"] = RL.name("epl", t) if t is not None else ""
        fin = [f for f in RL.finals("ucl", day) if f.get("champ")]
        out["ucl_champ"] = fin[-1]["champ"] if fin else "the champs"
        aw = [a for a in RL.awards("ballon", day) if a.get("winner")]
        out["ballon_dor"] = aw[-1]["winner"] if aw else "the best player in the world"
    except Exception:
        for k in NAMES:
            out.setdefault(k, "")
    return out


def weekly(sim):
    mlb.weekly(sim)
    RL.weekly(sim)
