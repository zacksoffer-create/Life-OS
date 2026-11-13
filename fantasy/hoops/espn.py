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
    return {"league": league, "pool": pool, "rosters": rosters}


def _team_name(t: dict) -> str:
    return (t.get("name") or f"{t.get('location', '')} {t.get('nickname', '')}").strip() or t.get("abbrev", "")


def parse(raw: dict, my_team: str | int | None = None) -> dict | None:
    """Boil the raw JSON down to what the page needs. None when there's no league data at all."""
    league, pool, rosters = raw.get("league"), raw.get("pool"), raw.get("rosters")
    if not league or not league.get("teams"):
        return None
    teams = [{"id": int(t["id"]), "abbrev": t.get("abbrev", ""), "name": _team_name(t)} for t in league["teams"]]
    me = None
    for t in teams:
        if isinstance(my_team, str) and t["name"].strip().lower() == my_team.strip().lower():
            me = t["id"]
    if me is None and isinstance(my_team, int):
        me = my_team

    players: dict[int, dict] = {}

    def entry(pid: int) -> dict:
        return players.setdefault(int(pid), {})

    for t in league["teams"]:
        for e in (t.get("roster") or {}).get("entries", []):
            pl = (e.get("playerPoolEntry") or {}).get("player") or {}
            p = entry(e.get("playerId") or pl.get("id"))
            p["team"] = int(t["id"])
            p["name"] = pl.get("fullName")
            p["pro"] = pl.get("proTeamId")
            if pl.get("injuryStatus"):
                p["inj"] = INJURY.get(pl["injuryStatus"])
            own = (pl.get("ownership") or {}).get("percentOwned")
            if own is not None:
                p["own"] = round(float(own), 1)

    for e in (pool or {}).get("players", []):
        pl = e.get("player") or {}
        pid = pl.get("id") or e.get("id")
        if pid is None:
            continue
        p = entry(pid)
        p.setdefault("name", pl.get("fullName"))
        p.setdefault("pro", pl.get("proTeamId"))
        if e.get("status") == "WAIVERS":
            p["waivers"] = True
        if pl.get("injuryStatus") and "inj" not in p:
            p["inj"] = INJURY.get(pl["injuryStatus"])
        own = (pl.get("ownership") or {}).get("percentOwned")
        if own is not None and "own" not in p:
            p["own"] = round(float(own), 1)
        if "team" not in p and e.get("onTeamId"):
            p["team"] = int(e["onTeamId"])

    for team_json in (rosters or {}).values():
        for a in team_json.get("athletes", []):
            items = a.get("items") if isinstance(a, dict) and "items" in a else [a]  # some feeds group by position
            for x in items:
                if x.get("id") and x.get("age") is not None:
                    entry(x["id"])["age"] = int(x["age"])

    settings = league.get("settings") or {}
    scoring = [(STAT_NAMES.get(i.get("statId"), f"stat {i.get('statId')}"), i.get("points"))
               for i in (settings.get("scoringSettings") or {}).get("scoringItems", [])]
    keepers = (settings.get("draftSettings") or {}).get("keeperCount")
    return {"name": settings.get("name", ""), "teams": teams, "me": me, "players": players, "scoring": scoring,
            "keepers": keepers}
