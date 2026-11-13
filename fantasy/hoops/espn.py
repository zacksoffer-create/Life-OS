"""Your ESPN league: who's on which fantasy team, who's available, injury tags, % owned, and player ages.

ESPN's fantasy player ids are the same ids as in the box scores, so everything joins on player id. The league has to be
viewable to the public (it is); a private league would need two login cookies.

Every download is saved under data/raw/ so an --offline rebuild still has the league, and every one is optional: if ESPN
is down or changes something, the page builds without the league columns instead of failing.
"""
from __future__ import annotations

import json
import os
import urllib.request

API = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/{season}/segments/0/leagues/{league}"
ROSTER_API = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team}/roster"
UA = {"User-Agent": "Mozilla/5.0 (rolling10 fantasy page)", "Accept": "application/json"}

INJURY = {"OUT": "OUT", "DAY_TO_DAY": "DTD", "QUESTIONABLE": "Q", "DOUBTFUL": "D", "SUSPENSION": "SUSP",
          "INJURY_RESERVE": "OUT"}

# ESPN's stat ids for basketball scoring, for printing the league's scoring next to ours
STAT_NAMES = {0: "PTS", 1: "BLK", 2: "STL", 3: "AST", 4: "OREB", 5: "DREB", 6: "REB", 9: "PF", 11: "TO", 13: "FGM",
              14: "FGA", 15: "FTM", 16: "FTA", 17: "3PM", 18: "3PA", 19: "FG%", 20: "FT%", 21: "3P%", 23: "FG missed",
              24: "FT missed", 25: "3P missed", 37: "DD", 38: "TD", 39: "QD", 40: "MIN", 41: "GS", 42: "GP"}


def _get(url: str, headers: dict | None = None) -> dict:
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _cached(path: str, fetch, offline: bool, log):
    if not offline:
        try:
            data = fetch()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            return data
        except Exception as e:  # noqa: BLE001 - any failure here just means "no league data this run"
            log(f"  ESPN: couldn't download {os.path.basename(path)} ({e}); using the last copy if there is one")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def download(raw_dir: str, season: int, league_id: int, offline: bool = False, log=print) -> dict:
    """Raw league JSON: teams and settings, rosters, the player pool, and NBA rosters (for ages)."""
    os.makedirs(raw_dir, exist_ok=True)
    base = API.format(season=season, league=league_id)
    league = _cached(os.path.join(raw_dir, "espn_league.json"),
                     lambda: _get(base + "?view=mTeam&view=mRoster&view=mSettings&view=mStatus"), offline, log)
    # Last season's final rosters: until the new season's draft is on ESPN, those are each team's keeper candidates
    prev = _cached(os.path.join(raw_dir, "espn_league_prev.json"),
                   lambda: _get(API.format(season=season - 1, league=league_id) + "?view=mTeam&view=mRoster"), offline, log)
    pool_filter = {"players": {"filterStatus": {"value": ["FREEAGENT", "WAIVERS", "ONTEAM"]}, "limit": 1500,
                               "sortPercOwned": {"sortPriority": 1, "sortAsc": False}}}
    pool = _cached(os.path.join(raw_dir, "espn_players.json"),
                   lambda: _get(base + "?view=kona_player_info", {"X-Fantasy-Filter": json.dumps(pool_filter)}),
                   offline, log)

    def nba_rosters():
        out = {}
        for team in range(1, 31):
            try:
                out[team] = _get(ROSTER_API.format(team=team))
            except Exception:  # noqa: BLE001
                continue
        if not out:
            raise RuntimeError("no NBA rosters")
        return out

    rosters = _cached(os.path.join(raw_dir, "espn_nba_rosters.json"), nba_rosters, offline, log)
    return {"league": league, "prev": prev, "pool": pool, "rosters": rosters, "season": season}


def _team_name(t: dict) -> str:
    return (t.get("name") or f"{t.get('location', '')} {t.get('nickname', '')}").strip() or t.get("abbrev", "")


# How the league's ESPN scoring items line up with SCORING in config.py
CONFIG_STAT = {"points": 0, "rebounds": 6, "assists": 3, "steals": 2, "blocks": 1, "turnovers": 11, "fgm": 13,
               "fga": 14, "ftm": 15, "fta": 16}


