# LIFE OS · Living World Laboratory (v0.1)

A persistent small-town life simulation with a lab built around it. The town is Guilford, Connecticut:
Guilford High School (the Grizzlies, Southern Connecticut Conference), its students, staff and their households. Every person decides for themselves what to do,
twice a day, from a transparent utility model. You can watch, inspect any decision down to the
random roll, change the rules, run controlled experiments, and step into one person's life.

**Story mode** is the playable side: build yourself, your family and the people you want in your life,
let the town fill in around them, and live seven years, from the first day of freshman year through
three years of college and the MLB Draft (or work). It has a full sports career in football, basketball, soccer, baseball and
softball, with separate boys' and girls' teams:
JV and varsity, starting spots, box scores, season stats, awards, injuries, recruiting, offers from real
colleges (UConn, Stanford, UCLA, LSU, UNC, Texas, Oklahoma, Florida State, Miami, Michigan) and the draft.

Everything here runs locally. No paid APIs, and no AI-generated text: the narrative comes from
procedural templates filled in from recorded simulation state.

## Run it

### The easy way (no typing)

1. Install Python from [python.org/downloads](https://www.python.org/downloads/). On Windows, tick **"Add python.exe to PATH"** on the installer's first screen.
2. Unzip the LIFE OS folder (on Windows: right-click the zip, then **Extract All**; don't run it from inside the zip).
3. Double-click **`Start LIFE OS (Windows).bat`** or **`Start LIFE OS (Mac).command`**.
   - Windows may say "Windows protected your PC": click **More info**, then **Run anyway**.
   - Mac may say it's from an unidentified developer: right-click the file, choose **Open**, then **Open** again.
4. The first time, it spends a minute or two setting up (needs internet). After that it starts in a few seconds.
   Your browser opens to the lab. Keep the black window open while you use it; close it to stop.

Don't open the Python app itself and paste commands into it. That window only understands Python code.

### The command-line way

You need **Python 3.10+** (tested on 3.13 and 3.15). Node is only needed if you want to change the interface (the built UI
is committed in `frontend/dist`).

```bash
cd lifeos
python -m pip install -r requirements.txt
python run.py                 # opens http://127.0.0.1:8765
```

Options: `--port 9000`, `--no-browser`, `--fresh` (ignore the autosave and start the demo world over).
The world autosaves to `lifeos/var/lifeos.db` (SQLite). Set `LIFEOS_DB=/path/to/file.db` to use another database.

**Changing the interface:**

```bash
cd lifeos/frontend
npm install
npm run dev      # http://localhost:5173, proxies /api to the Python server on 8765
npm run build    # rebuilds frontend/dist
```

## Your story (start here)

Open **My Story** in the sidebar and click **Start your story**. The setup has six steps:

1. **Welcome.** Name your story.
2. **You.** The character builder. Pick a starting archetype (athlete, brain, artist...) and it fills
   in a believable person, then tweak anything:
   - personality (10 traits), natural talent (5 aptitudes) and what drives them (6 motives);
   - interests and starting skills (a typical freshman is 25–50 in a sport);
   - height and build, jersey number, and a position in each sport you play.
3. **Family.** Your last name, guardians, how they parent, income and a pet (or no pet). Add siblings
   with a grade each; set "twin of" to make twins (same birthday, a twin bond).
   There are one-click buttons for an older brother who's a senior and twin sisters a year older than you.
   **Younger siblings** (6th, 7th or 8th grade) live at home in middle school and start high school as freshmen
   1, 2 or 3 years in.
4. **Your people.** Friends, a crush, a rival, a coach, anyone (up to 120). Each one gets the same builder, plus
   how they feel about you (best friend, crush, rival, teammate...). **Future freshman** makes someone younger,
   like the neighbor kid: pick **Next year**, **In 2 years** or **In 3 years** and they show up with that year's
   freshman class, taking one of its spots.
   Anyone besides you can also get a set path for after high school, like "play basketball at UConn":
   the offer shows up senior spring and they take it. Siblings have a quick dropdown for this on their card.
5. **The town.** How many students per grade (6–40). Generated classmates fill each grade around your people.
   Teams and casts grow with the school (past 12 a grade), so making varsity is about as hard at any size.
   12–20 plays smoothly on a phone; past 30, a day takes a few seconds there.

**Every fall, a new freshman class.** On Sept 1 everyone moves up a grade, the seniors are gone, and a freshman
class about the size of the one that graduated comes in. The people you made for that year come in with it: it's in
your feed ("Your little brother Sam starts at Guilford High School as a freshman."), your family and friends among
them text you, and every relationship you set up for them (your best friend's best friend, your neighbor) starts
that day. Until then, younger siblings show on the Home tab with their grade.
6. **Review & start.** Check catches every problem at once. You can also download your cast as a file
   and load it again later, so you don't have to rebuild your people.

**Playing.** The story page shows where you are in the seven years, how you're doing, your teams and
stats, your family and your people.
- **Live until something happens** runs the world until there's something for you: a story moment
  (tryouts, getting cut, an injury, a scholarship offer, a sibling leaving for college, someone asking
  you out, the college decision), an invitation, or a big event.
- **Play episodes back to back** (phone, Story tab) is just the story: **Next episode** lives your life up to the next
  storyline scene and stops there, every time. Every beat of a scene plays in a row, the last answer's button is Next
  episode, and an "8 days later" card shows the biggest things that happened in between (everything is one tap away).
  In between, your character handles the rest the way they would on their own: practices, games, classes, tryouts,
  invites. The scenes keep their real dates and pacing, so the story has the same shape it would day by day. **Back to
  living day by day** turns it off. API: `POST /api/story/advance {"until": "episode"}`; the mode is
  `{"binge": true}` on `/api/story/control`. It never lives a year forward looking: if none of your storyline scenes
  can come right now it stops at once and says why ("12 scenes: nobody in your story fits"), and otherwise it looks
  about two months ahead at most ("No storyline scene in the next two months"; tap again to keep going).
- **A big library stays quick.** What the game works out about each scene (who it needs, whether it's about a game,
  which sport) is kept until that scene changes, so adding a batch or opening Storylines doesn't redo every scene you
  have; the phone saves at most every 45 seconds while you play (and right away when you leave the app), since a save
  holds everything else up for a moment.
- **If a screen goes blank (iPhone).** Tap the same tab five times fast (the tab bar always shows) for **Diagnostics**,
  a plain panel about that screen: the build running and the latest online, the phone, the engine's memory, the story's
  size, what's on the Story page (and anything oversized), what's waiting, and whether the engine is busy. **Copy all
  of it** to send it. Switches, all remembered: **Simple look** (no animations, blur, shadows or blend), **Page
  scrolling** (the page scrolls instead of a box inside the app) and **Story page: hide a part** (the picture, the pills,
  today's strip/plate/week, the scene card, the choices, the setup card), to find what the phone won't draw. The Story
  page itself avoids what iPhone Safari stopped drawing: the scene card doesn't clip its contents and only fades in, the
  scene picture is a flat image (drawn once per place, season and time of day) with a plain tint, and nothing that
  scrolls has a backdrop blur. Also at `#/m/diag`.
- **Up next** (the bar at the top in episode mode) is the next ten episodes in the order they'll come, with about when
  (played forward on a copy, your character answering). Move any one up or down: the episode it passes now waits for
  it, saved in your story, and the list plays forward again so you see where everything lands. If a move would push an
  episode past its window, you're told it won't happen and can move it back. Moving one back undoes your earlier move
  instead of stacking another, and **Your changes** lists every move with Undo (or **Back to the story's own order**).
  **Play next** pulls an episode that could happen today straight to the front, right after the one on screen. Two
  things stay put: chapters of one storyline play in their order, and a scene that follows another in the story
  can't jump ahead of it. API: `GET /api/story/order`, `POST /api/story/order/move {sid, before}`,
  `/api/story/order/next {sid}`, `/api/story/order/clear {sid?}`.
- **Next choice** stops at your very next decision so you can pick exactly what you do. You see every
  real option and how likely you'd be to pick it on your own.
- **Focus** (athletics, academics, social, romance, family, rest, work) tilts what you do when you
  let yourself decide. It's a named term in every decision trace, so you can see how much it mattered.
- At any choice, **Let them decide** hands it back to the simulation.

**Your day on the phone.** The Story tab opens on today at a glance:
- **The day strip:** every part of today (morning, class, lunch, after school, evening, night). What you already did
  ("w/ Danny", "studied"), where you are now, and what's coming: practice, a game, a quiz, a plan you saved, or open time.
- **On your plate:** everything that needs you, from every corner of the game, in one list. Texts waiting on an answer,
  your pet chores, a test or game today or tomorrow, tryouts coming up, a dance you don't have a date for, a close
  friend's birthday, friends you haven't talked to in a week or more, and running on empty. Tap one to go handle it.
  When there's nothing, it says **You're all caught up**.
- **This week:** the next seven days with your games, tests, dances, tryouts, breaks and birthdays. Tap a day to see it.
- **What do you do?** is sorted into **Should** (practice, a shift, studying with a test tomorrow, your chore), **Want
  to** (the friend who asked, your partner, someone you're drifting from, a crush) and **Could** (everything else). Each
  choice says why it's there: "Quiz 1 tomorrow", "Coach takes attendance", "10 days since you talked". Choices that can
  wait have **Save for after school** or **Save for evening**: it's picked for you then, unless someone pulls you into
  something else first.
- **Invites never overrule you.** When you've made your own pick and a friend asks you to hang out in that same part of
  the day, the game doesn't answer for you: they text you to try again later ("saw you were busy. later this week?") and
  it's yours to answer. Plans you've said yes to show what and with whom: "Hanging out with Danny, next time you're free".
- **Game day: your game comes first.** In the part of the day your game (or your show) is in, **Play in your game vs
  Branford** sits at the top of Should. Everything else in that slot says **You'd miss your game**. A saved plan or a
  yes to an invite waits for your next free time instead of taking the game slot. If you skip it anyway, the team plays
  without you, and you're told: "You missed the game. Guilford Football lost to Branford, 14-21." On the Me tab, a team
  shows its record, and yours (**you 1-0**) under it when you've missed a game or joined after the season started.
  A game is only ever played once, even if a slot runs again after a reload.

Everyone else lives their own life the whole time. Your brother graduates and leaves, your sisters
go off to college a year later and come home for Thanksgiving, friends drift, rivals show up. Siblings
playing college sports somewhere else still get season stats on their page.

**Grades matter.** GPAs run on a real 4.0 scale (most kids land around 3.0–3.3). Every program has a GPA it
needs from recruits: the NCAA minimum is 2.3, and Stanford wants a 3.4. If your GPA is under it at
senior spring, the offer gets pulled. Regular admission to the big schools is hard (Stanford is a long shot
even with a 4.0). Southern Connecticut State and Gateway Community College are there as local options.

**Recruiting is earned.** Each college has a program strength per team (LSU baseball, UConn basketball on both sides,
UNC women's soccer, Oklahoma softball and Michigan football are near the top). The stronger the program, the better you need to be before
they offer. In senior spring you pick your path from the offers and admissions you've earned. On September 1
you arrive at college (teams, a roommate, new classmates, real conference opponents) or start working in town.

**The draft.** If you play college baseball, the Sports tab gets an MLB Draft board with your projected round
and why. The draft is in mid-July after your junior year: 20 rounds, real MLB teams, approximate slot values.
If you're picked, you choose: sign and start pro ball, or go back for senior year. That's the last chapter,
and the story closes with a look back at your seven years.

You can open anyone in **Character Studio** (including yourself) to see their full profile and athlete
page, and **History Explorer** shows the math behind anything that happened.

## Story pacing: many scenes a day

Storylines are paced by a scheduler (`backend/lifeos/scheduler.py`) instead of a fixed throttle. The old rules (at most one
scene every couple of days, five days between chapters) are gone; they live on only as the **Relaxed** setting.

- **Days and scenes are separate.** Each morning the game plans the day's storyline scenes and spreads them across it
  (morning, class, lunch, after school, evening, night). They come one at a time: the next one shows up once you've
  answered the last. **Continue story** on the Story tab plays the next one right away without moving the calendar,
  even past the day's target. A scene that unlocks another (`after`, no gap) can lead straight into it the same day.
- **How much story a day** (Me tab, or the Lab): **Relaxed** (the old pace), **Standard** (one or two a day),
  **Dense** (the default: two to five on a school day, three to seven on a weekend) or **Uncapped** (everything that's
  ready). These are targets, not quotas: nothing is invented to fill a day, and nothing authored is held back just to
  slow it down.
- **Nothing answers for you.** A storyline scene waits for you, however long, unless you turn on **Let my character
  decide story scenes**. Pending scenes survive closing the app.
- **The calendar stays real.** A scene is ready only when its school year, its months / dates / weekdays and its season
  fit. Scenes that don't say when get a season from the **season map**, built from Guilford's own calendar: tryouts the
  weeks around each team's tryout date, senior night in the last three weeks of that sport's season, playoffs and last
  games at the end, the Homecoming ask in the two weeks before the dance, the dance that weekend and the aftermath after,
  prom the same way, graduation the week of June 12, move-in at college in late August and September, summer in the
  summer. Baseball can't debut in September, the brother's last game can't come after his graduation, and move-in
  can't come before your own.
- **after means resolved.** A scene in `after` has to be answered (its last beat included) before what depends on it is
  ready; `gap_days` counts days from then, and no gap means it can come the same day. A scene whose school years are
  over counts as skipped (the rule from before), so later chapters don't get stuck.
- **Branches stay branches.** Remembered facts, `not_remembered` and in-order chapters work as before; when you pick
  one Homecoming date, the other three dances and aftermaths become unreachable, not forced.
- **Big moments get room.** Every scene has an importance (ambient, regular, major, finale), from the pack
  (`"importance"`) or read from its id and title. Dense pacing aims for about one major turn a week across storylines,
  unless the next follows straight from the last or its window is closing. Deadlines always win: a scene whose window
  is about to close moves to the front, so a year's leftovers don't pile onto its last day.
- **New optional fields** in a scene's `when` or a season plan's `schedule`: `not_before` / `not_after` (month-day
  inside the school year, like `"11-15"`) and `importance`. Everything else loads exactly as before.

**Story Schedule** (Lab, under History Explorer) shows every storyline's counts (played, queued, eligible, waiting,
expired, unreachable), every scene's state with the exact reason (`wrong_season`, `waiting_for_scene`, `missing_fact`,
`branch_closed`, `year_passed`, `missing_cast`, `major_breather`...), today's queue, an episode timeline with storyline
lanes, chain arrows and warnings, and a side-by-side run of all four pacing settings on the same seed. You can step one
scene, finish today, step a day or a week, release a blocked scene to test it, pin a scene's months or importance, set
storyline weights and override the targets. The phone has the same view under Me > Story schedule, with **Run the
check**: seven years forward on a copy, then a report you can save.

**The seeded report** for any set of packs (your season plan included):

```bash
python lifeos/tools/schedule_report.py "Season plan.json" storyline1.json storyline2.json --seed 1234 --out report
python lifeos/tools/schedule_report.py ... --full     # simulate the whole town (slower, exact requirements)
```

It writes `report.md` and `report.json`: every scene id with the day it played or why it didn't, deadline misses,
contradictions (out of season, before its prerequisite, out of chapter order) and who every cast slot is bound to. With
no packs it runs the synthetic season plan from the tests; the results are in `docs/reports/`.

**What the check fixed in the engine.** A real seven-year report (287 played, 254 unreachable) showed three ways whole
storylines went dark, and none of them were the story's fault:

- **Chapters nobody can play are stepped over.** If a chapter needs someone who doesn't exist in your world (a cast
  slot with no match, a kind of person nobody fits), an in-order storyline now moves past it instead of stopping there.
  The row says `missing_cast` and who it needed.
- **A link to another storyline is soft.** `after` pointing at a scene in a different pack that can never happen
  (you took the other Homecoming date) no longer closes this storyline too. Inside one pack it's still a real branch.
- **Year-end says why.** When a scene's last school year ends while it's still waiting, it's logged as missed with what
  it was waiting on (`chapter_order`: behind another chapter; `never_picked`: it was ready but never chosen), instead of
  a bare "year passed".

## Play a storyline start to finish

Me > Story schedule > open a storyline > **Play it start to finish** (or tap a chapter > **Play from here**). Every
chapter comes one after another, right now, so you can see what's actually in it: you read the scene, choose, see what
happens (and the next beat if it keeps going), then the next chapter. Each chapter stays on screen as a running script
(the scene, what you chose, what happened). It plays on a copy of your story (your family and people, everything that's
happened), so nothing here counts in your real story, and the dates are skipped so you can read straight through.
Your choices still steer it: a chapter on another branch is skipped and says exactly which choice leads to it ("only
if you chose “Go with Maya” in “The ask”"), and a chapter about someone nobody in your story fits says so. Play it again
to choose differently. Scenes you've added to a storyline play in it, right where they were wired in.

## Add a scene right here

From any chapter (in the player, **Add a scene after this one**; on the Story schedule, tap a chapter > **Add a scene
after this**), say what happens there (or leave it empty and ChatGPT fills the gap), and **Make my ChatGPT prompt**
builds a prompt for that one spot: the storyline's script (the scenes around the spot in full if it's a long one), what
you chose when you played it, what else is going on in the story then (other storylines' scenes in the same weeks first),
your family and cast, and the facts the story can remember. ChatGPT sends back just the new scene (`--- Title [tags]`
and its lines). Paste it, **Check it** (on a copy: does it load, when does it play), **Add it**: the game puts it into the
storyline's script right after that scene, so it plays there and the story carries on after it. No wiring, no separate
file; open the storyline's script and it's there. A problem in what you pasted is reported by its own line number.

```
GET  /api/story/add/weave?pack=&after=&ask=        -> {prompt, where, pack_name, after, next}
POST /api/story/add/preview {pack, after, text}    -> the storyline with it in, played on a copy
POST /api/story/add/insert {pack, after, text}     -> puts it in the script (after "" = before the first scene)
POST /api/story/playline/start {pack, from?}       -> the first chapter (and the ones skipped on the way, with why)
POST /api/story/playline/choose {index | null}     -> what you read, chose and what happened; the next beat if any
POST /api/story/playline/next                      -> the next chapter (or done, with your path)
POST /api/story/playline/stop
```

## Add to your story

Me > Story schedule > **Add to your story** (or the API) turns "I want more of this" into scenes that fit:

1. **Say what you want more of**, or tap a suggestion (fill the quiet weeks, more sophomore and junior year, fix what
   can't happen, a new storyline about someone already in it, bigger payoffs).
2. **Make my ChatGPT prompt.** It carries your family and cast (as `cast:` lines, with who each one is in your story),
   every storyline as its scene lines and tags, the facts their choices remember, how your seven years play right now
   from your last **Run the check** (scenes per month, the quiet stretches, what can't happen and why), and the storyline
   part of the script guide. Copy it or share it straight to the ChatGPT app.
3. **Paste what ChatGPT gives you** (the whole answer; the game finds the script inside) and **Check it**. Nothing is
   saved: the game plays seven years forward on a copy with it in and shows which new scenes play and when, which ones
   won't and why, what changed for scenes you already have, the before and after count, and the month grid. If it can't
   load, you get the problems by line number and a **fix-it message** to paste back to ChatGPT.
4. **Add it to my story.** Each `=== storyline` becomes its own script. A storyline sent back with the same title
   replaces yours (that's how ChatGPT adds to one you have).

A script can also retime scenes you already have, with a `schedule:` block: one line per scene, `Same Team: Cut day
[sophomore · March · after Prom night]`; `[replace]` swaps its old after-links for the new one, `[skip]` retires it.

```
GET  /api/story/add/prompt?ask=...      -> {prompt, chars, suggestions, checked, last_check}
POST /api/story/add/preview {text}      -> {ok, errors, error_lines, fix_prompt | new, changed, played_total, before, coverage}
POST /api/dialogue/packs {text}         -> adds it
```

## Knowing who everyone is

Every person has a profile built from what's actually true in the world right now, and the game uses it everywhere.

**On their contact page: Who they are.** What you see depends on how well you know them:

| You see | When | What |
|---|---|---|
| Everyone knows | always | year and age, the teams they play on and where ("Starting striker · Guilford Girls Soccer"), clubs, job, their group, who they're dating, family at school, what they're known as |
| You know | you've spent real time together (or family) | what they're into, what they're like, who they're closest to and who they don't get along with, what's going on lately (hurt, just got cut, not speaking to someone, a game tomorrow, stressed), grades, what's next (offers, college) |
| Only people close to them know | friends who trust each other, family you get along with, or the person you're dating | what drives them, what they're working toward, who they have a thing for (if it's you, they won't say), what home is like |

The rest shows as a locked row ("3 more things you don't know yet") with what it takes to learn them. The contact list
shows a one-line glance under each name: "Sophomore · Girls Soccer · dating Theo".

**Checking on people.** When someone you know is going through something, their page offers it: *Ask how the sprained
ankle is*, *Cheer them up about getting cut*, *Check on them after the breakup*, *See if they're okay*. They take it
seriously ("doctor says a couple more weeks. thanks for asking"), and it counts for more than a random check-in.

**The game knows who's talking to whom.**
- Lines know if a guy or a girl is talking, to a guy or a girl, and whether the whole conversation (you two, or a team
  or group chat) is guys or girls. "bro" is between guys; a girls' team gets "lock in tomorrow ladies", never "boys".
- Romance knows age and family. Feelings only grow on their own between people who are into each other's gender, aren't
  family, and are the right age for each other: both in high school (or both in college) and at most two grades apart,
  or a senior and a college freshman. Your own choices are yours: if you flirt with or ask out someone older, you're into
  them, and it's up to them.
- Group names fit the group: "the Bat Girls" only for a group of girls, "the Senior Lot Crowd" only for seniors.
- Story scripts can use the same tags on texting lines: `from_guy`, `from_girl`, `to_guy`, `to_girl`, `guys`, `girls`,
  `same_year`, `older`, `younger` and `hurt` (they're injured), and mods can combine tags (`close+guys`).

## Teams: boys' and girls', five sports

Guilford has seven high school teams, each with its own coach, tryouts and schedule:

| Season | Boys | Girls |
|---|---|---|
| Fall (tryouts early Sept.) | Football (Coach Bryant), Boys Soccer (Coach Lindqvist) | Girls Soccer (Coach Mensah) |
| Winter (tryouts mid-Nov.) | Boys Basketball (Coach Okafor) | Girls Basketball (Coach DiMarco) |
| Spring (tryouts early March) | Baseball (Coach Bryant) | Softball (Coach Torres) |

- **You only see your side.** Tryouts, goals, the planner and the story creator show the teams you can play on. A coach
  only takes players from their side, and walk-ons and call-ups follow the same rule.
- **One sport a season.** Once you're on a team (or signed up for its tryouts), the other team that season drops off your
  list. Football and boys' soccer are both in the fall, so pick one. Winter and spring are open.
- **Soccer** has keepers, backs, midfielders, wingers and strikers. Box scores add up to the score (every goal has a
  scorer, most have an assist), keepers get saves and clean sheets, and game day opens Soccer Playmaker.
- **Softball** plays like baseball (same positions, at-bats, innings and ERA), and its game day opens At Bat.
- **Short-handed coaches recruit.** When a team can't field a lineup after tryouts, the coach talks athletic kids who
  aren't playing anything that season into joining. It never does this to you.
- **College** has men's and women's teams: UConn Men's Basketball and UConn Women's Basketball, UNC Men's Soccer and
  Women's Soccer, softball wherever the school has it. Recruiting and offers come from your side's program. Texas, LSU,
  Oklahoma, Florida State and Miami have no men's soccer, and Miami has no softball. Football and basketball scholarships
  are full rides at D1; soccer, baseball and softball are partial.
- **Making people:** a girl you make who plays baseball becomes a softball player (her interest, skill and position
  carry over). A coach you make can run any of the seven teams (`coach_of`: `football`, `basketball`, `basketball_girls`,
  `baseball`, `softball`, `soccer`, `soccer_girls`).
- **Older saves** are brought up to date once, the first time they load: the new teams and coaches show up with the rest
  of this year's tryouts and games, girls on boys' teams move to the girls' team for that season (keeping varsity or JV),
  a girl's baseball becomes softball, some kids pick up soccer, and a college you're already at gets its women's teams.

## Your games line up with your storylines

A storyline decides its games, so the scores, your stats and your team's record always match what it says happened:

- **A scene after a game says how it went**, and the game goes that way. That's a scene in a storyline played in order
  whose words take a result for granted ("What a win!", "We lost 21-14", "that loss"), or one tagged `[if we won]`,
  `[if we lost]`, `[if I played great]`, `[if I won it]` (in an outline: a line ending `| if we won`). When it's the
  storyline's next chapter, it waits for your next game (in that sport, if the storyline's about one), the game is played
  to match (a real game: a score, your stat line, the standings, the Sports tab), and the scene comes right after it.
  Words about another season, the future or a maybe ("last year we lost", "we need a win") don't count. If two
  storylines want opposite results from the same game, neither gets it and the game decides.
- **Lines can say the real thing**: `{last_game}` (the 24-21 win over Branford), `{last_score}`, `{last_opp}`,
  `{my_line}` (6 catches for 98 yards and a touchdown), `{big_play}`, `{team_record}`, `{my_season}`.
- **Or let the real game decide**: two scenes side by side, one `[if we won]` and the next `[if we lost]` (outline lines
  ending `| if we won` and `| if we lost`). Whichever matches the game plays; the other never does. Nothing's forced.
  `[if I played badly]`, `[if I started]`, `[if I was benched]` and `[if rivalry game]` wait for a game that went that
  way too.
- **The big moment.** Game day's **Take over late. Play the big moment yourself** (and a storyline choice with
  `| play football` on a game day) still plays your sport's mini game, and how it goes is in your box score as the play
  (the touchdown, the homer, the late three; or the stop, the strikeout) and in the write-up. It can swing a close game,
  but a storyline that calls the game always wins: miss the big moment in a game the storyline says you won, and the
  write-up says the team held on.
- **ChatGPT knows.** The outline prompt has it say how each game went (`| if we won`), and the guide teaches the tags and
  words. For a storyline you already have: Story Studio → Storylines → open it → **Match it to your real games: copy the
  prompt** tags the scenes that take a result for granted and swaps made-up scores for the real words; paste its answer
  with **Paste a script** (the old version stays under Older versions). You don't have to: scenes that clearly say how a
  game went already work.

## The Sports tab and the league

Its own tab (Story · Scene · **Sports** · Phone · Home · Me), one view per team you're on, in four parts.

**The league is real now.** Every school in the conference (the 14 SCC schools Guilford plays; your college's conference
later) is a team that lasts the season: its own strength (some programs are better at a sport, and it shifts year to
year and story to story), its record, points for and against, streak, and three named stars with season stat lines. The
conference is pitched at your team's level (half your roster, half a typical team), so most seasons are a fight. Your
schedule rotates through the conference, and **Hand** is Guilford's rival (that game comes late, and it travels further
when you win it). Every week your team plays, the rest of the conference plays too (one team sits each round), so the
standings, power rankings and leaders are real.

- **Season:** the record and where it puts you ("2-2, #6 of 15 in the SCC"), the streak, the last game, the next one with
  the other team's record and the stars to watch (the rivalry game flagged). **Your playing time** in the coach's own terms:
  starters are the best players by sport rating, so you see your rating in its real parts (skill, athleticism, fitness,
  size and build, confidence), who you're ahead of or chasing for the last starting spot and by how much, the whole depth
  chart with the starting line, the coach's trust and your attendance, and your next move. Then your season line, your
  game log (rivalry games marked) and your awards.
- **League:** the standings (W-L, point difference, streak, this week's power-ranking move) and the league leaders, your
  teammates next to the other schools' stars.
- **Awards:** Player of the Week (every week, from every game in the conference: yours to win), the All-SCC race
  (everyone by impact per game, with the line that gets you named) and the team MVP race.
- **Recruiting:** who's interested and how much, the offers, and what college coaches look at.

**It feeds the Scene.** A team's prestige follows its record (a winning team's goes up, a title adds more), and prestige is
one of the things popularity is made of. A standout game, Player of the Week, an award or a title travels around school:
classmates who'd never met you get to know you and respect you a little (more if they follow the sport, more for the
rival game), which is what moves the Scene's ladder. `GET /api/phone/sports?team=`.

## The sports world: MLB, the NFL, the NBA and college, in the background

**The story starts Wednesday, Sept 1, 2010.** The Yankees are the defending champions (2009), and everything behind your
story is the real sports world from there, a day at a time. The Sports tab has three sides: **School** (above), **Pro**
(MLB, the NFL, the NBA, and soccer) and **College** (football, men's and women's basketball, baseball, men's and women's
soccer). You
don't play these; they're the world your story lives in, and storylines can use them. You never see past today: the
history pages, the titles and the what-ifs only show seasons that have happened.

### MLB

**Real history, day by day, then this world's.** The data is real from 1990 through 2025: every team-season, every
postseason series, the major awards, and every regular's season with a value in wins (an estimate in the spirit of WAR,
made from the Lahman database by `tools/build_mlb_data.py`; it reads Bonds 2001 at 12.8 and Judge 2022 at 10.7). From the
first day of the story, each real season plays out on its dates: the 2010 Yankees are 78-55 on day one, sweep the Twins,
lose the ALCS to Texas, and the Giants win it all. Standings move through the season, October reveals series a game at a
time, the leaders and your team's best players carry their real lines, and teams have the names they had then (the
Florida Marlins, the Cleveland Indians). The in-story MLB draft follows its era (40 rounds in early June in the 2010s;
20 in July from 2021), worst-to-first by last season's standings. Past 2025 (if your story gets there) it's this world's:
rosters from where everyone finished 2025, talent from each player's last three seasons, a 162-game season played series
by series, the current postseason, awards, then aging, retirements, free agency and rookies.

**What-ifs.** Twelve moves that were really on the table, each with the real story of how it fell apart:
- **The big four:** the Yankees sign Beltrán (2005), trade for Cliff Lee (July 2010), re-sign Canó (2014), sign Harper (2019)
- **Arms:** Maddux (1992), Lee in free agency (2010), the Santana trade (2008), Cole out of high school (2008)
- **Bats:** Machado (2019), keep Soto (2024), Crawford (2010), and A-Rod's Boston deal going through (2003)

Turn one on and your world's history replays from that day. Each season, the teams' wins move by what the players were
worth (and the guy who lost his job, and what the other team did instead). The playoff field is rebuilt in that year's
format, and October replays with as little change as possible. A series that really happened keeps its result unless the
new odds flip it, and a matchup that never happened is played fresh, with each team carrying how it really played that
October. Each what-if's page shows what moved, season by season the real path next to this world's, and the title odds
both ways (Cliff Lee in 2010: 16% to 27%). A what-if that's still in the story's future (Cano, Harper, Machado, Soto)
says so, and happens when the story gets there.

**On the page:**
- **My team:** your team (the Yankees unless you pick another), its record and place, where it stands in October, its
  titles (and which ones this world added or took away), its best players with their lines, the league's news (results,
  signings, retirements, prospects)
- **Standings:** both leagues by division (projections before Opening Day), and October as it happens
- **Leaders:** the live season's leaders in each league
- **What-ifs** and **History:** every season since 1990 as it went in your world, with its October and awards

**Fans.** Everyone has a team and how much they care. Guilford is split between Yankees and Red Sox country, with some Mets
fans. A title is a memory and a good week for its fans; a playoff exit stings; a rival's title stings a little. The MLB
draft in the story goes worst-to-first by last season's real (or this world's) standings.

**For storylines** (the guide and the weave prompt list these, so ChatGPT can write with them):
- `requires`:
  - season: `pro:baseball_season`, `pro:october`
  - your team: `pro:my_team_winning`, `pro:my_team_losing`, `pro:my_team_in_playoffs`, `pro:my_team_alive`,
    `pro:my_team_missed`, `pro:my_team_champs`
  - what-ifs: `pro:whatif:<id>`, e.g. `pro:whatif:harper_2019`, for a scene that only happens in a world where it went
    the other way
- placeholders: `{my_team}`, `{my_team_record}`, `{my_team_star}`, `{mlb_champ}`

`GET /api/phone/mlb`, `GET|POST /api/phone/mlb/whatif`, `GET /api/phone/mlb/year?y=`, `POST /api/phone/mlb/team`.

### The NFL, the NBA and college sports

Every game as it really happened, on its real date (`realleagues.py`, data from `tools/build_league_data.py`):
- **NFL** (every game, from nflverse) and **NBA** (every game, from ESPN via sportsdataverse): your team's record, place,
  last games and next game, the division tables, the playoffs as they happen (NBA series a game at a time), the champions
- **College football** (every FBS game; the bowls before 2023 aren't in the public data, but the title games and the
  playoff semifinals are), **men's and women's college basketball** (the power conferences, the story's colleges and the
  whole NCAA tournament, every game): your school's record, conference record and place, this week's top 25 (ours, from
  results: an Elo rating with margin of victory, not the AP poll), the playoff or the tournament round by round, the
  champions
- **College baseball** and **men's and women's college soccer** have no public game data, so they carry the real finals:
  the College World Series and the College Cups, who won, who lost, when

**Your teams.** The Giants and the Knicks to start (it's Connecticut: plenty of Patriots and Celtics fans around too), and
UConn in college, until you're at a college yourself: then it's your school, in every sport (or pick any school). On day
one UConn football opens at Michigan; that winter UConn basketball finishes ninth in the Big East and then wins eleven
straight, the conference tournament and the national title; the Giants win the Super Bowl after the 2011 season.

**Fans.** Everyone in town has an NFL team, an NBA team and how much they care about UConn. A title is a memory and a good
week for its fans; an exit stings. Your teams' playoff results and every title game are news.

### European soccer

Under **Pro → Soccer**: the **Premier League**, **La Liga**, **Serie A**, the **Bundesliga** and **Ligue 1**, every league
game on its real date (football-data.co.uk's results via the datasets/football-datasets mirror): your club's points and
W-D-L, where it sits, its last games and next one, the table by points then goal difference (2011-12: Man City over United
on goal difference, both on 89), and the champions, decided on the last day (2005-06 Serie A goes to Inter: Juventus were
stripped). The **Champions League** is its finals, every one, with your clubs' titles; the **Ballon d'Or** is its winners
(the FIFA Ballon d'Or 2010-15, and the women's from 2018). You start following Manchester United, Barcelona, Juventus,
Bayern and PSG; pick your own and their titles become memories, not just news.

**For storylines:** `pro:<league>:<condition>` with league `nfl`, `nba`, `cfb`, `mbb`, `wbb`, `cbase`, `msoc`, `wsoc` and
condition `in_season`, `my_team_winning`, `my_team_losing`, `my_team_in_postseason`, `my_team_alive`, `my_team_champs`,
`my_team_ranked` (college). Placeholders `{my_nfl_team}`, `{my_nba_team}`, `{my_college}`, `{my_nfl_record}` (and nba,
cfb, mbb, wbb), `{nfl_champ}` (and nba, cfb, mbb, wbb). European soccer: `pro:epl:` (and `laliga`, `seriea`, `bund`,
`ligue1`) with `in_season`, `my_team_winning`, `my_team_losing`, `my_team_champs`, `pro:ucl:my_team_champs`, and
`{my_club}`, `{epl_champ}`, `{ucl_champ}`, `{ballon_dor}`. `GET /api/phone/leagues`, `GET /api/phone/league?lg=`,
`POST /api/phone/league/follow`.

## Play on your phone

**The lab is your dashboard; your phone is where you play.** The phone app, *LIFE OS: Story*, runs the whole
game on the phone itself: no computer, no server, no monthly bill, and it works offline after the first visit.

**Install it (once):**
1. Open **https://zacksoffer-create.github.io/Life-OS/play/** in Safari on your iPhone (or Chrome on Android).
   The lab's **Play on Your Phone** page shows the same link as a QR code.
2. Tap **Share → Add to Home Screen**. It gets its own icon and opens full screen.
3. The first launch downloads about 12 MB (the game engine). After that it starts in a few seconds.

**Make your story right in the app:** tap **Create my story**. Seven short steps, built for your thumb:
1. **You:** name, who you're into, birthday, your color.
2. **Your look:** every option shown as a portrait.
3. **Who you are:** your type, plus sliders for personality, talent and drives.
4. **Sports:** play, maybe, or not, with position, day-one skill, height, build and jersey.
5. **Your family:** parents, how they parent, money, and a pet (dog, cat or rabbit, with name, breed and coat).
   Siblings are one tap each (older brother, older sister, twin sisters, twin brothers, your twin), and each one's
   after-high-school path can be set (say, UConn basketball).
6. **Your people:** best friend, crush, rival, teammate, coach.
7. **Ready:** look it over and start.

Problems get checked before you start, and tapping one takes you to the fix. Anything you skip gets generated. Your draft
saves on the phone as you go, so you can stop halfway. Siblings left on auto get your skin, hair and eye color
(with natural variation) when you've picked your look. **Save as a cast file** on the last step sends the whole cast to
the lab, and **Load a cast file to edit** brings one back.

**Or bring people from somewhere else:** build them in the lab (My Story → Start your story) and click **Download cast**,
or fill in the Excel worksheet, or use ChatGPT's JSON answer. Send the file to your phone (AirDrop, email, iCloud Drive)
and tap **Load a cast file or backup**. Or tap **Try a sample story**.

**Your story lives on your phone.** It saves by itself. **Me → Back up my story** saves a `.lifeos` file
(to Files, iCloud, AirDrop): the whole story in one file, meaning everyone, everything that's happened, and your storylines,
expansions and texting (and which are switched off).

**See it on a computer.** The phone's Me tab has a **See it on a computer** box with the link to the **desktop version**
(`play/LIFE-OS-desktop.zip`, published with every phone build, so it's always the same engine as the app; get it again
after updates). Unzip it, double-click **Start LIFE OS**, and on **My Story** click **Load a cast file or backup** and pick
the backup: the story opens in one step, with its storylines and texting, and whatever was open before is kept under
Saves & Worlds. (Saves & Worlds → **Open a backup or save file** does the same, with a box to open it right away or just
import it.) The whole history, every decision and the math behind it are there. Going back: Saves & Worlds →
**Download** gives a backup with your storylines in it, and the phone's **Restore** opens it. A storyline that's different
in the backup becomes the backup's version (the one it replaces is kept under **Older versions**); one that's the same is
left alone. Older desktop copies still open new backups (they read the story and skip the rest), and a desktop copy older
than the backup says so.

**How it works:** the same Python engine, compiled for the browser (Pyodide), runs in a background worker on the phone.
The phone screens talk to it exactly as they talk to the server on a computer. Saves go to the phone's own storage.
To publish an update: `python lifeos/tools/build_phone_app.py`, then commit the `docs/play/` folder (GitHub Pages serves it).

**Turning on the free hosting (one time):** on GitHub, open the repository's **Settings → Pages**, set **Source** to
*Deploy from a branch*, pick the branch with the app and the **/docs** folder, and **Save**. The link works a minute later.

### Or play over your Wi-Fi

If you'd rather keep the story on the computer (one world shared with the lab), double-click
**`Play on Phone (Windows).bat`** / **`Play on Phone (Mac).command`**, scan the QR code with your phone on the same Wi-Fi,
and keep the computer on while you play.

What's in it:
- **Story.** Where you are and what's happening right now, drawn as a scene, and what you do about it. Choices are worded like
  life ("Sit with Danny", "Take Buster to the park"), and outcomes come back in first person with what changed ("Danny +4, Energy −6").
  **Continue** goes to your next choice; **Skip ahead** lives until something happens.
- **Phone.** Your texts and contacts inside the game. Friends text you after a good hangout, the team chat lights up before games,
  your family chat has opinions, people ask you out by text, invitations arrive as messages, and you can answer or text people first.
- **Texting goes back and forth.** In a one-on-one chat you can **type anything**, or tap a suggestion (each has a little
  tone icon: 💬 ask, 😂 joke, 😏 flirt, 📅 plans, 🤝 check on them, 👋 bye). They answer like themselves and often ask you
  something back. What you type is read for what you're doing (hi, a question, a joke, a compliment, flirting, plans,
  checking on them, sorry, dry, rude, bye) and how much effort it shows; it doesn't understand every word like a person
  would. A conversation has energy: more if they like you, they're social or they're into you, less if they're stressed.
  Good messages give a little back, dry or rude ones drain it, and when it runs out they wrap it up ("gtg, ttyl"). Texting
  again right then gets you left on read. Ending it yourself on a good note helps. A typed "yeah i'm down" answers an invite.
  A day of texting one person can only move things so far, so spamming doesn't farm friendship.
- **Flirting you can read.** Every flirt, by text or in person, tells you why it went the way it did ("Landed: they were
  already into you and you'd built up to it." / "Awkward: they barely know you yet. Talk and hang out first."). It comes
  down to five things: **closeness** (do they know and like you), **interest** (are they into you), **the moment** (their
  mood, stress, how the conversation's going), **pace** (talking, joking around, a light flirt, then asking out) and
  **you** (confidence, charm, effort). Asking someone out over text gets "ask me in person 😳" when they're into you.
  Each person's contact page has **You and them**: where you are (strangers, know each other, friendly, flirty, talking
  stage, dating), your read on whether they're into you (once you know them a little), the signals behind it (texted you
  first, asked about you, laughed at your jokes, flirted back, short dry answers, left you on read, flirting in person),
  what to try next, and **How flirting works**. Flirt and ask-out choices say how risky they are ("Seems into you",
  "Risky: you barely know them").
- **Conversations hang together.** When they ask you something ("you going to the game friday?"), the suggestions answer
  that question (yes / no, what you're up to, how your day was), and a typed "yeah" counts. Bring something up (the game, a
  test, music, the weekend, food) and they answer about it; mention a test or a game and they follow up a day or two later
  ("how'd the test go??"). Someone into you answers fast, sometimes double-texts, and the chat header shows where you two
  are ("Flirty · Seems into you").
- **People are different.** Teasing, sweet stuff, being direct, making them laugh and cheesy lines each go over differently
  depending on the person's personality: everyone loves one or two and isn't into a couple. You find out by trying, and
  their contact page keeps track under **What works with them** ("Teasing: they love it", "Cheesy lines: not into it",
  "Being direct: not tried yet"). Flirt suggestions offer a style you know they love, or one you haven't tried. Teasing
  with a 😂 is teasing; the same words without it are rude.
- **Set what works on someone.** In the editor (Story Studio → People → anyone), **Flirting** has each style with
  **Loves it / It's fine / Not into it**. It starts from their personality ("their personality"); set any of it and that's
  how it goes ("set by you"), including what you'd already figured out about them. **Back to their personality** undoes
  it, and it carries into Start over like the rest of who they are.
- **It takes more for a girl to ask a guy out.** Same feelings, a guy will make the move sooner: she has to be a lot more
  into him and fairly sure he likes her back. Me → **Girls asking guys out**: Same, Harder (the default), Much harder or
  Rare. (In the lab it's the rule romance.girl_asks_guy, 0 to 3.) Asking someone out yourself works the same either way.
- **When they asked, it's a yes.** A friend who asked you along ("me and Cole are getting food. you in?"), invited you
  by text, or your group's plans for now: pick it from your choices instead of texting back and they're in. It used to go
  out as you asking them, so they could pass on their own invite.
- **Flirting goes back and forth.** A flirt that lands (or gets a laugh) isn't the end: they answer in the flavor of what
  you sent, and your next options build on it, in two styles plus playing it cool. A few good beats in a row and it goes
  somewhere: they're blushing, they want to hang out (plans made), they tell you to ask them out in person, or, late at
  night, they go to bed smiling. An awkward beat can fizzle it. Someone into you can start it too ("you looked happy
  today. it was cute"), and you can flirt back, play it cool, or let them down easy (kind, and they take it fine). Nobody
  flirts with family, and nobody's into you who couldn't be.
- **Group chats talk.** Your crew, your team and your family have conversations of their own: roasting someone's haircut,
  the night before a game, who ate the leftovers. They talk to each other, and when you open the chat the new messages
  land one at a time with typing dots. Jump in with one of a few things to say (defend them, pile on, send the pic): it
  lands differently with each of them, and sometimes the one you roasted DMs you after ("ok be honest. is it actually
  that bad").
- **Add your own texting.** Phone → Messages → **Add texting** (or Me → **Texting**): pick flirting, group chats or both,
  pick which parts (openers, how they answer, follow-ups, them flirting first, payoffs) and a style (every style, teasing /
  sarcastic, sweet, bold, funny, cheesy), say what you want ("the boys roasting each other about fantasy football"), and
  you see the size of the job before you copy anything ("ChatGPT fills in 12 flirt sections, about 36 lines, and 4 group
  chats"). The prompt is a fill-in template built from the game's own texting slots, so every header ChatGPT is handed
  has a place in the game, and it's told to keep the headers exactly as written. Paste what it writes and tap **Add it**
  (one step, no Check): every section that works goes in, and any that don't are listed under **Didn't go in** with why,
  plus **Copy a fix-it message for just these** so ChatGPT only redoes those. It's live right away and listed with your
  storylines to edit or remove. You can write them by hand too: `flirt tease:` with lines under it,
  `flirt answers bold, lands:`, `flirt first:`, `flirt payoff plans:`, and `group chat crew, weekend:` with the
  conversation (`A: ...`), what you can say (`* {B} you're gonna finish last | A +, B -, fun +`), their answers under it,
  and `dm B: ...` for someone texting you after. The guide has every block.
- **From text to in person.** When you ask someone out by text and they say "ask me in person 😳", the game plans it
  ("Asking Sophie out, next time you see them"), and they meant it: they'll say yes when you do.
- **Dating takes showing up.** Go a few days without talking to your partner and it shows: "Feeling distant: 5 days since
  you talked" on their page, "Sophie misses you" on your plate, and they text you about it.
- **Hanging out plays out.** When you pick a hangout, a date or the crew, a quick scene comes up with one choice: Danny
  dares you to jump off the dock, the diner's empty and Kira wants you to rate her placemat art, it starts pouring on the
  walk home, an inside joke is born. Each choice is a style (teasing, sweet, being direct, funny, cheesy, or play it safe),
  and how it goes depends on what that person likes, the same tastes you learn by texting. The choices show what you already
  know ("Teasing · Kira is not into it"), and the result says why ("Kira loves you being direct."). 16 scenes for friends,
  dates and the crew, never the same one twice in three weeks, at most one a day.
- **Hang out with the crew.** One choice, your two or three closest friends at once ("Hang out with Danny, Kira and Theo"):
  everyone gets closer, to you and to each other.
- **No wasted afternoons.** When you make a plan you ask first, so your friends aren't already booked. If your pick passes
  anyway, you hang out with someone else who's free ("Danny passed, so you hung out with Kira instead"); with the crew, the
  rest of the crew steps up. Other people's invites go to your texts instead of cluttering what just happened.
- **Your free time is clear.** A school day is morning, class, lunch, after school, evening, night. If you're on a team
  (or in the show) and it has practice or a game, after school is that: it isn't a choice, you just go (games on
  weekends too). Your free time is lunch and the evening, and the whole day on weekends. Each one says **Free time,
  Tonight: pick one thing**, sorted into **With friends** (the crew, hangouts, a date, lunch tables, family), **On your
  own** (homework, training, hobbies, rest, your pet) and **Go somewhere** (parties, games to watch, sign-ups); the
  drama (pranks, gossip, sneaking out) is under More options. Anything that needs you (homework before a quiz, a chore)
  has a **needs you** tag. **Texting doesn't use up your time**: text anyone, anytime, from the Phone tab, so "Message
  someone" isn't one of your choices anymore. Plans made by text fill your next free time and show at the top.
  Prefer not to pick every lunch? Turn on **Lunch on autopilot** on the Me tab (you sit with your usual table).
- **Your group.** The friends you actually spend your time with become your group on their own: **the boys**, **the
  girls** or **the crew**, from your closest friends, changing as friendships do (it's on the Me tab, with how tight you
  are and when you last hung out). In your free time it's one choice for what you'd really do: **Hop on the game with
  the boys**, **Park with the boys**, **Shoot around**, **Food run**, **Movie night at Danny's**, **Beach day** in the
  summer, **Homework on FaceTime** on school nights. Whoever's free comes (not whoever's at practice), it reads like
  what it was ("Three hours online with the boys. You lost more than you won and it didn't matter at all."), and a scene
  that fits often follows (game nights get their own: the hot mic, the last one alive, the rage quit, the little brother
  who grabs the controller). Some days they make plans themselves ("on at 8?" / "bet"): it's on your plate and first in
  your choices then. Join or skip; skipping now and then costs almost nothing, you just hear what you missed. **Zero
  maintenance:** their group chat is there to read, never needs an answer and never shows as unread.
- **Hanging out works like real life: mostly in small groups.**
  - **One on one is for people you're close to.** Someone only asks you to hang out, just the two of you, once you
    actually know each other (real friends, your partner, family, or someone who's into you), and it's rare: about one
    or two a week, not every day. People you barely know ask you along with the group instead.
  - **Small-group invites.** Some mornings a friend texts you about a few of their people: "me, Cole and Theo r getting
    food tn. u in?" Tap **i'm in** right in the thread and it's your plan (they all come), or it's the top choice in
    your free time ("Food with Danny, Cole and Theo · Danny asked you"). It's how you end up hanging out with friends
    of friends.
  - **Everyone has a schedule.** Nobody asks you while they have practice, a game or a show, or while you do. Friends
    who are busy aren't in your choices, and the With friends section says why: "Danny and Cole have practice."
  - **Groups first.** In your choices, your group and the small-group stuff come first, then one on one with people
    you're close to; one on one with people you barely know is still there, just further down.
- **Pets don't use up your time.** Feeding, walks, the park, playing, training, cuddles, treats, brushing and the bath
  (or the litter box, or the cage) are all quick taps on the Home tab, anytime. They're not in your free-time choices
  anymore. Your chores show on your plate with **Do it**; skip one and it usually still gets done (you mostly remember).
- **A mix up front.** The first choices in each section are one of each kind before a second "Sit with someone"; the rest
  are under More options.
- **More to text about.** Vent ("my day honestly sucked") and someone close has your back: your stress comes down, and you
  can thank them (once a day is support; more than that wears on people). Share good news ("i made varsity!!") and friends
  hype you up. Gossip ("did you hear about...") and some people want every detail while others aren't into it. And when
  you two just did something together (a hangout, a date, the boys, a game you won or lost), they bring it up when you
  start talking ("today was actually so fun"), once.
- **Your storylines' people text like themselves.** A pack's chat lines can belong to a kind of person (`older_sibling`,
  `crush`, `coach`, `best_friend`...): those people use their own lines first, so your brother texts like a brother and
  your coach like a coach. Every pack you made has an **Upgrade its texting** button (phone and lab) that copies a prompt
  with the pack in it: ChatGPT gives that storyline's people their own replies, questions, follow-ups, flirts by style and
  more, and the answer replaces the old pack. The prompt is also in `docs/dialogue-texting-prompt.md`.
- **Storylines play as stories.** Every pack you made plays as a storyline: its scenes come as chapters, in the order
  they're written, a few days apart (a chapter that can't happen yet waits, and the story moves on). Scene cards say where
  you are ("Big brother season · Chapter 3 of 8"), and the pack list shows what's next. Turn **Play in order** off on a
  storyline to let its scenes come up in any order. Storylines can now have scenes that keep going (a choice with `then`
  continues the scene right away, up to three decisions deep), choices that matter later (`remember` a fact, and a later
  chapter only happens on that path), and style choices (`vibe`: teasing, sweet, direct, funny, cheesy) that land or miss
  by what that person likes. **Build it out** on each storyline copies a prompt with the storyline in it: ChatGPT turns it
  into a real arc with at least 8 chapters, branches and two endings, scenes that keep going, style choices, mini games and
  its people's texting. Storyline scenes also come more often now (one every couple of days across all your storylines).
- **One big story, in episodes.** Your seven years play like a show. Each school year is a season, and every big thing
  that happens to you is an episode, numbered in the order it aired: your storylines' chapters and the game's own big
  moments (the first day, tryouts, getting asked out, the college decision). Hangouts and quizzes are the days in between.
  Scene cards say "Season 2 · Episode 6" with the storyline under it; the first episode of a year is the premiere and the
  year in review is the finale. When a storyline picks back up, its episode opens with **Previously**: what happened last
  time and what you chose. **Episode guide** (Me tab) lists every season and episode with what you chose, and what's coming
  up in each storyline. **Make it one story** (Me > Storylines) copies a prompt with all your storylines in it: ChatGPT sends
  back a **Season plan** pack that schedules every episode across your seven years (`schedule`: years, which episodes from
  other storylines come first, how long after) and adds crossover episodes that tie storylines together. A storyline's
  chapters now come at least 5 days apart (about weekly, like episodes), woven together with the others.
- **Storylines keep their people.** When a storyline is about "an older sibling" and you have more than one, it picks the
  one it's clearly about (a basketball story that says "he" and "his" gets your brother who plays basketball) and keeps
  them for every scene and every text after that. Open a storyline under Me > Storylines and **Who it's about** shows who
  it picked; change it anytime. Scripts can also name `brother`, `sister`, `older brother`, `older sister`, `younger brother`
  and `younger sister`, and the prompts tell ChatGPT to use those.
- **Scripts can add texting lines.** A script's `chat <path>:` blocks add to how people answer, what they ask back,
  follow-ups and flirt lines by style. The texting prompt asks for them, and the checker explains any mistakes.
  People can leave you on read. Contacts show how you feel about everyone and how they *seem* to feel about you (your read, not the truth).
  You only have someone's number once you've actually hung out or gotten close.
- **Home.** Your family and your pets. A pet is a real animal with needs, moods, a bond with each person and tricks to learn.
  The first time, you decide once who handles each chore (breakfast, dinner, walks, baths...): you, a sibling, your parents, or taking turns.
  After that the chores happen every day; forget yours and the pet (and your parents' group texts) let you know. The pet menu:
  cuddle, treats, feeding, brushing, walks, the park (you run into people there), play, teaching tricks. No pet? Ask your parents.
  Their answer depends on how they parent, money at home, your grades and how much they trust you.
- **Me.** Your stats, grades, teams, the seven-year timeline, your focus and when the story should stop to ask you.

## The Scene tab

Your school, live: its own tab (Story · **Scene** · Phone · Home · Me), in three parts: the **Ladder**, the **Crowd** and
the **Talk**.

**The Ladder** is built on the game's own popularity, recomputed every week from how everyone sees everyone (how many
people know you, how much they like and respect you and how popular *they* are, your teams' and groups' prestige, your
reputation). Every week the game takes a snapshot of everyone's rank, so the ladder can show movement.

- **You:** your rank at school ("#3 of 56", "Everybody knows you"), in your grade, this week's move (▲/▼), your rank over
  the whole story as a line, and who's next up the ladder.
- **What your standing is made of:** the same ingredients the game counts, each as a bar next to the best at school
  ("16 of 55 people at school know who you are", "6 like you, 3 don't", "Popular people like you: ...", "On Guilford
  Football", what people say about you), and **your next move**: the weakest one, in plain words.
- **Your week:** the things that happened to you this week that people would see (games, tryouts, parties, fights, your
  storyline scenes), not your quizzes or your pet.
- **Your storylines' people:** everyone your storylines are about (their cast slots), with their rank and movement.
- **Who's moving:** the biggest risers and fallers this week, each with the thing that moved them, pointing the right
  way: good news for a riser ("led Guilford Girls Soccer: 1 goal, 1 assist"), bad news for a faller ("tried to sit with
  Zoe and the table froze them out").
- **Superlatives:** the yearbook, live: Most Popular, Best Athlete, Biggest Brain, Life of the Party, Nicest Person,
  Drama Magnet, Most Likely to Succeed and Cutest Couple, with where you'd place.
- **The rankings:** everyone, for the whole school, your grade or any grade, with movement, what they're known for, and
  how they connect to you (friend, family, crush, dating, rival, your story). Tap anyone: their rank and what's
  happened lately, and a move: ask a friend to introduce you (if you barely know them and a friend does), make plans,
  text them, or read about them.

The **Crowd** is the groups and people you could meet; the **Talk** is what people are saying, who's fighting and
who's together (below). `GET /api/phone/ladder?scope=school|grade|9..12`.

**The Crowd and the Talk** (what used to be Phone → Scene; that link still lands here):
- **The groups:** every friend group at your school, the ones that formed on their own from who's actually friends with
  who (the Court Crew, the Honor Roll, the In-Crowd, the Theater Kids...). Each shows its people, its vibe, how popular
  it is, and how many of your friends are in it. Tap one to see everyone in it.
- **Getting in:** if a friend of yours is in a group, that's your way in: **Hang out with Danny** plans it for your
  next free time. Get close to the rest, and the next time the groups shift, you're in. Groups change on their own as
  friendships do.
- **People you could meet:** friends of your friends you don't know yet ("friends with Danny and Cole"). **Ask Danny**
  and they introduce you. It's free like texting, one a day, and how it goes depends on you, them, and how close your
  friend is with them. If it goes well you swap numbers.
- **Who's together:** every couple at school (new ones marked), and who just broke up.
- **Most popular:** the top six, and where you are among them.

## Drama and gossip

Rumors spread through the school on their own: who got rejected, who kissed who at a party, who got roasted at lunch.
Now you're in it.

- **Gossip finds you.** Most days a friend texts you the juiciest thing going around that you haven't heard ("ok you
  can't say anything but..."). **Phone → Scene → What people are saying** lists everything you've heard: who told you,
  and how far it's spread (just a few people, your grade's talking, half the school, everyone).
- **What you do with it** (free, once per rumor):
  - about someone else: **Warn them** (they trust you more), **Pass it on** (it spreads, you get the gossip rep, and
    they might hear it came from you), or **Keep it to yourself**;
  - about you: **Set the record straight** (works better if it's not true), **Own it**, or **Who started it?**
- **Drama comes to you** as story moments, at most one every few days:
  - **Two of your friends fall out** (over a group chat screenshot, someone's ex, a party invite...) and both want you
    on their side: pick one, stay out of it, or get them in a room together (it can fix it, or make it worse). Scene
    shows who's still not speaking.
  - **Someone's into your partner** (or your partner's into someone): ask them, warn the other person off, or let it
    go. Let it go when it's real, and you might hear about it later.
  - **Your crush gets with someone else:** be happy for them, tell them how you feel anyway (it can work, and it can
    blow up), or move on.
  - **A friend goes cold on you:** apologize, give it time, or write them off. Give it time, and sometimes they're the
    one who reaches out: "hey. can we talk?"
- **Parties happen most weekends now.** Somebody popular has people over most Fridays and Saturdays; if you're friends
  with the host or a friend of yours is going, you get a text that morning, and the party is one of your choices that
  night.
- Writers: the scenes and lines are in `backend/data/drama.json`.

## Big nights (parties and dances)

Going to a party, throwing one, or going to Homecoming, the Snow Ball or prom isn't one tap anymore. The night plays out as
four short scenes on the Story tab ("Mike's party · 2 of 4"), built around who actually showed up:

- **The opening:** walking in (find your friend, work the room and meet people, go looking for your crush, people-watch),
  hosting your own (play host, let your friend run the door, guard the furniture), or getting ready for a dance (photos
  with your date and your family, or the whole group crammed into one room).
- **Two things in the middle**, picked from who's there:
  - **Who do you end up with?** your crush, your partner or date, your friend, your rival, or someone new;
  - **Cups on the table** (you play cup pong; beer pong in college);
  - **Your crush alone on the porch** (talk, and maybe kiss, and maybe it turns into dating);
  - **Your rival** looking for trouble (laugh it off, get in their face, walk away);
  - **Two people about to fight** (step in, film it, stay out of it);
  - **A secret:** someone pulls you into the hallway with a real crush ("Jordan has a thing for you. Like, a real
    thing."); keep it, spread it, or dig;
  - **Your partner** talking to someone else a little too long (join them, trust it, pull them aside).
  - At a dance it's always **the dance-off** (you play it: tap on the beat), and with a date or your crush there,
    **the slow song**.
- **The end of the night:** the after-party (sometimes the kitchen light is on when you sneak in), a ride home with your
  friend, walking your crush or your date home. If the cops show up, that's how it ends: run, act normal, or help the host
  hide everything.
- **It does real things:** people you meet get your number, friendships and crushes move, a great moment can become a
  kiss and a kiss can become dating (and a rumor), a bust or a missed curfew means your parents find out.
- **The recap:** "Your night: stuck with Danny, won at cups, laughed off Cole, and hit the after-party." It's saved as a
  memory, and the night is one episode in your episode guide.
- Skipping ahead? Your character plays the night for you.
- Writers: every scene, choice and line is in `backend/data/nights.json`.

## Storylines about one specific person (cast slots)

A storyline can be about one exact person: your older brother, the senior basketball star, not "an older brother or
sister" (which could land on one of your twin sisters). That's a **cast slot**.

- **In a pack:** a `cast` section names the person (`"lead_brother": {"who": "older_brother", "sport": "basketball",
  "grade_offset": 3}`), and its scenes say `"who": "cast:lead_brother"`. The pack guide (and the ChatGPT prompts) explain
  every field: `who`, `sport`, `grade_offset`, `bind` (`start` or `first_scene`), `bond` (start at least this close) and
  `floor` (stay at least this close, whatever you choose).
- **Bound once, kept forever:** the slot is bound to one real person already in your story (never a new or changed one)
  and stays them through graduation, college, all of it. Remembered facts keep pointing at them.
- **Shared:** every pack that uses the same slot name gets the same person, so two storylines about your brother are about
  the same brother.
- **Nobody fits? Nothing happens.** If your story has no older brother who plays basketball, those scenes just don't
  come up. It never swaps in someone else.
- **Missed a season?** A chapter whose school years are over counts as skipped, so the rest of the storyline (the
  college years) still comes.
- **Lock a pack you already have:** on the storyline's card (Me → Story Studio → Storylines), **Lock its older brother or sister scenes onto
  one person**: pick **Your older brother**, the sport, and **Inseparable** if they start close and stay close. Every
  scene that said `older_sibling` now says `cast:older_brother`; names, text, choices and remembered facts don't change.
  Lock a second pack the same way and it's the same person ("Same person in Friday Nights").
- **See or change who it is:** the card shows the slot and who it's bound to; pick someone else who fits if you want.
- **On a computer:** `python lifeos/tools/pack_cast.py pack.json --slot lead_brother --who older_brother --sport basketball
  --grade-offset 3 --bond familiarity=95,affection=75,trust=75 --floor affection=55,trust=55` rewrites pack files the
  same way (checked by the game's own checker). `python lifeos/tools/cast_playthrough.py [packs...]` plays a seeded story
  (you a freshman, twin sisters in 10th, a senior brother) into college and prints who every scene was about.

## The menus: Story Studio and Texting

Everything you put into the game has two homes, both on the **Me** tab under **Make it yours**:

- **Story Studio**, the groundwork for your stories, in three tabs: **People** (add someone, edit yourself or anyone),
  **Storylines** (Write more, Paste a script, every storyline with its scenes, expansions and script; how it works and
  the season plan prompt fold away under the list) and **Roles** (what your storylines need, and who fills it; the tab
  shows how many nobody fits). **Start over** is at the bottom, since all of this comes along.
- **Texting**: how many flirt lines, group chats and text lines you've added, **Add texting** (pick what, copy the
  ChatGPT prompt, paste or upload what it writes, check, add) and **What you've added** (each pack, to turn on and off,
  edit or remove). Texting you add lives here, not in your storylines.

The rest of the Me tab (your focus, classes, pacing, when the story stops, your story file and backups) is where it was.

## The editor (change anyone, anything)

For setting your world up exactly how you want it, or fixing something later. It's **on when a story starts**, and
The **Editor** switch on the Me tab turns it off (and back on whenever you want).

- **Where:** Me → **Story Studio** → **People** (Add someone, Edit me, everyone in your world); the Story tab shows **Set
  your world up** for the first week; and every contact page gets an **Edit** button while it's on.
- **Everyone list:** search anyone by name, or filter to your people, your family, your grade, or everyone in the world.
- **A person:** everything the story builder sets, any time in the story: name and bio; **who they are** (gender,
  pronouns, who they're into, birthday, type); look; **body and sports** (height, build, jersey number, a position sport by
  sport); personality (all ten traits), talents, what drives them, skills, interests; **after high school** (let it play
  out, a college, a college to play a sport, or work); and how they're doing right now (mood, energy, social, fun, stress,
  popularity, GPA, money). Change as much as you want, then **Save changes** (or **Undo**). Works on you too. Changing who
  someone's into takes effect right away: a crush that no longer fits goes (dating stays until you change it). A new
  birthday keeps them in their own class.
- **Add someone:** at the top of the editor. A new kid at school (a grade), a sibling, or a teacher or coach; who they are
  to you (a friend, a crush, a rival, dating...); their type. Then you're on their page to set everything else.
- **Any two people:** **You and Danny** on a person's page, or tap anyone in their people list, or **Someone else…** to
  pick any pair. Set both sides separately (how Danny feels about you, how you feel about Danny): closeness, attraction,
  trust, respect, rivalry, how well they know each other. Or one tap: strangers, friends, close friends, best friends,
  one-way crush either way, like each other, dating, exes, rivals, can't stand each other, looks up to.
- **Dating is real:** setting two people to dating ends whoever they were with before, and setting them to anything else
  ends it between them. Attraction past 55 is a crush (and they're into that person's gender from then on).
- **Quiet:** edits don't send texts, make news or fill your feed. Labels (friend, best friend, rival) and crushes just
  update to match. Each save is one small entry in the lab's History, so you can see what was changed.
- Everything is checked before anything changes: if one value is off, nothing is saved and it tells you which.

### Start over with your groundwork

Playing is how you find out who people should be, so what you set up about them carries into a replay. **Me → Start over
(keep my changes)** goes back to the first day in the same town with the same people (a story is built from your setup,
and the same setup builds the same town), then puts back your **groundwork**:

- **Who people are:** anything you changed in the editor or the lab about who someone is: name, bio, look, gender,
  pronouns, who they're into, birthday, type, height and build, positions, jersey, after high school, personality,
  talents, what drives them, interests, what works when you flirt with them.
- **People you added** (Add someone, or Add someone who fits), made again the same way.
- **Relationships you set** in the editor (Danny and Cole: best friends).
- **Who your storylines are about**, when you picked: a storyline person you chose, or the sibling a storyline uses. Your
  pick stays your pick: on a day they don't fit, the storyline uses someone else that day and goes back to them.

Where things stood in the run doesn't come back: mood, energy, grades, money, popularity, and skills grown by practice
start fresh. The sheet lists everything that comes along; tap × to leave something out (it stays as it is in that run), or
pick **Just my setup** to start clean. **Make a new story** (change the setup first) has a **Bring my changes from this
run** box on its last step: anyone who's in the new setup gets them. Groundwork is saved with the story, so backups carry
it between the phone and the desktop.

### Roles: what your storylines need

**Me → Story Studio → Roles** lists everything your storylines that
are on need from your story, each role once with every storyline that uses it and how many scenes:

- **Storyline people** a storyline names (`cast: kayla = older sister, soccer`, `cast: jordan = friend of kayla`).
- **People in your life** its scenes are about (your older sister, a friend, your girlfriend or boyfriend, your rival).
- **Things about you** it needs (you're dating someone, your family has a pet, you're on a team, you have a sibling).

Each says who fills it (your pick, the game's pick, or who it is right now), or **Nobody fits** (those scenes wait).
When nobody fits, it shows who's **close** and what they're missing ("Ally: doesn't play soccer", "Nico: is your
brother, older"), with a one-tap fix where there is one (**Make Ally play soccer**, **Make you friends**, **Start
dating**) or **Edit** to change them yourself, and **Add someone who fits**. A role that's about someone in another
role's life (a friend of Kayla's) waits for that one first. Pick one person for a role and every storyline with it uses
them. The Studio's Roles tab (and its tile on the Me tab) says how many roles nobody fits. Everything you pick, fix or add here is groundwork: it comes
back when you start over.

**Nobody fits?** A storyline person nobody in your story fits (an older sister who plays soccer, a friend of Kayla's)
gets an **Add someone who fits** button in the storyline's **Who it's about**: someone is made to fit (grade, gender,
sport, who they are to you or to Kayla) and picked for it, then they're editable like anyone, and they come along when you
start over. (A younger sibling while you're a freshman, an older one past high school, or a coach can't be made this way:
add them in your setup.)

## Plan your characters first

Open **My Story → Start your story**. The first step has a **Want to plan it first?** panel:
- **Excel worksheet**: one column per person, every field explained, dropdowns for every choice, a Reference tab with every type,
  trait, position, college and relationship. Fill in what you know; blanks are generated. Load the filled file with **Load a cast file**.
- **Copy the ChatGPT prompt**: paste it into ChatGPT or Claude and it interviews you about each person, explains the numbers, and gives back
  a cast file. Save its JSON answer as a `.json` or `.txt` file and load it the same way.
- Copies are also in `docs/character-worksheet.xlsx` and `docs/character-worksheet-guide.md`.

## Classes, quizzes and mini games

**Classes:** every school year you get a real schedule: English, math, science, history, a language, PE, and an elective
that follows your interests. Strong students get honors and AP versions (Honors Geometry, AP U.S. History, AP Calculus AB...),
and every class has a teacher. **Me → Classes** shows each class's grade, your GPA and the next quiz or test.

**Quizzes and tests you take yourself:**
- On a quiz day (every two weeks, in one of your classes) and on midterms and finals (all your classes), a moment asks:
  **Take it yourself** or **Let it ride**.
- Take it and you get a timed quiz: 15 seconds a question, questions from that class's subject and your grade level.
- Math is generated by course (Algebra I through Calculus), so it never repeats and the answers are always right.
- Your score counts: the test grade blends your answers (55%) with your character's preparation (45%: studying, academic
  skill, mood, stress), and the class's grade remembers how you did.

**Class games (most school days):** a teacher throws something quick at the class, and it shows up before school as a
card like "Second period · Chemistry: Fill it to the line". Three choices: **go for it** (you play it, a few seconds),
**let the classmate next to you take it**, or **sit it out**. The choice you play has a green **Play** tag.
- The games, all built into the phone:
  - **Hold it**: press and hold, the level rises (faster the longer you hold), let go on the line. It's a beaker in chem,
    one brushstroke in art, a power throw in gym, a held note in band.
  - **Stop it**: a needle swings back and forth; tap to stop it in the zone. It's a real pendulum in physics (stop it at the
    bottom), the beat in band, jumping in on the rope in gym.
  - **Quick math**: five problems, three answers, a few seconds each. Making change in economics, counting atoms in chemistry.
  - **Flash**: squares light up in a pattern; tap it back. Ear training in band, memory span in psychology.
  - **Odd one out**: find the typo in English, the missing accent in Spanish, the mutation in a strand of DNA, the shade
    that's off in art.
  - **In order**: tap the cards in order. Events oldest first in history (with the years shown after), elements by atomic
    number, the planets, the number line, binary, the rainbow, tempos, ABC order with words that all start the same.
  - **Quick hands**: wait for it, then tap. Catch the falling ruler in physics (it tells you how many centimeters it fell),
    first hand up in history, a reaction test in psychology. Jump early and it's a miss.
  - **Lightning round**: three trivia questions from that class, ten seconds each.
- Three tries (or rounds) each, a little harder as you go. Each one gets a call right away ("Perfect!", "A bit over",
  "Too early!"), and the end screen gives your percent. Great is 80%+, good 50%+, like every mini game.
- Difficulty goes up with your grade (college is the hardest). Your academics and talent widen the window a little.
- What it does: a great round is a better mood, less stress, a bit of academics, and the classmate who watched likes you a
  little more. A miss is a laugh (fun goes up). Going for it counts toward that class's grade (a nudge, up to +3 or -2),
  and **Me → Classes** shows your class games won per class.
- Quiz and test days stay quizzes. Skipping ahead lets your character decide, so a week skip doesn't stop for these.
- Don't want them? **Me → Class challenges** turns them off.
- Writers: the setups (what each teacher says, how it lands) are in `backend/data/class_games.json`, and the order and
  odd-one-out cards are in its `banks`. Story scripts can use the quick games in any scene too (`hold`, `sweep`,
  `mathdash`, `flash`, `oddone`, `lineup`, `reflex`).

**Mini games:** short rounds whose results feed the story.
- **Free play:** in free time, the Story tab shows **Or play something**: pickup soccer (penalty kicks or an 11 v 11 match), shooting around in the driveway,
  running the offense at the park (Playmaker), running the option at practice (Option Arcade), hitting at the batting cages
  (At Bat), batting practice (Swing Lab), and on
  weekends a round of golf (Fairway) and cup pong in a friend's basement (beer pong at a party once you're in college).
  The first round each day counts as practice (a small skill gain, plus fun), scaled by how you did.
- **Game day:** **Take over late. Play the big moment yourself.** plays your sport's game. A great round adds +7 to your
  game performance, a good one +3, a miss -2. It appears once that sport's game is ready.
- **Scenes:** a story script can put a game in a scene (`play soccer`, with `great:` / `good:` / `miss:` outcomes).
- **Soccer Playmaker** (soccer, 11 v 11) is soccer's game-day game: whoever has the ball is you. Drag to dribble,
  flick toward a teammate to pass (it leads his run), flick at the goal to shoot, hold still to look up while it slows
  down and your forwards run in behind, tap to fake. Game day is Clutch: three attacks against a tougher defense, and
  two goals is a great round, one a good one. Free play opens its home screen (Match, Clutch, Practice).
- **Penalty kicks** (soccer) stays as its own free play: swipe from the ball toward the goal; a faster swipe hits harder
  and higher, and curving your swipe bends it. The keeper reads you more often at higher difficulty, and your
  character's skill steadies your aim.
- **Option Arcade** (football) is football played by hand. The option: hold GIVE to snap and give it to the fullback,
  let go to pull it, read the next man and PITCH or keep. The jet sweep. The passing game: pull back to aim and let go to
  throw (or flick), against Cover 1, 2, 3 and the blitz, and scramble when it breaks down. Then steer the runner: swipe to juke,
  spin, hurdle, tap to truck. Game day is first and goal from the 10 with the whole playbook, four downs; a touchdown is
  a great round.
- **The games from `games/`** (Basketball Playground, Fairway, Pong Night, At Bat, Swing Lab, Option Arcade, Soccer Playmaker) run inside the app with
  their mechanics untouched. Each opens to its own home screen in free play; on game day basketball, baseball, softball and soccer open
  straight into a short clutch round. Edit them in `games/src/`, then run `python lifeos/tools/sync_games.py` and rebuild.
- **Swing Lab** is the batting prototype: a bigger, brighter, slower ball, a swipe through an invisible contact plane,
  fastball / changeup / curveball told apart only by how they move, a training mode, and two cameras to compare. Its
  stats sheet tracks whether you can follow the ball, time the swipe, and get better with practice.

**Add a game:** every game is one standalone HTML file in `frontend/public/minigames/`, so it can live in Google Drive
too. Paste in `lifeos-bridge.js`, call `LifeOS.finish({score, max})` when the round ends, register it in
`backend/data/minigames.json`, and rebuild. The full contract is in `frontend/public/minigames/README.md`. Paper toss
is registered as "coming" and appears once its file lands.

## Story scripts (with ChatGPT, Claude, or by hand)

Everything you add to the story (storylines, one-off scenes, texts, reply buttons, texting lines, story-feed lines,
trivia) is a **story script**: plain text, like a screenplay. The game reads it and checks every line; what it can fix
(a typo, a tag it doesn't know, a line that's too long, a fact nothing sets) it fixes, and tells you what it changed by
line number. It only refuses a paste with nothing usable left in it. The game ships with none: you write them.

```
=== Same Team
cast: bro = older brother, plays basketball, 3 years older, close
when: freshman-junior

--- The tryout list  [freshman · November · weekday]
The list goes up outside the gym. {bro} is already there.
bro: You're actually trying out? Coach'll eat you alive.
* "Watch me."               | confidence +, bro respect +
    bro: ...Alright. Don't embarrass me.
* "Help me get ready?"      | bro affection ++, basketball +
    bro: Driveway. Six a.m. Don't be late.
    remember bro_trains_you
* Shrug.                    | bro affection -

--- Six a.m.  [next day · if bro_trains_you]
bro: You're late. {Again.|Shocker.|Unbelievable.}
* Run the drill             | play basketball
    great: You hit nine straight. | bro respect ++
    good: Not bad.               | bro respect +
    miss: You airball the last one.
```

- `=== Title` starts a storyline; its scenes play in the order written, each waiting for the one before (tags hold a
  scene to its season). `order: any` lets them come in any order. `cast:` names a specific person who stays the same
  person for the whole story, across storylines.
- `--- Title [tags]` starts a scene. Tags: school year, month or date, weekday/weekend, `after <scene>`, `next day` /
  `a week later`, `if <fact>`, feelings (`if bro trust 40+`), stats, how big it is (`small`, `big`, `finale`).
- `Name: line` is someone talking; the first person who talks is who the scene is about. `{a|b}` gives versions so a
  line doesn't repeat word for word.
- `* choice | effects`: effects in plain words (`mood +`, `bro affection ++`, `remember made_jv`, `play basketball`,
  `60% +athletic`, `vibe funny`). Indent under a choice for what happens: lines, outcomes (`great:` / `good:` / `miss:`
  for a mini game, `yes:` / `no:` for a roll), or more `*` choices (the scene keeps going, up to five beats deep).
- Blocks for the game's pools: `texts <pool>:`, `replies <set>:`, `chat <path>:`, `narration <key>:`, `mods ...:`,
  `trivia <subject>:`, `choices <moment>:`, and `schedule:` to retime any scene.

**On the phone:** Me → **Story Studio** → **Storylines** → **Write more**. A storyline is built in two steps, so ChatGPT never has to fit a
whole storyline into one reply and never has to get the timing right:

1. **Plan it.** Say what you want ("Mike and me on the same team, freshman year", or tap an idea), pick how big (6 to 8
   scenes, 12 to 18, or 30 to 45 through the whole year), and copy the outline prompt (about 3,000 characters). ChatGPT
   sends back an **outline**: one line per scene, `3. Tryouts | November · big | You both try out.`, with branches like
   `| only if you picked "Say sorry" in 5`. Paste it (or upload the file) and **Check it**: you see every scene, its
   time and its branch before anything is written. **Make it** saves the storyline (nothing plays yet).
2. **Write the scenes.** Pick how many per prompt (1, 3 or 6; 3 is the default, since ChatGPT cuts long replies short)
   and copy the prompt for the next ones. It holds only what ChatGPT needs for those scenes: the outline lines, the scene
   right before them, which choices the branches need (and, for a scene that follows a choice, that choice in the words
   the earlier scene actually used), and the short version of the guide. Paste what comes back and **Add these scenes**;
   the bar shows how many are written (5 of 8). Repeat until it's done. A scene written again replaces the old one.
   The prompt ends with a **template to fill in**: each scene's exact `--- 4. Title` line, then the shape every scene has
   (setup, the back-and-forth, the question, then 2 or 3 choices with what happens after each). Template lines ChatGPT
   leaves unfilled (`<choice 3>`) just come out.

**Working on several at once.** The storylines you're writing sit side by side at the top of the screen, each with how
far along it is ("3/12 written", "2 to fix"): tap one to switch to it, no closing and reopening. After you add a batch, the
screen scrolls back up to the next prompt, and **Next storyline** takes you to the next one that still has scenes to
write. Scenes per prompt is remembered. Write more on its own also lists them under **Or keep writing one of yours**. The
title and the X stay put at the top (below the status bar) however far down you scroll.

**Every scene asks you something, or it doesn't go in.** A storyline scene ends on a question with 2 to 4 choices, so
you always get to decide how it goes before the next one comes. A scene that comes in with no choices ("it never asks you
anything") can't be added, wherever it comes from: a Write more batch, Paste a script, adding a scene right
where it goes, or Fix or change it. It's listed under **Didn't go in** with why, everything else in the paste goes in, a
scene you were rewriting keeps the version it had, and the fix-it message (and the next prompt) asks for it again.
A scene with only one choice goes in but is flagged ("give it 2 to 4"). Those, and scenes already in from before this
rule, show up under **Fix or change it** and on the write screen as needing a fix; a
finished storyline has **Check its scenes**. A storyline whose scenes can't come in your story as it stands says so on its
chip ("done · 2 can't come"); Read it says why.

**Fix or change a storyline you already have.** Story Studio → Storylines → open one → **Fix or change it**. Nothing
about writing new scenes changes; this is for what's already in:

1. **What's broken**: every scene that never asks you anything, gives only one choice, or has a choice with nothing after
   it (tap one to see it as it is). **Copy the fix-it prompt** gives ChatGPT just those scenes, as they are now, with
   what's wrong with each.
2. **Or change something**: say it in your own words ("make Danny any friend instead of one set person", "move it to
   junior year", "make Nicole nicer in scene 4") and **Copy the change prompt**. ChatGPT gets the storyline as it is and
   sends back only the cast lines and scenes that change (and fixes anything broken on the way), so a long storyline
   never gets cut off.
3. **Paste ChatGPT's reply** and **Put it in**: each scene replaces the one with the same number (or title) in place,
   `cast:` and `years:` lines replace theirs, and everything else stays as it was. A scene that still can't go in stays
   as it was and says why. You see what went in and what's still broken, with a fix-it message for just what's left.
   **Undo my last paste** puts back the storyline from before.
4. **Who's in it**: each cast line, tagged **One person** or **A role**. **Change** switches it right there, no ChatGPT:
   a name makes it that one person; a role (friend, teammate, classmate, ex, coach, a brother or sister...) lets the game
   pick whoever fits in your story and keep them. Their lines don't change.

**Every choice keeps what happens after it.** ChatGPT is asked for choices with no indenting: `* ` starts a choice and
the lines after it, down to the next `* `, are what happens when you pick it; `** ` is a choice inside the choice above it;
`either way:` starts what plays whichever you picked. The old indented way works too, and so do the ways ChatGPT writes
them anyway: outcomes flush left under each choice, `Choice 1:` / `Option A:` / `A)` lines, `Outcome:` labels, effects in
parentheses or after an arrow (`(+Nicole affection)`). A reply that got **cut off** (its code block never closed, or its
last scene stops right after a choice or before its choices) doesn't save half a scene: that scene stays out and the next
prompt asks for it again. Scenes that went in with **missing pieces** (a choice with nothing after it, or no choice like the
one a later scene follows, or only one choice; a scene with no choices doesn't go in at all) are listed under **Went in, but missing pieces**, and **Copy a fix-it message for ChatGPT**
asks for just those scenes, whole.

The game owns the order, the timing and the branches, not ChatGPT: scenes go in outline order whatever order they're
pasted in; a scene with a month or holiday gets it, and the blank ones are spaced out between them through the school
year; a branch becomes a fact the right choice remembers. Whatever tags ChatGPT puts on a scene are ignored (except
`big` and `with`). Scenes not written yet just don't play, so you can play the first half while the rest gets written.

**Nothing gets rejected for something fixable.** A typo (`afection`, `Thanksgivng`, `dany:`), an effect the game doesn't
have, a line that's too long, a fifth choice, an `if` on a fact nothing sets: each is fixed or dropped, and the notes say
what changed ("scene 4 (Turkey Day): 'afection' read as 'affection'"). Only a paste with no storyline, scene or lines in
it comes back.

**Read it** shows the storyline in the order it'll play, each scene with its date, plus the outline's scenes that aren't
written yet ("6. Making Up · spaced out · only if you picked "Say sorry" in 5"). **Write the next scenes** on a
storyline's row picks up where you left off. **Add an expansion**, **Edit the script**, **Play now** and **Make it one
story** work as before, and **Paste a script** still takes a whole script in one go (fixed the same way, with notes).

**Nothing you add can wipe out what you have.** An expansion is always its own piece under its storyline, even when
ChatGPT reuses the storyline's name or forgets the `expands:` line (it becomes "<Storyline>: more"). A paste with the same
name as a storyline you have replaces it only when it's a newer version of it (it still has every scene the old one had,
or it's a new season plan); anything else is added alongside it ("... (2)") with a note. And every storyline that gets
replaced, edited or removed keeps its last few versions: Me → Story Studio → Storylines → **Older versions** → **Restore**.

**Updates arrive on their own.** The site publishes `version.json` (the newest engine's id) with every build, and the
app checks it whenever it opens and whenever you come back to it. Opened on an old copy, it saves and updates right
away; if it was already open (say you just came back from ChatGPT with scenes to paste), a banner says *A newer version
of LIFE OS is out* and waits for you to tap **Update**, so it never restarts in the middle of something. The bottom of
Storylines says *Engine <id> · the newest* (or *a newer one is out*, with an Update button). The page, the engine and
its worker are always checked with the server first (past the browser's own 10-minute copy), and the saved copy is
only for when you're offline.

**Timing, by hand or with ChatGPT.** In **Read it**, *When it happens* shows each storyline's (and expansion's)
timing (for an outlined storyline, changing it rewrites the outline's `years:` and its lines); **Change** it to pick its school years (and seasons), and **Spread them out** to space its scenes evenly across
that time, in order. Every scene moves into those years: tick *Keep each scene's own month* to leave Tryouts in
November and spread the rest around it, or untick it and the spread decides every month. Holidays and school days keep
their day. Tap any scene's date to move just that scene to a year and month. Everything you change is written into the
script (`when: freshman · spread`, `--- Tryouts [freshman · November]`), so what you read is what plays. In a script,
a scene's own year or month always wins over its storyline's.

**Make it one story** still works across everything: ChatGPT gets every storyline (expansions included) with its cast
lines and scene lines, and sends back a season plan. One line can move a whole storyline (`Danny [freshman · spread]`)
or a single scene (`Danny: Tryouts [freshman · November]`), and crossover scenes tie storylines together. Every name
in a plan is checked against your storylines: a typo comes back as an error with what it probably meant, instead of
quietly doing nothing.

**When a storyline won't play.** The usual causes, and what the game does about them:
- A scene that waits on a fact nothing remembers (`if season_shared_start` when no choice anywhere says `remember
  season_shared_start`) would never come. Pasting one takes the `if` off (with a note, and the likely typo); one
  already in your game says so in Read it and Play it start to finish, and the storyline moves on past it.
- In a storyline in order, `after <the scene before>` is just the order: one scene that can't happen no longer takes
  every scene after it down with it. (In `order: any` storylines, `after` still means "only once that one happened".)
- Room: a scene's opening lines can run about 4,000 characters together (15 to 25 lines of back and forth), a line
  800, a choice 140. The guide tells ChatGPT these numbers.
- Too long for one ChatGPT reply: build it with an outline (above) and a few scenes per prompt. In the one-paste flow
  the prompts still tell it to stop after a whole scene and send `=== <Title> (part 2)` with `expands: <Title>` when you
  say continue.

**Expansions** keep storylines growing without ever resending them: `=== Sisters: Holidays` with `expands: Sisters`
under it. An expansion already has its storyline's people (no copying cast lines), can say `after <one of its
scenes>` and `if <a fact it remembers>`, and lives in its own file, so a big storyline never has to be sent back whole
(ChatGPT gets it, plus the scene lines of the expansions it already has). Change the storyline's cast and its
expansions follow.

**What scripts can say about time and people:**
- Holidays on their real dates every year, including the ones that move: Thanksgiving, Easter, Mother's and Father's
  Day, Memorial and Labor Day, MLK Day, the Super Bowl (the real Sunday each year)... and the school calendar's own days:
  the first and last day of school, homecoming and homecoming week, the Snow Ball, prom and prom week, midterms, finals
  and finals week, report cards, graduation, Thanksgiving, winter and spring break. A scene on one of those always gets
  its day.
- Class scenes: `in biology` (any class you take that year: chemistry, spanish, us history...) puts a scene on a school
  day in that class, and `{teacher}` / `{class}` say your actual teacher and class.
- Walk-ons: `Mom:`, `Dad:`, `{teacher}:`, `Coach Reyes:` can talk in any scene (the game doesn't track their feelings,
  so effects go on you, your family or the scene's person).
- Someone in your world, by name: `cast: ally = Ally Soffer` (or just `Ally` if the first name is unique). The storyline
  is about exactly that person, and the same name in any storyline is the same person: storylines belong to the world,
  not to one character. The prompts list the people around you by name (family, best friend, closest friends, crush,
  rival, teammates) so ChatGPT can write about them.
- Someone in another person's life: `cast: kayla = friend of sis, girl` (also best friend / teammate / boyfriend /
  girlfriend of). The game picks them from your sister's world and makes them actually friends, and they stay the same
  person in every storyline that names them.

**Built for a big library.** Each script is compiled once and kept (on the phone too, so opening the app doesn't
recompile everything); only a changed file compiles again. The scheduler checks a scene's year, month and date before
anything else and remembers each scene's season per school year, so a seven-year check with 2,000 scenes takes about
8 seconds on a computer (it took about 85 before), and loading 5,000 scenes takes about half a second.

**In the lab:** Content Library → **Dialogue**. Same steps, plus downloading the guide.

Scenes on screen read like the script: narration, then each line of talk with the speaker's name. The game still rests
every line it uses before using it again, fits texting lines to the moment (`when` tags like `late_night`, `close`,
`crush`), and dresses lines with openers, closers and ways of saying things (`mods`).

The full reference is `docs/story-script-guide.md` (generated from the game's own lists, so it's never out of date), and
the prompt is `docs/story-script-prompt.md`.

**For Claude (or anyone editing the repo):** write the script, check it with
`python -m lifeos.dialogue check my-story.story` (run from `backend/`), and drop it in `var/dialogue/` (lab) or paste it
on the phone. Scripts are saved one storyline per `.story` file.

## Tests

```bash
cd lifeos
python -m pytest backend/tests -q      # 59 tests, about a minute
```

They cover every acceptance criterion in the brief. Each name below is a test:
- **Characters and time:** stable identities, consistent time advancement, school-year rollover and graduation (traced and untraced).
- **Behavior:** NPCs initiate interactions on their own; relationships form, change and stay directed; parameters change decisions, both in exact scoring and in behavior; temperature controls determinism.
- **History:** event change logs add up to the actual state change in a slot; the history is internally consistent; important outcomes have traces whose terms add up to the utility and whose probabilities reproduce.
- **Reproducibility:** same seed gives the same outcomes and a different seed diverges; tracing never changes outcomes; a loaded save continues exactly like the original.
- **Configuration:** invalid configuration is rejected without partially applying; every rule parameter is read by the engine.
- **Lab tools:** experiment runs are isolated and reproducible; player choices go through the same resolvers; lab edits are validated and recorded; the workbook round-trips.
- **Demo:** the demo world produces measurably different lives.
- **Phone** (`test_phone.py`): the family dog becomes a real pet with a one-time chore setup; quick and timed pet activities; asking for and adopting a pet; texts come from what happens and replies change relationships; plans made by text happen; second-person text; everyone has a look; the phone API flow; the character worksheet round-trip.
- **Story mode** (`test_story.py`): the spec builds you, your siblings (twins included), your people and the town; validation reports every problem; moment choices change state and are recorded; a football season has rosters, box scores and stats; a senior leaves with a path, arrives at college and comes home for Thanksgiving; the story API flow works end to end. Also: the Guilford setting and the real colleges; a sibling set to play basketball at UConn ends up there; offers get pulled over GPA; the MLB draft after junior year and the finale; offscreen college seasons.

## Demonstration scenario

```bash
python demo.py                # ~1 minute: 180 days of the demo world + the approval experiment
python demo.py --days 365 --seeds 5
```

It prints, from the recorded history, how the featured characters' lives went: who they got close to,
what they tried out for, where it went wrong. It then compares Marcus (athletic aptitude 90,
discipline 26) with Devon (aptitude 60, discipline 92). Last, it runs the social-approval experiment
across paired seeds and prints differences with 95% intervals. In one run the basketball skill went
Marcus 58→64 and Devon 48→73, and raising social approval ×2.5 clearly raised exclusions and rumors
(4 of 4 seeds). The friendship effect was unresolved.

## A tour of the lab

| Section | What you can do |
|---|---|
| **My Story** | Story mode: the setup wizard, then your life. Moments, choices, invitations, focus, your teams, season stats, box scores, awards, recruiting board, family and people. |
| **World Overview** | Clock, population and world statistics, the notable-events feed (filter by social / romance / conflict / school), upcoming calendar, spotlight (most popular, most stressed, loneliest), weekly trend charts, cliques, institutions. |
| **Character Studio** | Every person as a card. Their profile keeps the layers separate: personality, aptitude, learned skills (with the talent ceiling marked), motives, current condition, circumstances (household, money, groups). Also goals, interests, reputation and learned expectations. The relationships table shows both sides: how they see each person, what they *think* that person feels, and what that person actually feels. Then their timeline, recent decisions (each opens its trace) and memories. **Edit** any attribute, validated and logged as a lab edit. **Create a character** with the full character builder (personality, body, positions, relationships). Athletes get an athlete page with season stats, career totals, awards and recruiting. |
| **Social Network** | A force-directed map: mutual friendships, one-sided ones (dashed), couples, crushes, rivalries. Click a person or a line. Below it: cliques, groups and institutions (rosters, captains, records, cut lists), the biggest perception gaps, and households. |
| **Live Any Life** | Pick anyone. At each decision point you see their real options, why each is available, and how likely they would be to pick it on their own. Choose one, or let them decide. The simulation resolves it with the same rules and dice as everyone else's choices. |
| **History Explorer** | Every event, filterable by person, type, importance, date range and text, with a CSV export. Each event shows its calculation (probabilities and rolls), every state change (before, after and why), the memories it created, its causes and its consequences. The **decision trace inspector** shows every option weighed, each term's contribution, the temperature, the random roll and the weights in effect. |
| **Experiment Center** | Presets and a builder: a base world (fresh from a generation seed, the current world, or a save), the number of days, the seeds, and variants with rule overrides. Runs happen in separate processes. Results are labelled honestly: one seed is a *deterministic paired comparison* (including whose lives changed and the day the timelines split); several seeds are a *repeated-run measurement* (means, 95% intervals on paired differences, direction counts, effect sizes). |
| **Engine Workshop** | 78 rule parameters with ranges, defaults and descriptions, applied from the next slot. Changes are validated, logged as lab events and versioned. Per-action coefficients (base, risk, need/motive/trait weights, target terms, on/off). Excel workbook export and import. Change log. |
| **Content Library** | The data catalogs: actions, goals, narrative templates, world and institutions, archetypes and staff, attribute definitions, metrics. |
| **Saves & Worlds** | Save, load, download and upload snapshots. Generate a new world (generation seed, population, with or without the featured cast). Change the simulation seed. |

Time controls are in the top bar: Day / Week / Month / Year, Auto with a speed setting, and quick save.
A simulated day takes roughly 0.03–0.1 s, and a full traced year roughly 25–35 s.

## How it works (short version)

See [`docs/DESIGN.md`](docs/DESIGN.md) for the full design and the assumptions behind it.

- **One authoritative world** (`backend/lifeos/model.py`) holds characters, directed relationships,
  bonds, households, groups, cliques, rumors, the calendar, the rules and the history. The server
  holds one instance. Saves are complete compressed snapshots.
- **Time**: each day runs a fixed list of phases. School days are morning → classes → lunch\* → after school\* → night;
  other days are morning → day\* → evening\* → night. \* marks a decision slot. Weekly and yearly processing hangs off night.
- **Decisions** (`decision.py`): every acting character enumerates (action, target) candidates from
  `data/actions.json` and scores each one as a sum of named terms:
  - needs, motives × their global weights, and traits
  - interests, and feelings toward the target
  - goals, memories, learned experience, habit and peer conformity
  - minus risk, plus commitment and situational terms

  An action's possible targets share one slot of probability. The choice is a softmax draw with a personal
  temperature (impulsive people are noisier). Every term is recorded.
- **Resolution** (`actions.py`, `institutions.py`): invitations can be declined by the other person,
  who weighs it against their own plan. Interactions have one true quality, but each side experiences
  it with its own noise, and each forms a *belief* about the other. That is how one-sided friendships
  and misread crushes happen. Collective events (lunch tables with exclusion, practices, tryouts judged
  by each coach's own weights, games, shows, dances, parties, elections) resolve after individual actions.
- **Consequences**: memories, learned expectations, goals (created by failure, rejection, grudges,
  loneliness...), skill growth toward an aptitude ceiling, confidence drift, interest drift,
  popularity and reputation, rumors that spread and can be traced back to whoever started them.
  Some consequences are delayed: tryout results post the next morning, and parents find out the next day.
- **Randomness** (`rng.py`): every draw comes from a stream derived from the seed plus a name and keys
  (for example decision / day / slot / character). Unrelated systems don't share random numbers, and
  there is no hidden RNG state, so a save plus the seed fully determines the future.

## Project layout

```
lifeos/
  run.py                 start the server (+ open the browser)
  demo.py                the demonstration scenario
  requirements.txt
  backend/
    data/                the data catalogs (JSON): rules schema, actions, world, people, templates, goals,
                         sports, colleges, story moments, texts
      dialogue/          (empty: the game ships no storylines; yours are .story scripts)
    lifeos/              the engine and API (Python); script.py compiles story scripts, dialogue.py loads them
      rng.py rules.py catalogs.py model.py history.py calendar.py worldgen.py
      decision.py actions.py social.py institutions.py households.py development.py
      sports.py college.py story.py moments.py
      narrative.py metrics.py engine.py experiments.py storage.py spreadsheet.py api.py
      appearance.py pets.py messages.py pov.py phone_api.py worksheet.py
    tests/test_lifeos.py tests/test_story.py tests/test_phone.py
  frontend/              React + TypeScript + Vite; dist/ is the built app the server serves
  docs/DESIGN.md
```

## Status: what works and what doesn't yet

**Working and tested:**
- The world, time advancement, autonomous agents, social dynamics, institutions and households.
- Persistent history with decision traces and state-change logs.
- Rules and action editing with validation, save/load, experiments, the workbook round-trip, play mode, and all the UI sections.
- Story mode: the spec and builder, siblings and twins, custom relationships, moments, focus, invitations, the three sports, recruiting, the college decision, college life and breaks at home, jobs in town.

**Not implemented or partial in v0.1 (labelled honestly):**
- **Guardians** are household-level actors with a parenting style. They react to grades and trouble, but they aren't autonomous agents.
- **Pets** in your household are full animals with needs, bonds, tricks and chores. Pets in other households are still a simple line (they relieve stress at home).
- **Phone art** is hand-drawn vector illustration (portraits generated from each person's look, scene backdrops per place, season and time of day). Image generation wasn't available, so there are no painted backgrounds.
- **Texts** are written from templates with a per-person voice. You can type anything, but it's read for intent and tone with simple
  rules (no AI), so it catches what you're doing, not every detail of what you said.
- **The phone app** keeps your story on that one phone (back it up). It's slower than a computer on long skips (a few seconds for a week, longer for months) and trims old background history sooner to fit in phone memory. Experiments and the Engine Workshop stay in the lab.
- **Careers and economy** are minimal: two part-time employers, allowance by income level, and costs for outings.
- **After high school**: your own college is fully simulated (teams, classes, roommate, classmates). Everyone else who leaves town lives offscreen: weekly updates, no daily decisions, home for breaks. Graduates who stay in town work full time. The seven chapters end with the MLB Draft after college junior year and a final review. The world keeps running after that, but pro ball is offscreen (no minor league seasons yet), and there's no grad school or later adult life.
- **College sports** are simplified: one varsity team per side (men's and women's), a short schedule (11 football games, 18 basketball, 14 baseball, about 10 soccer and 14 softball), and no transfer portal, redshirts or NIL.
- **Boys' and girls' teams** follow the usual high school setup: football and baseball are boys' teams, softball is the girls' spring sport, and basketball and soccer have one of each. Girls can't go out for football here. Nonbinary students can try out for either side. One fall sport at a time, so football and boys' soccer split the same boys, and a small school runs thin rosters.
- **Real names, simulated numbers.** Guilford, its spots (the Green, Jacobs Beach, Bishop's Orchards), the SCC opponents, the colleges, their conferences and the MLB teams are real. Program strengths, GPA cutoffs, draft projections and slot values are design values for the simulation, not official figures. Every person is generated or made by you.
- **Spreadsheet import** covers Rules, Actions and Characters. Groups, templates and goals are edited in the JSON catalogs; restart the server to reload them.
- **Narrative text** is template-based and functional rather than literary.
- **Balance** is a first pass. The demo produces plausible years, but the numbers are design values meant to be tuned in the Workshop. Known tendencies: moods trend high over a long run, team rosters in a 36-student school are small, and outcomes vary a lot between seeds (which is what the Experiment Center is for).
- **Speed**: a traced year takes 25–35 s in pure Python. In story mode, people far from your life act less often and aren't traced, so a story year runs in about the same time. Experiments run untraced and in parallel.
- **History retention**: routine events older than 60 days are folded into per-person counters. Routine decision traces are kept for 45 days, and traces for important events are kept forever. All of this is configurable in the Workshop.
