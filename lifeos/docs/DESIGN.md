# LIFE OS v0.1: design notes and assumptions

This document records the decisions made while building v0.1: what each engine does, the
mechanics as implemented, the assumptions behind them, and where to extend. All numbers are
experimental design values meant to be tuned in the Engine Workshop, not claims about real life.

## 1. Architecture

A modular monolith in Python with a React lab on top.

| Layer | Module | Responsibility |
|---|---|---|
| Foundation | `rng.py` | Seeded random streams derived from (seed, stream name, keys); softmax pick with a recorded roll |
| | `rules.py` | Rules schema (`data/rules_schema.json`): types, ranges, defaults, validation, cross-checks, version hashes |
| | `catalogs.py` | Data catalogs (actions, world, people, templates, goals) plus per-world action overrides and their validation |
| | `model.py` | The world: characters, directed relationships, bonds, households, groups, cliques, rumors, calendar, schedule |
| | `history.py` | Events, decision traces, the `Effects` change recorder, retention and compaction |
| | `calendar.py` | Dates, phases of the day, breaks, and the yearly institutional calendar |
| | `storage.py` | SQLite saves (compressed full snapshots) and experiment records |
| Intelligence | `decision.py` | Candidate generation, named utility terms, softmax choice, traces |
| | `development.py` | Goals (generation, priority, closure), skill decay, interest drift toward friends, habit decay |
| Domains | `actions.py` | Resolvers for individual actions: solo activities, interactions, romance, conflict, information, risk, sign-ups, jobs, parties, mentoring |
| | `social.py` | Interaction quality and perception, relationship labels and milestones, popularity, clique detection, rumors |
| | `institutions.py` | The school day, exams, lunch tables and exclusion, practices, tryouts and auditions, games, shows, dances, parties, elections, jobs, graduation, the new year |
| | `households.py` | Guardian reactions, allowance, weekends away, support |
| | `sports.py` | Sport ratings, varsity/JV, starters, box scores, season stats, awards, injuries, recruiting, admissions, paths |
| | `college.py` | Life after high school: departures, the protagonist's college, offscreen lives, breaks at home, jobs in town |
| Story | `story.py` | The story spec: validation, building you, your family, your people and the town; the dashboard summary |
| | `moments.py` | Story moments: triggers, choices, chance rolls, auto-choice when you let them decide |
| | `narrative.py` | Template rendering from structured events (presentation-only randomness) |
| Lab | `metrics.py`, `experiments.py`, `spreadsheet.py`, `api.py` | World statistics, isolated multi-process experiments, the Excel round-trip, and the HTTP API |
| Orchestration | `engine.py` | `Simulation`: phases, slots, invitations and responses, fallbacks, nightly and weekly processing, player mode, lab edits |

## 2. Characters: separated layers

| Layer | Fields | Changes how |
|---|---|---|
| Stable tendencies | 10 traits: sociability, confidence, discipline, ambition, impulsivity, empathy, competitiveness, curiosity, volatility, loyalty | Very slowly. Confidence drifts with success and failure, scaled by volatility, and settles back toward its own baseline. |
| Natural aptitude | athletic, academic, creativity, technical, charisma | Fixed. Sets each skill's growth rate and ceiling. |
| Learned capability | 9 skills | Practice, team practice, classes and mentoring raise them; they fade when unused. |
| Motivations | achievement, approval, belonging, pleasure, altruism, mastery | Fixed per person. Global multipliers in the Workshop. |
| Condition | energy, social, fun, stress, mood | Daily drain and recovery; events. |
| Circumstances | household (style, income, pet), money, memberships, grounded/pressure flags, partner | Institutions, households, choices. |
| Experience | memories, learned expectations per action, habits, reputation tags | Every outcome. |

**Talent vs. discipline**, the case named in the brief. A practice session gains
`base x 0.55 x skill_rate x (0.4 + 1.2 x aptitude/100) x ceiling_factor`, scaled by session quality.
- **Session quality** depends on discipline, energy and stress.
- **The ceiling** is `(1 - w) x 100 + w x aptitude`, where `w` is the talent-ceiling weight.
- **How often someone practices** comes from discipline in the utility model.

So a talented, undisciplined athlete grows fast per session but practices rarely and gets dropped
by coaches for missing practice. A modestly talented, disciplined one practices constantly, impresses
effort-minded coaches, and rises to a lower ceiling.

## 3. Relationships

