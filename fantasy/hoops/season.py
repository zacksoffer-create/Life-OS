"""A finished season, whole: player arcs, fantasy weeks, the league replayed, and the draft and keepers review.

Everything here is built from two things that never change once a season is over: the box scores and the league's
ESPN import (fantasy/seasons/<season>/espn/, made once by tools/import_season.py). Fantasy points use the same
SCORING as the live page, and the build checks every team's daily score against ESPN's.
"""
from __future__ import annotations

import datetime as dt
import json
import os

import numpy as np
import pandas as pd

from . import config, model, page

TIERS = {"NONE": 0, "WINNERS_BRACKET": 1, "WINNERS_CONSOLATION_LADDER": 2, "LOSERS_CONSOLATION_LADDER": 3}
BENCH, IR = 12, 13  # ESPN lineup slots; every other slot is a starting spot
LOG_FIELDS = page.LOG_FIELDS + ["ft", "st"]  # + fantasy team that day (0 = none), lineup (1 started, 0 bench, 2 IR)
ARC_FIELDS = ["rank", "total", "best10", "best10end", "worst10", "worst10end", "p10", "p50", "p90", "sd", "boom",
              "bust", "missed", "absence", "absenceStart"]


def load_espn(season_dir: str) -> dict | None:
    d = os.path.join(season_dir, "espn")
    if not os.path.exists(os.path.join(d, "league.json")):
        return None
    out = {}
    for name in ("league", "days", "names"):
        with open(os.path.join(d, f"{name}.json"), encoding="utf-8") as f:
            out[name] = json.load(f)
    return out


def _day(ts) -> int:
    return int((pd.Timestamp(ts) - page.EPOCH).days)


def calendar(league: dict, opening: pd.Timestamp) -> list[list[int]]:
    """The league's matchup weeks as [week, first day, last day, playoffs?], days counted like the page (from 2017)."""
    spans: dict[int, list[int]] = {}
    for m in league["schedule"]:
        for s in (m["home"], m["away"]):
            for k in (s or {}).get("byDay") or {}:
                a = spans.setdefault(m["mp"], [10**6, 0])
                a[0], a[1] = min(a[0], int(k)), max(a[1], int(k))
    regular = league["settings"]["schedule"].get("matchupPeriodCount") or 0
    base = _day(opening) - 1  # scoring period 1 is opening night
    return [[mp, base + a, base + b, int(mp > regular)] for mp, (a, b) in sorted(spans.items())]


def lineups(days: dict, opening: pd.Timestamp) -> pd.DataFrame:
    """Every team-player-day from the daily lineups: day, fantasy team, player, lineup (1 started, 0 bench, 2 IR)."""
    base = _day(opening) - 1
    rows = [(base + int(sp), team, pid, 2 if slot == IR else 0 if slot == BENCH else 1)
            for sp, entries in days.items() for team, pid, slot in entries]
    return pd.DataFrame(rows, columns=["day", "ft", "player_id", "st"])


def transactions(lu: pd.DataFrame) -> list[list]:
    """Adds, drops and trades, read off the day-to-day lineups: [day, kind, team, player, other team]."""
    out = []
    by_day = {d: dict(zip(g.player_id, g.ft)) for d, g in lu.groupby("day")}
    days = sorted(by_day)
    for prev_d, d in zip(days, days[1:]):
        prev, cur = by_day[prev_d], by_day[d]
        for pid, team in cur.items():
            if pid not in prev:
                out.append([d, "add", int(team), int(pid), 0])
            elif prev[pid] != team:
                out.append([d, "trade", int(team), int(pid), int(prev[pid])])
        for pid, team in prev.items():
            if pid not in cur:
                out.append([d, "drop", int(team), int(pid), 0])
    return out