def scoring_matches(league_items: list[tuple[int, float]], scoring: dict) -> bool:
    ours = {CONFIG_STAT[k]: float(v) for k, v in scoring.items() if v}
    return ours == {sid: float(pts) for sid, pts in league_items if pts}


def _entries(league: dict | None):
    for t in (league or {}).get("teams") or []:
        for e in (t.get("roster") or {}).get("entries") or []:
            ppe = e.get("playerPoolEntry") or {}
            yield int(t["id"]), e, ppe, ppe.get("player") or {}


def parse(raw: dict, my_team: str | int | None = None) -> dict | None:
    """Boil the raw JSON down to what the page needs. None when there's no league data at all.

    Before the new season's draft is on ESPN ("predraft"), teams are their final rosters from last season and players
    a team has already entered as keepers are marked kept. After it ("season"), teams are the live rosters.
    """
    league, prev, pool, rosters = raw.get("league"), raw.get("prev"), raw.get("pool"), raw.get("rosters")
    season = raw.get("season")
    if not league or not league.get("teams"):
        return None
    teams = [{"id": int(t["id"]), "abbrev": t.get("abbrev", ""), "name": _team_name(t)} for t in league["teams"]]
    me = None
    for t in teams:
        if isinstance(my_team, str) and t["name"].strip().lower() == my_team.strip().lower():
            me = t["id"]
    if me is None and isinstance(my_team, int):
        me = my_team
    drafted = bool((league.get("draftDetail") or {}).get("drafted"))
    predraft = not drafted and bool((prev or {}).get("teams"))

    players: dict[int, dict] = {}

    def entry(pid) -> dict:
        return players.setdefault(int(pid), {})

    def info(p: dict, pl: dict, fresh: bool) -> None:
        p.setdefault("name", pl.get("fullName"))
        p.setdefault("pro", pl.get("proTeamId"))
        if not fresh:
            return  # last season's roster: its injury tags and ownership are stale
        if pl.get("injuryStatus") and "inj" not in p:
            p["inj"] = INJURY.get(pl["injuryStatus"])
        own = (pl.get("ownership") or {}).get("percentOwned")
        if own is not None and "own" not in p:
            p["own"] = round(float(own), 1)

    if predraft:
        for tid, e, ppe, pl in _entries(prev):
            p = entry(e.get("playerId") or pl.get("id"))
            info(p, pl, fresh=False)
            p["team"] = tid
    for tid, e, ppe, pl in _entries(league):
        p = entry(e.get("playerId") or pl.get("id"))
        info(p, pl, fresh=True)
        p["team"] = tid
        if predraft:  # on a roster before the draft = entered as a keeper; keeperValue is the round he costs
            p["kept"] = int(ppe.get("keeperValue") or 0) or 1

    for e in (pool or {}).get("players", []):
        pl = e.get("player") or {}
        pid = pl.get("id") or e.get("id")
        if pid is None:
            continue
        p = entry(pid)
        info(p, pl, fresh=True)
        if e.get("status") == "WAIVERS":
            p["waivers"] = True
        if not predraft and "team" not in p and e.get("onTeamId"):
            p["team"] = int(e["onTeamId"])
        for s in pl.get("stats") or []:
            if (s.get("seasonId") == season and s.get("statSourceId") == 0 and s.get("statSplitTypeId") == 0
                    and s.get("appliedAverage") is not None):
                p["espn_fpg"] = float(s["appliedAverage"])  # ESPN's own fantasy points per game, for the build check

    for team_json in (rosters or {}).values():
        for a in team_json.get("athletes", []):
            items = a.get("items") if isinstance(a, dict) and "items" in a else [a]  # some feeds group by position
            for x in items:
                if x.get("id") and x.get("age") is not None:
                    entry(x["id"])["age"] = int(x["age"])

    settings = league.get("settings") or {}
    items = [(i.get("statId"), i.get("points")) for i in (settings.get("scoringSettings") or {}).get("scoringItems", [])]
    draft = settings.get("draftSettings") or {}
    return {"name": settings.get("name", ""), "teams": teams, "me": me, "players": players,
            "scoring": [(STAT_NAMES.get(sid, f"stat {sid}"), pts) for sid, pts in items], "scoring_items": items,
            "keepers": draft.get("keeperCount"), "mode": "predraft" if predraft else "season",
            "draft_date": draft.get("date"), "roster_season": (season - 1) if (predraft and season) else season}
