// Story: where you are, what's happening, and what you do next. The heart of the phone app.
import React, { useEffect, useRef, useState } from "react";
import { useStore } from "../store";
import MiniGame, { MGConfig, MGResult } from "../minigames/MiniGame";
import { Chip, Choice, DaySlot, FeedItem, Line, MiniGameRow, Moment, phoneApi, pgo, PlateItem, Today, UpNext, WeekDay } from "./api";
import { Portrait, Scene } from "./art";
import { PIcon } from "./icons";
import { buzz, cx, errText, Face, Lines, money, Sheet, StatChips, Talk, useWho } from "./kit";
import { usePhone } from "./PhoneContext";
import { SetupNudge } from "./Editor";

const KICKER: Record<string, string> = {
  first_day: "New chapter", cut: "Tryouts", injury: "Injury", benched: "Playing time", offer: "Recruiting", college_decision: "The big decision",
  game_day: "Game day", sibling_leaves: "Family", rumor: "People are talking", heartbreak: "Heartbreak", summer: "Summer", graduation: "Graduation",
  college_arrival: "New chapter", year_review: "Looking back", asked_out: "Romance", asked_to_dance: "Romance", mlb_draft: "MLB Draft",
  draft_passed: "MLB Draft", story_end: "The end of the beginning", class_quiz: "Class", class_game: "In class",
};
// the result banner: class games read like class, sports like sports
const CLASS_GAMES = new Set(["trivia", "hold", "sweep", "mathdash", "flash", "oddone", "lineup", "reflex"]);
const mgHead = (game: string, tier: string) =>
  CLASS_GAMES.has(game) ? (tier === "great" ? "Nailed it." : tier === "good" ? "Not bad." : "Rough one.") : tier === "great" ? "Clutch." : tier === "good" ? "Solid." : "Not your day.";
const CAT: Record<string, string> = {
  social: "Friends", romance: "Romance", academic: "School", conflict: "Drama", leisure: "Downtime", family: "Family", activity: "Getting better",
  obligation: "Commitments", achievement: "Big moves", risk: "Risky", staff: "Mentoring",
};
const ACTION_ICON: Record<string, string> = {
  study: "book", study_at_lunch: "book", practice_skill: "ball", train: "bolt", hobby: "sparkle", rest: "moon", sit_alone: "moon",
  attend_practice: "ball", attend_event: "star", work_shift: "work", sign_up: "star", quit_group: "x", sneak_out: "moon", prank: "warn",
  family_time: "home", pet_time: "paw", pet_walk: "walk", pet_park: "tree", pet_play: "ballplay", pet_train: "wand", throw_party: "sparkle",
  go_to_party: "sparkle", spectate: "trophy", confront: "bolt", spread_rumor: "chat", gossip: "chat", chat_online: "chat",
};
const CAT_ICON: Record<string, string> = { social: "people", romance: "heart", academic: "book", conflict: "bolt", leisure: "moon", family: "home",
  activity: "ball", obligation: "clock", achievement: "star", risk: "warn", staff: "people" };
const PERSON_KEYS = ["them", "other", "sibling", "roommate", "coach", "origin", "best_friend"];

type Outcome = { lines: Line[]; chips: Chip[]; title?: string; mg?: { tier: string; score: number; max: number; game?: string; summary?: string } };
type Playing = { cfg: MGConfig; m?: Moment; index?: number };

