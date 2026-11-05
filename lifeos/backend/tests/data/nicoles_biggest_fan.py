"""A storyline built the way ChatGPT writes them: the outline, twelve clean scenes, then scenes 13 to 18 with the habits
that broke the importer (narration in *italics*, **bold** names, effects after arrows and in parentheses, talk and a
second round of choices after the choices, remember lines at the end of a scene)."""

BASE = "The Twin Sisters: Popularity, Friends, and Family Reputation"
TITLE = f"{BASE}: Nicole's Biggest Fan"

TITLES = ["First Game in the Stands", "The Sign", "Away Game Bus", "Rain Delay", "The Bad Call", "Senior Night Planning",
          "Practice Snacks", "The Rival School", "Homecoming Halftime", "The Injury Scare", "Film Night", "The Comeback",
          "Front Row Seats", "The Banner", "Nicole Hears About It", "The Playoff Crowd", "Losing Together", "Banquet Speech"]
WHEN = ["freshman · September", "", "freshman · October", "", "freshman · November", "", "", "sophomore · September",
        "homecoming", "", "", "sophomore · March · big", "junior · September", "", "", "junior · November · big", "",
        "junior · June · finale"]

OUTLINE = (f"=== {TITLE}\nexpands: {BASE}\ncast: nicole = Nicole Soffer\nyears: freshman-junior\n"
           "about: Zack is Nicole's loudest supporter at every game.\n\noutline:\n"
           + "".join(f"{i}. {t} | {w} | Zack cheers for Nicole." + (' | only if you picked "Front row" in 13' if i == 15 else "") + "\n"
                     for i, (t, w) in enumerate(zip(TITLES, WHEN), 1)))

SCENES_1_12 = "".join(f"""--- {i}. {t}
nicole: You're here again.
* "Wouldn't miss it." | nicole affection +
    nicole: Loudest guy in the bleachers.
* "Mom made me come."
    nicole: Sure she did.

""" for i, t in enumerate(TITLES[:12], 1))

# scenes 13 to 18, as ChatGPT wrote them
SCENES_13_18 = """Here are scenes 13–18!

```
--- 13. Front Row Seats
*The gym is packed. Nicole spots Zack from the court.*
**Nicole:** You got here early.
* "Front row" -> nicole affection +
    nicole: Okay, that's actually sweet.
* "Traffic was light." (nicole affection -)
    nicole: Romantic.
nicole: Are you going to wear the shirt?
* "Obviously." | nicole affection ++
    remember wore_the_shirt
* "It's in the car."
nicole: Whatever. Just be loud.
remember front_row_season

--- 14. The Banner
zack: I made something.
*He unrolls a bedsheet that says NICOLE SOFFER FAN CLUB.*
nicole: Please tell me you didn't.
* "I did. Three coats of paint." | nicole affection +
* "Jennifer helped." | nicole affection +, nicole trust +
    nicole: Of course she did.
nicole: Hang it where I can't see it.

--- 15. Nicole Hears About It
nicole: People are talking about my brother's banner.
* "Good talk or bad talk?"
    nicole: Good. Annoyingly good.
* "I can take it down." | nicole affection -
    nicole: Don't you dare.

--- 16. The Playoff Crowd
nicole: There are like a thousand people here.
* "And I'm the loudest." | nicole affection +, crowd_energy +
* "Breathe. You've got this." | nicole trust +

--- 17. Losing Together
*The final buzzer. Nicole's team loses by two.*
nicole: Don't say anything.
* Sit next to her quietly | nicole trust ++
    nicole: ...Thanks.
    remember sat_after_the_loss
* "You were the best one out there." | nicole affection +
nicole: Next year.
* "Next year." | nicole affection +
* "Front row again."
    remember front_row_again

--- 18. Banquet Speech
nicole: I have to thank people in my speech.
* "Thank me first." | nicole affection +
    nicole: You're third. Mom and Coach first.
* "Don't mention the banner." | nicole affection +
    nicole: Oh, I'm absolutely mentioning the banner.
remember banquet_speech
```
"""

# a scene that can't go in as written (a choice that's only effects, and a line nobody speaks), to show it's reported
BROKEN_16 = """--- 16. The Playoff Crowd
nicole: There are like a thousand people here.
* | nicole affection +
"""