def arcs(g: pd.DataFrame, box: pd.DataFrame) -> dict:
    """One player's season shape: best and worst 10-game stretches, floor and ceiling, absences."""
    played = g[g.played]
    fp = played.fp.to_numpy(float)
    out = {"total": float(fp.sum()) if len(fp) else 0.0}
    if len(fp) >= 10:
        r = pd.Series(fp).rolling(10).mean().to_numpy()
        i, j = int(np.nanargmax(r)), int(np.nanargmin(r))
        days = played.day.to_numpy()
        out.update(best10=r[i], best10end=int(days[i]), worst10=r[j], worst10end=int(days[j]))
    if len(fp):
        avg = fp.mean()
        out.update(p10=np.percentile(fp, 10), p50=np.percentile(fp, 50), p90=np.percentile(fp, 90),
                   sd=fp.std(), boom=int((fp >= 1.5 * avg).sum()) if avg > 0 else 0,
                   bust=int((fp <= 0.5 * avg).sum()) if avg > 0 else 0)
    # Absences: games his team played (he was listed in the box score) that he didn't
    out_rows = box[~box.played]
    out["missed"] = int(len(out_rows))
    longest, start, run, run_start = 0, None, 0, None
    for d, p in zip(box.day, box.played):
        if p:
            run = 0
            continue
        run_start = d if run == 0 else run_start
        run += 1
        if run > longest:
            longest, start = run, run_start
    out["absence"], out["absenceStart"] = longest, start
    if start is not None:
        reasons = box[(box.day >= start) & ~box.played].reason.dropna()
        reasons = reasons[reasons.str.upper() != "COACH'S DECISION"]
        out["why"] = reasons.iloc[0].title() if len(reasons) else None
    return out


