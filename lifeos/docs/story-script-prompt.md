<!-- The ChatGPT prompt for new storylines (Me > Storylines > Copy the ChatGPT prompt). Generated; don't edit by hand. -->

You're writing for LIFE OS, a life-simulation game: I play one person from the first day of high school (Guilford High School in Guilford, Connecticut, fall 2010) through college. The game's stories are written as story scripts (the format is below).

## What I want

[describe it here: who it's about, what happens, which years]

## How to answer

- Reply with ONE code block (```) holding the whole script, and nothing after it.
- If it won't all fit in one reply, stop after a whole scene (never in the middle of one) and say "say continue for part 2". When I say continue, send the rest as a new code block that starts with `=== <the same title> (part 2)` and `expands: <the storyline's title>`, its first scene tagged `after <the last scene you sent>` (and part 3 the same way). I add each part as it comes.
- Write a lot, and make it a story: storylines with scenes in order, talk that goes back and forth, choices that matter later (remember / if), beats where a scene keeps going, the mini games where they fit, versions {a|b} on lines that repeat.
- Follow the format and the lists exactly. The game checks every line and tells me what to fix by line number.

# LIFE OS story scripts

Everything you add to LIFE OS (storylines, one-off scenes, texting lines) is a story script: plain text, like a screenplay. The game reads it and checks every line. What it can fix (a typo, a tag it doesn't know, a line that's too long, a fact nothing sets) it fixes, and tells you what it changed by line number; it only refuses a paste with nothing usable left in it.

## The shape

```
=== Same Team
cast: bro = older brother, plays basketball, 3 years older, close
about: You and your brother on the same team for one season.
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
* "Five more minutes..."    | bro respect -
    bro: I'm telling Coach.

--- Cut day  [a week later · big]
The roster's on the gym door.
* Look for your name        | 60% +athletic
    yes: It's there. Second line from the bottom. | mood ++, remember made_jv
    no: It isn't.                                 | mood --, stress +
* Wait for {bro}
    bro: Come on. We'll look together.
    * "I can't."            | bro affection +, fits -confidence
        bro: Then I will.
    * "Okay."
        bro texts: proud of u either way
```

## Storylines

- `=== Title` starts a storyline. Its scenes play in the order they're written, each one waiting for the one before (as soon as it's ready: tags hold it to its season), so don't tag a scene `after` the scene before it. If one can't happen, the storyline moves on to the next. `order: any` under the title lets them come in any order (good for a bag of one-off moments).
- `cast: <name> = <who they are>`: a specific person the storyline is about, the same person for the whole story (across storylines too: the same cast name means the same person). Who: brother, classmate, coach, ex, friend, older brother, older sibling, older sister, sibling, sister, teammate, twin, younger brother, younger sibling, younger sister. Then any of: `plays <sport>` (baseball, basketball, football, soccer, softball), `3 years older` / `2 years younger`, `girl` / `guy`, `close` (you start close), `from the start` (picked on day one, not at their first scene), and any words that describe them ("the one who got away").
- Someone in your story, by name: `cast: ally = Ally Soffer` (or just the first name if it's unique). The storyline is about exactly that person, and the same name in another storyline means the same person.
- Someone in another cast member's life: `cast: kayla = friend of sis, girl` (also `best friend of`, `teammate of`, `boyfriend of`, `girlfriend of`). The game picks them from that person's own friends (or team), and they stay the same person.
- `expands: <Storyline>` (under the title, like `=== Sisters: Holidays` then `expands: Sisters`): an expansion, more scenes for a storyline you have, in its own piece. It already has that storyline's cast (don't copy the cast: lines) and can say `after <one of its scenes>`.
- `when: <tags>`: tags every scene in the storyline gets (like `freshman-junior`). A scene's own year, month or day wins over these.
- `when: freshman · spread` spreads the storyline's scenes across that school year, in order, about evenly from September to June (or across several years: `freshman-sophomore · spread`; or a season: `junior · spring · spread`). Scenes with their own timing keep it.
- `about: <notes>`: what the storyline is about, for you and for ChatGPT.
- A scene in another storyline: `after Same Team: Cut day`.

## Outlines (big storylines)

For a storyline with more than a handful of scenes, plan it first: an `outline:` block under the title, one line per scene, then write the scenes a few at a time. The outline owns the order, the timing and the branches, so the scenes themselves are just people and choices.

```
=== Brothers: Same Team
cast: mike = Mike Soffer
years: freshman

outline:
1. Saved You a Seat | September | Mike saves you a seat on the bus.
2. The Passenger Seat | | Mike drives you to school for the first time.
3. Tryouts | November · big | You both try out.
4. Turkey Day | Thanksgiving | Mike is weird at dinner.
5. The Fight | December | You fight about playing time.
6. Making Up | | Mike apologizes. | only if you picked "Say sorry" in 5

--- 1. Saved You a Seat
mike: Sit. Don't make it weird.
* "Thanks." | mike affection +
* Sit in the back
```

- Each line: `number. Title | when | what happens`, and optionally `| only if you picked "<choice>" in <number>`.
- `when` is a month, a holiday (Halloween, Thanksgiving, Christmas), a school day (homecoming, prom, winter break, the first or last day of school), `big` for a major scene, or blank: blank scenes are spaced out between the ones around them. `years:` under the title says which school year(s). A time the game doesn't know is left out, with a note.
- A scene is `--- <number>. <Title>` and matches its outline line by number (or title). Tags on it are ignored, except `big` and `with`: its time and place come from the outline. Scenes not written yet just don't play.
- `only if you picked "Say sorry" in 5`: the game finds the choice in scene 5 most like "Say sorry", has it remember that, and plays the scene only if you picked it. If scene 5 has nothing like it, the scene plays either way.
- On the phone: Me > Storylines > Write more makes the outline prompt, then a prompt for the next few scenes at a time, and shows how many are written.

## Scenes

`--- Title  [tags]` starts a scene. Tags (separate with · or commas):

- School year: freshman, sophomore, junior, senior, college freshman ... college senior, ranges like `freshman-junior`, or `high school` / `college`.
- Month or season: `November`, `Nov`, `fall`, `winter`, `spring`, `summer`. A day: `Oct 31`, or a holiday: `Halloween`, `Christmas Eve`, `Christmas`, `New Year's Eve`, `New Year's Day`, `Valentine's Day`, `St. Patrick's Day`, `April Fools`, `July 4th`, `Veterans Day`.
- Days that move, worked out for every year: `Thanksgiving`, `Black Friday`, `Easter`, `Mother's Day`, `Father's Day`, `Memorial Day`, `Labor Day`, `MLK Day`, `Presidents' Day`, `Columbus Day`, `Super Bowl` (the real Sunday each year). The school calendar's own days: `first day of school`, `last day of school`, `homecoming`, `homecoming week`, `snow ball`, `prom`, `prom week`, `midterms`, `midterms week`, `finals`, `finals week`, `report cards`, `graduation`, `thanksgiving break`, `winter break`, `spring break`. A scene tagged with one of these always gets its day (you don't need a chance). `after Nov 15` / `before Thanksgiving` for a window.
- In class: `in biology` (or `in art`, `in chemistry`, `in economics`, `in english`, `in government`, `in health`, `in math`, `in music`, `in physics`, `in psychology`, `in spanish`, `in tech`, `in us history`, `in world history`, `in gym`) puts it on a school day in that class, if you're taking it that year; `{teacher}` and `{class}` say your teacher's name and the class. `in class` is any class.
- Day: `weekday`, `weekend`, `school day`, `summer break`, or a weekday (`friday`).
- How likely on a day it can happen (one-off scenes): `rare`, `uncommon`, `sometimes`, `often`, `likely`, `always`, or `10%`. Storyline scenes don't need one.
- Repeats: scenes happen once; `repeats every 30 days` lets one come back.
- Order and gaps: `after <scene title>` (or `after <Storyline>: <title>`), `same day`, `next day`, `a week later`, `3 days later`, `a month later`.
- Facts: `if <fact>` / `unless <fact>` (a fact a choice remembered). A fact has to be remembered by a choice somewhere (`remember <fact>` under it): never wait on a fact nothing sets, or the scene never comes. Situations: `if dating`, `if single`, `if has pet`, `if has sibling`, `if plays sport`, `if in season`, `if injured`, `if grounded`, `if school day`, `if weekend`, `if summer`, `if in high school`, `if in college`.
- Feelings and stats: `if bro trust 40+` (how the scene's person feels about you), `if my affection 60+` (how you feel about them), `if stress 60+`, `if mood 20-`, `if gpa 3.5+`.
- The sports world: `if pro:<condition>`, like `if pro:my_team_in_playoffs` (your MLB team: baseball_season, october, my_team_winning, my_team_losing, my_team_in_playoffs, my_team_alive, my_team_missed, my_team_champs), `if pro:<league>:<condition>` with league nfl, nba, cfb, mbb, wbb, epl, laliga, seriea, bund, ligue1, ucl, cbase, msoc, wsoc and condition in_season, my_team_winning, my_team_losing, my_team_in_postseason, my_team_alive, my_team_champs, my_team_ranked (college). A what-if world: `if pro:whatif:harper_2019`.
- Who it's with: `with best friend`, `with crush`, `with older sister`, `with coach`, or a cast name. Without it, the first person who talks is who the scene is about. Kinds of people: best friend, brother, classmate, coach, crush, ex, friend, older brother, older sibling, older sister, partner, rival, sibling, sister, teammate, twin, younger brother, younger sibling, younger sister.
- How big: `small`, `regular`, `big` (a turning point), `finale`.

## People and lines

- A plain line is narration, in second person ("You...").
- `name: line` is someone talking: a cast name, `you`, `best friend`, `sibling`, `partner`, or the kind of person the scene is with (`friend:`, `coach:`).
- Anyone else can talk too, as a walk-on: `Mom:`, `Dad:`, `Grandma:`, `{teacher}:`, `Coach Reyes:`, `The waiter:`. They're just a name on the line: the game doesn't track how they feel, so effects go on you (`mood +`), your family (`family affection +`) or the scene's person.
- `{bro}` says a cast member's name; `{best friend}`, `{sibling}`, `{partner}`, `{me}` too. The game also fills in {ballon_dor}, {cfb_champ}, {class}, {epl_champ}, {mbb_champ}, {mlb_champ}, {my_cfb_record}, {my_club}, {my_college}, {my_mbb_record}, {my_nba_record}, {my_nba_team}, {my_nfl_record}, {my_nfl_team}, {my_team}, {my_team_record}, {my_team_star}, {my_wbb_record}, {nba_champ}, {nfl_champ}, {pet}, {school}, {sport}, {teacher}, {town}, {ucl_champ}, {wbb_champ}.
- `{a|b|c}` gives a line versions; the game rotates them so nothing repeats.
- Room: a scene's opening lines can run about 4,000 characters together (15 to 25 lines of back and forth); one line up to 800; a choice up to 140; a title up to 100. Longer than that, split it: more lines, or a beat (choices under a choice).
- A scene can involve your best friend, sibling, partner and anyone in the storyline's cast, plus the one person it's with.

## Choices

- `* <what you say or do>  | <effects>`. 1 to 4 per scene (none at all makes a "Continue"). Quotes for things you say.
- Lines indented under a choice play after you pick it. `remember <fact>` / `forget <fact>` on their own line work too, and `bro texts: <line>` sends you a text later that day. A line can end in effects too: `bro: Fine. | bro respect +`. (The scene's opening lines can't: effects only happen when you choose.)
- Choices indented under a choice keep the scene going: the lines right before them are the next beat. Up to five deep.
- Outcomes, indented under the choice: after `play <game>` write `great:`, `good:`, `miss:`; after a chance like `60% +athletic` write `yes:` and `no:`; after `vibe <style>` write `good:`, `meh:`, `bad:`. Each is a line, then | effects.
- `memory: <text> (good)` gives you a memory (good, great, bad, awful).

## Effects

Separate with commas. `+` small, `++` medium, `+++` big, `-` `--` `---` down, or a number like `+5`.

- How someone feels about you: `<person> affection +` (or trust, respect, attraction, rivalry, familiarity). `both` at the end for both ways; `my <person> affection +` for how you feel about them.
- You: `mood +`, `energy -`, `fun -`, `social -`, `stress -` (energy, social = not lonely, fun, stress).
- Traits: ambition, competitiveness, confidence, curiosity, discipline, empathy, impulsivity, loyalty, sociability, volatility (also confident, loyal, disciplined...).
- Skills: academics, art, baseball, basketball, drama, fitness, football, music, soccer, softball, sport, tech, writing (`sport` = your main sport). Interests: `into <x> +` with academics, art, baseball, basketball, batting_cage, coding, cooking, drama, fashion, fitness, football, gaming, guitar, journaling, music, outdoors, pickup_games, reading, shows, sketching, soccer, softball, sport, tech, writing.
- Reputation: `rep <tag> +` with athlete, embarrassed, flaky, gossip, host, legend, mean, performer, star, tough, troublemaker. Family: `family affection +` (you and every sibling).
- `play <game>`: `baseball` (a big at-bat, batting practice, a home run derby with friends); `basketball` (shooting around in the driveway, HORSE with a sibling, open gym, a dare from half court); `cup_pong` (a friend's basement, a party (beer pong in college)); `flash` (remembering a pattern, ear training in band, a memory bet); `football` (a goal-line stand at practice, a backyard game, a bet on one play); `golf` (a round with a parent, a golf outing, a bet on one hole); `hold` (a steady pour in chem lab, one brushstroke, a power throw in gym, holding a note (press, hold, let go on the line)); `lineup` (a timeline review, ranking things with friends, putting cards in order); `mathdash` (mental math with a friend, splitting a check, making change at a register job, counting atoms); `oddone` (proofreading a friend's essay, spot the difference, a typo on a sign); `paper_toss` (bored in class, the trash can across the room); `playmaker` (running the offense at the park, a pickup run where you have to find the open man); `reflex` (catching something falling, a reaction test, first hand up, a quick-draw bet); `soccer_11` (a pickup match, gym class, a game where your team needs a goal); `soccer_pk` (penalties at the park, settling an argument, a gym-class shootout); `sweep` (stopping a pendulum, hitting the beat, timing a jump rope, any "tap at the right moment"); `swing_lab` (the batting cages, a hitting lesson); `trivia` (a pop quiz, a study session, trivia night at a restaurant, a bet over who knows more); `sport` = your sport's game.
- `60% +charisma -impulsivity`: a roll on your talents (academic, athletic, charisma, creativity, technical) and traits.
- `vibe <style>`: funny, tease, bold, chill, cheesy, sweet (lands or misses by what they like).
- `focus <mode>` (academics, athletics, balanced, family, rest, romance, social), `hang out with <person>`, `text <person> "<line>"`, `fits loyalty` / `fits -discipline` (who'd pick this when the game picks for you; trait effects count too).

## Texting: flirting and group chats

Flirt lines and group chat conversations go in their own blocks, in any script (on the phone: Phone > Add texting writes the ChatGPT prompt for you). They go live as soon as they're added, alongside the game's own.

### Flirting

Each block is a header line ending in a colon, then its lines under it, indented two spaces, one line each.

- `flirt <style>:` what I can send to start flirting while we're still getting to know each other; `flirt <style> later:` the same, once we're already flirty. Styles: tease, sweet, bold, funny, cheesy.
- `flirt answers <style>, <how it went>:` how they answer a flirt in that style. How it went: lands (they're into it), laughs (they liked it but play it off), awkward, no (they shut it down, kindly).
- `flirt follow-ups <style>:` what I can say next after it landed; `flirt follow-ups <style> after a laugh:` after they laughed it off. Here the style can also be cool (playing it cool).
- `flirt first:` them flirting with me first (`flirt first later:` once we're flirty).
- `flirt back <style>:` what I can answer when they flirt first. Also `flirt back cool:` and `flirt back letdown:` (letting them down easy, kindly).
- `flirt payoff <blush|plans|goodnight|ask>:` how they end it when it really went somewhere: blushing, making plans, going to bed smiling, or telling me to ask them out in person.

```
flirt tease:
  ok who said you could be this funny
flirt answers tease, lands:
  oh so we're doing this 😏
flirt follow-ups bold:
  so are we hanging out or what
flirt payoff plans:
  ok diner friday. you're buying fries
```

### Group chats

```
group chat crew, weekend:
  A: fantasy draft is tonight. who's in
  B: i'm taking the jets defense first
  C: why would you do that
  B: because i believe
  * {B} you're gonna finish last | A +, B -, fun +
      A: LMAO
      B: watch me
      dm B: ok be honest is the jets thing bad
  * i'm in. i'm winning the whole thing | A +, crew +
      C: we'll see about that
  * i'll be the commissioner | crew ++
      A: finally someone responsible
```

- `group chat <crew|team|family>, <when>:` then 3 to 6 lines of them talking to each other, then 2 or 3 things I can say (`* what I say | effects`), each a different kind of answer, with what they say back indented under it.
- crew is my friend group and team is my teammates: they're A, B and C. family is parent, other parent, sibling, other sibling (the game knows which is Mom or Dad).
- when (optional, after a comma): weekend, school day, school night, winter, pet, game tomorrow, after a win, after a loss. Team chats are best around games.
- Effects: who it lands with (`A +`, `B -`, `++` for a lot), `fun +`, `stress -`, `mood +`, `crew +` (the group gets closer), `trust +` (my parents trust me more).
- `dm B: ...` under a reply: that person texts me privately afterward (optional, once in a while).
- In what anyone says, names are {A}, {B}, {C} and {me}; {opp} is the other team and {pet} our pet.

## Lines for the game's pools

A block is a header line and then one entry per line under it (until a blank line or the next header).

- `texts <pool>:` text messages. Pools: `invite` (A friend asks you to hang out); `invite_later` (A friend who asked while you were busy, texting to try again later); `invite_date` (Someone you're dating or into asks you somewhere, just the two of you); `after_good` (A friend, after a good hangout); `after_good_date` (After a good date); `after_awkward` (After a hangout that went badly); `u_ok` (A friend checks on you after something bad happened with {other}); `they_apologize` (Someone apologizes after a fight); `congrats_team` (A friend congratulates you on making {team}); `consolation_cut` (A friend, after you got cut); `congrats_award` (A friend, after you won {event}); `rumor` (A friend tells you people are talking about you); `chatter_partner` (Your boyfriend or girlfriend, a random sweet text); `flirt_in` (Someone with a crush on you flirts); `asked_out` (Someone asks you out (you answer yes or no)); `asked_to_dance` (Someone asks you to {event} (a dance)); `park_followup` (Someone you met at the dog park, about your dog {pet}); `team_pregame` (Team group chat the night before a game); `team_win` (Team group chat after a win); `team_loss` (Team group chat after a loss); `parent_pregame` (Mom or Dad in the family chat before your game); `parent_win` (Mom or Dad after your team won); `parent_loss` (Mom or Dad after a loss); `parent_made_team` (Mom or Dad after you made {team}); `parent_cut` (Mom or Dad after you got cut); `parent_award` (Mom or Dad after you won {event}); `parent_offer` (Mom or Dad after a scholarship offer from {college}); `parent_report_proud` (Mom or Dad after a good report card); `parent_report_worried` (Mom or Dad after a bad report card); `parent_grounded` (Mom or Dad grounding you); `parent_drafted` (Mom or Dad after you got drafted by {team}); `pet_adopted` (Family chat the day a new pet comes home); `pet_chores_set` (A parent confirming your pet chores ({chores})); `pet_you_forgot` (A parent: you forgot a pet chore ({chore_a})); `pet_you_forgot_strict` (A strict parent: you forgot a pet chore); `pet_sibling_forgot` (A parent: a sibling ({who}) forgot a pet chore); `pet_streak` (A parent: the pet's been happy because you've been on it); `pet_sad` (A parent: the pet's been moping); `pet_vet` (A parent: the pet went to the vet); `pet_reminder` (A parent reminding you about a pet chore); `sibling_home` (A brother or sister away at college, coming home); `sibling_leaving` (A brother or sister leaving for college); `sibling_chatter` (A brother or sister, random texts); `coach_starting` (Your coach: you're starting); `coach_bench` (Your coach: you're coming off the bench); `react_warm` (How someone answers your warm reply); `react_funny` (How someone answers your funny reply); `react_dry` (How someone answers your dry reply); `react_flirt_yes` (Someone who's into you, answering your flirt); `react_flirt_no` (Someone who isn't into you, answering your flirt); `react_plans_yes` (Someone saying yes to plans); `react_plans_no` (Someone saying no to plans); `react_parent` (Mom or Dad answering your nice reply); `react_parent_annoyed` (Mom or Dad answering an attitude reply); `reply_hey` (Someone answering your 'hey' (they're glad you texted)); `reply_hey_dry` (Someone answering your 'hey' (meh)); `first_hey` (YOU, texting someone first: just saying hey); `first_hang` (YOU, asking someone to hang out ({place} available)); `first_flirt` (YOU, flirting first); `first_good_luck` (YOU, wishing someone luck before their game); `first_congrats` (YOU, congratulating someone); `first_sorry` (YOU, apologizing); `chatter_plans` (A friend, random text about plans (reply set: chatter_plans)); `chatter_school` (A friend, random text about school (reply set: chatter_school)); `chatter_vent` (A friend venting (reply set: chatter_vent)); `chatter_funny` (A friend texting something funny (reply set: chatter_funny)); `chatter_game` (A friend texting about a game (reply set: chatter_game)); `parent_first_day` (Mom or Dad, the first morning of high school); `friend_first_day` (A friend, the first morning of high school); `hang_talk` (IN PERSON: something they say while you're hanging out at {place} (shows in the story feed)); `date_talk` (IN PERSON: something they say on a date at {place}); `chat_talk` (IN PERSON: something they say when you stop and talk (hallway, lunch, practice)); `awkward_talk` (IN PERSON: something they say when a hangout or date is going badly).
- `replies <set>:` buttons you can answer with, each ending in its tone: `on it (warm)`. Sets: `warm`, `awkward`, `support`, `apology`, `thanks`, `rumor`, `chatter_plans`, `chatter_school`, `chatter_vent`, `chatter_funny`, `chatter_game`, `partner`, `flirt`, `sibling`, `generic`. Tones: `warm` (friendly); `funny` (makes them laugh); `vent` (honest about how you feel); `thanks` (grateful); `forgive` (you let something go); `flirt` (flirty); `dry` (short and flat); `cold` (shuts them down); `sibling_warm` (brother or sister only: affectionate); `sibling_tease` (brother or sister only: teasing).
- `narration <key>:` story-feed lines, like `narration study.focused:` (keys: study, practice_skill, hobby, rest, hang_out and more, each `.focused` / `.distracted`).
- `mods <open|close|talk> <tag>:` openers ("ok so"), closers ("lol") and ways of saying things ("{them_first} {says}, grinning"), for a context: morning, afternoon, evening, late_night, school_day, weekend, summer, high_school, college, new, friend, close, crush, partner, ex, rival, family, parent, sibling, coach, teammate, happy, down, stressed, tired, hurt, you_happy, you_down, you_stressed, from_guy, from_girl, to_guy, to_girl, guys, girls, same_year, older, younger (join with +: close+guys).
- `chat <path>:` texting conversation lines, like `chat reply.greet.warm:`, `chat topic.school:`, `chat people.older_brother.reply.greet.warm:` (lines for one kind of person), `chat ask.general:` (each ends with what it asks: (yesno), (doing), (day), (weekend), (open) or (flirty)).
- `trivia <subject>:` `Question? = right answer | wrong | wrong | wrong (grade 10)`. Subjects: english, biology, chemistry, physics, us_history, world_history, government, spanish, health, art, music, tech, psychology, economics, general.
- `choices <moment>:` more `*` choices on one of the game's own moments (like `choices rumor:`).

## Retiming scenes

`schedule:` (a line on its own inside a storyline) and then one line per scene to retime, from any storyline: `Same Team: Cut day [sophomore · March · after Prom night]`; `[replace]` replaces its after-links, `[skip]` retires it.

A line can retime a whole storyline: `Same Team [freshman · spread]` puts all of it in freshman year, spread out in order (holidays and school days keep their day). Names have to match: a scene or storyline that isn't there is an error, with what it might have meant.

## Writing well

- Real people, real voices: short lines, specific details, how teenagers actually talk. PG-13.
- Every choice should feel different and matter a little. Use `remember` and `if` so later scenes answer earlier choices.
- Let scenes breathe: a couple of lines of setup, talk that goes back and forth, a beat or two deep where it matters.
- Use versions `{a|b}` on lines that come back, and the mini games where they fit.
- `//` starts a comment the game ignores.