Directed: `rels[(a, b)]` is how `a` sees `b`.

**Fields:**
- familiarity
- affection (−100..100)
- respect
- attraction
- trust
- rivalry
- `perceived`: a's belief about b's affection for a

**Labels** (stranger, acquaintance, friend, close friend, best friend, rival, dislikes) are derived per
side from thresholds in the rules. Crushes are a separate flag. **Formal roles** (sibling, partner, ex,
teammate) live in undirected bonds.

**Perception.** An interaction has one true quality. Each participant experiences it with their own
noise. Each then updates `perceived` from a noisy reading of the other: the noise is reduced by
empathy, and confidence adds an optimistic bias. That is how one person comes to believe they are
close friends while the other sees an acquaintance. The Social Network's *Perception gaps* tab shows
the largest disagreements.

**Milestones** fire when a label crosses a threshold; repeats within 90 days are ignored. Affection
fades toward neutral without contact (4% a week by default; half that for partners and siblings).

## 4. Decisions

For each decision slot, every acting character:
1. **Enumerates candidates** from `data/actions.json`: role and slot eligibility, requirements (money,
   grounded, romance on/off, weekend, a household that allows parties...) and a target selector.
   Selectors include known people, strangers, crushes, partner, grudges, falling-outs, struggling
   friends, listeners with a rumor to share, opportunities, memberships, scheduled events, parties and
   siblings. Attention is bounded: at most `shortlist_size` people are considered per action, the
   strongest relationships plus one at random.
2. **Scores each candidate** as a sum of named terms:
   - base
   - needs (urgency^1.5)
   - motives × global motive weights, and traits
   - interest
   - target terms (affection, attraction, rivalry, popularity × approval, grudge...)
   - memories with the target (capped; reversed for conflict actions)
   - learned experience (negative experience amplified by low confidence), habit, and friends' recent behavior × belonging
   - risk × personal risk aversion, and commitment × discipline/loyalty
   - goal contributions and situational terms (homework, tryouts today, already has plans, nerves...)
3. **Shares probability among an action's targets.** Every candidate gets `−T·ln(n)`, so an action
   with many possible targets doesn't win just because it has more entries.
4. **Draws a softmax** with temperature `T x (1 + impulsive_noise x (impulsivity − 50)/100 + stress over 70)`.

All characters decide from the same start-of-slot state. Decisions are then resolved in a seeded order.
- **Invitations:** the other person compares the appeal of accepting (scored from their own point of
  view, +4 for being asked) against their own plan. Accepting cancels that plan. If the invitation
  falls through, the inviter does their best solo option instead.
- **Collective events** resolve after the individual choices.

**Traces** keep every candidate's utility and probability, the full term breakdown for the top five
and the chosen one, the temperature, the roll and a pointer to the rules version in effect.
Explanations in the UI are built only from these recorded numbers.

## 5. Events and consequences

Every resolver follows the same contract:
1. evaluate circumstances;
2. draw from the actor's resolution stream;
3. record each factor, probability and roll in `calc`;
4. change state only through `Effects`, which logs `[entity, field, before, after, why]`;
5. create memories and rumors;
6. schedule delayed consequences.

Examples of delayed consequences: tryout and audition results post the next morning; parents find
out about a prank the next day; a loyal friend tells the subject of a rumor; a hiring decision comes
two days after applying.

**An emergent loop the brief asked for:**
1. A student tries out and is cut. The coach's evaluation is recorded:
   `talent weight x performance + effort weight x (discipline + recent practice) + favoritism + seniority`.
2. Their reaction depends on resolve (competitiveness + discipline + ambition − volatility + confidence).
   Resilient students form "get better at X" and "make the team next time" goals, and their interest
   rises. Others lose interest.
3. The goals raise the utility of practice; skills grow.
4. If a rostered player is dropped for missing practices, the coach calls up the best cut candidate
   still interested.

None of this is scripted as a sequence.

## 6. Institutions in the first world

**Teams** (soccer in fall, basketball in winter, baseball in spring):
- tryouts (sign-up window, attendance, nerves, coach evaluation, next-day results, captain)
- practices, weekly games (strength vs. a random opponent, a standout player, spectators)
- rolling attendance: dropped for missing more than 4 of the last 8 sessions, configurable
- call-ups, and season end

**Drama:** two productions a year with auditions, a lead, rehearsals and a show with a review.

