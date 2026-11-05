"""Soccer and softball, and boys' and girls' teams: who can try out where, one sport a season, soccer box scores that add
up, gendered college teams and recruiting, and older saves brought up to date."""
import copy
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import college, minigames, sports, teams  # noqa: E402
from lifeos.engine import Simulation  # noqa: E402
from lifeos.story import StoryError, begin, create_story, validate_story  # noqa: E402
from tests.test_story import spec  # noqa: E402

GIRLS = {"basketball_girls", "soccer_girls", "softball"}
BOYS = {"football", "basketball", "baseball", "soccer"}


def _world(per=12):
    w = create_story(spec(per=per))
    sim = Simulation(w)
    begin(sim)
    return w, sim


def test_every_team_has_a_side_and_the_new_sports_exist():
    w, sim = _world()
    hs = {g["id"]: g for g in w.groups.values() if g["kind"] == "team" and g.get("school") == "hchs"}
    assert set(hs) == GIRLS | BOYS
    assert all(hs[g]["gender"] == "f" for g in GIRLS) and all(hs[g]["gender"] == "m" for g in BOYS)
    assert hs["basketball"]["name"] == "Guilford Boys Basketball" and hs["basketball_girls"]["name"] == "Guilford Girls Basketball"
    assert {"soccer", "softball"} <= set(sim.cat.sports["sports"]) and {"soccer", "softball"} <= set(sim.cat.skills)
    assert all(hs[g]["staff"] in w.chars for g in hs), "every team has its coach"
    keys = {i["group"] for i in w.calendar if i["kind"] in ("tryout", "game")}
    assert GIRLS | BOYS <= keys, "every team has tryouts and games this year"


def test_girls_try_out_for_girls_teams_and_boys_for_boys_teams():
    w, sim = _world()
    me = w.chars[w.meta["protagonist"]]
    girl = next(c for c in w.students() if c.gender == "f" and c.school == "hchs")
    boy_opps = {o[0] for o in sim.institutions.opportunities(me)}
    girl_opps = {o[0] for o in sim.institutions.opportunities(girl)}
    assert "football" in boy_opps and not boy_opps & GIRLS
    assert "soccer_girls" in girl_opps and not girl_opps & BOYS
    nb = copy.copy(girl)
    nb.gender = "nb"
    assert sports.can_play(nb, w.groups["soccer"]) and sports.can_play(nb, w.groups["soccer_girls"])
    assert sports.sports_for("m") == ["football", "basketball", "baseball", "soccer"]
    assert sports.sports_for("f") == ["basketball", "soccer", "softball"]


def test_the_coach_only_takes_players_from_their_side():
    w, sim = _world()
    it = next(i for i in w.calendar if i["kind"] == "tryout" and i["group"] == "soccer_girls")
    boy = w.meta["protagonist"]
    girl = next(c.id for c in w.students() if c.gender == "f" and c.school == "hchs")
    w.registrations[it["key"]] = [boy, girl]
    sim.advance_days(it["day"] - w.day + 2)
    assert boy not in w.groups["soccer_girls"]["members"]
    rows = [e for e in w.history.events.values() if e["type"] == "tryout" and e["outcome"] == "held" and e.get("group") == "soccer_girls"]
    assert rows and all(r["char"] != boy for r in rows[-1]["data"]["rows"])


def test_one_sport_a_season():
    w, sim = _world()
    me = w.chars[w.meta["protagonist"]]
    fb = next(i for i in w.calendar if i["kind"] == "tryout" and i["group"] == "football")
    w.registrations.setdefault(fb["key"], []).append(me.id)
    opps = {o[0] for o in sim.institutions.opportunities(me)}
    assert "soccer" not in opps, "trying out for football rules out boys' soccer this fall"
    assert sports.clash(w, me, w.groups["soccer"])["id"] == "football"
    assert sports.clash(w, me, w.groups["basketball"]) is None, "winter is a different season"


