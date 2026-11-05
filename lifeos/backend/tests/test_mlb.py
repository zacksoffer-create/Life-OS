"""MLB in the background: real history that replays exactly when nothing's changed, what-ifs that move real value and
replay October with as little change as possible, live seasons from 2026 that add up, fans who feel October, and the hooks
storylines use ({my_team}, pro: requirements)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import dialogue, mlb, moments, pro  # noqa: E402
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


def test_with_nothing_changed_every_season_is_what_really_happened():
    D = mlb.data()
    assert D.first == 1990 and D.last >= 2025
    for y in range(D.first, D.last + 1):
        r = mlb.replay(7, (), y)
        real = next((s[2] for s in D.post[y] if s[1] == "WS"), None)
        assert r["champ"] == real, y
        assert len(r["series"]) == len(D.post[y]) and all(s["how"] == "real" for s in r["series"]), y
    assert mlb.replay(7, (), 2009)["champ"] == "NYY" and mlb.replay(7, (), 1994)["champ"] is None


def test_values_read_like_war():
    D = mlb.data()

    def season(key, y):
        p = D.pidx[key]
        return sum(v for (_, v, _, _) in D.rows(p, y))
    assert season("bondsba01", 2001) > 11 and season("judgeaa01", 2022) > 9 and season("martipe02", 2000) > 8
    assert 0 < season("riverma01", 2004) < 5


def test_a_what_if_moves_real_value_and_replays_october():
    d = mlb.deltas(("lee_trade_2010",))
    assert set(d) == {2010}
    assert d[2010]["NYY"][0] > 1.5 and d[2010]["TEX"][0] < -1.5  # Lee's Texas half goes to New York
    assert d[2010]["NYY"][1] > d[2010]["NYY"][0]  # an ace is worth more in October
    r = mlb.replay(7, ("lee_trade_2010",), 2010)
    assert r["changed"] and r["odds"]["NYY"]["alt"] > r["odds"]["NYY"]["real"]
    assert r["wins"]["NYY"] > 95 and r["wins"]["TEX"] < 90
    # the same world rolls the same October every time; another world can roll differently
    assert mlb.replay(7, ("lee_trade_2010",), 2010)["series"] == r["series"]
    # a what-if that ends before today never reaches the live world, one that runs to now does
    assert all(m["years"][1] < 2025 for m in mlb.WHATIF["lee_trade_2010"]["moves"])
    assert any(m["years"][1] >= 2025 for m in mlb.WHATIF["harper_2019"]["moves"])
    for wid in mlb.WHATIF:
        assert mlb.deltas((wid,)), wid  # every player id resolves


def test_live_seasons_add_up(tmp_path):
    c, sim = _story()
    w = sim.w
    mlb.set_whatif(sim, "harper_2019", True)
    st = mlb.state(sim)
    mlb._build_live(sim)
    assert st["live"]["pl"]["harpebr03"]["t"] == "NYY", "a what-if's player who's still playing plays there"
    assert st["live"]["pl"]["schwaky01"]["t"] == "PHI"
    del st["live"]
    w.day = mlb.season_days(2027)["off"] + 1  # (only MLB looks at the calendar here)
    mlb.catch_up(sim)
    for y in ("2026", "2027"):
        a = st["arch"][y]
        assert all(sum(r) == 162 for r in a["rec"].values()), y
        assert sum(r[0] for r in a["rec"].values()) == sum(r[1] for r in a["rec"].values())
        assert a["champ"] in mlb.data().teams and len(a["post"]) == 4 + 4 + 2 + 1  # wild cards, DS, CS, WS
        assert {x["award"] for x in a["awards"]} >= {"mvp", "cy"}
        wins = sorted(r[0] for r in a["rec"].values())
        assert 40 <= wins[0] and wins[-1] <= 125
    assert any(n["kind"] in ("signing", "retire") for n in st["news"])
    # the draft goes worst-to-first by last season's record in this world
    order = mlb.draft_order(sim, 2027)
    rec = st["arch"]["2026"]["rec"]
    by_name = {mlb.team_name(t, short=False): t for t in rec}
    assert rec[by_name[order[0]]][0] <= rec[by_name[order[-1]]][0]
    v = mlb.view(sim)
    assert v["my_team"]["team"] == "NYY"
    if st["live"]["pl"].get("harpebr03", {}).get("t") == "NYY":  # (unless he's retired by now)
        assert any(s.get("moved") and s["name"] == "Bryce Harper" for s in v["my_team"]["stars"])
    assert mlb.year_view(sim, 2026)["champ"]


def test_october_2010_plays_out_on_its_real_dates_and_fans_feel_it():
    c, sim = _story()
    w = sim.w
    prot = w.meta["protagonist"]
    cur = mlb.current(sim)
    assert cur["year"] == 2010 and cur["phase"] == "regular" and cur["rec"]["NYY"][0] > 70 and not cur["october"]
    assert pro.requirement(sim, None, "pro:baseball_season") and not pro.requirement(sim, None, "pro:october")
    assert pro.requirement(sim, None, "pro:my_team_champs"), "the Yankees won the 2009 World Series"
    v = mlb.view(sim)
    assert v["my_team"]["titles"]["real"][-1] == 2009 and v["years"][-1] == 2009, "nothing past today"
    assert mlb.team_name("FLA", False, 2010) == "Florida Marlins" and mlb.team_name("CLE", True, 2016) == "Indians"
    w.day = mlb.season_days(2010)["DS"] + 1
    cur = mlb.current(sim)
    assert cur["phase"] == "october" and pro.requirement(sim, None, "pro:my_team_in_playoffs")
    ds = [s for s in cur["october"] if s["round"] == "DS"]
    assert ds and not any(s["done"] for s in ds), "the Division Series has only just started"
    w.day = mlb.season_days(2010)["WS"] + 12
    mlb.weekly(sim)
    assert mlb.current(sim)["champ"] == "SFG" and pro.last_champ(sim) == "SFG"
    assert not pro.requirement(sim, None, "pro:my_team_alive") and not pro.requirement(sim, None, "pro:my_team_champs")
    mem = [m["text"] for m in w.chars[prot].memories if m["kind"].startswith("pro_")]
    assert any("Rangers" in t for t in mem), mem  # the Yankees went out to Texas in the ALCS
    with pytest.raises(ValueError):
        mlb.year_view(sim, 2015)  # (hasn't happened yet)


def test_storylines_can_use_the_pros():
    c, sim = _story()
    ok = dialogue.check({"name": "Dad and the Yankees", "scenes": [{
        "id": "dad_yanks", "who": "best_friend", "title": "{my_team} game on", "text": "{them_first} has the {my_team} on. They're {my_team_record}.",
        "when": {"requires": ["pro:baseball_season", "pro:whatif:harper_2019"]},
        "choices": [{"label": "Watch with them", "ops": [["mood", 3]]}, {"label": "Not tonight", "ops": []}]}]})
    assert ok["ok"], ok["errors"]
    bad = dialogue.check({"name": "x", "scenes": [{"id": "x1", "who": "parent", "title": "t", "text": "t",
                                                    "when": {"requires": ["pro:yankees_rule"]},
                                                    "choices": [{"label": "a", "ops": []}, {"label": "b", "ops": []}]}]})
    assert not bad["ok"] and "pro:whatif:<id>" in " ".join(bad["errors"])
    assert not pro.requirement(sim, None, "pro:whatif:harper_2019")
    mlb.set_whatif(sim, "harper_2019", True)
    assert pro.requirement(sim, None, "pro:whatif:harper_2019")
    n = pro.names(sim, None)
    assert n["my_team"] == "Yankees" and "-" in n["my_team_record"] and n["my_team_star"]
    mlb.set_team(sim, "BOS")
    assert pro.names(sim, None)["my_team"] in ("Red Sox", "Yankees")  # names cache by day; the team itself moved
    assert mlb.my_team(sim) == "BOS"
    assert "pro:my_team_in_playoffs" in dialogue.guide_markdown()


def test_the_phone_pages():
    c, sim = _story()
    v = c.get("/api/phone/mlb").json()
    assert v["my_team"]["name"] == "New York Yankees" and v["standings"] and len(v["whatifs"]) == 12
    w = c.get("/api/phone/mlb/whatif", params={"id": "cole_2008"}).json()
    assert w["moves"][0]["name"] == "Gerrit Cole" and not w["seasons"] and w["later"], "2013-19 hasn't happened yet in 2010"
    w = c.get("/api/phone/mlb/whatif", params={"id": "beltran_2005"}).json()
    assert [s["year"] for s in w["seasons"]] == [2005, 2006, 2007, 2008, 2009] and w["later"]["years"] == "2010-2011"
    r = c.post("/api/phone/mlb/whatif", json={"id": "cole_2008", "on": True}).json()
    assert r["view"]["on"] and "cole_2008" in r["whatifs"]
    y = c.get("/api/phone/mlb/year", params={"y": 2009}).json()
    assert y["champ"] == "Yankees" and any(a["name"] == "Joe Mauer" for a in y["awards"])
    assert c.get("/api/phone/mlb/year", params={"y": 2031}).status_code == 404
    assert c.post("/api/phone/mlb/team", json={"team": "NOPE"}).status_code == 400
    assert c.post("/api/phone/mlb/team", json={"team": "NYM"}).json()["my_team"]["team"] == "NYM"
