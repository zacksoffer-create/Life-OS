"""SQLite persistence: save slots (full world snapshots, history included) and experiments.

A save is the complete world as JSON, zlib-compressed. Because randomness is derived from the
seed plus the day/slot/character, a loaded save continues exactly as the original would have.
"""
from __future__ import annotations

import json
import os
import threading
import time
import zlib

from .history import History
from .model import World

DEFAULT_DB = os.environ.get("LIFEOS_DB") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "var", "lifeos.db")


def world_to_bytes(w: World, with_history: bool = True) -> bytes:
    d = w.to_dict()
    if not with_history:
        d["history"] = None
    # level 1: a few times faster than 6 for a slightly bigger file (the phone saves every half minute while you play)
    return zlib.compress(json.dumps(d, separators=(",", ":")).encode("utf-8"), 1)


def world_from_bytes(b: bytes) -> World:
    return World.from_dict(json.loads(zlib.decompress(b).decode("utf-8")))


def world_to_json(w: World, with_history: bool = False) -> str:
    d = w.to_dict()
    if not with_history:
        d["history"] = None
    return json.dumps(d, separators=(",", ":"))


def world_from_json(s: str) -> World:
    w = World.from_dict(json.loads(s))
    if w.history is None:
        w.history = History()
    return w


class Store:
    def __init__(self, path: str = DEFAULT_DB):
        import sqlite3
        self.path = path
        if path != ":memory:":
            os.makedirs(os.path.dirname(path), exist_ok=True)
        self._lock = threading.Lock()
        self._mem = sqlite3.connect(":memory:", check_same_thread=False) if path == ":memory:" else None
        with self._conn() as cx:
            cx.execute("""CREATE TABLE IF NOT EXISTS saves (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, kind TEXT NOT NULL, created REAL NOT NULL,
                day INTEGER, date_label TEXT, seed INTEGER, gen_seed INTEGER, population INTEGER, rules_version TEXT,
                events INTEGER, notes TEXT, size INTEGER, blob BLOB NOT NULL)""")
            cx.execute("""CREATE TABLE IF NOT EXISTS experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, created REAL NOT NULL, status TEXT NOT NULL,
                spec TEXT NOT NULL, result BLOB, finished REAL, error TEXT)""")
            cx.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")

    def _conn(self):
        import sqlite3
        if self._mem is not None:
            return _Ctx(self._mem, self._lock)
        cx = sqlite3.connect(self.path, timeout=30)
        return _Ctx(cx, self._lock, close=True)

    # --- saves ---------------------------------------------------------------
    def save_world(self, w: World, name: str, kind: str = "manual", notes: str = "") -> int:
        from .calendar import label
        blob = world_to_bytes(w)
        pop = sum(1 for c in w.chars.values() if c.status == "active")
        from .rules import rules_hash
        with self._conn() as cx:
            if kind == "autosave":
                cx.execute("DELETE FROM saves WHERE kind='autosave'")
            cur = cx.execute(
                "INSERT INTO saves (name, kind, created, day, date_label, seed, gen_seed, population, rules_version, events, notes, size, blob) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (name, kind, time.time(), w.day, label(w.day), w.seed, w.gen_seed, pop, rules_hash(w.rules),
                 len(w.history.events) if w.history else 0, notes, len(blob), blob))
            return cur.lastrowid

    def list_saves(self) -> list[dict]:
        with self._conn() as cx:
            rows = cx.execute("SELECT id, name, kind, created, day, date_label, seed, gen_seed, population, rules_version, events, notes, size "
                              "FROM saves ORDER BY created DESC").fetchall()
        keys = ["id", "name", "kind", "created", "day", "date_label", "seed", "gen_seed", "population", "rules_version", "events", "notes", "size"]
        return [dict(zip(keys, r)) for r in rows]

    def load_blob(self, sid: int) -> bytes | None:
        with self._conn() as cx:
            r = cx.execute("SELECT blob FROM saves WHERE id=?", (sid,)).fetchone()
        return r[0] if r else None

    def load_world(self, sid: int) -> World | None:
        b = self.load_blob(sid)
        return world_from_bytes(b) if b else None

    def latest_autosave(self) -> World | None:
        with self._conn() as cx:
            r = cx.execute("SELECT blob FROM saves WHERE kind='autosave' ORDER BY created DESC LIMIT 1").fetchone()
        return world_from_bytes(r[0]) if r else None

    def delete_save(self, sid: int) -> bool:
        with self._conn() as cx:
            cur = cx.execute("DELETE FROM saves WHERE id=?", (sid,))
            return cur.rowcount > 0

    # --- experiments -----------------------------------------------------------
    def create_experiment(self, name: str, spec: dict) -> int:
        with self._conn() as cx:
            cur = cx.execute("INSERT INTO experiments (name, created, status, spec) VALUES (?,?,?,?)",
                             (name, time.time(), "running", json.dumps(spec)))
            return cur.lastrowid

    def finish_experiment(self, eid: int, result: dict | None, error: str | None = None):
        blob = zlib.compress(json.dumps(result).encode()) if result is not None else None
        with self._conn() as cx:
            cx.execute("UPDATE experiments SET status=?, result=?, finished=?, error=? WHERE id=?",
                       ("failed" if error else "done", blob, time.time(), error, eid))

    def list_experiments(self) -> list[dict]:
        with self._conn() as cx:
            rows = cx.execute("SELECT id, name, created, status, spec, finished, error FROM experiments ORDER BY created DESC").fetchall()
        out = []
        for r in rows:
            spec = json.loads(r[4])
            out.append({"id": r[0], "name": r[1], "created": r[2], "status": r[3], "finished": r[5], "error": r[6],
                        "days": spec.get("days"), "seeds": spec.get("seeds"), "variants": [v["name"] for v in spec.get("variants", [])]})
        return out

    def get_experiment(self, eid: int) -> dict | None:
        with self._conn() as cx:
            r = cx.execute("SELECT id, name, created, status, spec, result, finished, error FROM experiments WHERE id=?", (eid,)).fetchone()
        if not r:
            return None
        return {"id": r[0], "name": r[1], "created": r[2], "status": r[3], "spec": json.loads(r[4]),
                "result": json.loads(zlib.decompress(r[5]).decode()) if r[5] else None, "finished": r[6], "error": r[7]}

    def delete_experiment(self, eid: int) -> bool:
        with self._conn() as cx:
            return cx.execute("DELETE FROM experiments WHERE id=?", (eid,)).rowcount > 0

    def mark_stale_experiments(self):
        with self._conn() as cx:
            cx.execute("UPDATE experiments SET status='failed', error='server restarted before it finished' WHERE status='running'")