def test_soccer_box_scores_add_up_to_the_score():
    rng = random.Random(3)
    for score, win in (("3-1", True), ("0-2", False), ("2-0", True), ("1-1", False)):
        box = {f"p{i}": {"pos": pos, "starter": True, "line": sports.stat_line("soccer", pos, 1.0, True, rng)}
               for i, pos in enumerate(["GK", "FB", "CB", "CB", "FB", "CM", "CM", "WM", "WM", "ST", "ST"])}
        sports.soccer_box(box, score, win, rng)
        a, b = (int(x) for x in score.split("-"))
        ours, theirs = (max(a, b), min(a, b)) if win else (min(a, b), max(a, b))
        assert sum(v["line"].get("goals", 0) for v in box.values()) == ours
        assert sum(v["line"].get("assists", 0) for v in box.values()) <= ours
        assert box["p0"]["line"].get("goals", 0) == 0, "keepers don't score here"
        assert bool(box["p0"]["line"].get("clean_sheets")) == (theirs == 0)
    assert sports.line_text("soccer", {"goals": 2, "assists": 1, "shots": 4}) == "2 goals, 1 assist, 4 shots"
    assert sports.line_text("soccer", {"saves": 6, "clean_sheets": 1}) == "6 saves, a clean sheet"
    assert sports.line_text("softball", {"ab": 4, "h": 2, "rbi": 1}) == "2-for-4, 1 RBI"


def test_a_soccer_season_plays_out():
    w, sim = _world(per=14)
    sim.advance_days(40)
    games = [e for e in w.history.events.values() if e["type"] == "game" and e["outcome"] in ("win", "loss")
             and e["data"].get("sport") == "soccer"]
    assert games, "boys' and girls' soccer both play"
    assert {e["group"] for e in games} == {"soccer", "soccer_girls"}
    for e in games:
        a, b = (int(x) for x in e["data"]["score"].split("-"))
        ours = max(a, b) if e["outcome"] == "win" else min(a, b)
        assert sum(v["line"].get("goals", 0) for v in e["data"]["box"].values()) == ours
    for gid in ("soccer", "soccer_girls"):
        side = {"soccer": "m", "soccer_girls": "f"}[gid]
        assert all(w.chars[m].gender in (side, "nb") for m in w.groups[gid]["members"])


def test_game_day_mini_games():
    assert minigames.resolve_game("sport", {"sport_id": "soccer"}) == "soccer_11"
    assert minigames.resolve_game("sport", {"sport_id": "softball"}) == "baseball"


def test_a_girls_baseball_is_softball_in_story_setup():
    s = spec()
    s["protagonist"].update({"first": "Zoe", "gender": "f", "attracted_to": ["m"]})
    w = create_story(s)
    me = w.chars[w.meta["protagonist"]]
    assert "baseball" not in me.interests and me.interests["softball"] == 90 and me.positions["softball"] == "SS"
    sim = Simulation(w)
    begin(sim)
    assert "softball" in {o[0] for o in sim.institutions.opportunities(me)} or any(
        i["group"] == "softball" for i in w.calendar if i["kind"] == "tryout")


def test_college_paths_check_the_side():
    s = spec()
    s["cast"].append({"key": "z", "first": "Zed", "gender": "m", "grade": 12, "path": {"college": "texas", "sport": "soccer"}})
    try:
        validate_story(s)
        assert False, "Texas has no men's soccer"
    except StoryError as e:
        assert "men's soccer" in str(e)
    s["cast"][-1].update({"gender": "f", "first": "Zia"})
    validate_story(s)  # women's soccer at Texas is fine
    s["cast"][-1]["path"] = {"college": "miami", "sport": "baseball"}
    try:
        validate_story(s)
        assert False, "a girl's baseball is softball, and Miami has none"
    except StoryError as e:
        assert "softball" in str(e)


