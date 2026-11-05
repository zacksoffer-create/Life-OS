"""Bring the games (games/) into LIFE OS as mini games.

    python lifeos/tools/sync_games.py

Builds every game page (games/build.py), then copies each into lifeos/frontend/public/minigames/ under the name LIFE OS
loads it by. The lab serves that folder; build_phone_app.py copies it into the phone app. Each game page carries the LifeOS
bridge (games/src/shared/lifeos.js), so opened on its own it still plays exactly as before.
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GAMES = os.path.join(ROOT, "games")
OUT = os.path.join(ROOT, "lifeos", "frontend", "public", "minigames")
PAGES = {
    "basketball-playground.html": "basketball.html",
    "fairway.html": "golf.html",
    "pong-night.html": "cup_pong.html",
    "at-bat.html": "baseball.html",
    "swing-lab.html": "swing.html",
    "option-arcade.html": "football.html",
    "soccer-playmaker.html": "soccer11.html",
}


def main():
    sys.path.insert(0, GAMES)
    global standalone
    import standalone  # noqa: F401  (games/standalone.py: the document wrapper)
    subprocess.run([sys.executable, os.path.join(GAMES, "build.py")], check=True, cwd=GAMES)
    os.makedirs(OUT, exist_ok=True)
    for src, dst in PAGES.items():
        path = os.path.join(GAMES, "dist", src)
        text = open(path, encoding="utf-8").read()
        if "lifeos:minigame" not in text:
            print(f"skip {src}: it doesn't have the LifeOS bridge yet")
            continue
        body = text if text.lstrip().lower().startswith("<!doctype") else standalone.HEAD + text + standalone.FOOT  # same wrapper as games/standalone.py
        with open(os.path.join(OUT, dst), "w", encoding="utf-8") as f:
            f.write(body)
        print(f"{src} -> minigames/{dst} ({len(body) // 1024} KB)")


if __name__ == "__main__":
    main()