class FileStore:
    """Saves as plain files (for the phone app, where there's no SQLite). Same interface as Store; no experiments."""

    def __init__(self, folder: str):
        self.folder = folder
        os.makedirs(folder, exist_ok=True)
        self._index_path = os.path.join(folder, "saves.json")

    def _index(self) -> list:
        try:
            with open(self._index_path) as f:
                return json.load(f)
        except (OSError, ValueError):
            return []

    def _write_index(self, rows):
        tmp = self._index_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(rows, f)
        os.replace(tmp, self._index_path)

    def save_world(self, w: World, name: str, kind: str = "manual", notes: str = "") -> int:
        from .calendar import label
        from .rules import rules_hash
        blob = world_to_bytes(w)
        rows = self._index()
        if kind == "autosave":
            for r in [r for r in rows if r["kind"] == "autosave"]:
                try:
                    os.remove(os.path.join(self.folder, f"save-{r['id']}.bin"))
                except OSError:
                    pass
            rows = [r for r in rows if r["kind"] != "autosave"]
        sid = max([r["id"] for r in rows] + [0]) + 1
        tmp = os.path.join(self.folder, f"save-{sid}.bin.tmp")
        with open(tmp, "wb") as f:
            f.write(blob)
        os.replace(tmp, os.path.join(self.folder, f"save-{sid}.bin"))
        rows.insert(0, {"id": sid, "name": name, "kind": kind, "created": time.time(), "day": w.day, "date_label": label(w.day),
                        "seed": w.seed, "gen_seed": w.gen_seed, "population": sum(1 for c in w.chars.values() if c.status == "active"),
                        "rules_version": rules_hash(w.rules), "events": len(w.history.events) if w.history else 0, "notes": notes,
                        "size": len(blob)})
        self._write_index(rows)
        return sid

    def list_saves(self) -> list:
        return self._index()

    def load_blob(self, sid: int):
        try:
            with open(os.path.join(self.folder, f"save-{int(sid)}.bin"), "rb") as f:
                return f.read()
        except OSError:
            return None

    def load_world(self, sid: int):
        b = self.load_blob(sid)
        return world_from_bytes(b) if b else None

    def latest_autosave(self):
        auto = [r for r in self._index() if r["kind"] == "autosave"]
        return self.load_world(auto[0]["id"]) if auto else None

    def delete_save(self, sid: int) -> bool:
        rows = self._index()
        keep = [r for r in rows if r["id"] != sid]
        if len(keep) == len(rows):
            return False
        try:
            os.remove(os.path.join(self.folder, f"save-{sid}.bin"))
        except OSError:
            pass
        self._write_index(keep)
        return True

    def create_experiment(self, name, spec):
        raise RuntimeError("experiments run in the lab on a computer")

    def finish_experiment(self, eid, result, error=None):
        pass

    def list_experiments(self) -> list:
        return []

    def get_experiment(self, eid):
        return None

    def delete_experiment(self, eid) -> bool:
        return False

    def mark_stale_experiments(self):
        pass


class _Ctx:
    def __init__(self, cx, lock, close=False):
        self.cx, self.lock, self.close = cx, lock, close

    def __enter__(self):
        self.lock.acquire()
        return self.cx

    def __exit__(self, et, ev, tb):
        try:
            if et is None:
                self.cx.commit()
            else:
                self.cx.rollback()
            if self.close:
                self.cx.close()
        finally:
            self.lock.release()
        return False
