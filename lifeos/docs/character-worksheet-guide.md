# LIFE OS character worksheet guide

Use this to plan the people in your story (you, your family, your friends, your crush, your rivals, your coaches) before you build them in the app. The story starts on the first day of school at Guilford High School in Guilford, and runs seven years.

You have three ways to do it:

1. **Fill in the Excel worksheet** (`character-worksheet.xlsx`) and load it in the app: My Story, Start your story, Load a cast file.
2. **Talk it through with ChatGPT or Claude.** Paste the prompt below, answer its questions, and save the JSON it gives you as a `.json` file. Load that file the same way.
3. **Mix them.** Talk it through first, then type the numbers into the worksheet.

Anything you leave blank is generated from the person's type, so you only need to decide what matters to you.

## The prompt to paste

````text
You're helping me plan the characters for my LIFE OS story, a life simulation that starts on my first day at Guilford High School in Guilford and runs seven years (high school, then college or work).

Interview me one person at a time: me first, then my family (parents, siblings, a pet if we have one), then the people I want in my story (friends, a crush, rivals, coaches, and younger kids who'll start high school later, like a little brother or the neighbor kid). I can add as many people as I want. For each person, ask a few natural questions about who they are, what they're into and how we know each other, then propose numbers and explain them in one line each. Push back if I make someone great at everything; real people have a couple of clear strengths and a weakness or two. Keep it conversational, not a form.

The fields (all optional except first names; blanks get generated):
- first, last, gender (m/f/nb), pronouns, attracted_to (list of m/f/nb), grade (9-12 on day one; for a younger sibling or anyone still in middle school, 8, 7 or 6: they start high school as a freshman 1, 2 or 3 years in), birthday [month, day], archetype (athlete, artist, scholar, socialite, loner, rebel, leader, techie, performer, caretaker, drifter), bio
- traits 0-100: sociability, confidence, discipline, ambition, impulsivity, empathy, competitiveness, curiosity, volatility, loyalty
- aptitudes 0-100 (natural talent): athletic, academic, creativity, technical, charisma
- motives 0-100: achievement, approval, belonging, pleasure, altruism, mastery
- interests 0-100 and skills 0-100 by id: academics, football, basketball, baseball, soccer, softball, fitness, art, music, robotics, writing, acting (plus hobbies as interests). A typical freshman is 25-50 in a sport. Teams are split: boys play football, basketball, soccer and baseball; girls play basketball, soccer and softball (a girl's baseball turns into softball).
- body: height_in (inches), build (slight/average/athletic/strong); positions per sport (football QB/RB/WR/TE/OL/DL/LB/DB/K, basketball PG/SG/SF/PF/C, baseball and softball P/C/1B/2B/3B/SS/OF, soccer GK/CB/FB/CM/WM/ST); jersey
- look: skin, hair, hair_color, eyes, facial_hair, glasses, freckles (options are in the guide)
- relationships: [{"to": "me" or another person's key, "type": best_friend|close_friend|friend|acquaintance|crush|admirer|mutual_crush|dating|ex|rival|enemy|teammate|neighbor|mentor, "strength": -40..40}], written from that person's side
- siblings: key, twin_of ("me" or another sibling's key), strength (how well we get along, -40..40)
- anyone but me can have a path after high school: {"kind": "work"} or {"college": "uconn", "sport": "basketball"} (colleges: uconn, stanford, ucla, lsu, unc, texas, oklahoma, fsu, miami, michigan, scsu, gateway)
- family: last, guardians (names), style (warm/strict/permissive/distant/overbearing), income (low/middle/high), pet ({"species": "dog", "name": "Buster"}, or null for none)

When we're done, give me the whole thing as one JSON object in exactly this shape, in a single code block, with nothing I'd need to fix by hand:
{"title": "...", "students_per_grade": 12, "protagonist": {...}, "family": {...}, "siblings": [{"key": "S1", ...}], "cast": [{"key": "P1", ...}]}
students_per_grade is how many classmates each grade starts with (6-40, around my people); 12-20 plays smoothly on a phone.
````

## Numbers: what they mean

Every 0-100 number: 50 is average, 70+ stands out, 85+ is rare. Nobody should be high at everything; the interesting people have a few clear strengths and a weakness or two.

### Stable tendencies (traits)

Personality. Changes very slowly (confidence drifts with success and failure).

- **sociability**: Seeks out company; drains faster when alone.
- **confidence**: Willing to risk rejection; overestimates how things went.
- **discipline**: Follows through on practice, study and commitments.
- **ambition**: Wants to get somewhere; values long-term payoffs.
- **impulsivity**: Acts on the moment; adds randomness and risk tolerance.
- **empathy**: Reads others accurately; dislikes cruelty; helps.
- **competitiveness**: Wants to win; forms rivalries with peers at a similar level.
- **curiosity**: Open to new things; enjoys learning.
- **volatility**: Emotional reactivity: bigger swings, quicker to confront.
- **loyalty**: Sticks with people and commitments.

### Natural aptitude (aptitudes)

Innate potential. Sets how fast a skill grows and how high it can go.

- **athletic**: Sports.
- **academic**: Schoolwork and writing.
- **creativity**: Art and music.
- **technical**: Robotics and code.
- **charisma**: Acting and first impressions.

### Motivations (motives)

What this person wants. Multiplied by the global motive weights in the Workshop.

- **achievement**: Grades, teams, winning.
- **approval**: Status and being liked by the crowd.
- **belonging**: Closeness and group membership.
- **pleasure**: Fun now.
- **altruism**: Helping others.
- **mastery**: Getting good at a craft for its own sake.

### Interests and starting skills

Interests (0-100) decide what they choose to do with their time. Skills (0-100) are how good they are on day one; a typical freshman is 25-50 in a sport, varsity seniors are 55-75, and college recruits are higher. Talent (aptitude) sets how fast skills grow and how high they can go.

Skills: `academics`, `football`, `basketball`, `baseball`, `soccer`, `softball`, `drama`, `art`, `music`, `tech`, `writing`, `fitness`

Hobbies (interests only): `gaming`, `reading`, `sketching`, `guitar`, `pickup_games`, `batting_cage`, `shows`, `fashion`, `outdoors`, `coding`, `cooking`, `journaling`

## Starting types

| type | name | typical personality |
|---|---|---|
| `athlete` | Athlete | competitiveness 75, confidence 65, loyalty 62 |
| `artist` | Artist | curiosity 75, empathy 65, volatility 60 |
| `scholar` | Scholar | discipline 75, ambition 75, curiosity 70 |
| `socialite` | Social butterfly | sociability 85, confidence 70, impulsivity 60 |
| `loner` | Loner | curiosity 65, loyalty 60, empathy 55 |
| `rebel` | Rebel | impulsivity 80, volatility 70, confidence 65 |
| `leader` | Leader | ambition 80, confidence 75, sociability 70 |
| `techie` | Builder | curiosity 80, discipline 60, ambition 55 |
| `performer` | Performer | sociability 70, curiosity 65, volatility 65 |
| `caretaker` | Caretaker | empathy 85, loyalty 80, sociability 60 |
| `drifter` | Drifter | impulsivity 55, sociability 50, empathy 50 |

## Sports and positions

- **Football**: `QB` Quarterback, `RB` Running back, `WR` Wide receiver, `TE` Tight end, `OL` Offensive line, `DL` Defensive line, `LB` Linebacker, `DB` Defensive back, `K` Kicker
- **Basketball**: `PG` Point guard, `SG` Shooting guard, `SF` Small forward, `PF` Power forward, `C` Center
- **Baseball**: `P` Pitcher, `C` Catcher, `1B` First base, `2B` Second base, `SS` Shortstop, `3B` Third base, `OF` Outfield
- **Soccer**: `GK` Goalkeeper, `CB` Center back, `FB` Fullback, `CM` Central midfield, `WM` Winger, `ST` Striker
- **Softball**: `P` Pitcher, `C` Catcher, `1B` First base, `2B` Second base, `SS` Shortstop, `3B` Third base, `OF` Outfield

Body matters: height helps in basketball (and for pitchers), build matters in football (`strong` for linemen, `athletic` or `slight` for skill positions). Builds: `slight`, `average`, `athletic`, `strong`.

## Relationship types

Always written from the other person's side, toward the one they point at (`me` = you).

- `twin`: Twin
- `sibling`: Sibling
- `best_friend`: Best friend
- `close_friend`: Close friend
- `friend`: Friend
- `acquaintance`: Know each other
- `crush`: Has a crush on them
- `admirer`: They have a crush on this person
- `mutual_crush`: We like each other
- `dating`: Dating
- `ex`: Ex
- `rival`: Rivals
- `enemy`: Can't stand each other
- `teammate`: Teammates growing up
- `neighbor`: Neighbors
- `mentor`: Looks up to them

## After high school (for anyone but you)

Leave it out to let it play out. `{"kind": "work"}` stays in town. `{"college": "uconn", "sport": "basketball"}` plays a sport there; `{"college": "uconn"}` goes as a student.

Program strength 0-100 by team (blank: no team on that side). A girl's `sport` is her side's team: `basketball` at UConn means women's basketball, and `baseball` for a girl means softball.

| id | college | conference | football | men's basketball | women's basketball | baseball | softball | men's soccer | women's soccer |
|---|---|---|---|---|---|---|---|---|---|
| `uconn` | University of Connecticut | Big East | 58 | 96 | 99 | 78 | 55 | 70 | 62 |
| `stanford` | Stanford University | ACC | 72 | 74 | 88 | 88 | 82 | 84 | 95 |
| `ucla` | University of California, Los Angeles | Big Ten | 76 | 88 | 86 | 86 | 96 | 80 | 92 |
| `lsu` | Louisiana State University | SEC | 90 | 74 | 92 | 95 | 90 |  | 70 |
| `unc` | University of North Carolina | ACC | 76 | 92 | 76 | 87 | 72 | 84 | 98 |
| `texas` | University of Texas at Austin | SEC | 92 | 82 | 90 | 88 | 94 |  | 78 |
| `oklahoma` | University of Oklahoma | SEC | 88 | 72 | 80 | 80 | 99 |  | 62 |
| `fsu` | Florida State University | ACC | 85 | 76 | 80 | 88 | 92 |  | 96 |
| `miami` | University of Miami | ACC | 86 | 78 | 74 | 85 |  |  | 58 |
| `michigan` | University of Michigan | Big Ten | 93 | 82 | 80 | 76 | 86 | 74 | 72 |
| `scsu` | Southern Connecticut State University | NE10 | 40 | 40 | 40 | 40 | 40 | 40 | 40 |
| `gateway` | Gateway Community College |  |  |  |  |  |  |  |  |

## Looks

- **skin**: `porcelain`, `fair`, `light`, `medium`, `tan`, `olive`, `brown`, `deep`
- **hair**: `buzz`, `short`, `crew`, `side_part`, `messy`, `curly_short`, `fade`, `afro`, `bob`, `long_straight`, `long_wavy`, `ponytail`, `bun`, `curly_long`, `braids`, `locs`, `bald`
- **hair_color**: `black`, `dark_brown`, `brown`, `light_brown`, `auburn`, `red`, `strawberry`, `blonde`, `platinum`, `gray`
- **eyes**: `dark_brown`, `brown`, `hazel`, `green`, `blue`, `gray`
- **facial_hair**: `none`, `stubble`, `mustache`, `goatee`, `beard`
- **glasses**, **freckles**: true or false

## The cast file format

This is what the AI should give you back (and what the app saves when you download a cast). Everything except first names is optional.

```json
{
  "title": "The Soffer Years",
  "students_per_grade": 12,
  "protagonist": {
    "first": "Zack",
    "last": "Soffer",
    "gender": "m",
    "grade": 9,
    "archetype": "athlete",
    "attracted_to": [
      "f"
    ],
    "traits": {
      "discipline": 70,
      "competitiveness": 85,
      "sociability": 68
    },
    "aptitudes": {
      "athletic": 82,
      "academic": 55
    },
    "interests": {
      "football": 80,
      "basketball": 78,
      "baseball": 92
    },
    "skills": {
      "football": 42,
      "basketball": 45,
      "baseball": 52
    },
    "body": {
      "height_in": 71,
      "build": "athletic"
    },
    "positions": {
      "football": "WR",
      "basketball": "SG",
      "baseball": "SS"
    },
    "jersey": 2,
    "birthday": [
      4,
      12
    ],
    "look": {
      "hair": "short",
      "hair_color": "brown"
    }
  },
  "family": {
    "last": "Soffer",
    "guardians": [
      "Linda",
      "Rob"
    ],
    "style": "warm",
    "income": "middle",
    "pet": {
      "species": "dog",
      "name": "Buster"
    }
  },
  "siblings": [
    {
      "key": "S1",
      "first": "Mike",
      "gender": "m",
      "grade": 12,
      "archetype": "athlete",
      "interests": {
        "basketball": 88
      },
      "path": {
        "college": "uconn",
        "sport": "basketball"
      },
      "strength": 10
    },
    {
      "key": "S2",
      "first": "Ally",
      "gender": "f",
      "grade": 10
    },
    {
      "key": "S3",
      "first": "Jen",
      "gender": "f",
      "grade": 10,
      "twin_of": "S2"
    }
  ],
  "cast": [
    {
      "key": "P1",
      "first": "Danny",
      "last": "Kim",
      "gender": "m",
      "grade": 9,
      "archetype": "athlete",
      "relationships": [
        {
          "to": "me",
          "type": "best_friend"
        }
      ]
    },
    {
      "key": "P2",
      "first": "Sophie",
      "last": "Lane",
      "gender": "f",
      "grade": 9,
      "relationships": [
        {
          "to": "me",
          "type": "mutual_crush"
        }
      ]
    }
  ]
}
```
