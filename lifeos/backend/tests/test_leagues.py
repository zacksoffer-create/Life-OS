"""The NFL, the NBA and college sports behind the story, as they really happened: on their real dates, nothing past today,
your teams (the Giants, the Knicks, UConn, then your own college), fans who feel the titles, and hooks for storylines."""
import datetime as dt
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import calendar as calm  # noqa: E402
from lifeos import dialogue, moments, pro  # noqa: E402
from lifeos import realleagues as RL  # noqa: E402
from tests.test_story import spec  # noqa: E402


@pytest.fixture(autouse=True)
def own_packs(tmp_path, monkeypatch):
    monkeypatch.setattr(dialogue, "USER_DIR", str(tmp_path / "dialogue"))
    dialogue.reload()
    yield
    dialogue.reload()


def _story():
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    c = TestClient(api.app)
    assert c.post("/api/story/new", json={"spec": spec(per=8)}).status_code == 200
    for m in moments.pending(api.lab.w):
        moments.resolve(api.lab.sim, m["id"], None)
    return c, api.lab.sim


def _on(sim, y, m, d):
    sim.w.day = calm.day_of(dt.date(y, m, d))


def test_the_story_starts_in_fall_2010():
    assert calm.START == dt.date(2010, 9, 1)
    c, sim = _story()
    v = RL.view(sim, "nfl")
    assert v["season"] == "2010" and v["my_team"]["name"] == "New York Giants" and v["my_team"]["record"] is None
    assert v["my_team"]["next"]["opp"] == "Panthers"
    assert [x["season"] for x in v["champions"]][0] == "2009", "nothing past today"
    mbb = RL.view(sim, "mbb")
    assert mbb["season"] == "2009-10" and mbb["champions"][0]["champ"] == "Duke Blue Devils"


def test_uconn_2011_plays_out_day_by_day():
    c, sim = _story()
    _on(sim, 2011, 3, 1)
    card = RL.view(sim, "mbb")["my_team"]
    assert card["name"] == "UConn Huskies" and card["conf_record"] == "9-7" and not RL.in_postseason("mbb", "2011", card["team"], sim.w.day)
    _on(sim, 2011, 4, 3)
    assert pro.requirement(sim, None, "pro:mbb:my_team_alive") and RL.champion("mbb", "2011", sim.w.day) is None
    _on(sim, 2011, 4, 5)
    v = RL.view(sim, "mbb")
    assert v["champ"] == "UConn Huskies" and v["my_team"]["record"] == "32-9" and v["my_team"]["status"].startswith("Champions")
    assert pro.requirement(sim, None, "pro:mbb:my_team_champs") and not pro.requirement(sim, None, "pro:mbb:my_team_alive")
    RL.weekly(sim)
    me = sim.w.chars[sim.w.meta["protagonist"]]
    assert any("UConn men's basketball won the national championship" in m["text"] for m in me.memories)
    assert any("to win the national championship" in n["text"] for n in RL.state(sim)["news"])
    assert pro.names(sim, None)["mbb_champ"] == "UConn"


def test_the_pros_and_their_titles():
    c, sim = _story()
    _on(sim, 2012, 2, 4)
    assert RL.champion("nfl", "2011", sim.w.day) is None and pro.requirement(sim, None, "pro:nfl:my_team_alive")
    _on(sim, 2012, 2, 6)
    assert RL.name("nfl", RL.champion("nfl", "2011", sim.w.day)) == "Giants" and pro.requirement(sim, None, "pro:nfl:my_team_champs")
    _on(sim, 2011, 6, 13)
    nba = RL.view(sim, "nba")
    assert nba["champ"] == "Dallas Mavericks" and "lost to Celtics" in nba["my_team"]["status"]
    assert all(p["done"] for p in nba["postseason"]) and {p["round"] for p in nba["postseason"]} == {"R1", "CSF", "CF", "F"}
    RL.set_follow(sim, "nfl", "NE")
    assert RL.name("nfl", RL.followed(sim, "nfl")) == "Patriots"
    with pytest.raises(ValueError):
        RL.set_follow(sim, "nfl", "Hartford Colonials")


def test_your_college_once_you_are_there():
    c, sim = _story()
    me = sim.w.chars[sim.w.meta["protagonist"]]
    assert RL.my_college(sim) == "UConn" and RL.name("cfb", RL.followed(sim, "cfb")) == "UConn"
    me.path = {"kind": "college", "college": "lsu"}
    assert RL.my_college(sim) == "LSU" and RL.followed(sim, "cbase") == "LSU"
    _on(sim, 2011, 1, 11)
    cfb = RL.view(sim, "cfb")
    assert cfb["my_team"]["name"] == "LSU" and cfb["champ"] == "Auburn" and cfb["top25"]
    RL.set_follow(sim, "cfb", "Stanford")
    assert RL.my_college(sim) == "Stanford"
    _on(sim, 2011, 12, 31)
    soc = RL.view(sim, "wsoc")
    assert soc["titles_only"] and soc["finals"][0]["champ"] == "Stanford" and "2011" in soc["school_titles"]


