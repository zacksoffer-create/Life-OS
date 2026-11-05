"""Build backend/data/leagues/*.json: real game-by-game results for the leagues that run behind the story.

Sources (all public, fetched from raw.githubusercontent.com; --download gets them):
- NFL: nflverse's games file (every game since 1999)
- NBA, men's and women's college basketball: sportsdataverse's ESPN schedules (hoopR / wehoop), 2005-06 on
- The Premier League, La Liga, Serie A, the Bundesliga and Ligue 1: football-data.co.uk's results, from the
  datasets/football-datasets mirror on GitHub, 2005-06 on (every league game)
- College football: sportsdataverse's cfbfastR schedules, 2005 on. The older files stop before the bowls, so the title
  games (and the playoff semifinals from 2014) for those seasons come from TITLE_GAMES below.
College baseball and college soccer have no game data anywhere public, so titles.json holds their real finals by hand,
along with the Champions League finals and the Ballon d'Or winners.

    pip install pyarrow pandas
    python3 lifeos/tools/build_league_data.py --download --src /tmp/leagues     # fetch, then build
    python3 lifeos/tools/build_league_data.py --src /tmp/leagues                # build from what's there

What it writes: data/leagues/<league>/teams.json, index.json and one file per season; per season (compact, so the
phone bundle stays small):
- teams (one table per league, by ESPN / nflverse id, with the season's name when it changed: the Florida Marlins rule)
- groups: conference or division membership that season
- games: [day, home, away, home score, away score, kind, round]; day counts from 2000-01-01; kind 0 regular, 1 conference,
  2 conference tournament, 3 national tournament / playoffs, 4 other postseason (NIT, bowls), 5 the title game
- college basketball keeps the power conferences, the story's colleges and the whole NCAA tournament (every one of their
  games); the rest of Division I is only there as opponents
- polls (college): a weekly top 25 from results (an Elo rating with margin of victory, carried over between seasons), so
  "ranked" means something; it's ours, not the AP's
- the champion and the title game
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import json
import math
import os
import re
import urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "backend", "data", "leagues")
EPOCH = dt.date(2000, 1, 1)
FILES_FROM = 2010  # the story starts in fall 2010: seasons before that keep only their champion (the 2009-10 season is "2010")
SD = "https://raw.githubusercontent.com/sportsdataverse"
URLS = {
    "nfl": ["https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"],
    "cfb": [f"{SD}/cfbfastR-data/main/schedules/csv/cfb_schedules_{y}.csv" for y in range(2005, 2026)],
    "mbb": [f"{SD}/hoopR-mbb-data/main/mbb/schedules/parquet/mbb_schedule_{y}.parquet" for y in range(2006, 2027)],
    "wbb": [f"{SD}/wehoop-wbb-data/main/wbb/schedules/parquet/wbb_schedule_{y}.parquet" for y in range(2006, 2027)],
    "nba": [f"{SD}/hoopR-nba-data/main/nba/schedules/parquet/nba_schedule_{y}.parquet" for y in range(2006, 2027)],
    "soccer": [f"https://raw.githubusercontent.com/datasets/football-datasets/main/datasets/{slug}/season-{y % 100:02d}{(y + 1) % 100:02d}.csv"
               for slug in ("premier-league", "la-liga", "serie-a", "bundesliga", "ligue-1") for y in range(2005, 2026)],
}
SOCCER = {"epl": ("premier-league", "Premier League"), "laliga": ("la-liga", "La Liga"), "seriea": ("serie-a", "Serie A"),
          "bund": ("bundesliga", "Bundesliga"), "ligue1": ("ligue-1", "Ligue 1")}
TITLE_OVERRIDE = {("seriea", 2006): "Inter"}  # Juventus finished first and were stripped (Calciopoli); Inter got it
CLUBS = {  # football-data's names -> the names people use
    "Man United": "Manchester United", "Man City": "Manchester City", "Nott'm Forest": "Nottingham Forest",
    "Newcastle": "Newcastle United", "Tottenham": "Tottenham Hotspur", "West Ham": "West Ham United", "Wolves": "Wolverhampton",
    "West Brom": "West Bromwich Albion", "QPR": "Queens Park Rangers", "Brighton": "Brighton & Hove Albion",
    "Leicester": "Leicester City", "Stoke": "Stoke City", "Swansea": "Swansea City", "Hull": "Hull City", "Norwich": "Norwich City",
    "Cardiff": "Cardiff City", "Leeds": "Leeds United", "Wigan": "Wigan Athletic", "Bolton": "Bolton Wanderers",
    "Blackburn": "Blackburn Rovers", "Birmingham": "Birmingham City", "Ath Madrid": "Atlético Madrid", "Ath Bilbao": "Athletic Bilbao",
    "Betis": "Real Betis", "Sociedad": "Real Sociedad", "Celta": "Celta Vigo", "Espanol": "Espanyol", "Sp Gijon": "Sporting Gijón",
    "La Coruna": "Deportivo La Coruña", "Vallecano": "Rayo Vallecano", "Alaves": "Alavés", "Malaga": "Málaga", "Leganes": "Leganés",
    "Inter": "Inter Milan", "Milan": "AC Milan", "Roma": "AS Roma", "Bayern Munich": "Bayern Munich", "Dortmund": "Borussia Dortmund",
    "Leverkusen": "Bayer Leverkusen", "M'gladbach": "Borussia Mönchengladbach", "Ein Frankfurt": "Eintracht Frankfurt",
    "FC Koln": "FC Köln", "Nurnberg": "Nürnberg", "Greuther Furth": "Greuther Fürth", "Paris SG": "Paris Saint-Germain",
    "St Etienne": "Saint-Étienne", "Nimes": "Nîmes",
}
POWER = {"Atlantic Coast Conference", "Big East Conference", "Big Ten Conference", "Big 12 Conference",
         "Southeastern Conference", "Pac-12 Conference", "Pac-10 Conference", "American Athletic Conference"}
STORY_SCHOOLS = {"UConn", "Stanford", "UCLA", "LSU", "North Carolina", "Texas", "Oklahoma", "Florida State", "Miami",
                 "Michigan"}

# College football title games (and playoff semifinals) the older files don't have: [date, winner, w pts, loser, l pts, note]
TITLE_GAMES = {
    2005: [["2006-01-04", "Texas", 41, "USC", 38, "BCS National Championship (Rose Bowl)"]],
    2006: [["2007-01-08", "Florida", 41, "Ohio State", 14, "BCS National Championship"]],
    2007: [["2008-01-07", "LSU", 38, "Ohio State", 24, "BCS National Championship"]],
    2008: [["2009-01-08", "Florida", 24, "Oklahoma", 14, "BCS National Championship"]],
    2009: [["2010-01-07", "Alabama", 37, "Texas", 21, "BCS National Championship"]],
    2010: [["2011-01-10", "Auburn", 22, "Oregon", 19, "BCS National Championship"]],
    2011: [["2012-01-09", "Alabama", 21, "LSU", 0, "BCS National Championship"]],
    2012: [["2013-01-07", "Alabama", 42, "Notre Dame", 14, "BCS National Championship"]],
    2013: [["2014-01-06", "Florida State", 34, "Auburn", 31, "BCS National Championship"]],
    2014: [["2015-01-01", "Ohio State", 42, "Alabama", 35, "Playoff semifinal (Sugar Bowl)"],
           ["2015-01-01", "Oregon", 59, "Florida State", 20, "Playoff semifinal (Rose Bowl)"],
           ["2015-01-12", "Ohio State", 42, "Oregon", 20, "College Football Playoff National Championship"]],
    2015: [["2015-12-31", "Clemson", 37, "Oklahoma", 17, "Playoff semifinal (Orange Bowl)"],
           ["2015-12-31", "Alabama", 38, "Michigan State", 0, "Playoff semifinal (Cotton Bowl)"],
           ["2016-01-11", "Alabama", 45, "Clemson", 40, "College Football Playoff National Championship"]],
    2016: [["2016-12-31", "Alabama", 24, "Washington", 7, "Playoff semifinal (Peach Bowl)"],
           ["2016-12-31", "Clemson", 31, "Ohio State", 0, "Playoff semifinal (Fiesta Bowl)"],
           ["2017-01-09", "Clemson", 35, "Alabama", 31, "College Football Playoff National Championship"]],
    2017: [["2018-01-01", "Georgia", 54, "Oklahoma", 48, "Playoff semifinal (Rose Bowl)"],
           ["2018-01-01", "Alabama", 24, "Clemson", 6, "Playoff semifinal (Sugar Bowl)"],
           ["2018-01-08", "Alabama", 26, "Georgia", 23, "College Football Playoff National Championship"]],
    2018: [["2018-12-29", "Clemson", 30, "Notre Dame", 3, "Playoff semifinal (Cotton Bowl)"],
           ["2018-12-29", "Alabama", 45, "Oklahoma", 34, "Playoff semifinal (Orange Bowl)"],
           ["2019-01-07", "Clemson", 44, "Alabama", 16, "College Football Playoff National Championship"]],
    2019: [["2019-12-28", "LSU", 63, "Oklahoma", 28, "Playoff semifinal (Peach Bowl)"],
           ["2019-12-28", "Clemson", 29, "Ohio State", 23, "Playoff semifinal (Fiesta Bowl)"],
           ["2020-01-13", "LSU", 42, "Clemson", 25, "College Football Playoff National Championship"]],
    2020: [["2021-01-01", "Alabama", 31, "Notre Dame", 14, "Playoff semifinal (Rose Bowl)"],
           ["2021-01-01", "Ohio State", 49, "Clemson", 28, "Playoff semifinal (Sugar Bowl)"],
           ["2021-01-11", "Alabama", 52, "Ohio State", 24, "College Football Playoff National Championship"]],
    2021: [["2021-12-31", "Alabama", 27, "Cincinnati", 6, "Playoff semifinal (Cotton Bowl)"],
           ["2021-12-31", "Georgia", 34, "Michigan", 11, "Playoff semifinal (Orange Bowl)"],
           ["2022-01-10", "Georgia", 33, "Alabama", 18, "College Football Playoff National Championship"]],
    2022: [["2022-12-31", "Georgia", 42, "Ohio State", 41, "Playoff semifinal (Peach Bowl)"],
           ["2022-12-31", "TCU", 51, "Michigan", 45, "Playoff semifinal (Fiesta Bowl)"],
           ["2023-01-09", "Georgia", 65, "TCU", 7, "College Football Playoff National Championship"]],
}

# The finals of the sports with no public game data (dates are the final day, give or take a day).
# [season, date, champion, runner-up, score or series, note]
TITLES = {
    "cbase": {"label": "College baseball", "event": "College World Series", "rows": [
        [2005, "2005-06-26", "Texas", "Florida", "2-0", ""], [2006, "2006-06-26", "Oregon State", "North Carolina", "2-1", ""],
        [2007, "2007-06-24", "Oregon State", "North Carolina", "2-0", ""], [2008, "2008-06-25", "Fresno State", "Georgia", "2-1", ""],
        [2009, "2009-06-24", "LSU", "Texas", "2-1", ""], [2010, "2010-06-29", "South Carolina", "UCLA", "2-0", ""],
        [2011, "2011-06-28", "South Carolina", "Florida", "2-0", ""], [2012, "2012-06-25", "Arizona", "South Carolina", "2-0", ""],
        [2013, "2013-06-25", "UCLA", "Mississippi State", "2-0", ""], [2014, "2014-06-25", "Vanderbilt", "Virginia", "2-1", ""],
        [2015, "2015-06-24", "Virginia", "Vanderbilt", "2-1", ""], [2016, "2016-06-30", "Coastal Carolina", "Arizona", "2-1", ""],
        [2017, "2017-06-27", "Florida", "LSU", "2-0", ""], [2018, "2018-06-28", "Oregon State", "Arkansas", "2-1", ""],
        [2019, "2019-06-26", "Vanderbilt", "Michigan", "2-1", ""], [2020, None, None, None, None, "Canceled (COVID-19)"],
        [2021, "2021-06-30", "Mississippi State", "Vanderbilt", "2-1", ""], [2022, "2022-06-26", "Ole Miss", "Oklahoma", "2-0", ""],
        [2023, "2023-06-26", "LSU", "Florida", "2-1", ""], [2024, "2024-06-24", "Tennessee", "Texas A&M", "2-1", ""],
        [2025, "2025-06-22", "LSU", "Coastal Carolina", "2-0", ""]]},
    "msoc": {"label": "College soccer (men)", "event": "College Cup", "rows": [
        [2005, "2005-12-11", "Maryland", "New Mexico", "1-0", ""], [2006, "2006-12-03", "UC Santa Barbara", "UCLA", "2-1", ""],
        [2007, "2007-12-16", "Wake Forest", "Ohio State", "2-1", ""], [2008, "2008-12-14", "Maryland", "North Carolina", "1-0", ""],
        [2009, "2009-12-13", "Virginia", "Akron", "0-0", "on penalties"], [2010, "2010-12-12", "Akron", "Louisville", "1-0", ""],
        [2011, "2011-12-11", "North Carolina", "Charlotte", "1-0", ""], [2012, "2012-12-16", "Indiana", "Georgetown", "1-0", ""],
        [2013, "2013-12-15", "Notre Dame", "Maryland", "2-1", ""], [2014, "2014-12-14", "Virginia", "UCLA", "0-0", "on penalties"],
        [2015, "2015-12-13", "Stanford", "Clemson", "4-0", ""], [2016, "2016-12-11", "Stanford", "Wake Forest", "0-0", "on penalties"],
        [2017, "2017-12-10", "Stanford", "Indiana", "1-0", "in double overtime"], [2018, "2018-12-09", "Maryland", "Akron", "1-0", ""],
        [2019, "2019-12-15", "Georgetown", "Virginia", "3-3", "on penalties"], [2020, "2021-05-17", "Marshall", "Indiana", "1-0", "in overtime (played in spring 2021)"],
        [2021, "2021-12-12", "Clemson", "Washington", "2-0", ""], [2022, "2022-12-12", "Syracuse", "Indiana", "2-2", "on penalties"],
        [2023, "2023-12-11", "Clemson", "Notre Dame", "2-1", ""], [2024, "2024-12-16", "Vermont", "Marshall", "2-1", ""]]},
    "wsoc": {"label": "College soccer (women)", "event": "Women's College Cup", "rows": [
        [2005, "2005-12-04", "Portland", "UCLA", "4-0", ""], [2006, "2006-12-03", "North Carolina", "Notre Dame", "2-1", ""],
        [2007, "2007-12-09", "USC", "Florida State", "2-0", ""], [2008, "2008-12-07", "North Carolina", "Notre Dame", "2-1", ""],
        [2009, "2009-12-06", "North Carolina", "Stanford", "1-0", ""], [2010, "2010-12-05", "Notre Dame", "Stanford", "1-0", ""],
        [2011, "2011-12-04", "Stanford", "Duke", "1-0", ""], [2012, "2012-12-02", "North Carolina", "Penn State", "4-1", ""],
        [2013, "2013-12-08", "UCLA", "Florida State", "1-0", "in overtime"], [2014, "2014-12-07", "Florida State", "Virginia", "1-0", ""],
        [2015, "2015-12-06", "Penn State", "Duke", "1-0", ""], [2016, "2016-12-04", "USC", "West Virginia", "3-1", ""],
        [2017, "2017-12-03", "Stanford", "UCLA", "3-2", ""], [2018, "2018-12-02", "Florida State", "North Carolina", "1-0", ""],
        [2019, "2019-12-08", "Stanford", "North Carolina", "0-0", "on penalties"], [2020, "2021-05-17", "Santa Clara", "Florida State", "1-1", "on penalties (played in spring 2021)"],
        [2021, "2021-12-06", "Florida State", "BYU", "0-0", "on penalties"], [2022, "2022-12-05", "UCLA", "North Carolina", "3-2", "in overtime"],
        [2023, "2023-12-04", "Florida State", "Stanford", "5-1", ""], [2024, "2024-12-08", "North Carolina", "Wake Forest", "1-0", ""]]},
    "ucl": {"label": "Champions League", "event": "Champions League", "split": True, "rows": [  # season = the year it ends
        [2006, "2006-05-17", "Barcelona", "Arsenal", "2-1", ""], [2007, "2007-05-23", "AC Milan", "Liverpool", "2-1", ""],
        [2008, "2008-05-21", "Manchester United", "Chelsea", "1-1", "on penalties"], [2009, "2009-05-27", "Barcelona", "Manchester United", "2-0", ""],
        [2010, "2010-05-22", "Inter Milan", "Bayern Munich", "2-0", ""], [2011, "2011-05-28", "Barcelona", "Manchester United", "3-1", ""],
        [2012, "2012-05-19", "Chelsea", "Bayern Munich", "1-1", "on penalties"], [2013, "2013-05-25", "Bayern Munich", "Borussia Dortmund", "2-1", ""],
        [2014, "2014-05-24", "Real Madrid", "Atlético Madrid", "4-1", "after extra time"], [2015, "2015-06-06", "Barcelona", "Juventus", "3-1", ""],
        [2016, "2016-05-28", "Real Madrid", "Atlético Madrid", "1-1", "on penalties"], [2017, "2017-06-03", "Real Madrid", "Juventus", "4-1", ""],
        [2018, "2018-05-26", "Real Madrid", "Liverpool", "3-1", ""], [2019, "2019-06-01", "Liverpool", "Tottenham Hotspur", "2-0", ""],
        [2020, "2020-08-23", "Bayern Munich", "Paris Saint-Germain", "1-0", ""], [2021, "2021-05-29", "Chelsea", "Manchester City", "1-0", ""],
        [2022, "2022-05-28", "Real Madrid", "Liverpool", "1-0", ""], [2023, "2023-06-10", "Manchester City", "Inter Milan", "1-0", ""],
        [2024, "2024-06-01", "Real Madrid", "Borussia Dortmund", "2-0", ""], [2025, "2025-05-31", "Paris Saint-Germain", "Inter Milan", "5-0", ""],
        [2026, "2026-05-30", "Paris Saint-Germain", "Arsenal", "1-1", "on penalties"]]},
    "ballon": {"label": "Ballon d'Or", "event": "Ballon d'Or", "award": True, "rows": [
        # [year, the day it was given, winner, his club, women's winner, her club] (2010-15: FIFA Ballon d'Or; women's from 2018)
        [2005, "2005-11-28", "Ronaldinho", "Barcelona", None, None], [2006, "2006-11-27", "Fabio Cannavaro", "Real Madrid", None, None],
        [2007, "2007-12-02", "Kaká", "AC Milan", None, None], [2008, "2008-12-02", "Cristiano Ronaldo", "Manchester United", None, None],
        [2009, "2009-12-01", "Lionel Messi", "Barcelona", None, None], [2010, "2011-01-10", "Lionel Messi", "Barcelona", None, None],
        [2011, "2012-01-09", "Lionel Messi", "Barcelona", None, None], [2012, "2013-01-07", "Lionel Messi", "Barcelona", None, None],
        [2013, "2014-01-13", "Cristiano Ronaldo", "Real Madrid", None, None], [2014, "2015-01-12", "Cristiano Ronaldo", "Real Madrid", None, None],
        [2015, "2016-01-11", "Lionel Messi", "Barcelona", None, None], [2016, "2016-12-12", "Cristiano Ronaldo", "Real Madrid", None, None],
        [2017, "2017-12-07", "Cristiano Ronaldo", "Real Madrid", None, None], [2018, "2018-12-03", "Luka Modrić", "Real Madrid", "Ada Hegerberg", "Lyon"],
        [2019, "2019-12-02", "Lionel Messi", "Barcelona", "Megan Rapinoe", "Reign FC"], [2020, None, None, None, None, None],
        [2021, "2021-11-29", "Lionel Messi", "Paris Saint-Germain", "Alexia Putellas", "Barcelona"],
        [2022, "2022-10-17", "Karim Benzema", "Real Madrid", "Alexia Putellas", "Barcelona"],
        [2023, "2023-10-30", "Lionel Messi", "Inter Miami", "Aitana Bonmatí", "Barcelona"],
        [2024, "2024-10-28", "Rodri", "Manchester City", "Aitana Bonmatí", "Barcelona"],
        [2025, "2025-09-22", "Ousmane Dembélé", "Paris Saint-Germain", "Aitana Bonmatí", "Barcelona"]]},
}

NFL_TEAMS = {  # nflverse code -> (franchise, name by era: [(first season, name)], conference, division)
    "ARI": ("ARI", [(1999, "Arizona Cardinals")], "NFC", "West"), "ATL": ("ATL", [(1999, "Atlanta Falcons")], "NFC", "South"),
    "BAL": ("BAL", [(1999, "Baltimore Ravens")], "AFC", "North"), "BUF": ("BUF", [(1999, "Buffalo Bills")], "AFC", "East"),
    "CAR": ("CAR", [(1999, "Carolina Panthers")], "NFC", "South"), "CHI": ("CHI", [(1999, "Chicago Bears")], "NFC", "North"),
    "CIN": ("CIN", [(1999, "Cincinnati Bengals")], "AFC", "North"), "CLE": ("CLE", [(1999, "Cleveland Browns")], "AFC", "North"),
    "DAL": ("DAL", [(1999, "Dallas Cowboys")], "NFC", "East"), "DEN": ("DEN", [(1999, "Denver Broncos")], "AFC", "West"),
    "DET": ("DET", [(1999, "Detroit Lions")], "NFC", "North"), "GB": ("GB", [(1999, "Green Bay Packers")], "NFC", "North"),
    "HOU": ("HOU", [(2002, "Houston Texans")], "AFC", "South"), "IND": ("IND", [(1999, "Indianapolis Colts")], "AFC", "South"),
    "JAX": ("JAX", [(1999, "Jacksonville Jaguars")], "AFC", "South"), "KC": ("KC", [(1999, "Kansas City Chiefs")], "AFC", "West"),
    "STL": ("LAR", [(1999, "St. Louis Rams")], "NFC", "West"), "LA": ("LAR", [(2016, "Los Angeles Rams")], "NFC", "West"),
    "SD": ("LAC", [(1999, "San Diego Chargers")], "AFC", "West"), "LAC": ("LAC", [(2017, "Los Angeles Chargers")], "AFC", "West"),
    "OAK": ("LV", [(1999, "Oakland Raiders")], "AFC", "West"), "LV": ("LV", [(2020, "Las Vegas Raiders")], "AFC", "West"),
    "MIA": ("MIA", [(1999, "Miami Dolphins")], "AFC", "East"), "MIN": ("MIN", [(1999, "Minnesota Vikings")], "NFC", "North"),
    "NE": ("NE", [(1999, "New England Patriots")], "AFC", "East"), "NO": ("NO", [(1999, "New Orleans Saints")], "NFC", "South"),
    "NYG": ("NYG", [(1999, "New York Giants")], "NFC", "East"), "NYJ": ("NYJ", [(1999, "New York Jets")], "AFC", "East"),
    "PHI": ("PHI", [(1999, "Philadelphia Eagles")], "NFC", "East"), "PIT": ("PIT", [(1999, "Pittsburgh Steelers")], "AFC", "North"),
    "SEA": ("SEA", [(1999, "Seattle Seahawks")], "NFC", "West"), "SF": ("SF", [(1999, "San Francisco 49ers")], "NFC", "West"),
    "TB": ("TB", [(1999, "Tampa Bay Buccaneers")], "NFC", "South"), "TEN": ("TEN", [(1999, "Tennessee Titans")], "AFC", "South"),
    "WAS": ("WAS", [(1999, "Washington Redskins"), (2020, "Washington Football Team"), (2022, "Washington Commanders")], "NFC", "East"),
}
NBA_DIV = {  # by the ESPN abbreviation in recent seasons
    "BOS": ("East", "Atlantic"), "BKN": ("East", "Atlantic"), "NJ": ("East", "Atlantic"), "NY": ("East", "Atlantic"),
    "PHI": ("East", "Atlantic"), "TOR": ("East", "Atlantic"), "CHI": ("East", "Central"), "CLE": ("East", "Central"),
    "DET": ("East", "Central"), "IND": ("East", "Central"), "MIL": ("East", "Central"), "ATL": ("East", "Southeast"),
    "CHA": ("East", "Southeast"), "MIA": ("East", "Southeast"), "ORL": ("East", "Southeast"), "WSH": ("East", "Southeast"),
    "DEN": ("West", "Northwest"), "MIN": ("West", "Northwest"), "OKC": ("West", "Northwest"), "SEA": ("West", "Northwest"),
    "POR": ("West", "Northwest"), "UTAH": ("West", "Northwest"), "UTA": ("West", "Northwest"), "GS": ("West", "Pacific"),
    "LAC": ("West", "Pacific"), "LAL": ("West", "Pacific"), "PHX": ("West", "Pacific"), "SAC": ("West", "Pacific"),
    "DAL": ("West", "Southwest"), "HOU": ("West", "Southwest"), "MEM": ("West", "Southwest"), "NO": ("West", "Southwest"),
    "NOH": ("West", "Southwest"), "NOP": ("West", "Southwest"), "SA": ("West", "Southwest"),
}
NBA_ROUND = {"RD16": "R1", "QTR": "CSF", "SEMI": "CF", "FINAL": "F"}
NFL_ROUND = {"WC": "WC", "DIV": "DIV", "CON": "CON", "SB": "SB"}


def day(s) -> int:
    if isinstance(s, (dt.date, dt.datetime)):
        d = s.date() if isinstance(s, dt.datetime) else s
    else:
        d = dt.date.fromisoformat(str(s)[:10])
    return (d - EPOCH).days


def download(src: str):
    for lg, urls in URLS.items():
        os.makedirs(os.path.join(src, lg), exist_ok=True)
        for u in urls:
            path = os.path.join(src, lg, os.path.basename(u))
            if os.path.exists(path) and os.path.getsize(path) > 0:
                continue
            print("fetching", u)
            try:
                urllib.request.urlretrieve(u, path)
            except Exception as e:  # a season that isn't published yet
                print("  skipped:", e)


class Teams:
    def __init__(self):
        self.idx, self.rows = {}, []

    def get(self, key, name, short, abbr=""):
        if key not in self.idx:
            self.idx[key] = len(self.rows)
            self.rows.append([name, short, abbr])
        else:  # the latest name wins (seasons store the old one when it differs)
            self.rows[self.idx[key]] = [name, short, abbr or self.rows[self.idx[key]][2]]
        return self.idx[key]


# ------------------------------------------------------------------------------------------------- ratings and polls
def polls(season: dict, ratings: dict, k=20.0, home=60.0, every=7) -> list:
    """Weekly top 25 by an Elo rating with margin of victory (starts from last season's, regressed a third)."""
    for t in list(ratings):
        ratings[t] = 1500 + (ratings[t] - 1500) * 2 / 3
    games = sorted(season["games"], key=lambda g: g[0])
    if not games:
        return []
    out, nxt = [], games[0][0] + every
    played = {}
    for g in games:
        while g[0] >= nxt:
            out.append([nxt, _top(ratings, played)])
            nxt += every
        d, h, a, hs, as_ = g[:5]
        rh, ra = ratings.setdefault(h, 1400.0), ratings.setdefault(a, 1400.0)
        neutral = g[5] >= 3
        e = 1 / (1 + 10 ** ((ra - rh - (0 if neutral else home)) / 400))
        s = 1.0 if hs > as_ else 0.0 if hs < as_ else 0.5
        mov = math.log(abs(hs - as_) + 1) * 2.2 / ((abs(rh - ra)) * 0.001 + 2.2)
        ratings[h] = rh + k * mov * (s - e)
        ratings[a] = ra - k * mov * (s - e)
        played[h] = played.get(h, 0) + 1
        played[a] = played.get(a, 0) + 1
    out.append([games[-1][0] + 1, _top(ratings, played)])
    return out


def _top(ratings, played, n=25):
    return [t for t, _ in sorted(((t, r) for t, r in ratings.items() if played.get(t, 0) >= 2), key=lambda x: -x[1])[:n]]


# ------------------------------------------------------------------------------------------------- the leagues
def build_basketball(src: str, lg: str) -> dict:
    import pandas as pd
    T = Teams()
    seasons, ratings, conf_names = {}, {}, {}
    files = sorted(glob.glob(os.path.join(src, lg, f"{lg}_schedule_*.parquet")))
    for f in files:
        y = int(re.search(r"_(\d{4})\.parquet$", f).group(1))
        d = pd.read_parquet(f)
        d = d[d.status_type_completed == True]  # noqa: E712
        d = d[d.season_type.isin([2, 3])]
        if not len(d):
            continue
        if "groups_name" in d:
            for gid, gname in d[["groups_id", "groups_name"]].dropna().drop_duplicates().values.tolist():
                conf_names[int(gid)] = gname
        rows = d.to_dict("records")
        names = {}
        for r in rows:
            for side in ("home", "away"):
                key = str(r[f"{side}_id"])
                nm = r.get(f"{side}_display_name") or r.get(f"{side}_location")
                short = r.get(f"{side}_location") or r.get(f"{side}_short_display_name") or nm
                if lg == "nba":
                    short = r.get(f"{side}_name") or short
                t = T.get(key, nm, short, r.get(f"{side}_abbreviation") or "")
                names[t] = nm
        conf = {}
        if lg != "nba":
            for r in rows:
                for side in ("home", "away"):
                    cid = r.get(f"{side}_conference_id")
                    if cid is not None and cid == cid:
                        conf[T.idx[str(r[f"{side}_id"])]] = int(cid)
        games = []
        for r in rows:
            h, a = T.idx[str(r["home_id"])], T.idx[str(r["away_id"])]
            notes = str(r.get("notes_headline") or "")
            kind, rnd = 0, ""
            if lg == "nba":
                if r["season_type"] == 3:
                    kind, rnd = 3, NBA_ROUND.get(r.get("type_abbreviation"), "")
                    if rnd == "F":
                        kind = 5
            else:
                tid = r.get("tournament_id")
                if r["season_type"] == 3 and tid == 22:
                    kind = 3
                elif r["season_type"] == 3:
                    kind = 4
                elif r.get("conference_competition") and ((tid is not None and tid == tid) or notes.strip()):
                    kind = 2  # the conference tournament (it has a tournament id or a headline; regular conference games don't)
                elif r.get("conference_competition"):
                    kind = 1
            g = [day(r["game_date"]), h, a, int(r["home_score"]), int(r["away_score"]), kind]
            if rnd:
                g.append(rnd)
            games.append(g)
        games.sort(key=lambda g: (g[0], g[1]))
        if lg != "nba":  # the NCAA tournament's rounds, counted back from the final
            t = [g for g in games if g[5] == 3]
            for i, g in enumerate(reversed(t)):
                g[5] = 5 if i == 0 else 3
                g.append("NC" if i == 0 else "F4" if i < 3 else "E8" if i < 7 else "S16" if i < 15 else "R32" if i < 31
                         else "R64" if i < 63 else "FF")
        season = {"label": f"{y - 1}-{str(y)[2:]}", "games": games, "names": names}
        if lg == "nba":
            grp = {}
            for t, nm in names.items():
                ab = T.rows[t][2]
                cdv = NBA_DIV.get(ab)
                if cdv:
                    grp.setdefault(f"{cdv[0]}|{cdv[1]}", []).append(t)
            season["groups"] = grp
        else:
            grp = {}
            for t, cid in conf.items():
                grp.setdefault(conf_names.get(cid, str(cid)), []).append(t)
            season["groups"] = grp
            tracked = {t for c, ts in grp.items() if c in POWER for t in ts}
            tracked |= {t for t in names if T.rows[t][1] in STORY_SCHOOLS}
            tracked |= {x for g in games if g[5] in (3, 5) for x in (g[1], g[2])}
            season["polls"] = polls(season, ratings, k=22.0, home=75.0)
            for p in season["polls"]:
                tracked |= set(p[1])
            season["games"] = [g for g in games if g[1] in tracked or g[2] in tracked]
            season["groups"] = {c: sorted(t for t in ts if t in tracked) for c, ts in grp.items()
                                if any(t in tracked for t in ts) and c in POWER or c in {conf_names.get(conf.get(t)) for t in tracked}}
            season["groups"] = {c: ts for c, ts in season["groups"].items() if ts}
        fin = next((g for g in reversed(season["games"]) if g[5] == 5), None)
        if fin:
            season["champ"] = fin[1] if fin[3] > fin[4] else fin[2]
        seasons[str(y)] = season
    return _pack(lg, T, seasons)


def build_cfb(src: str) -> dict:
    T = Teams()
    seasons, ratings = {}, {}
    for y in range(2005, 2030):
        f = os.path.join(src, "cfb", f"cfb_schedules_{y}.csv")
        if not os.path.exists(f):
            continue
        rows = [r for r in csv.DictReader(open(f, encoding="utf-8")) if r["completed"] in ("TRUE", "True", "true")]
        fbs = {r[f"{s}_team"] for r in rows for s in ("home", "away") if r[f"{s}_division"] == "fbs"}
        rows = [r for r in rows if r["home_team"] in fbs or r["away_team"] in fbs]
        conf, names, games = {}, {}, []
        for r in rows:
            for s in ("home", "away"):
                t = T.get(r[f"{s}_team"], r[f"{s}_team"], r[f"{s}_team"])
                names[t] = r[f"{s}_team"]
                if r[f"{s}_team"] in fbs and r[f"{s}_conference"] not in ("", "NA"):
                    conf[t] = r[f"{s}_conference"]
            try:
                hs, as_ = int(r["home_points"]), int(r["away_points"])
            except ValueError:
                continue
            note = r.get("notes") or ""
            post = r["season_type"] == "postseason"
            kind = 0
            rnd = ""
            if post:
                kind = 4
                if "National Championship" in note:
                    kind, rnd = 5, "NC"
                elif "Playoff" in note:
                    kind, rnd = 3, ("SF" if "Semifinal" in note else "QF" if "Quarterfinal" in note else "R1")
            elif r.get("conference_game") in ("TRUE", "True", "true"):
                kind = 1
            g = [day(r["start_date"]), T.idx[r["home_team"]], T.idx[r["away_team"]], hs, as_, kind]
            if rnd:
                g.append(rnd)
            games.append(g)
        for dte, w, wp, lo, lp, note in TITLE_GAMES.get(y, []):
            if not any(g[5] == 5 for g in games) or "semifinal" in note:
                if any(g[0] == day(dte) and {T.rows[g[1]][0], T.rows[g[2]][0]} == {w, lo} for g in games):
                    continue
                g = [day(dte), T.get(w, w, w), T.get(lo, lo, lo), wp, lp, 5 if "Championship" in note else 3,
                     "NC" if "Championship" in note else "SF"]
                games.append(g)
        games.sort(key=lambda g: (g[0], g[1]))
        grp = {}
        for t, c in conf.items():
            grp.setdefault(c, []).append(t)
        season = {"label": str(y), "games": games, "names": names, "groups": {c: sorted(v) for c, v in grp.items()}}
        season["polls"] = polls(season, ratings, k=25.0, home=55.0)
        fin = next((g for g in reversed(games) if g[5] == 5), None)
        if fin:
            season["champ"] = fin[1] if fin[3] > fin[4] else fin[2]
        seasons[str(y)] = season
    return _pack("cfb", T, seasons)


def build_nfl(src: str) -> dict:
    T = Teams()
    seasons = {}
    rows = list(csv.DictReader(open(os.path.join(src, "nfl", "games.csv"), encoding="utf-8")))
    by = {}
    for r in rows:
        if r["home_score"] == "" or int(r["season"]) < 2005:
            continue
        by.setdefault(int(r["season"]), []).append(r)
    for y, rs in sorted(by.items()):
        names, games, grp = {}, [], {}
        for r in rs:
            for s in ("home", "away"):
                code = r[f"{s}_team"]
                fr, era, conf, div = NFL_TEAMS[code]
                nm = [n for (y0, n) in era if y0 <= y][-1] if any(y0 <= y for y0, _ in era) else era[0][1]
                latest = NFL_TEAMS[[c for c, v in NFL_TEAMS.items() if v[0] == fr][-1]][1][-1][1]
                t = T.get(fr, latest, latest.split()[-1] if not latest.endswith("Team") else "Washington", fr)
                names[t] = nm
                key = f"{conf}|{div}"
                if t not in grp.setdefault(key, []):
                    grp[key].append(t)
            kind, rnd = (0, "") if r["game_type"] == "REG" else (5, "SB") if r["game_type"] == "SB" else (3, NFL_ROUND[r["game_type"]])
            if kind == 0 and r.get("div_game") == "1":
                kind = 1
            g = [day(r["gameday"]), T.idx[NFL_TEAMS[r["home_team"]][0]], T.idx[NFL_TEAMS[r["away_team"]][0]],
                 int(r["home_score"]), int(r["away_score"]), kind]
            if rnd:
                g.append(rnd)
            games.append(g)
        games.sort(key=lambda g: (g[0], g[1]))
        season = {"label": str(y), "games": games, "names": names, "groups": {k: sorted(v) for k, v in grp.items()}}
        fin = next((g for g in reversed(games) if g[5] == 5), None)
        if fin:
            season["champ"] = fin[1] if fin[3] > fin[4] else fin[2]
        seasons[str(y)] = season
    return _pack("nfl", T, seasons)


def _pack(lg: str, T: Teams, seasons: dict) -> dict:
    for s in seasons.values():  # keep a season's name only where it differs from the team's current one
        s["names"] = {str(t): nm for t, nm in s["names"].items() if nm != T.rows[t][0]}
    return {"id": lg, "teams": T.rows, "seasons": seasons}


def build_soccer(src: str, lg: str) -> dict:
    """A domestic league: every game, and the table at the end (3 points a win, then goal difference, then goals)."""
    slug, label = SOCCER[lg]
    T = Teams()
    seasons = {}
    for y in range(2006, 2030):
        f = os.path.join(src, "soccer", f"season-{(y - 1) % 100:02d}{y % 100:02d}.csv".replace("season-", f"{slug}-"))
        if not os.path.exists(f):
            f = os.path.join(src, "soccer", f"season-{(y - 1) % 100:02d}{y % 100:02d}.csv")
            if not os.path.exists(f):
                continue
        games = []
        for r in csv.DictReader(open(f, encoding="utf-8", errors="replace")):
            if not r.get("HomeTeam") or r.get("FTHG") in ("", None) or r.get("FTAG") in ("", None):
                continue
            h = T.get(r["HomeTeam"], CLUBS.get(r["HomeTeam"], r["HomeTeam"]), r["HomeTeam"])
            a = T.get(r["AwayTeam"], CLUBS.get(r["AwayTeam"], r["AwayTeam"]), r["AwayTeam"])
            d = r["Date"]
            if "/" in d:  # (older files: dd/mm/yy)
                dd, mm, yy = d.split("/")
                d = f"{2000 + int(yy) if len(yy) == 2 else int(yy)}-{int(mm):02d}-{int(dd):02d}"
            games.append([day(d), h, a, int(float(r["FTHG"])), int(float(r["FTAG"])), 1])
        if not games:
            continue
        games.sort(key=lambda g: (g[0], g[1]))
        pts, gd, gf = defaultdict(int), defaultdict(int), defaultdict(int)
        for g in games:
            _, h, a, hs, as_ = g[:5]
            for t, f_, a_ in ((h, hs, as_), (a, as_, hs)):
                pts[t] += 3 if f_ > a_ else 1 if f_ == a_ else 0
                gd[t] += f_ - a_
                gf[t] += f_
        table = sorted(pts, key=lambda t: (-pts[t], -gd[t], -gf[t], T.rows[t][0]))
        champ, runner = table[0], table[1]
        if (lg, y) in TITLE_OVERRIDE:  # a title taken away after the fact
            champ, runner = T.idx[TITLE_OVERRIDE[(lg, y)]], None
        seasons[str(y)] = {"label": f"{y - 1}-{y % 100:02d}", "games": games, "names": {}, "groups": {label: sorted(pts)},
                           "champ": champ, "title": [games[-1][0], champ, runner, pts[champ], pts[runner] if runner is not None else None]}
    return _pack(lg, T, seasons)


def write(lg: str, data: dict):
    """One folder per league: teams.json, index.json (every season's dates and title game) and a file per season, so the
    phone only reads the season the story's in."""
    d = os.path.join(OUT, lg)
    os.makedirs(d, exist_ok=True)
    for f in glob.glob(os.path.join(d, "*.json")):
        os.remove(f)
    with open(os.path.join(d, "teams.json"), "w", encoding="utf-8") as f:
        json.dump(data["teams"], f, separators=(",", ":"))
    index = {}
    for k, season in data["seasons"].items():
        g = season["games"]
        fin = next((x for x in reversed(g) if x[5] == 5), None)
        index[k] = {"label": season["label"], "first": g[0][0], "last": g[-1][0],
                    "title": fin[:5] if fin else season.get("title"), "champ": season.get("champ"), "names": season.get("names") or {}}
        if int(k) < FILES_FROM:
            continue  # (before the story: only its champion, in the index)
        with open(os.path.join(d, f"{k}.json"), "w", encoding="utf-8") as f:
            json.dump(season, f, separators=(",", ":"))
    with open(os.path.join(d, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, separators=(",", ":"))
    size = sum(os.path.getsize(x) for x in glob.glob(os.path.join(d, "*.json")))
    print(f"{lg}: {min(index)}-{max(index)}, {len(data['teams'])} teams, "
          f"{sum(len(x['games']) for x in data['seasons'].values())} games, {size / 1e6:.2f} MB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--src", required=True, help="folder for the downloaded files (one subfolder per league)")
    ap.add_argument("--download", action="store_true", help="fetch the files first")
    ap.add_argument("--only", help="build just these leagues (comma-separated)")
    a = ap.parse_args()
    if a.download:
        download(a.src)
    os.makedirs(OUT, exist_ok=True)
    want = set((a.only or "nfl,nba,cfb,mbb,wbb," + ",".join(SOCCER)).split(","))
    for lg in ("nfl", "nba", "cfb", "mbb", "wbb", *SOCCER):
        if lg in want:
            write(lg, build_nfl(a.src) if lg == "nfl" else build_cfb(a.src) if lg == "cfb" else
                  build_soccer(a.src, lg) if lg in SOCCER else build_basketball(a.src, lg))
    with open(os.path.join(OUT, "titles.json"), "w", encoding="utf-8") as f:
        json.dump(TITLES, f, indent=1)
    print("titles.json:", ", ".join(TITLES))