export default function StoryTab() {
  const { state, refresh, toast, setBusy: setGlobalBusy } = usePhone();
  const lab = useStore();
  const [choices, setChoices] = useState<Choice[] | null>(null);
  const [atPractice, setAtPractice] = useState<{ first: string; what: string }[]>([]);
  const [choiceKey, setChoiceKey] = useState("");
  const [more, setMore] = useState(false);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [recap, setRecap] = useState<FeedItem[] | null>(null);
  const [skip, setSkip] = useState<{ done: number; days: number } | null>(null);
  const [between, setBetween] = useState<{ days: number; feed: FeedItem[] } | null>(null);
  const [upNext, setUpNext] = useState<UpNext | null>(null);
  const [upOpen, setUpOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [showToday, setShowToday] = useState(false);
  const [playing, setPlaying] = useState<Playing | null>(null);
  const [games, setGames] = useState<MiniGameRow[] | null>(null);
  const [today, setToday] = useState<Today | null>(null);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; };
  }, []);

  const key = state ? `${state.day}:${state.scene.phase}:${state.last_event}` : "";
  const wantChoices = !!state && state.decision_ready && state.moments.length === 0;

  useEffect(() => {
    if (!wantChoices || choiceKey === key) return;
    let off = false;
    setChoiceKey(key);
    setChoices(null);
    setMore(false);
    phoneApi.choices().then((r) => {
      if (!off) setChoices(r.ready ? r.options || [] : []);
      if (!off) setAtPractice(r.busy || []);
    }).catch((e) => !off && toast(errText(e), "bad"));
    return () => { off = true; };
  }, [wantChoices, key]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!wantChoices) return;
    phoneApi.minigames().then((r) => setGames(r.games)).catch(() => setGames(null));
  }, [wantChoices, key]);

  // your day at a glance: the parts of today, what needs you, the week ahead
  const loadToday = () => phoneApi.today().then(setToday).catch(() => setToday(null));
  useEffect(() => {
    if (state?.active) loadToday();
  }, [key, state?.unread, state?.needs_reply]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!state) return null;
  const s = state;
  const moment = s.moments[0];
  const run = async (fn: () => Promise<void>) => {
    if (busy) return;
    setBusy(true);
    setGlobalBusy(true);
    try {
      await fn();
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      if (alive.current) setBusy(false);
      setGlobalBusy(false);
    }
  };

  const later = (c: Choice) => run(async () => {
    buzz();
    const r = await phoneApi.later(c.index);
    toast(r.note, "good");
    await refresh();
    loadToday();
  });

  const choose = (c: Choice) => run(async () => {
    buzz();
    const r = await phoneApi.choose(c.index, c.crew, c.act);
    setChoices(null);
    setOutcome({ lines: r.lines.length ? r.lines : [{ id: -1, type: "none", text: "The time slips by. Nothing much to report." }], chips: r.chips, title: c.text });
    await refresh();
  });

  const pickMoment = (m: Moment, index: number | null) => run(async () => {
    buzz();
    setBetween(null);
    const r = await phoneApi.moment(m.id, index);
    if (r.minigame) {  // you play this one yourself
      setPlaying({ cfg: r.minigame, m, index: index ?? undefined });
      return;
    }
    setOutcome({ lines: r.lines, chips: r.chips, title: m.title });
    await refresh();
  });

  // Continue story: the next storyline scene now, without moving the calendar
  const continueStory = () => run(async () => {
    buzz();
    const r = await phoneApi.storyContinue();
    if (!r.moment) toast(r.note || "Nothing else is ready today.", "good");
    await refresh();
  });

  const playFree = (g: MiniGameRow) => run(async () => {
    buzz();
    setPlaying({ cfg: await phoneApi.minigameStart(g.id) });
  });

  const finishPlay = (res: MGResult) => {
    const p = playing;
    setPlaying(null);
    if (!p) return;
    run(async () => {
      if (p.m) {
        const r = await phoneApi.moment(p.m.id, p.index ?? null, { session: p.cfg.session, score: res.score, max: res.max, stats: res.stats });
        setOutcome({ lines: r.lines, chips: r.chips, title: p.m.title, mg: r.minigame && { ...r.minigame, summary: res.summary } });
      } else {
        const r = await phoneApi.minigameFinish(p.cfg.session, res.score, res.max, res.stats);
        const lines = r.rewarded ? r.lines : [...r.lines, { id: -2, type: "note", text: "You already got your practice in today. This one was just for fun." }];
        setOutcome({ lines, chips: r.chips, title: p.cfg.title, mg: r.result && { ...r.result, summary: res.summary } });
        phoneApi.minigames().then((x) => setGames(x.games)).catch(() => undefined);
      }
      await refresh();
    });
  };

  const quitPlay = () => {
    const p = playing;
    setPlaying(null);
    if (!p) return;
    if (p.m) {
      if (window.confirm("Stop here and let the game decide how it went?")) {
        run(async () => {
          const r = await phoneApi.moment(p.m!.id, p.index ?? null, { auto: true });
          setOutcome({ lines: r.lines, chips: r.chips, title: p.m!.title });
          await refresh();
        });
      }
    } else phoneApi.minigameQuit().catch(() => undefined);
  };

  const next = () => run(async () => {
    const j = await phoneApi.advance("decision");
    if (j.status === "failed") throw new Error(j.error || "the day didn't load");
    await refresh();
  });

  const skipAhead = () => run(async () => {
    const before = s.last_event;
    let j = await phoneApi.advance("moment");
    setSkip({ done: j.done || 0, days: j.days || 0 });
    while (j.status === "running") {
      await new Promise((r) => setTimeout(r, 600));
      j = await phoneApi.job();
      if (alive.current) setSkip({ done: j.done || 0, days: j.days || 0 });
    }
    setSkip(null);
    if (j.status === "failed") throw new Error(j.error || "something went wrong while time passed");
    const st = await phoneApi.state(before);
    setRecap(st.feed.slice().reverse());
    await refresh();
    lab.refresh();
  });

  // Episodes back to back: your life plays itself up to the next storyline scene, and you see what happened in between
  const binge = !!s.control?.binge;
  const nextEpisode = () => run(async () => {
    buzz();
    const before = s.last_event;
    let j = await phoneApi.advance("episode");
    setSkip({ done: j.done || 0, days: j.days || 0 });
    while (j.status === "running") {
      await new Promise((r) => setTimeout(r, 500));
      j = await phoneApi.job();
      if (alive.current) setSkip({ done: j.done || 0, days: j.days || 0 });
    }
    setSkip(null);
    if (j.status === "failed") throw new Error(j.error || "something went wrong while time passed");
    const st = await phoneApi.state(before);
    const days = Math.max(0, (j.end_day ?? 0) - (j.start_day ?? 0));
    setBetween(days > 0 || st.feed.length ? { days, feed: st.feed.slice().reverse() } : null);
    if (j.stop === "time") toast(`No storyline scene in the next two months${j.why ? ` (${j.why})` : ""}. Tap again to keep going, or see Me > Story schedule.`, "bad");
    if (j.stop === "nothing_left") toast(`None of your storyline scenes can come right now${j.why ? ` (${j.why})` : ""}. Me > Story schedule shows why.`, "bad");
    if (j.stop === "end") toast("That's your whole story.", "good");
    await refresh();
    lab.refresh();
  });
  const setBinge = (on: boolean) => run(async () => {
    buzz();
    await phoneApi.control({ binge: on });
    setBetween(null);
    await refresh();
  });
  const startBinge = async () => {
    await setBinge(true);
    if (!moment) nextEpisode();
  };
  // Up next: the coming episodes in order, and yours to rearrange
  const openUpNext = () => run(async () => {
    setUpOpen(true);
    setUpNext(null);
    setUpNext(await phoneApi.order());
  });
  const moveEp = (sid: string, before: string) => run(async () => {
    buzz();
    const r = await phoneApi.orderMove(sid, before);
    setUpNext(r);
    if (r.note) toast(r.note, r.note.startsWith("Heads up") ? "bad" : "good");
  });
  const clearOrder = (sid?: string) => run(async () => {
    buzz();
    setUpNext(await phoneApi.orderClear(sid));
  });
  const playNext = async (sid: string, title: string) => {
    let ok = false;
    await run(async () => {
      buzz();
      await phoneApi.orderNext(sid);
      ok = true;
      setUpOpen(false);
      toast(moment ? `“${title}” is next, right after this one.` : `Up next: “${title}”.`, "good");
    });
    if (!ok) return;
    if (binge && !moment) nextEpisode();
    else refresh();
  };
  const afterOutcome = () => {
    setOutcome(null);
    if (binge && !s.moments.length) nextEpisode();
  };

  const todayFeed = s.feed.filter((f) => f.date === s.date);
  // your free time, sorted by what kind of thing it is: with friends, on your own, going somewhere (the trouble is under More)
  const groups = (["people", "solo", "out", "trouble"] as const).map((g) => ({ g, list: (choices || []).filter((c) => (c.section || "solo") === g) }));
  const shown = groups.map(({ g, list }) => ({ g, list: more ? list : g === "trouble" ? [] : varied(list, g === "people" ? 4 : g === "solo" ? 3 : 2) }));
  const hidden = groups.reduce((n, { list }, i) => n + list.length - shown[i].list.length, 0);
  const freeTitle = { lunch: "Lunch", after_school: "After school", evening: "Tonight", day: s.scene.weekend ? "Your day" : "Today" }[s.scene.phase] || "Free time";

  return (
    <div className="ph-story">
      <div className={cx("ph-hero", moment && "compact")}>
        <Scene art={s.scene.art} season={s.scene.season} phase={s.scene.phase} className="ph-hero-art" />
        <div className="ph-hero-fade" />
        <TopBar />
        <div className="ph-hero-text" key={key}>
          <div className="ph-kicker">{s.scene.time}{s.scene.break ? ` · ${s.scene.break}` : ""}</div>
          <h1>{s.scene.title}</h1>
          {!moment && <p>{s.scene.line}</p>}
        </div>
      </div>

      <div className="ph-pad ph-story-b">
        {today && !binge && <DayStrip strip={today.strip} />}
        {!moment && !skip && !binge && <SetupNudge />}
        {binge && !skip && (
          <div className="ph-binge-bar">
            <span><PIcon name="story" size={14} /> Episodes, back to back</span>
            <button className="ph-link" onClick={openUpNext} disabled={busy}>Up next</button>
            <button className="ph-link" onClick={() => setBinge(false)} disabled={busy}>Day by day</button>
          </div>
        )}
        {binge && between && !skip && <Between b={between} onAll={() => setRecap(between.feed)} />}
        {!binge && s.queued && (
          <div className="ph-planned"><PIcon name="clock" size={16} /> Planned: {s.queued.label}</div>
        )}
        {today && !moment && !skip && !binge && <Plate items={today.plate} />}
        {today && !moment && !skip && !binge && <Week days={today.week} />}

        {skip ? (
          <SkipProgress done={skip.done} />
        ) : moment ? (
          <MomentCard m={moment} more={s.moments.length - 1} busy={busy} onPick={pickMoment} />
        ) : binge ? (
          <div className="ph-binge">
            <div className="ph-kicker">Episodes, back to back</div>
            <button className="ph-btn primary block big" onClick={nextEpisode} disabled={busy}>
              {busy ? <span className="ph-spinner small light" /> : <>Next episode <PIcon name="chevron" size={18} /></>}
            </button>
            <small className="ph-dim">{s.stories?.played ? `${s.stories.played} played so far. ` : ""}Your life plays itself in between: practices, games, classes and plans. Your character decides those; the scenes wait for you.</small>
            <button className="ph-link center" onClick={() => setBinge(false)} disabled={busy}>Back to living day by day</button>
          </div>
        ) : s.decision_ready ? (
          <div className="ph-choices">
            <div className="ph-free-h">
              <div className="ph-kicker">Free time</div>
              <b>{freeTitle}: pick one thing</b>
              <small>Texting doesn't use up your time. Text anyone, anytime, from the Phone tab.</small>
            </div>
            {choices === null ? (
              <div className="ph-choice ghost-load"><span className="ph-spinner small" /> Thinking it over…</div>
            ) : choices.length === 0 ? (
              <button className="ph-btn primary block" onClick={next} disabled={busy}>Keep going</button>
            ) : (
              <>
                {shown.map(({ g, list }) => list.length > 0 && (
                  <div key={g} className={cx("ph-cgroup", "g-" + g)}>
                    <div className="ph-cgroup-t">{{ people: "With friends", solo: "On your own", out: "Go somewhere", trouble: "Stir things up" }[g]}</div>
                    {g === "people" && atPractice.length > 0 && <div className="ph-busy-line">{busyLine(atPractice)}</div>}
                    {list.map((c, i) => <ChoiceCard key={c.key || c.index} c={c} gut={!!c.gut} busy={busy} onPick={choose} onLater={later} delay={i} />)}
                  </div>
                ))}
                {hidden > 0 && !more && (
                  <button className="ph-more" onClick={() => setMore(true)}>More options ({hidden})</button>
                )}
                <button className="ph-link center" onClick={next} disabled={busy}>Let it play out</button>
              </>
            )}
            {games && games.some((g) => g.available) && (
              <div className="ph-play">
                <div className="ph-play-t">Or play something</div>
                <div className="ph-play-row">
                  {games.filter((g) => g.available).map((g) => (
                    <button key={g.id} className="ph-play-c" disabled={busy} onClick={() => playFree(g)}>
                      <span className="ph-icon-bubble"><PIcon name={g.icon} size={20} /></span>
                      <b>{g.label}</b>
                      <small>{g.rewarded_today ? "played today" : g.best ? `best ${Math.round(g.best * 100)}%` : g.title}</small>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="ph-next">
            {s.committed && (
              <div className="ph-committed">
                <PIcon name={s.committed.kind === "practice" ? "ball" : s.committed.kind === "show" ? "star" : "trophy"} size={20} />
                <span><b>{s.committed.kind === "practice" ? "Practice" : s.committed.kind === "show" ? "Showtime" : "Game time"}</b>
                  <small>{s.committed.label}. It's not optional, you just go. Your free time is lunch and tonight.</small></span>
              </div>
            )}
            <button className="ph-btn primary block big" onClick={next} disabled={busy}>
              {busy ? <span className="ph-spinner small light" /> : <>What's next <PIcon name="chevron" size={18} /></>}
            </button>
          </div>
        )}

        {!skip && !moment && !binge && (s.stories?.waiting ?? 0) > 0 && (
          <button className="ph-continue" onClick={continueStory} disabled={busy}>
            <PIcon name="story" size={18} />
            <span><b>Continue story</b><small>{s.stories!.waiting} more scene{s.stories!.waiting === 1 ? "" : "s"} today. Play the next one now, or they'll come up through the day.</small></span>
            <PIcon name="chevron" size={18} />
          </button>
        )}

        {!skip && !moment && !binge && (
          <button className="ph-skip" onClick={skipAhead} disabled={busy}>
            <PIcon name="skip" size={16} />
            <span><b>Live until something happens</b><small>Your life plays out on its own until there's something for you.</small></span>
          </button>
        )}
        {!skip && !moment && !binge && (
          <button className="ph-skip ph-binge-on" onClick={startBinge} disabled={busy}>
            <PIcon name="story" size={16} />
            <span><b>Play episodes back to back</b><small>Just the story: one scene after another, with your life playing itself in between.</small></span>
          </button>
        )}

        <div className="ph-today">
          <button className="ph-today-h" onClick={() => setShowToday(!showToday)}>
            <span>{todayFeed.length ? "Today so far" : "Recently"}</span>
            <span className="ph-dim">{showToday ? "Hide" : `${(todayFeed.length || Math.min(6, s.feed.length))}`}</span>
          </button>
          {showToday && (
            <div className="ph-feed">
              {(todayFeed.length ? todayFeed : s.feed.slice(0, 6)).map((f) => <FeedRow key={f.id} f={f} />)}
              {!s.feed.length && <div className="ph-dim">Nothing yet. Your story is just starting.</div>}
            </div>
          )}
        </div>
      </div>

      <Sheet open={!!outcome} onClose={() => setOutcome(null)} title={outcome?.title} className="ph-outcome">
        {outcome && (
          <>
            {outcome.mg && (
              <div className={cx("ph-mg-result", outcome.mg.tier)}>
                <b>{mgHead(outcome.mg.game || "", outcome.mg.tier)}</b>
                <span>{CLASS_GAMES.has(outcome.mg.game || "") && outcome.mg.summary ? outcome.mg.summary
                  : outcome.mg.score % 1 === 0 && outcome.mg.max <= 20 ? `${outcome.mg.score} of ${outcome.mg.max}` : `${Math.round((outcome.mg.score / outcome.mg.max) * 100)}%`}</span>
              </div>
            )}
            <Lines lines={outcome.lines} />
            <StatChips chips={outcome.chips} />
            <button className="ph-btn primary block" onClick={afterOutcome}>
              {binge && !s.moments.length ? <>Next episode <PIcon name="chevron" size={16} /></> : "Continue"}
            </button>
          </>
        )}
      </Sheet>

      <Sheet open={upOpen} onClose={() => setUpOpen(false)} title="Up next" className="ph-upnext">
        <UpNextList d={upNext} busy={busy} onMove={moveEp} onNext={playNext} onClear={clearOrder} />
      </Sheet>

      {playing && <MiniGame config={playing.cfg} onDone={finishPlay} onQuit={quitPlay} />}

      <Sheet open={!!recap} onClose={() => setRecap(null)} title="While you were living it" className="ph-recap">
        {recap && (
          <>
            {recap.length === 0 ? <p className="ph-dim">A quiet stretch. Nothing worth writing home about.</p> : (
              <div className="ph-feed">
                {recap.slice(-30).map((f) => <FeedRow key={f.id} f={f} showDate />)}
                {recap.length > 30 && <div className="ph-dim ph-center">…and {recap.length - 30} more things before that.</div>}
              </div>
            )}
            <button className="ph-btn primary block" onClick={() => setRecap(null)}>Got it</button>
          </>
        )}
      </Sheet>
    </div>
  );
}

function TopBar() {
  const { state } = usePhone();
  if (!state) return null;
  const me = state.me;
  const energy = me.needs?.energy ?? me.energy ?? 50;
  const moodWord = me.mood >= 75 ? "great" : me.mood >= 58 ? "good" : me.mood >= 42 ? "okay" : me.mood >= 28 ? "low" : "rough";
  return (
    <div className="ph-topbar">
      <div className="ph-glass">
        <b>{state.weekday.slice(0, 3)}</b>
        <span>{state.date.replace(/^\w+,\s*/, "")}</span>
      </div>
      <div className="ph-topbar-r">
        <div className="ph-glass" title={`Energy ${energy}`}>
          <PIcon name="bolt" size={14} />
          <span className="ph-mini"><i style={{ width: `${energy}%` }} className={energy < 30 ? "low" : ""} /></span>
        </div>
        <div className={cx("ph-glass", "mood-" + moodWord)} title="Mood">{moodWord}</div>
        <div className="ph-glass"><PIcon name="cash" size={14} /> {money(me.money)}</div>
      </div>
    </div>
  );
}

/** The first few choices of a group, mixed: one of each kind before a second "Sit with someone". */
/** "Danny and Cole have practice." Who's not around right now, so it makes sense why they're not options. */
function busyLine(b: { first: string; what: string }[]) {
  const names = b.map((x) => x.first);
  const who = names.length > 2 ? `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}` : names.join(" and ");
  const what = b.every((x) => x.what === "game") ? "a game" : b.every((x) => x.what === "show") ? "a show" : "practice";
  return `${who} ${names.length === 1 ? "has" : "have"} ${what}.`;
}

function varied(list: Choice[], n: number): Choice[] {
  const out: Choice[] = [];
  const seen = new Set<string>();
  for (const c of list) {
    if (out.length >= n) break;
    if (!seen.has(c.action)) { out.push(c); seen.add(c.action); }
  }
  for (const c of list) {
    if (out.length >= n) break;
    if (!out.includes(c)) out.push(c);
  }
  return list.filter((c) => out.includes(c));
}

function ChoiceCard({ c, gut, busy, onPick, onLater, delay = 0, small }: { c: Choice; gut?: boolean; busy: boolean; onPick: (c: Choice) => void;
  onLater?: (c: Choice) => void; delay?: number; small?: boolean }) {
  return (
    <div className="ph-choice-wrap">
    <button className={cx("ph-choice", small && "compact", "cat-" + c.category)} disabled={busy} onClick={() => onPick(c)} style={{ animationDelay: `${delay * 60}ms` }}>
      <span className={cx("ph-choice-i", c.crew && "crew")}>
        {c.crew && c.target ? (
          <span className="ph-crew-faces">{[c.target, ...c.crew].slice(0, 3).map((id) => <Face key={id} id={id} size={small ? 26 : 30} />)}</span>
        ) : c.target ? <Face id={c.target} size={small ? 34 : 42} /> : <span className="ph-icon-bubble"><PIcon name={ACTION_ICON[c.action] || CAT_ICON[c.category] || "star"} size={small ? 18 : 21} /></span>}
      </span>
      <span className="ph-choice-m">
        <b>{c.text}</b>
        <span className="ph-choice-s">
          {c.group === "should" && <em className="needs">needs you</em>}
          {c.who ? `${c.reason} · ${c.who}` : c.reason || CAT[c.category] || c.category}
          {c.risk >= 0.3 && c.reason !== "Risky" && <em className="risky">risky</em>}
          {gut && <em className="gut"><PIcon name="sparkle" size={11} /> your gut</em>}
        </span>
      </span>
      <PIcon name="chevron" size={18} className="ph-choice-c" />
    </button>
    {c.later && onLater && (
      <button className="ph-later" disabled={busy} onClick={() => onLater(c)}><PIcon name="clock" size={13} /> {c.later}</button>
    )}
    </div>
  );
}

// ---------------------------------------------------------------- your day at a glance

function DayStrip({ strip }: { strip: DaySlot[] }) {
  return (
    <div className="ph-day" role="list" aria-label="Today">
      {strip.map((d) => (
        <div key={d.phase} role="listitem" title={d.plan || undefined}
          className={cx("ph-slot", d.state, d.state === "later" && d.decide && d.note === "open" && "open", d.kind && "k-" + d.kind)}>
          <PIcon name={d.state === "done" ? "check" : d.icon} size={16} />
          <b>{d.label}</b>
          <small>{d.note || (d.state === "done" ? "done" : "")}</small>
        </div>
      ))}
    </div>
  );
}

function Plate({ items }: { items: PlateItem[] }) {
  const [all, setAll] = useState(false);
  const list = all ? items : items.slice(0, 4);
  return (
    <div className="ph-plate">
      <div className="ph-section-t ph-plate-h">On your plate {items.length > 0 && <em>{items.length} thing{items.length === 1 ? "" : "s"}</em>}</div>
      {items.length === 0 ? (
        <div className="ph-caught"><PIcon name="check" size={16} /> You're all caught up.</div>
      ) : (
        <div className="ph-card ph-plate-list">
          {list.map((it) => (
            <button key={it.id} className={cx("ph-plate-row", "k-" + it.kind)} disabled={!it.go} onClick={() => it.go && pgo(it.go)}>
              <span className="ph-plate-i"><PIcon name={it.icon} size={16} /></span>
              <span className="ph-plate-m"><b>{it.title}</b><small>{it.sub}</small></span>
              {it.go && it.cta && <span className="ph-plate-go">{it.cta}</span>}
            </button>
          ))}
          {items.length > 4 && !all && <button className="ph-link center" onClick={() => setAll(true)}>Show all {items.length}</button>}
        </div>
      )}
    </div>
  );
}

function Week({ days }: { days: WeekDay[] }) {
  const [open, setOpen] = useState<number | null>(null);
  const sel = open === null ? null : days[open];
  return (
    <div className="ph-week-wrap">
      <div className="ph-section-t">This week</div>
      <div className="ph-week">
        {days.map((d) => (
          <button key={d.n} className={cx("ph-wd", d.n === 0 && "today", open === d.n && "sel", !d.school && "off")} onClick={() => setOpen(open === d.n ? null : d.n)}
            aria-label={`${d.date}: ${d.items.map((i) => i.label).join(", ") || "nothing planned"}`}>
            <small>{d.n === 0 ? "TODAY" : d.dow}</small>
            <b>{d.num}</b>
            <span className="ph-wd-i">{d.items[0] ? <PIcon name={d.items[0].icon} size={13} /> : null}{d.items.length > 1 && <i>+{d.items.length - 1}</i>}</span>
          </button>
        ))}
      </div>
      {sel && (
        <div className="ph-wd-detail">
          <b>{sel.date}</b>
          {sel.items.length ? sel.items.map((i, k) => <span key={k}><PIcon name={i.icon} size={13} /> {i.label}</span>) : <span className="ph-dim">Nothing on the calendar.{sel.school ? " A normal school day." : ""}</span>}
        </div>
      )}
    </div>
  );
}

export function MomentCard({ m, more, busy, onPick }: { m: Moment; more: number; busy: boolean; onPick: (m: Moment, i: number | null) => void }) {
  const who = useWho();
  const pid = PERSON_KEYS.map((k) => m.ctx?.[k]).find((v) => typeof v === "string" && who(v));
  const person = pid ? who(pid) : null;
  const mood = m.kind === "asked_out" || m.kind === "asked_to_dance" ? "flirty" : m.kind === "heartbreak" || m.kind === "cut" ? "sad" : m.kind === "rumor" ? "surprised" : "neutral";
  return (
    <div className={cx("ph-moment", "k-" + m.kind)}>
      <div className="ph-moment-k">
        {m.episode_label || m.storyline || (m.kind === "class_game" && m.ctx?.class_name ? `${m.ctx.period} · ${m.ctx.class_name}` : KICKER[m.kind]) || "A moment"}
        {more > 0 && <span> · {more} more after this</span>}
      </div>
      {m.episode_label && m.storyline && <div className="ph-moment-series">{m.storyline}</div>}
      {person && (
        <div className="ph-moment-who">
          <Portrait look={person.look} size={88} mood={mood as any} color={person.color} name={person.first} />
          <span>{person.name}</span>
        </div>
      )}
      <h2>{m.title}</h2>
      {m.previously && <p className="ph-moment-prev">{m.previously}</p>}
      <Talk className="ph-moment-t" text={m.text} />
      <div className="ph-moment-c">
        {m.choices.map((c, i) => (
          <button key={i} className={cx("ph-mchoice", c.game && "is-game")} disabled={busy} onClick={() => onPick(m, i)} style={{ animationDelay: `${i * 70}ms` }}>
            {c.game && (
              <span className="ph-mgame"><PIcon name="skip" size={12} /> Play · {c.game.title}</span>
            )}
            <b>{c.label}</b>
            {c.hint && <span>{c.hint}</span>}
          </button>
        ))}
      </div>
      {m.choices.length > 1 && (
        <button className="ph-link center" disabled={busy} onClick={() => onPick(m, null)}>Let it happen</button>
      )}
    </div>
  );
}

/** The next episodes in the order they'll come. Move one up or down, or play one that's ready next. */
function UpNextList({ d, busy, onMove, onNext, onClear }: {
  d: UpNext | null; busy: boolean; onMove: (sid: string, before: string) => void; onNext: (sid: string, title: string) => void;
  onClear: (sid?: string) => void;
}) {
  if (!d) return <div className="ph-choice ghost-load"><span className="ph-spinner small" /> Playing it forward…</div>;
  const when = (n: number, date: string) => n <= 0 ? "Today" : n === 1 ? "Tomorrow" : n < 14 ? `In ${n} days · ${date.replace(/, \d{4}$/, "")}` : date.replace(/, \d{4}$/, "");
  return (
    <div className="ph-up">
      <p className="ph-dim small">About when each one comes, your character answering the ones before it. Move one up and the one it passes waits for it.</p>
      {d.now && <div className="ph-up-now"><b>Now</b> {d.now.title}</div>}
      {d.list.length === 0 && <p className="ph-dim">Nothing else is coming up. Me &gt; Story schedule shows what's waiting and why.</p>}
      {d.list.map((r, i) => (
        <div key={r.sid} className={cx("ph-up-row", (r.importance === "major" || r.importance === "finale") && "big")}>
          <span className="ph-up-n">{i + 1}</span>
          <div className="ph-up-t">
            <b>{r.title}</b>
            <small>{r.storyline}</small>
            <small className="ph-up-when">{when(r.in_days, r.date)}{r.waits_for.length > 0 && ` · after “${r.waits_for[0]}”`}</small>
            {r.ready && i > 0 && <button className="ph-up-go" disabled={busy} onClick={() => onNext(r.sid, r.title)}>Play next</button>}
          </div>
          <div className="ph-up-arrows">
            <button aria-label="Move up" disabled={busy || i === 0} onClick={() => onMove(r.sid, d.list[i - 1].sid)}><PIcon name="chevron" size={18} className="up" /></button>
            <button aria-label="Move down" disabled={busy || i === d.list.length - 1} onClick={() => onMove(d.list[i + 1].sid, r.sid)}><PIcon name="chevron" size={18} className="down" /></button>
          </div>
        </div>
      ))}
      {d.changes.length > 0 && (
        <div className="ph-up-changes">
          <div className="ph-kicker">Your changes</div>
          {d.changes.map((c) => (
            <div key={c.sid} className="ph-up-change">
              <span>“{c.title}” waits for {c.waits_for.map((x) => `“${x.title}”`).join(" and ")}</span>
              <button className="ph-link" disabled={busy} onClick={() => onClear(c.sid)}>Undo</button>
            </div>
          ))}
          <button className="ph-link center" disabled={busy} onClick={() => onClear()}>Back to the story's own order</button>
        </div>
      )}
    </div>
  );
}

/** Between episodes: how long it was and the biggest things that happened, with everything one tap away. */
function Between({ b, onAll }: { b: { days: number; feed: FeedItem[] }; onAll: () => void }) {
  // what happened to you, ahead of the class games and small moments your character answered along the way
  const real = b.feed.filter((f) => f.type !== "moment");
  const top = (real.length ? real : b.feed).slice().sort((x, y) => y.importance - x.importance).slice(0, 3).sort((x, y) => x.id - y.id);
  const when = b.days === 0 ? "Later that day" : b.days === 1 ? "The next day" : b.days < 14 ? `${b.days} days later` : b.days < 60 ? `${Math.round(b.days / 7)} weeks later` : `${Math.round(b.days / 30)} months later`;
  return (
    <div className="ph-between">
      <div className="ph-between-h"><PIcon name="clock" size={14} /> <b>{when}</b></div>
      {top.map((f) => <p key={f.id}>{f.text}</p>)}
      {b.feed.length > top.length && <button className="ph-link" onClick={onAll}>Everything that happened ({b.feed.length})</button>}
    </div>
  );
}

function SkipProgress({ done }: { done: number }) {
  return (
    <div className="ph-skipping">
      <div className="ph-skipping-orb"><PIcon name="clock" size={26} /></div>
      <b>Living it out…</b>
      <span className="ph-dim">{done > 0 ? `${done} day${done === 1 ? "" : "s"} so far` : "Here we go"}</span>
      <div className="ph-indeterminate"><i /></div>
    </div>
  );
}

function FeedRow({ f, showDate }: { f: FeedItem; showDate?: boolean }) {
  return (
    <div className="ph-feed-row" onClick={() => f.with[0] && pgo(`phone/contact/${f.with[0]}`)}>
      {f.with[0] ? <Face id={f.with[0]} size={30} /> : <span className="ph-feed-dot" />}
      <div>
        <p>{f.text}</p>
        {showDate && <small className="ph-dim">{f.date}</small>}
      </div>
    </div>
  );
}
