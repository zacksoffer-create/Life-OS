"""Pack the numbers the phone page needs into one JSON blob and drop it into the page template."""
from __future__ import annotations

import datetime as dt
import json
import math
import os

import pandas as pd

from . import config, model

EPOCH = pd.Timestamp("2017-01-01")  # the page counts days from here
FIELDS = ["gp", "fpg", "mpg", "fpm", "ppg", "rpg", "apg", "spg", "bpg", "tpg", "ts", "efg", "usg", "astp", "rebp",
          "orebp", "drebp", "tovp", "stlp", "blkp"]
SEASON_FIELDS = ["gp", "mpg", "fpg", "fpm", "ppg", "rpg", "apg", "spg", "bpg", "tpg", "ts", "efg", "usg", "astp",
                 "rebp", "tovp", "stlp", "blkp"]
LOG_FIELDS = ["day", "opp", "home", "start", "min", "pts", "reb", "ast", "stl", "blk", "tov", "fgm", "fga", "ftm",
              "fta", "fp"]
WINDOW_KEYS = ["l5", "l10", "l20", "season", "last", "base"]


def _num(x, digits=1):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    v = round(float(x), digits)
    return int(v) if v == int(v) else v


def _row(r: pd.Series, fields: list[str]) -> list:
    return [_num(r[f], 3 if f == "fpm" else 0 if f == "gp" else 1) for f in fields]


def _day(ts) -> int:
    return int((pd.Timestamp(ts) - EPOCH).days)


def build_payload(df: pd.DataFrame, sched: pd.DataFrame, season: int) -> dict:
    played = df[df.played]
    through = played.date.max()
    on_page = played[played.season >= season - config.PAGE_SEASONS_BACK].player_id.unique()

    win = {k: model.rates(v) for k, v in model.windows(df, season).items()}
    last = model.missed_games(df, season)
    hist = model.seasons(df)
    latest = played.groupby("player_id").tail(1).set_index("player_id")

    recent = played.copy()
    recent["back"] = recent.groupby("player_id").cumcount(ascending=False)
    l10_now = recent[(recent.back < config.TREND_WINDOW) & (recent.season == season)].groupby("player_id").size()

    # Why he's been out, if ESPN gave a reason for the games since his last one
    dnp = df[~df.played & df.reason.notna()].merge(last[["date"]].rename(columns={"date": "last_date"}),
                                                    left_on="player_id", right_index=True)
    dnp = dnp[dnp.date > dnp.last_date].groupby("player_id").tail(1).set_index("player_id").reason

    logs = played[played.season >= season - 1].copy()
    logs["day"] = (logs.date - EPOCH).dt.days
    logs["opp"] = logs.opponent_team_id
    logs["home"] = (logs.home_away == "home").astype(int)
    logs["start"] = logs.starter.fillna(False).astype(bool).astype(int)
    for c in LOG_FIELDS[4:]:
        logs[c] = logs[c].round().astype(int)
    log_rows = {pid: g[LOG_FIELDS].values.tolist() for pid, g in logs.groupby("player_id")}
    hist_rows = {pid: [[int(r.season), r.team, *_row(r, SEASON_FIELDS)] for _, r in g.iterrows()]
                 for pid, g in hist[hist.player_id.isin(on_page)].groupby("player_id")}
    teams = {int(t): a for t, a in df.groupby("team_id").team.last().items()}

    players = []
    for pid in on_page:
        info = latest.loc[pid]
        p = {
            "id": int(pid),
            "n": info["name"],
            "pos": info["pos"] or "",
            "tm": int(info.team_id),
            "last": _day(info.date),
            "miss": int(last.at[pid, "missed"]) if last.at[pid, "season"] == season else None,
            "now": int(l10_now.get(pid, 0)),
            "why": (dnp.get(pid) or "").title() or None,
            "w": {k: (_row(win[k].loc[pid], FIELDS) if pid in win[k].index else None) for k in WINDOW_KEYS},
        }
        p["log"] = log_rows.get(pid, [])
        p["hist"] = hist_rows.get(pid, [])
        players.append(p)

    start_of_week = through.normalize() - pd.Timedelta(days=through.weekday())
    upcoming = sched[(sched.season_type == 2) & ~sched.type_abbreviation.isin(model.NOT_REGULAR)
                     & (sched.status_type_name != "STATUS_POSTPONED")].copy()
    upcoming["date"] = pd.to_datetime(upcoming.game_date)
    upcoming = upcoming[upcoming.date >= start_of_week].sort_values("date")
    schedule = [[_day(r.date), int(r.home_id), int(r.away_id)] for r in upcoming.itertuples()]

    return {
        "meta": {
            "season": season,
            "seasonLabel": f"{season - 1}-{str(season)[2:]}",
            "through": _day(through),
            "built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "firstSeason": config.FIRST_SEASON,
            "scoring": config.SCORING,
            "trend": [config.TREND_WINDOW, config.BASELINE_GAMES],
            "fields": FIELDS,
            "seasonFields": SEASON_FIELDS,
            "logFields": LOG_FIELDS,
            "windows": WINDOW_KEYS,
        },
        "teams": teams,
        "players": players,
        "schedule": schedule,
    }


def render(payload: dict, template_path: str, out_dir: str) -> list[str]:
    """Write the page twice: as an Artifact page (no document wrapper) and as a standalone index.html."""
    with open(template_path, encoding="utf-8") as f:
        template = f.read()
    blob = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    marker = "/*__DATA__*/null"
    if marker not in template:
        raise ValueError(f"{template_path} has no {marker} placeholder")
    page = template.replace(marker, blob)
    os.makedirs(out_dir, exist_ok=True)
    artifact = os.path.join(out_dir, "rolling10.html")
    standalone = os.path.join(out_dir, "index.html")
    with open(artifact, "w", encoding="utf-8") as f:
        f.write(page)
    with open(standalone, "w", encoding="utf-8") as f:
        f.write('<!doctype html><html lang="en"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body>'
                + page + "</body></html>")
    return [artifact, standalone]