def test_colleges_have_mens_and_womens_teams():
    w, sim = _world()
    girl = next(c for c in w.students() if c.gender == "f" and c.school == "hchs")
    girl.path = {"kind": "college", "college": "uconn", "sport": "basketball", "scholarship": True}
    meta = college.ensure_college(sim, "uconn")
    assert w.groups["col_basketball"]["name"] == "UConn Men's Basketball" and w.groups["col_basketball"]["gender"] == "m"
    assert w.groups["col_basketball_w"]["name"] == "UConn Women's Basketball" and w.groups["col_basketball_w"]["gender"] == "f"
    assert {"col_softball", "col_soccer", "col_soccer_w", "col_football", "col_baseball"} <= set(w.groups)
    assert meta["levels"]["basketball_w"] > meta["levels"]["basketball"], "UConn women's basketball is the stronger program"
    assert sports.team_for(w, girl, "basketball", "college") == "col_basketball_w"
    assert w.chars["col_coach_basketball_w"].role_label == "UConn women's basketball coach"
    assert sports.aid_label(sim.cat.college_by_id["uconn"], "soccer") == "partial scholarship"
    assert sports.aid_label(sim.cat.college_by_id["uconn"], "basketball") == "full scholarship"


def test_recruiting_only_offers_teams_that_exist_on_your_side():
    w, sim = _world()
    boy = w.chars[w.meta["protagonist"]]
    boy.grade = 12
    boy.skills["soccer"] = 95
    boy.interests["soccer"] = 95
    boy.gpa = 4.0
    rng = random.Random(1)
    for _ in range(6):
        sports.recruiting_update(sim.institutions, boy, "soccer", rng)
    cols = {k.split(":")[0] for k in boy.recruiting["interest"]}
    assert cols and not cols & {"texas", "lsu", "oklahoma", "fsu", "miami"}, "no men's soccer at those schools"
    assert all(o.get("side") == "soccer" for o in boy.recruiting["offers"])


def _old_save():
    """A world as it was before soccer and the split: three teams, no genders, a girl on basketball and baseball."""
    w = create_story(spec(per=10))
    for gid in ("soccer", "soccer_girls", "basketball_girls", "softball"):
        del w.groups[gid]
    for g in w.groups.values():
        g.pop("gender", None)
    w.groups["basketball"]["name"] = "Guilford Basketball"
    for cid in ("coach_dimarco", "coach_lindqvist", "coach_mensah", "coach_torres"):
        del w.chars[cid]
    w.calendar = [i for i in w.calendar if i.get("group") not in ("soccer", "soccer_girls", "basketball_girls", "softball")]
    girl = next(c for c in w.students() if c.gender == "f" and c.school == "hchs" and c.grade >= 10)
    for c in w.chars.values():
        for s in ("soccer", "softball"):
            c.skills.pop(s, None)
            c.interests.pop(s, None)
    girl.interests["baseball"] = 80
    girl.skills["baseball"] = 50
    girl.positions["baseball"] = "P"
    for gid in ("basketball", "baseball"):
        w.groups[gid]["members"].append(girl.id)
        w.groups[gid].setdefault("levels", {})[girl.id] = "varsity"
        girl.memberships.append(gid)
    w.meta.pop("teams_version", None)
    return w, girl


def test_an_older_save_gets_the_new_teams_once():
    w, girl = _old_save()
    sim = Simulation(w)
    assert w.meta["teams_version"] == teams.VERSION
    assert {"soccer", "soccer_girls", "basketball_girls", "softball"} <= set(w.groups)
    assert w.groups["basketball"]["gender"] == "m" and w.groups["basketball"]["name"] == "Guilford Boys Basketball"
    assert {"coach_dimarco", "coach_lindqvist", "coach_mensah", "coach_torres"} <= set(w.chars)
    assert "basketball" not in girl.memberships and "basketball_girls" in girl.memberships
    assert w.groups["basketball_girls"]["levels"][girl.id] == "varsity"
    assert "softball" in girl.memberships and girl.interests["softball"] == 80 and girl.positions["softball"] == "P"
    assert any(c.interests.get("soccer", 0) >= 25 for c in w.students()), "some kids pick up soccer"
    assert any(i.get("group") == "soccer_girls" and i["kind"] == "game" for i in w.calendar)
    assert all(i["day"] >= w.day for i in w.calendar if i.get("group") in ("soccer", "softball"))
    before = copy.deepcopy(sorted(w.groups))
    Simulation(w)
    assert sorted(w.groups) == before, "it only runs once"
    sim.advance_days(3)  # and the world keeps going