def test_storylines_can_ask_about_any_league():
    c, sim = _story()
    ok = dialogue.check({"name": "Tourney", "scenes": [{
        "id": "march_run", "who": "best_friend", "title": "{my_college} is still alive",
        "text": "{them_first} won't stop talking about {my_college} ({my_mbb_record}). The {my_nfl_team} lost again.",
        "when": {"requires": ["pro:mbb:my_team_alive"]},
        "choices": [{"label": "Watch the game with them", "ops": [["mood", 3]]}, {"label": "Study", "ops": []}]}]})
    assert ok["ok"], ok["errors"]
    bad = dialogue.check({"name": "x", "scenes": [{"id": "bad_one", "who": "best_friend", "title": "t", "text": "t",
                                                    "when": {"requires": ["pro:mbb:my_team_rules"]},
                                                    "choices": [{"label": "a", "ops": []}, {"label": "b", "ops": []}]}]})
    assert not bad["ok"]
    g = dialogue.guide_markdown()
    assert "if pro:<league>:<condition>" in g and "my_team_alive" in g and "mbb" in g
    from lifeos import script
    r = script.compile_script("=== Tourney\n\n--- Still alive  [college · March · if pro:mbb:my_team_alive]\n"
                              "best friend: {my_college} is still alive. {my_mbb_record}.\n* Watch the game | mood +\n* Study\n")
    assert not r["errors"], r["errors"]
    assert r["packs"][0]["scenes"][0]["when"]["requires"] == ["pro:mbb:my_team_alive"]
    r = script.compile_script("=== x\n\n--- Nope  [if pro:mbb:my_team_rules]\nbest friend: hi\n* ok\n")
    assert r["errors"] and r["errors"][0]["line"] == 3


def test_the_phone_pages():
    c, sim = _story()
    lines = c.get("/api/phone/leagues").json()["leagues"]
    assert {x["league"] for x in lines} == set(RL.LEAGUES) and any(x["in_season"] for x in lines if x["league"] == "cfb")
    v = c.get("/api/phone/league", params={"lg": "nba"}).json()
    assert v["my_team"]["name"] == "New York Knicks" and v["standings"]
    v = c.post("/api/phone/league/follow", json={"lg": "mbb", "team": "North Carolina"}).json()
    assert v["my_team"]["name"] == "North Carolina Tar Heels"
    assert c.get("/api/phone/league", params={"lg": "cbase"}).json()["school"] == "North Carolina"
    assert c.get("/api/phone/league", params={"lg": "xfl"}).status_code == 404


def test_european_soccer_the_champions_league_and_the_ballon_dor():
    c, sim = _story()
    v = RL.view(sim, "epl")
    assert v["season"] == "2010-11" and v["my_team"]["name"] == "Manchester United" and v["champions"][0]["champ"] == "Chelsea"
    _on(sim, 2011, 5, 23)
    v = RL.view(sim, "epl")
    assert v["champ"] == "Manchester United" and v["my_team"]["record"] == "23-11-4" and v["my_team"]["points"] == 80
    assert v["my_team"]["place"] == "1st in the Premier League"
    _on(sim, 2012, 5, 14)
    rows = RL.view(sim, "epl")["standings"][0]["rows"]
    assert [r["name"] for r in rows[:2]] == ["Manchester City", "Manchester United"] and rows[0]["pts"] == rows[1]["pts"] == 89
    assert RL.index("seriea")["2006"]["champ"] == RL.find("seriea", "Inter"), "Juventus were stripped of 2005-06"
    _on(sim, 2011, 5, 27)
    assert not pro.requirement(sim, None, "pro:ucl:my_team_champs") or RL.finals("ucl", sim.w.day)[-1]["season"] == 2010
    _on(sim, 2011, 5, 29)
    ucl = RL.view(sim, "ucl")
    assert ucl["finals"][0]["label"] == "2010-11" and ucl["finals"][0]["champ"] == "Barcelona"
    assert pro.requirement(sim, None, "pro:ucl:my_team_champs"), "Barcelona is your La Liga club to start"
    ballon = RL.view(sim, "ballon")
    assert ballon["winners"][0]["year"] == 2010 and ballon["winners"][0]["winner"] == "Lionel Messi"
    assert pro.names(sim, None)["ballon_dor"] == "Lionel Messi" and pro.names(sim, None)["ucl_champ"] == "Barcelona"
    RL.set_follow(sim, "epl", "Arsenal")
    assert RL.name("epl", RL.followed(sim, "epl")) == "Arsenal" and "Arsenal" in RL.my_clubs(sim)
    with pytest.raises(ValueError):
        RL.set_follow(sim, "ucl", "Barcelona")
    _on(sim, 2011, 6, 1)
    RL.weekly(sim)
    news = [n["text"] for n in RL.state(sim)["news"]]
    assert "Manchester United win the Premier League (2010-11)." in news
    assert any("in the Champions League final" in t for t in news)
    me = sim.w.chars[sim.w.meta["protagonist"]]
    assert not any("La Liga" in m["text"] for m in me.memories), "a club you didn't pick is news, not a memory"
    assert c.get("/api/phone/league", params={"lg": "ballon"}).json()["award"]
    assert c.post("/api/phone/league/follow", json={"lg": "bund", "team": "Dortmund"}).json()["my_team"]["name"] == "Borussia Dortmund"
