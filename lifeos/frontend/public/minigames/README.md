# LIFE OS mini games

Each mini game is one standalone HTML file in this folder. It runs on its own (open it in a browser, or keep it in Google
Drive) and inside the app, where its score feeds the story.

## Add a game in 4 steps

1. **Put the file here**, e.g. `football.html`. One self-contained page: inline CSS and JS, a canvas, touch controls. It
   should fill the screen (the app shows it full screen under a small title bar).
2. **Add the bridge.** Paste `lifeos-bridge.js` into the page (or `<script src="lifeos-bridge.js"></script>`), then:
   ```js
   LifeOS.onStart(config => startGame(config));          // config.skill, config.difficulty, config.seed, config.mode...
   // ...when the round ends:
   LifeOS.finish({ score: made, max: attempts, summary: `${made} of ${attempts}` });
   ```
   Call `LifeOS.quit()` if the player backs out. Opened on its own, the game still works and the bridge does nothing.
3. **Register it** in `backend/data/minigames.json`: set `"file"`, set `"status": "ready"`, and set which skill it uses.
   Optionally add `free` (where it shows up for free play, and when) and `practice` (what a day's play does).
4. **Rebuild the phone app** (`python lifeos/tools/build_phone_app.py`).

## What the score does

A round is `score / max`. **Great** is 80% or more, **good** is 50% or more, anything less is a **miss**.
- **Free play** (the "Or play something" strip on the Story tab): once a day per game it gives practice (a small skill
  gain), fun and energy, scaled by how you did.
- **Game day:** the "Take over late. Play the big moment yourself." choice plays your sport's game (`sport_games` in
  minigames.json maps basketball, football, baseball and soccer to their games). Great is +7 to your game performance,
  good +3, a miss -2. The choice only shows once that sport's game is `ready`.
- **Story scenes** from dialogue packs can use any game with the `minigame` op.
- **Class quizzes, midterms and finals** use the built-in quiz. Your answers count toward the test.

## config

| field | meaning |
|---|---|
| `skill` | 0-100, the character's relevant skill blended with talent. Use it to steady aim, add assist, etc. |
| `difficulty` | 0-100. Higher in clutch moments and in later school years. |
| `mode` | `free`, `clutch` (game on the line), `quiz`. |
| `seed` | Use it for your randomness so a round can be replayed. |
| `me`, `them` | First names. |
| `sport`, `opponent` | On game day. |
| `college` | true once the player is in college (cup pong becomes beer pong, etc.). |

## Games

The games built in `games/` (basketball, golf, pong, At Bat, Swing Lab, Option Arcade, Soccer Playmaker) are copied here by
`python lifeos/tools/sync_games.py`. Edit them in `games/src/`, not here: the sync overwrites these copies.

| file | game id(s) | status | launches |
|---|---|---|---|
| `soccer11.html` | `soccer_11` | ready: Soccer Playmaker, 11 v 11 (game day uses this) | menu / clutch (three attacks) |
| `soccer.html` | `soccer_pk` | ready: penalty kicks (flick) | menu / clutch |
| `basketball.html` | `basketball`, `playmaker` | ready: Basketball Playground | menu / clutch (game day) / playmaker |
| `baseball.html` | `baseball` | ready: At Bat (game day uses this) | menu / clutch |
| `swing.html` | `swing_lab` | ready: Swing Lab batting prototype | menu / clutch (3 PAs) |
| `golf.html` | `golf` | ready: Fairway (weekends) | menu / short |
| `cup_pong.html` | `cup_pong` | ready: cup pong, beer pong in college (weekend nights) | menu / game |
| `football.html` | `football` | ready: Option Arcade (game day uses this) | menu / clutch (Goal Line: four downs from the 10) |
| `paper_toss.html` | `paper_toss` | coming (idea: the toss mechanic) | |

`play` in minigames.json says which mode a game opens in for each context (free play, game day clutch, story scene);
the game reads it from `config.play`.
