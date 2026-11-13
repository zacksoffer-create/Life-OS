"""Import a finished season of the ESPN league, once, into fantasy/seasons/<season>/espn/ (committed to the repo).

    python3 fantasy/tools/import_season.py 2026        # 2026 = the 2025-26 season

A finished season never changes, so this runs one time per season (from the Actions tab: Rolling 10 data > Run
workflow > import_season). It needs ESPN's fantasy API, which the GitHub job can reach.

What it saves (compact JSON, no league members' names):
- league.json   settings (scoring, matchup weeks, playoffs, keepers), teams and final standings, every matchup with
                its scores, the draft with keepers marked, and the final rosters
- days.json     every team's lineup on every day of the season: {scoring period: [[team, player, lineup slot]]}
- dates.json    the calendar date of each scoring period
- names.json    player names for every player id above
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from hoops import config  # noqa: E402

GAME = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/{season}"
LEAGUE = GAME + "/segments/0/leagues/{league}"
UA = {"User-Agent": "Mozilla/5.0 (rolling10 season import)", "Accept": "application/json"}


def get(url: str, headers: dict | None = None, tries: int = 3):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={**UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            if attempt == tries - 1:
                print(f"  failed: {url.split('?')[-1][:90]} ({e})")
                return None
            time.sleep(2 * (attempt + 1))


def side(s: dict | None) -> dict | None:
    if not s:
        return None
    return {"team": s.get("teamId"), "total": s.get("totalPoints"),
            "byDay": s.get("pointsByScoringPeriod") or {}}


def main() -> int:
    season = int(sys.argv[1])
    lid = config.ESPN_LEAGUE_ID
    out = os.path.join(HERE, "..", "seasons", str(season), "espn")
    os.makedirs(out, exist_ok=True)
    base = LEAGUE.format(season=season, league=lid)
    names: dict[int, str] = {}

    lg = get(base + "?view=mTeam&view=mSettings&view=mStatus&view=mDraftDetail&view=mMatchupScore&view=mStandings"
             "&view=mRoster")
    if not lg:
        print("Couldn't read the league")
        return 1
    st, se = lg.get("status") or {}, lg.get("settings") or {}
    print(f"League {lid}, season {season}: {se.get('name')!r}; status "
          f"{ {k: st.get(k) for k in ('firstScoringPeriod', 'finalScoringPeriod', 'latestScoringPeriod')} }")
    sched = se.get("scheduleSettings") or {}
    print(f"  matchup periods: {len(sched.get('matchupPeriods') or {})}; regular season: "
          f"{sched.get('matchupPeriodCount')}; playoff teams: {sched.get('playoffTeamCount')}; "
          f"playoff round length: {sched.get('playoffMatchupPeriodLength')}")

    def roster(t):
        rows = []
        for e in (t.get("roster") or {}).get("entries") or []:
            ppe = e.get("playerPoolEntry") or {}
            pl = ppe.get("player") or {}
            pid = e.get("playerId") or pl.get("id")
            if pl.get("fullName"):
                names[int(pid)] = pl["fullName"]
            rows.append([pid, e.get("lineupSlotId"), e.get("acquisitionType"), ppe.get("keeperValue")])
        return rows

    teams = [{k: t.get(k) for k in ("id", "abbrev", "name", "location", "nickname", "record", "playoffSeed",
                                    "rankCalculatedFinal", "rankFinal", "points", "divisionId")} for t in lg.get("teams") or []]
    final_rosters = {t["id"]: roster(t) for t in lg.get("teams") or []}
    schedule = [{"id": m.get("id"), "mp": m.get("matchupPeriodId"), "home": side(m.get("home")),
                 "away": side(m.get("away")), "winner": m.get("winner"), "tier": m.get("playoffTierType")}
                for m in lg.get("schedule") or []]
    dd = lg.get("draftDetail") or {}
    picks = [{"overall": p.get("overallPickNumber"), "round": p.get("roundId"), "roundPick": p.get("roundPickNumber"),
              "team": p.get("teamId"), "player": p.get("playerId"), "keeper": p.get("keeper"),
              "reserved": p.get("reservedForKeeper"), "bid": p.get("bidAmount")} for p in dd.get("picks") or []]
    print(f"  teams: {len(teams)}; matchups: {len(schedule)} (with scores: "
          f"{sum(1 for m in schedule if m['home'] and m['home']['total'])}); draft picks: {len(picks)} "
          f"(keepers: {sum(1 for p in picks if p['keeper'])}); final roster sizes: "
          f"{[len(v) for v in final_rosters.values()]}")
    league = {
        "season": season,
        "settings": {
            "name": se.get("name"), "size": se.get("size"),
            "scoring": (se.get("scoringSettings") or {}).get("scoringItems"),
            "schedule": sched,
            "lineupSlots": (se.get("rosterSettings") or {}).get("lineupSlotCounts"),
            "draft": {k: (se.get("draftSettings") or {}).get(k) for k in ("type", "date", "keeperCount", "keeperOrderType",
                                                                           "pickOrder", "auctionBudget")},
        },
        "status": {k: st.get(k) for k in ("firstScoringPeriod", "finalScoringPeriod", "latestScoringPeriod")},
        "teams": teams, "finalRosters": final_rosters, "schedule": schedule,
        "draft": {"drafted": dd.get("drafted"), "picks": picks},
    }

    # The calendar: which date each scoring period is
    pro = get(GAME.format(season=season) + "?view=proTeamSchedules_wl")
    dates = {}
    for t in ((pro or {}).get("settings") or {}).get("proTeams") or []:
        for sp, games in (t.get("proGamesByScoringPeriod") or {}).items():
            for g in games:
                if g.get("date") and sp not in dates:
                    dates[sp] = time.strftime("%Y-%m-%d", time.gmtime((g["date"] - 5 * 3600 * 1000) / 1000))
    print(f"  dated scoring periods: {len(dates)}"
          + (f" ({min(dates, key=int)} = {dates[min(dates, key=int)]}, {max(dates, key=int)} = {dates[max(dates, key=int)]})" if dates else ""))

    # Every team's lineup on every day
    last = int(st.get("latestScoringPeriod") or st.get("finalScoringPeriod") or 0)
    days = {}
    for sp in range(1, last + 1):
        d = get(base + f"?view=mRoster&scoringPeriodId={sp}")
        if not d:
            continue
        days[sp] = [[t["id"], r[0], r[1]] for t in d.get("teams") or [] for r in roster(t)]
        time.sleep(0.15)
    sizes = sorted(len(v) for v in days.values())
    print(f"  daily lineups: {len(days)} days; players per day min {sizes[0] if sizes else 0}, max {sizes[-1] if sizes else 0}")
    if days:
        first, final = days[min(days)], days[max(days)]
        print(f"  day {min(days)} vs day {max(days)}: {len({tuple(x[:2]) for x in first} ^ {tuple(x[:2]) for x in final})} "
              f"team-player pairs differ (0 would mean ESPN ignored the date)")

    for name, obj in (("league", league), ("days", days), ("dates", dates), ("names", names)):
        with open(os.path.join(out, f"{name}.json"), "w", encoding="utf-8") as f:
            json.dump(obj, f, separators=(",", ":"))
    print(f"Saved to fantasy/seasons/{season}/espn/: " + ", ".join(
        f"{n} {os.path.getsize(os.path.join(out, n + '.json')) / 1e3:.0f} KB" for n in ("league", "days", "dates", "names")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