def build(df: pd.DataFrame, season: int, espn: dict | None, ages: dict[int, int] | None = None) -> dict:
    """The season page's data."""
    s = df[df.season == season].copy()
    s["day"] = (s.date - page.EPOCH).dt.days
    played = s[s.played]
    opening = played.date.min()
    teams_nba = {int(t): a for t, a in df.groupby("team_id").team.last().items()}

    league = espn["league"] if espn else None
    lu = lineups(espn["days"], opening) if espn else pd.DataFrame(columns=["day", "ft", "player_id", "st"])
    weeks = calendar(league, opening) if league else []

    # Fantasy context on every game: whose team he was on that day and whether he was in the starting lineup
    s = s.merge(lu, on=["day", "player_id"], how="left")
    s["ft"] = s.ft.fillna(0).astype(int)
    s["st"] = s.st.fillna(-1).astype(int)
    played = s[s.played]

    sums = played.groupby("player_id")[model.COMPONENTS].sum()
    rates = model.rates(sums)
    totals = played.groupby("player_id").fp.sum().sort_values(ascending=False)
    rank = pd.Series(np.arange(1, len(totals) + 1), index=totals.index)

    logs = played.copy()
    logs["opp"] = logs.opponent_team_id
    logs["home"] = (logs.home_away == "home").astype(int)
    logs["start"] = logs.starter.fillna(False).astype(bool).astype(int)
    for c in page.LOG_FIELDS[4:]:
        logs[c] = logs[c].round().astype(int)
    log_rows = {pid: g[LOG_FIELDS].values.tolist() for pid, g in logs.groupby("player_id")}
    boxes = {pid: g for pid, g in s.groupby("player_id")}

    picks = (league or {}).get("draft", {}).get("picks") or []
    pick_of = {p["player"]: p for p in picks}
    on_rosters = set(lu.player_id.unique())
    ids = sorted(set(played.player_id.unique()) | on_rosters | set(pick_of))
    names = {int(k): v for k, v in (espn or {}).get("names", {}).items()}
    latest = s.sort_values("date").groupby("player_id").tail(1).set_index("player_id")
    last_day = lu.day.max() if len(lu) else None
    final_team = dict(zip(lu[lu.day == last_day].player_id, lu[lu.day == last_day].ft)) if last_day else {}

    players = []
    for pid in ids:
        info = latest.loc[pid] if pid in latest.index else None
        name = info["name"] if info is not None else names.get(int(pid))
        if not name:
            continue
        p = {"id": int(pid), "n": name, "pos": (info["pos"] if info is not None else "") or "",
             "tm": int(info.team_id) if info is not None else 0,
             "s": page._row(rates.loc[pid], page.FIELDS) if pid in rates.index else None,
             "log": log_rows.get(pid, [])}
        a = arcs(boxes[pid], boxes[pid]) if pid in boxes else {"total": 0.0, "missed": 0, "absence": 0}
        a["rank"] = int(rank[pid]) if pid in rank.index else None
        p["a"] = [page._num(a.get(k), 1) if k in ("best10", "worst10", "p10", "p50", "p90", "sd", "total")
                  else a.get(k) for k in ARC_FIELDS]
        if a.get("why"):
            p["why"] = a["why"]
        if pid in pick_of:
            k = pick_of[pid]
            p["dr"] = [k["overall"], k["round"], k["roundPick"], k["team"], int(bool(k["keeper"]))]
        if final_team.get(pid):
            p["fin"] = int(final_team[pid])
        if ages and int(pid) in ages:
            p["age"] = ages[int(pid)]
        if pid in boxes:
            months = boxes[pid][boxes[pid].played].groupby(boxes[pid].date.dt.to_period("M")).fp.agg(["size", "mean"])
            p["mo"] = [[str(m), int(r["size"]), page._num(r["mean"])] for m, r in months.iterrows()]
        players.append(p)

    # The draft against how the season went: a pick's slot value is the total of the player who finished at that rank
    ranked_totals = totals.to_numpy()
    draft = []
    for k in sorted(picks, key=lambda x: x["overall"]):
        tot = float(totals.get(k["player"], 0.0))
        slot = float(ranked_totals[k["overall"] - 1]) if k["overall"] - 1 < len(ranked_totals) else 0.0
        draft.append([k["overall"], k["round"], k["roundPick"], k["team"], k["player"], int(bool(k["keeper"])),
                      page._num(tot, 0), int(rank[k["player"]]) if k["player"] in rank.index else None,
                      page._num(tot - slot, 0)])

    teams, matchups = [], []
    if league:
        for t in league["teams"]:
            rec = (t.get("record") or {}).get("overall") or {}
            name = (t.get("name") or f"{t.get('location', '')} {t.get('nickname', '')}").strip()
            teams.append([t["id"], t.get("abbrev", ""), name, rec.get("wins", 0), rec.get("losses", 0), rec.get("ties", 0),
                          rec.get("pointsFor", 0), rec.get("pointsAgainst", 0), t.get("playoffSeed"),
                          t.get("rankCalculatedFinal") or t.get("rankFinal")])
        for m in league["schedule"]:
            h, w = m["home"] or {}, m["away"] or {}
            matchups.append([m["mp"], h.get("team"), h.get("total"), w.get("team"), w.get("total"),
                             {"HOME": 1, "AWAY": 2}.get(m["winner"], 0), TIERS.get(m["tier"], 0)])

    nba_games = {int(t): sorted(int(d) for d in g.day.unique()) for t, g in played.groupby("team_id")}

    return {
        "meta": {
            "season": season, "seasonLabel": f"{season - 1}-{str(season)[2:]}",
            "first": _day(opening), "last": int(played.day.max()),
            "built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "scoring": config.SCORING, "fields": page.FIELDS, "logFields": LOG_FIELDS, "arcFields": ARC_FIELDS,
            "league": {"name": league["settings"]["name"], "me": _my_team(teams), "keepers": league["settings"]["draft"].get("keeperCount")
                       or config.KEEPERS, "playoffTeams": league["settings"]["schedule"].get("playoffTeamCount"),
                       "regularWeeks": league["settings"]["schedule"].get("matchupPeriodCount")} if league else None,
        },
        "nba": teams_nba,
        "weeks": weeks,
        "teams": teams,
        "matchups": matchups,
        "draft": draft,
        "moves": transactions(lu) if len(lu) else [],
        "nbaGames": nba_games,
        "players": players,
    }


def _my_team(teams: list[list]) -> int | None:
    for t in teams:
        if str(t[2]).strip().lower() == config.MY_TEAM.strip().lower():
            return t[0]
    return None


def check_against_espn(payload: dict, espn: dict, opening: pd.Timestamp) -> tuple[int, int]:
    """Recompute every team's daily score from the lineups and compare with ESPN's: (matching team-days, all)."""
    base = _day(opening) - 1
    ours: dict[tuple[int, int], float] = {}
    for p in payload["players"]:
        for g in p["log"]:
            row = dict(zip(LOG_FIELDS, g))
            if row["ft"] and row["st"] == 1:
                key = (row["ft"], row["day"] - base)
                ours[key] = ours.get(key, 0) + row["fp"]
    same = total = 0
    for m in espn["league"]["schedule"]:
        for s in (m["home"], m["away"]):
            for k, v in ((s or {}).get("byDay") or {}).items():
                total += 1
                same += abs(ours.get((s["team"], int(k)), 0) - v) < 0.01
    return same, total