**Clubs** (art, robotics, jazz band, the paper): open membership, weekly meetings, members drift away
when they stop showing up.

**Student council:** sign-ups and an election where each student votes from affection, respect,
popularity × approval, clique loyalty and noise.

**Jobs:** two employers; hiring scored on discipline, charm and reputation; shifts; firing for missed shifts.

**School:**
- classes: academic skill, ambient classmate contact, daily stress
- quizzes every two weeks, midterms and finals, which feed GPA
- report cards with guardian reactions
- dances with asking windows, dates and wallflowers
- parties: hosts need a permissive or away household; invitations, crashers, kisses, fights,
  getting busted, hurt feelings over not being invited

**Graduation and the new year:** seniors become alumni and keep their relationships; the rest move
up a grade; new freshmen arrive, sometimes as younger siblings; the calendar rebuilds.

## 7. Randomness and reproducibility

Streams are derived with BLAKE2b from (seed, stream, keys):
- `decide/day/slot/char`
- `resolve/day/slot/char`
- `collective/day/slot`
- `order/day/slot`
- `weekly/day`, `dawn/day`, ...

World generation uses separate streams from `gen_seed`. Narrative wording uses its own stream, so
editing templates never changes outcomes. There is no RNG state to save; the tests verify three things:
- a loaded save continues exactly like the uninterrupted run;
- tracing on and off produce identical worlds;
- the same seed reproduces the same event sequence.

## 8. Experiments

Each (variant, seed) run deserializes its own copy of the base world in a worker process, with
history off. Variants reuse the baseline's seeds (common random numbers).

