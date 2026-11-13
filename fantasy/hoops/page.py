"""Pack the numbers the phone page needs into one JSON blob and drop it into the page template."""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import re

import pandas as pd

from . import config, model

EPOCH = pd.Timestamp("2017-01-01")  # the page counts days from here
SEASON_PAGES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "docs", "fantasy")
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


def keeper_scores(sums: dict[str, pd.DataFrame], weight: float) -> pd.Series:
    """FP/G over this season and last, with each of last season's games counting `weight` of one of this season's."""
    cur, prev = sums["season"], sums["last"]
    ids = cur.index.union(prev.index)
    fp = cur.fp.reindex(ids, fill_value=0) + weight * prev.fp.reindex(ids, fill_value=0)
    gp = cur.gp.reindex(ids, fill_value=0) + weight * prev.gp.reindex(ids, fill_value=0)
    return (fp / gp.where(gp > 0)).dropna()


def build_payload(df: pd.DataFrame, sched: pd.DataFrame, season: int, league: dict | None = None) -> dict:
    played = df[df.played]
    through = played.date.max()
    on_page = played[played.season >= season - config.PAGE_SEASONS_BACK].player_id.unique()

    sums = model.windows(df, season)
    win = {k: model.rates(v) for k, v in sums.items()}
    kv = keeper_scores(sums, config.KEEPER_LAST_SEASON_WEIGHT)
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
        p["kv"] = _num(kv.get(pid))
        players.append(p)

    league_meta = None
    if league:
        lp = league["players"]
        shown = {p["id"] for p in players}
        # Rostered players with no games in the last two seasons (a rookie who hasn't debuted, a long injury) still
        # belong on their fantasy team's list
        for pid, x in lp.items():
            if x.get("team") and pid not in shown and x.get("name"):
                players.append({"id": pid, "n": x["name"], "pos": "", "tm": int(x["pro"]) if x.get("pro") else 0,
                                "last": None, "miss": None, "now": 0, "why": None,
                                "w": {k: None for k in WINDOW_KEYS}, "log": [], "hist": [], "kv": None})
        for p in players:
            x = lp.get(p["id"], {})
            p["ft"] = x.get("team", 0)  # fantasy team id; 0 = available
            if x.get("waivers"):
                p["wv"] = 1
            for k in ("inj", "own", "age", "kept"):
                if x.get(k) is not None:
                    p[k] = x[k]
        league_meta = {
            "name": league["name"],
            "teams": [[t["id"], t["abbrev"], t["name"]] for t in league["teams"]],
            "me": league["me"],
            "keepers": league.get("keepers") or config.KEEPERS,
            "lastWeight": config.KEEPER_LAST_SEASON_WEIGHT,
            "mode": league.get("mode", "season"),  # "predraft": teams are last season's rosters
            "rosterSeason": league.get("roster_season") or season,
        }

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
            "league": league_meta,
            # Finished seasons that have their own page (docs/fantasy/<label>/), newest first
            "seasonPages": sorted((d for d in os.listdir(SEASON_PAGES) if re.fullmatch(r"\d{4}-\d{2}", d)
                                   and os.path.exists(os.path.join(SEASON_PAGES, d, "index.html"))),
                                  reverse=True) if os.path.isdir(SEASON_PAGES) else [],
            "historyPage": os.path.exists(os.path.join(SEASON_PAGES, "history", "index.html")),
            "youngPage": os.path.exists(os.path.join(SEASON_PAGES, "young", "index.html")),
            "pagesUrl": config.PAGES_URL,
        },
        "teams": teams,
        "players": players,
        "schedule": schedule,
    }


DATA_MARK, URL_MARK = "/*__DATA__*/null", "/*__DATA_URL__*/null"

# What an Artifact viewer adds around a page, for the copies that are whole documents of their own
HEAD = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '<meta name="apple-mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="Rolling 10">'
        '<meta name="theme-color" content="#F2F4F8" media="(prefers-color-scheme: light)">'
        '<meta name="theme-color" content="#0C1423" media="(prefers-color-scheme: dark)">'
        '<link rel="apple-touch-icon" href="apple-touch-icon.png"><link rel="icon" href="apple-touch-icon.png">'
        '<style>html{box-sizing:border-box;-webkit-text-size-adjust:100%}'
        ':root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}'
        'body{margin:0}[hidden]{display:none!important}img{max-width:100%}</style>')


def _document(page: str) -> str:
    """The page as a whole HTML document: its title, fonts and styles go in the head."""
    cut = page.index('<div id="app">')
    return HEAD + page[:cut] + "</head><body>" + page[cut:] + "</body></html>"


BASE_CSS_MARK = "/*__BASE_CSS__*/"


def read_template(path: str) -> str:
    """A page template with the shared styles (web/base.css) filled in."""
    with open(path, encoding="utf-8") as f:
        template = f.read()
    with open(os.path.join(os.path.dirname(path), "base.css"), encoding="utf-8") as f:
        return template.replace(BASE_CSS_MARK, f.read())


def render(payload: dict, template_path: str, out_dir: str, pages_dir: str | None = None,
           data_url: str | None = None) -> list[str]:
    """Write every form of the page.

    out_dir/rolling10.html  the Artifact page, numbers baked in
    out_dir/index.html      the same as a whole document, to open from disk
    out_dir/data.json       the numbers alone, which the workflow publishes on the fantasy-data branch
    pages_dir/index.html    the GitHub Pages copy: no numbers inside, it fetches data_url when it opens
    """
    template = read_template(template_path)
    for mark in (DATA_MARK, URL_MARK):
        if mark not in template:
            raise ValueError(f"{template_path} has no {mark} placeholder")
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    baked = template.replace(DATA_MARK, data.replace("</", "<\\/"))
    os.makedirs(out_dir, exist_ok=True)
    files = {
        os.path.join(out_dir, "rolling10.html"): baked,
        os.path.join(out_dir, "index.html"): _document(baked),
        os.path.join(out_dir, "data.json"): data,
    }
    if pages_dir and data_url:
        os.makedirs(pages_dir, exist_ok=True)
        files[os.path.join(pages_dir, "index.html")] = _document(template.replace(URL_MARK, json.dumps(data_url)))
    for path, text in files.items():
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    if pages_dir and data_url:
        icon(os.path.join(pages_dir, "apple-touch-icon.png"))
        files[os.path.join(pages_dir, "apple-touch-icon.png")] = None
    return list(files)


def icon(path: str) -> None:
    """A home-screen icon: a basketball-orange tile with a big 10. Drawn once; kept if it's already there."""
    if os.path.exists(path):
        return
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return
    size = 180
    img = Image.new("RGB", (size, size), (210, 86, 27))
    d = ImageDraw.Draw(img)
    d.ellipse([15, 15, size - 15, size - 15], outline=(240, 160, 120), width=5)
    font = None
    for name in ("DejaVuSans-Bold.ttf", "Arial Bold.ttf", "Helvetica-Bold.ttf"):
        try:
            font = ImageFont.truetype(name, 92)
            break
        except OSError:
            continue
    font = font or ImageFont.load_default()
    d.text((size / 2, size / 2 + 2), "10", fill=(255, 255, 255), font=font, anchor="mm")
    img.save(path)
