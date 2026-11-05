"""A backup is your whole story: the world and everything you wrote for it. It opens on the desktop (the lab) in one step
with your storylines and texting in it, comes back to the phone the same way, still opens in older copies, and an older
desktop copy is told when a backup is newer than it."""
import os
import sys
import zlib
import json

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import backup, dialogue  # noqa: E402
from lifeos.storage import world_from_bytes  # noqa: E402
from tests.test_story import spec  # noqa: E402

MINE = "=== Bus Rides\ncast: mike = older brother\nyears: freshman\n\n--- Saved a Seat\nmike: Saved you a seat.\n* \"Thanks.\"\nmike: Anytime.\n"
TEXTING = "=== Texting\nflirt tease:\n  you wish\n"


@pytest.fixture
def phone(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    monkeypatch.setattr(dialogue, "USER_DIR", str(tmp_path / "phone"))
    dialogue.reload()
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    c = TestClient(api.app)
    assert c.post("/api/story/new", json={"spec": spec(per=6)}).status_code == 200
    a = dialogue.add_script(MINE)["ids"][0]
    t = dialogue.add_script(TEXTING)["ids"][0]
    dialogue.set_enabled(t, False)
    yield c, api, tmp_path, a
    dialogue.reload()


def _desktop(api, tmp_path, monkeypatch, name="desktop"):
    """Another copy of LIFE OS: its own library, its own world."""
    from lifeos.storage import Store
    monkeypatch.setattr(dialogue, "USER_DIR", str(tmp_path / name))
    dialogue.reload()
    api.lab = api.Lab(Store(":memory:"), fresh=True)


def test_a_phone_backup_opens_on_the_desktop_in_one_step_with_everything(phone, monkeypatch):
    c, api, tmp, pid = phone
    r = c.get("/api/phone/backup")
    assert r.status_code == 200 and r.headers["content-disposition"].endswith('.lifeos"')
    data = r.content
    me = api.lab.w.meta["protagonist"]
    _desktop(api, tmp, monkeypatch)
    assert not dialogue.packs()
    j = c.post("/api/saves/upload?load=1", content=data).json()
    assert j["loaded"] and j["storylines"] == {"added": 2, "updated": 0, "same": 0} and "2 added" in j["said"]
    assert api.lab.w.meta["protagonist"] == me and j["title"]
    rows = {p["id"]: p for p in c.get("/api/dialogue/packs").json()["packs"]}
    assert rows[pid]["name"] == "Bus Rides" and rows[pid]["enabled"]
    assert not next(p for p in rows.values() if p["name"] == "Texting")["enabled"], "switched off stays off"
    assert any(s["name"].startswith(j["title"]) for s in c.get("/api/saves").json()), "it's under Saves too"
    # the desktop's own story isn't lost when one is loaded over it
    j2 = c.post("/api/saves/upload?load=1", content=data).json()
    assert j2["kept"] and j2["storylines"]["same"] == 2 and not j2["storylines"]["added"]


def test_my_story_load_on_the_desktop_keeps_whats_open(phone, monkeypatch):
    c, api, tmp, _ = phone
    data = c.get("/api/phone/backup").content
    _desktop(api, tmp, monkeypatch)
    assert c.post("/api/story/new", json={"spec": spec(per=6)}).status_code == 200
    j = c.post("/api/phone/restore?keep=1", content=data).json()
    assert j["story"] and j["kept"] and j["storylines"]["added"] == 2
    saves = c.get("/api/saves").json()
    assert any("before loading a backup" in s["name"] for s in saves)


def test_round_trip_back_to_the_phone_and_a_different_version_is_kept(phone, monkeypatch):
    c, api, tmp, pid = phone
    data = c.get("/api/phone/backup").content
    _desktop(api, tmp, monkeypatch)
    c.post("/api/saves/upload?load=1", content=data)
    # changed on the desktop, downloaded, back on the phone
    dialogue.add_script(dialogue.script_of(pid) + "\n--- Late Bus\nmike: Missed it again.\n* \"Ugh.\"\nmike: Yep.\n", into=pid)
    sid = c.get("/api/saves").json()[0]["id"]
    back = c.get(f"/api/saves/{sid}/download").content
    assert json.loads(zlib.decompress(back))["bundle"]["packs"], "a desktop download carries the storylines too"
    monkeypatch.setattr(dialogue, "USER_DIR", str(tmp / "phone"))
    dialogue.reload()
    j = c.post("/api/phone/restore", content=back).json()
    assert j["storylines"]["updated"] == 1 and j["storylines"]["same"] == 1
    assert "Late Bus" in dialogue.script_of(pid)
    assert any(v["why"] == "replaced by a backup" for v in dialogue.history()), "the phone's version can come back"


def test_older_copies_and_older_backups_still_open(phone, monkeypatch):
    c, api, tmp, _ = phone
    data = c.get("/api/phone/backup").content
    w = world_from_bytes(data)  # how a desktop copy from before bundles reads it: the world, the rest skipped
    assert w.meta.get("protagonist")
    from lifeos.storage import world_to_bytes
    old = world_to_bytes(api.lab.w)  # a backup from before bundles
    j = c.post("/api/phone/restore", content=old).json()
    assert j["story"] and j["storylines"] == {"added": 0, "updated": 0, "same": 0}
    for junk in (b"hello", b"\x00\x01\x02", zlib.compress(b'{"not": "a world"}')):
        r = c.post("/api/saves/upload", content=junk)
        assert r.status_code == 422 and "isn't a LIFE OS backup" in r.json()["detail"]


def test_a_backup_from_a_newer_copy_says_so(phone, monkeypatch):
    c, api, tmp, _ = phone
    d = json.loads(zlib.decompress(c.get("/api/phone/backup").content))
    d["bundle"]["release"] = "2099-01-01"
    j = c.post("/api/saves/upload?load=1", content=zlib.compress(json.dumps(d).encode())).json()
    assert j["loaded"] and "newer LIFE OS (2099-01-01)" in j["newer"]
    d["bundle"]["release"] = backup.RELEASE
    assert c.post("/api/saves/upload", content=zlib.compress(json.dumps(d).encode())).json()["newer"] is None


def test_a_backup_cant_write_outside_the_storyline_folder(phone, monkeypatch):
    c, api, tmp, _ = phone
    d = json.loads(zlib.decompress(c.get("/api/phone/backup").content))
    d["bundle"]["packs"] = [{"file": "../../evil.story", "text": MINE}, {"file": "state.json", "text": "{}"},
                            {"file": "x.py", "text": "print(1)"}, {"file": ".hidden.story", "text": MINE}]
    _desktop(api, tmp, monkeypatch, "desk2")
    j = c.post("/api/saves/upload", content=zlib.compress(json.dumps(d).encode())).json()
    assert j["storylines"]["added"] == 1  # (../../evil.story lands as evil.story, in the folder)
    assert sorted(f for f in os.listdir(dialogue.USER_DIR) if not f.startswith(".")) == ["evil.story", "state.json"]
    assert not os.path.exists(os.path.join(tmp, "evil.story"))