**Single seed: a deterministic paired comparison.**
- the metric differences;
- the per-character differences: friends, popularity, mood, GPA, groups gained or lost, partner changes;
- the first day the two timelines diverged (from a per-day digest of everyone's actions).

**Several seeds: a repeated-run measurement.**
- per-seed paired differences;
- mean, SD, a 95% t-interval and the count of seeds that went each way;
- an effect size (mean difference divided by the pooled SD).

The UI and `demo.py` say which kind of result they are showing, and warn that small samples are provisional.

## 9. Assumptions worth revisiting

- **Two decisions per day** (lunch plus after school on school days; daytime plus evening otherwise)
  is enough resolution for social life. Staff decide once a day.
- **Guardians are part of the household, not agents.** Their style parameters drive reactions.
- **Popularity is a rank:** a percentile of a weighted "known × liked/respected by people who are
  themselves popular" score, plus prestige from membership.
- **Cliques are mutual-affection communities** found weekly by label propagation (minimum size 3).
  A clique that dissolves and returns within four weeks keeps its identity.
- **Orientation is a simple per-person set of genders** and gates both attraction growth and a
  romantic yes. Pair chemistry is a fixed latent value per pair, so some pairs just click.
- **Money is coarse:** an allowance by income level, part-time pay, and costs for outings, dates and parties.
- **Default balance:** the default values produce plausible years for the demo world; other worlds
  and seeds vary a lot. Expect to tune.

## 10. Extension points

- **New actions:** add an entry to `data/actions.json` with an existing resolver (`solo`, `interact`
  and others), or register a resolver with `@resolver("name")` in `actions.py`. Target selectors live in
  `decision.targets`.
- **New goals:** add a type to `data/goals.json` (label, advancing actions and weights) and a
  generation rule in `development.generate`.
- **New institutions:** add a group to `data/world.json`. Teams, productions, clubs, councils and jobs
  already work. A new kind needs calendar entries (`calendar.build_year`) and a collective resolver in
  `institutions.after_slot`.
- **New rules:** add a parameter to `data/rules_schema.json` and read it where needed. The test suite
  fails if a parameter is never read.
- **New domains** (careers, adult life, pets as agents): add roles to the action catalog's `roles`,
  slot actors in `engine.slot_actors`, and the domain module.
- **Spreadsheet master:** `spreadsheet.py` already round-trips Rules, Actions and Characters. Groups,
  templates and goals would follow the same pattern.

## 11. Story mode

Story mode is the same simulation with one person marked as the protagonist and a few extra systems
around them. Nothing about the protagonist's life is scripted: moments are triggered by things that
actually happened in the world, and their choices run through the same `Effects` recorder as everything else.

### The spec

`story.create_story(spec)` builds a world from a JSON spec:
- the protagonist;
- `family` (last name, guardians, parenting style, income, pet);
- `siblings`, where `twin_of` gives a shared birthday and a twin bond;
- `cast`, any number of custom students or staff, with `coach_of` for coaches;
- `students_per_grade`, which the generator fills around the custom people.

Every person field is optional except a first name. Blanks come from the archetype's distributions, so
a sketch of a person becomes a full one. Relationships use presets (`REL_PRESETS`: best friend, crush,
mutual crush, rival, twin...). Each preset sets the directed fields (affection, attraction, rivalry,
trust...) from the subject's point of view, plus a reciprocal for the other side, and a strength
of ±40 scales it. Validation collects every error with a path (`cast[1].traits.swagger`) before
anything is built, so the UI can show them all at once.

### Sports

- **Rating** = 0.6·skill + 0.15·athletic aptitude + 0.12·fitness + body bonus + 0.06·(confidence−50) + 6.
  The body bonus is height for basketball (more for C/PF) and pitchers, and build for football
  (strong for linemen, athletic or slight for skill positions).
- **Tryouts** rank everyone who registered. The top N make varsity; the next ones in grades 9–11 make JV.
  Coaches start the top-rated healthy players. A long bench streak can trigger the "riding the bench" moment.
- **Games** draw a team performance against an opponent strength. Each player's stat line comes from
  their position's template, scaled by how they played and whether they started. Every game event carries the full box score.
- **Season stats** are keyed `sport:YYYY-YY:level`. At season's end the best impact per game wins MVP,
  and strong seasons win All-Conference.
- **Skill growth** in sports follows a curve (`dev.sport_ceiling_curve`, default 2.2): the gain per
  practice is multiplied by (room under your talent ceiling)^curve. Early progress is quick and the
  last stretch toward your ceiling is slow, so a freshman at 45 is usually 60–75 by senior year and
  only real talents reach college level.
- **Recruiting**: every college in `data/colleges.json` has a program strength per sport (0–100).
  - Bar to get an offer = 52 + 0.36 × program.
  - Recruiting score = rating + recent varsity production + awards + a grade bonus.
  - Interest grows with how close you are to the bar. Offers come junior and senior year once you're past it.
  - Baseball and D2 offers are partial scholarships; football and basketball are full.
- **Grades**: exams map to the 4.0 scale (80 = B = 3.0), and the average student settles around 3.0–3.3.
  - Each program has an `athlete_min_gpa` (NCAA minimum 2.3; Stanford 3.4). At admissions in senior
    spring, offers you're under get pulled, with an event that says why.
  - Regular admission: P = admit_cap × sigmoid((GPA − min_gpa) / 0.12). The cap keeps the most
    selective schools a long shot even with a 4.0.
- **The path** is chosen in senior spring from offers, admissions and staying to work. The player picks
  from the college_decision moment. Everyone else scores the options from their own interests,
  ambition, money, the program's strength and the school's academic rank.
- **Path presets**: any person except the protagonist can be given `path: {college, sport}` (or
  `{kind: "work"}`). They're built to play that sport, the offer arrives at admissions, and they take it.

### The MLB Draft

The draft happens every July 13. College juniors and seniors who play baseball are in the pool.
- **Scout score** = baseball rating + 0.3 × (impact per game − their team's level) × share of starts
  + 2.5 per college baseball honor (max 8) + program exposure.
- **Pick** = 10 × e^(0.2 × (97 − score)), plus some draft-day luck. Past pick 615 (20 rounds) is undrafted.
- **Teams** are the 30 MLB clubs in a seeded order. Slot values are interpolated from approximate recent figures.
- **First assignment**: High-A for rounds 1–2, Low-A for rounds 3–10, rookie ball after that.
- **The protagonist's choice**: sign (path becomes `pro` and they go offscreen) or go back to school.
  If undrafted, they can go back, sign as a free agent if a team called, or walk away from baseball.
- **Other draftees** sign if they went in the top 10 rounds or are seniors.
- **The finale**: the day after the draft is settled in year seven, the story_end moment closes the
  story with a review of all seven years.

### Setting

The town and school come from `data/world.json` and are used everywhere text names a place:
Guilford, Connecticut; Guilford High School (the Grizzlies, green and white, Southern Connecticut
Conference); real local spots and real SCC opponents. College opponents come from each college's
conference list. Changing the setting is a data edit; no code names the town.

### After high school

On September 1 the paths take effect. Your college is created the first time someone from town
arrives: teams with college schedules, clubs, a campus job, coaches, a professor, a roommate and a
cohort of classmates. Graduates going elsewhere go offscreen. They get weekly drift instead of daily
decisions, keep their relationships, and come home for breaks, so the twins are at the Thanksgiving table.
Graduates who stay in town take full-time jobs. Townies who play a sport somewhere else get a season
summary when that season ends: games, starts and a stat line from their rating against the program's
level, with upperclassmen getting credit for experience. If the protagonist later picks the same
college, anyone from town already there moves onto campus and onto the roster.

### Playing

- **Focus** adds a named +7 term ("your focus: athletics") to the protagonist's matching actions when
  the simulation decides for them. It's visible in every trace.
- **Advance until**:
  - `decision`: the next slot where the protagonist acts;
  - `moment`: a story moment, an invitation you asked to see, or a big event, with day/week/month limits.

  The job reports why it stopped.
- **Moments** wait in `meta.moments`. A choice runs ops (stat changes, focus, sign-ups, memories,
  chance rolls against the person's own traits). If you don't choose within a few days, the
  protagonist chooses for themselves with `auto_choice`, which respects their traits and orientation.
- **Invitations** to the protagonist wait in the inbox. Accepting queues a yes at the next free slot.

### Level of detail

The protagonist's circle is tracked with full detail:
- family;
- custom characters;
- their top relationships;
- teammates and coaches.

Everyone else in town is untraced. People in another location who aren't in the circle skip lunch and evening slots and
act every other day. This keeps a seven-year story at roughly 25–35 s per simulated year without
changing how the people you care about behave.

## 12. The phone

The phone app (`#/m`) is a second view of the same simulation, built for a single player.

### First person

`pov.second_person` rewrites lines about the protagonist ("Zack was named captain" becomes "You were named
captain"), with verb agreement and possessives. It only rewrites they/their when nobody else is in the line.
Scenes come from the phase, the place and what's on today: lunch is the cafeteria, a game day after school is
the field, a summer day is Jacobs Beach. Choices are the protagonist's real options, worded naturally (`phone_api.PHRASE`).

### Texting (`messages.py`, `data/texts.json`)

Threads live in `w.meta["phone"]`: DMs, the family chat (guardians appear as Mom/Dad when their names say so) and team chats.
Texts come from:
- events, via a hook in `Simulation.finish`;
- delayed "later today" texts, delivered after each phase;
- daily chatter, weighted by how much a friend likes you and how sociable they are;
- the night before games;
- pet chores.

Invitations and moments like being asked out arrive as texts whose replies resolve the real invitation or moment.

Every sender has a voice from their personality: casual people lowercase, abbreviate and use emoji that fit the kind of message;
parents and coaches write properly. Reply options carry effects (affection, perceived feelings, attraction, forgiveness,
parent trust).

Texting first is limited to once per person per day. Their answer depends on how they feel about you and their personality,
and they can leave you on read. Agreeing to hang out by text queues a plan, and the invitee accepts at the next free slot
(`SlotState.agreed`).

You only have someone's number after a real interaction or once you're familiar enough.

### Pets (`pets.py`)

The protagonist's household pets are full entities in `w.meta["pets"]`:
- species, breed, coat, personality;
- happiness, fullness, energy, health and cleanliness;
- a bond with each person, with diminishing returns;
- trick progress.

Chores per species (feeding twice a day, walks, litter, baths...) are assigned once in `w.meta["responsibilities"]`:
- a person;
- `parents`;
- `rotate`, meaning the kids at home take turns by day.

Each night every due chore resolves. A sibling or the protagonist does it with a probability based on discipline,
loyalty, stress and a busy day (games, exams). Misses hurt the pet's happiness and draw family texts. Streaks raise parent trust.

Quick activities (cuddle, treat, feed, brush) happen immediately with daily limits. Timed ones (walk, park, play, train) are
real actions, `pet_walk`, `pet_park`, `pet_play` and `pet_train`, which anyone in the household can choose. The phone either
does them in the current slot or queues them for the next free one. The park can introduce you to someone.

Asking for a pet rolls against household warmth, permissiveness, income, your GPA, existing pets and parent trust.
A yes unlocks adoption: name, breed and coat, then the one-time chore setup.

### Looks (`appearance.py`)

Every character has a look: skin, hair style and color, eyes, facial hair, glasses, freckles. Generated looks come from a hash
of the character id, so they never consume simulation randomness. Builder choices override them. The phone draws portraits
from the look, with an expression per moment.

### The worksheet (`worksheet.py`)

The Excel worksheet has one column per person and one row per field. Column A holds the field codes the importer reads.
Dropdowns and number limits come from the catalogs, and the Reference tab lists types, positions, colleges, looks and
relationship types. `parse_workbook` turns a filled sheet into a story spec. `guide_markdown` produces the AI interview prompt
and the cast-file format, so a conversation with ChatGPT or Claude ends in a file the wizard loads.

## 13. The phone app (no server)

`docs/play/` at the repository root is a static site: the phone screens plus the engine. In the browser:
- `engine-worker.js` loads Pyodide (CPython compiled to WebAssembly) and unpacks `engine.zip`, which holds
  `backend/lifeos`, `backend/data`, the FastAPI stand-in (`backend/standalone/fastapi`) and openpyxl.
- It mounts IndexedDB at `/data` and calls `lifeos.local_api.boot()`.
- The FastAPI stand-in records each route as `api.py` and `phone_api.py` are imported.
- `local_api.handle()` matches a request to its handler, converts path, query and body parameters from the annotations,
  and returns the same JSON or bytes the real server would.
- On the main thread, `src/standalone/bridge.ts` replaces `fetch` for `/api/...` with a message to the worker. The phone
  screens don't know whether they're talking to a server or the phone.

Differences from the server:
- There are no threads. Long advances are generators (`Lab._launch`); the worker pumps them about 0.12 s at a time,
  so progress polls get answered in between.
- `FileStore` replaces SQLite.
- Autosave is throttled to every 30 seconds. The worker also flushes and syncs IndexedDB when the app is hidden.
- History is leaner (`local_api.LEAN`) to fit phone memory.
- The service worker caches everything for offline use.

`lifeos/tools/build_phone_app.py` builds all of it. `tests/test_phone_app.py` runs the same handlers through the stand-in.

**Making a story on the phone** (`src/phone/CreateStory.tsx`, at `#/m/create`):
- It runs the same seven steps as the lab's wizard, laid out for a phone: you, your look, who you are, sports, family, your people, ready.
- Both wizards share one draft model, `src/story/draft.ts`, which holds `Draft`, `buildSpec`, `parseErrors` and the people templates.
  Whichever one you use, the server gets the same story spec.
- The phone keeps its draft in `localStorage` (`lifeos.phoneDraft.v1`), separate from the lab's.
- Siblings and people are edited in full-screen sheets.
- The last step calls `/api/story/validate` and lists the problems; each one jumps to the step or person it's about.
- `/api/story/catalog` also carries the pet species (breeds and coats), the school and the town, so the screens never hardcode them.
- A picked pet can name its breed and coat. `validate_story` checks both, and `pets.ensure` carries the coat over.
- `appearance.resemble()`: when you pick your own look, siblings left on auto take your skin, hair color and eyes when the story is built.
  They use the same odds as generated families: skin is shared (sometimes a shade off), hair color usually is, and eye color often is.

## 14. Dialogue packs

`lifeos/dialogue.py`: everything people say comes from data, and dialogue packs add to it without touching code.
- **Base content:** `data/texts.json` (66 text pools), `messages.REPLY_SETS` (reply buttons, by tone), `data/templates.json`
  (narration), `data/moments.json` (the built-in moments).
- **Packs:** `data/dialogue/*.json` (built in) and `dialogue.USER_DIR` (yours: `var/dialogue/` on a computer, `/data/dialogue/`
  on the phone, which syncs to IndexedDB). They load in order and only append; duplicate lines are skipped. `state.json` there
  remembers which packs are off.
- **Merging:** `dialogue.merged()` builds the combined content once and caches it until a pack changes. `Catalogs` takes
  `templates` and `moments` from it, `messages.T()` the text pools, `messages._replies` the reply sets. A set bigger than 3 shows
  3 at a time, keeping a mix of tones.
- **Checking:** `check(pack)` returns errors (won't load) and warnings (will) in plain words, with "did you mean" suggestions.
  Placeholders are checked per spot against what the code really fills in, taken from the base lines, so a pack can't leave a
  literal `{x}` on screen.
- **Scenes** are moments with a `scene` block: `who`, `when`, plus the people the text needs.
  - `maybe_scene()` runs each morning in story mode from its own random stream. It allows at most one pack scene every
    `SCENE_GAP_DAYS` days and none while another moment waits, except scenes on a set date.
  - It picks the person from `candidates()`, filters them by `you_feel`/`they_feel`, and fills `{them_first}` and the rest.
  - A choice whose text or ops mention someone gets `requires` automatically, so it's hidden when that person doesn't exist.
    A scene needs two usable choices to start.
- **New ops:**
  - `say`: lines shown after the choice, in `ev.data.say` and on the phone.
  - `text`: they text you later today.
  - `hang_out`: queues plans.
  - `remember` / `forget`: `w.meta.remembered`, which keeps who the fact was about, so a follow-up scene stays with that person.
  - `skill` / `interest` accept `"sport"`, meaning your main sport.
- **The guide:** `guide_markdown()` and `PROMPT` are generated from the data, so the AI always gets the real lists.
  `docs/dialogue-guide.md` is a copy, regenerated with `python -m lifeos.dialogue guide`.
- **API:** `/api/dialogue/packs` (list, add), `/packs/{id}/enabled`, `/packs/{id}/remove`, `/check`, `/guide.md`, `/prompt`,
  `/current`, `/try/{scene}`. The same handlers answer on the phone through `local_api`.

## 15. Classes, quizzes and mini games

- **`classes.py`:**
  - `schedule()` builds the year's classes from `data/classes.json`: standard or honors/AP by academic aptitude or GPA,
    plus an elective from interests, each with a teacher. It's made once per school year and kept in
    `w.meta.classes.sched`.
  - `quiz_context()` turns a calendar exam into a class quiz (rotating through the schedule by quiz number) or a test
    across every class (midterms and finals: more questions).
  - `grades()`: per-class percent = GPA-based baseline + subject fit (aptitudes) + played quiz average (30%).
- **Playable exams:** `engine._story_dawn` triggers the `class_quiz` moment on exam days. Choice 1 is a
  `["minigame", "trivia", ...]` op. When you play it, `minigames.finish` sets `c.flags.quiz_played`, and
  `institutions.exam` blends that score (55%) with the modeled score (45%). The calc shows both terms, and
  `classes.record` stores it.
- **`trivia.py`:**
  - The bank is `data/trivia.json`: q, a, three wrong answers, grade, by subject. Dialogue packs can add a `trivia`
    section.
  - Math is generated per course (algebra1, geometry, algebra2, precalc, calculus, statistics) with computed answers.
  - `round_for()` mixes subjects for tests and avoids repeats via `w.meta.trivia_seen`.
- **`minigames.py`:** registry `data/minigames.json` (games, status, skill and aptitude, free-play rules, practice rewards,
  tiers, `sport_games`).
  - Sessions: `start` → config (skill, difficulty, seed, questions...) → the client plays → `finish(score, max)` → tier
    (great ≥ 0.8, good ≥ 0.5, else miss).
  - Free play rewards once a day per game.
  - Moment rounds set `ctx._mg` and resolve the moment. The `minigame` op runs that tier's ops; unplayed, it rolls its
    fallback odds against the character.
  - `choice_ok` hides choices whose game isn't ready.
  - The `clutch` op adds to game performance in `sports._game`.
- **Phone:**
  - `/api/phone/moment/{mid}` returns `{"minigame": config}` for a played choice, and the second call finishes it.
  - Other endpoints: `/api/phone/minigames`, `/minigame/start|finish|quit`, `/classes`.
  - `src/minigames/MiniGame.tsx` hosts HTML games in an iframe over a postMessage bridge (`lifeos:init` →
    `lifeos:minigame` ready/finish/quit). `Trivia.tsx` is the built-in quiz.
- **Games:** `frontend/public/minigames/*.html` (the lab serves them; `build_phone_app.py` copies them into
  `docs/play/minigames/`). The contract is in that folder's README.
  - `soccer.html` is written here. The rest are built in `games/` and copied in by `tools/sync_games.py`
    (basketball-playground → basketball, fairway → golf, pong-night → cup_pong, at-bat → baseball, swing-lab → swing,
    option-arcade → football).
  - Each registry entry's `play` maps a context (free / clutch / scene) to a launch mode; `config()` sends it as
    `config.play` and the game's embed glue opens that mode. One page can back two entries (`basketball` and
    `playmaker` both load basketball.html).
  - `sport_games.baseball` is At Bat. Swing Lab (`swing_lab`) is the batting feel prototype and can take over game day
    by pointing `sport_games.baseball` at it.

