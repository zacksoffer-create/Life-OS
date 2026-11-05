// Me: who you are right now, how you're doing, and how you want to play.
import React, { useState } from "react";
import { EpisodeGuide, pgo, phoneApi } from "./api";
import { Portrait } from "./art";
import { PIcon } from "./icons";
import { Bar, cx, errText, money, Sheet } from "./kit";
import { usePhone } from "./PhoneContext";
import ClassesCard from "./ClassesCard";
import { EngineLine } from "./DialogueCard";
import { STANDALONE, StoryFilesCard } from "./StoryFiles";

const FOCUS: [string, string, string, string][] = [
  ["balanced", "Balanced", "star", "No push. You follow your own personality."],
  ["athletics", "Athletics", "ball", "Practice, training, games, tryouts."],
  ["academics", "School", "book", "Studying and homework come first."],
  ["social", "Friends", "people", "Hanging out, parties, meeting people."],
  ["romance", "Romance", "heart", "Flirting, dates, asking someone out."],
  ["family", "Family", "home", "Time at home, the pets, helping out."],
  ["rest", "Downtime", "moon", "Rest, hobbies, recharging."],
  ["work", "Work", "work", "Shifts and picking up hours."],
];
const TOGGLES: [string, string, string][] = [
  ["ask_invites", "Ask me about invitations", "Stop when a close friend invites you somewhere."],
  ["ask_romance", "Ask me when someone asks me out", "Romance is your call, not the dice."],
  ["stop_before_games", "Stop before my games", "Pick how you play on game day."],
  ["stop_on_big", "Stop for big moments", "Tryout results, offers, injuries, the big stuff."],
  ["auto_lunch", "Lunch on autopilot", "Sit with your usual table without stopping. Turn it off to pick every lunch."],
  ["class_games", "Class challenges", "Quick games in class most school days (a few seconds each). Off: just quizzes and tests."],
  ["editor", "Editor", "Change anyone's personality, look, mood and relationships. Turn it off once your world is set up."],
  ["auto_scenes", "Let my character decide story scenes", "Off: every storyline scene waits for you, however long. On: if you skip past one, your character answers it."],
];
const PACING: [string, string, string][] = [
  ["relaxed", "Relaxed", "A scene every couple of days"],
  ["standard", "Standard", "One or two a day"],
  ["dense", "Dense", "Two to five on school days, more on weekends"],
  ["uncapped", "Uncapped", "Everything that's ready"],
];
const CHAPTERS = ["Fr", "So", "Jr", "Sr", "C1", "C2", "C3"];
// how much more it takes for a girl to ask a guy out than the other way around
const ASK_BAR: [number, string, string][] = [
  [0, "Same", "Girls ask guys out as easily as guys ask girls."],
  [1, "Harder", "She has to be a lot more into him, and fairly sure he likes her back."],
  [2, "Much harder", "Only when she's really into him. Mostly she waits for him to ask."],
  [3, "Rare", "Almost never, unless she's crazy about him."],
];

function useRoleOpen() {
  const [n, setN] = React.useState(0);
  React.useEffect(() => {
    phoneApi.roles().then((b) => setN(b.open)).catch(() => setN(0));
  }, []);
  return n;
}

export default function MeTab() {
  const roleOpen = useRoleOpen();
  const { state, refresh, toast } = usePhone();
  const [busy, setBusy] = useState<string | null>(null);
  const [guide, setGuide] = useState<EpisodeGuide | null>(null);
  const openGuide = async () => {
    try {
      setGuide(await phoneApi.episodes());
    } catch (e) {
      toast(errText(e), "bad");
    }
  };
  if (!state) return null;
  const s = state;
  const me = s.me;
  const set = async (patch: any, key: string) => {
    setBusy(key);
    try {
      await phoneApi.control(patch);
      await refresh();
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setBusy(null);
    }
  };
  const place = me.path?.kind === "pro" ? `Pro ball · ${me.path.team || "free agent"}` : me.school === "hchs" ? s.setting.school
    : me.school === "college" ? (me.path?.name || "College") : me.location === "hollow_creek" ? s.setting.town : "Away";
  const year = Math.min(7, s.progress.year);
  return (
    <div className="ph-me">
      <div className="ph-me-head">
        <div className="ph-me-bg" />
        <Portrait look={me.look} size={128} mood={me.mood >= 60 ? "happy" : me.mood < 35 ? "sad" : "neutral"} color={me.color} name={me.first} jersey={me.jersey || null} ring="#fff" />
        <h1>{me.name}</h1>
        <div className="ph-me-sub">{me.year_label} · {me.age} · {place}</div>
        {me.injured && <div className="ph-tag bad">Injured</div>}
      </div>

      <div className="ph-pad">
        <div className="ph-stats">
          <Stat icon="grad" label="GPA" value={me.gpa?.toFixed(2)} tone={me.gpa >= 3.3 ? "good" : me.gpa < 2.3 ? "bad" : ""} />
          <Stat icon="cash" label="Money" value={money(me.money)} />
          <Stat icon="people" label="Friends" value={me.friends} />
          <Stat icon="star" label="Popularity" value={Math.round(me.popularity)} />
        </div>

        <div className="ph-card">
          <div className="ph-card-t">How you're doing</div>
          <Bar label="Mood" value={me.mood} />
          <Bar label="Energy" value={me.needs?.energy ?? 0} tone="sky" />
          <Bar label="Stress" value={me.needs?.stress ?? 0} invert />
          <Bar label="Social" value={me.needs?.social ?? 0} tone="grape" />
          <Bar label="Fun" value={me.needs?.fun ?? 0} tone="sun" />
        </div>

        {s.squad && (
          <div className="ph-card ph-squad">
            <div className="ph-card-t row">
              <span>{s.squad.name[0].toUpperCase() + s.squad.name.slice(1)}</span>
              <span className="ph-dim">{s.squad.last ? `together ${s.squad.last}` : "your group"}</span>
            </div>
            <div className="ph-squad-faces">
              {s.squad.members.map((m) => (
                <span key={m.id}><Portrait look={m.look} size={46} name={m.first} /><small>{m.first}</small></span>
              ))}
            </div>
            <Bar label="How tight you are" value={s.squad.cohesion} tone="grape" />
            {s.squad.plan && (
              <p className="ph-squad-plan">{s.squad.plan.joined ? "You went: " : "Today: "}{s.squad.plan.label.toLowerCase()} {s.squad.plan.when}</p>
            )}
            {s.squad.jokes.length > 0 && <p className="ph-dim small">Inside jokes: {s.squad.jokes.join(" · ")}</p>}
            <p className="ph-dim small">Nothing to manage. They show up in your free time, and their group chat never needs an answer.</p>
          </div>
        )}

        {s.teams.length > 0 && (
          <div className="ph-card">
            <div className="ph-card-t">Your teams</div>
            {s.teams.map((t) => (
              <div key={t.id} className="ph-team">
                <span className="ph-icon-bubble"><PIcon name="ball" size={18} /></span>
                <div>
                  <b>{t.name}</b>
                  <small className="ph-dim">{[t.level === "jv" ? "JV" : "Varsity", t.position].filter(Boolean).join(" · ")}</small>
                </div>
                <span className="ph-team-r">
                  {t.record.w}-{t.record.l}
                  {t.mine && (t.mine.w !== t.record.w || t.mine.l !== t.record.l) && (
                    <small title="The games you played in this season">you {t.mine.w}-{t.mine.l}</small>
                  )}
                </span>
              </div>
            ))}
          </div>
        )}

        <div className="ph-card">
          <div className="ph-card-t row"><span>Your seven years</span><span className="ph-dim">Year {year} of 7</span></div>
          <div className="ph-prog"><i style={{ width: `${Math.max(1.5, s.progress.pct)}%` }} /></div>
          <div className="ph-prog-l">
            {CHAPTERS.map((c, i) => <span key={c} className={cx(i + 1 < year && "done", i + 1 === year && "now")}>{c}</span>)}
          </div>
          {s.progress.complete && <p className="ph-dim small">The seven chapters are written. Your world keeps going if you do.</p>}
          <button className="ph-btn soft block ph-ep-btn" onClick={openGuide}><PIcon name="book" size={17} /> Episode guide</button>
        </div>
        <Sheet open={!!guide} onClose={() => setGuide(null)} title="Your story, so far" className="ph-episodes">
          {guide && <EpisodeGuideView g={guide} />}
        </Sheet>

        <div className="ph-section-t">Your focus</div>
        <p className="ph-dim small ph-tight">When you let things play out, your focus pulls you toward these kinds of choices. It nudges; it doesn't force.</p>
        <div className="ph-focus">
          {FOCUS.map(([k, l, icon, d]) => (
            <button key={k} className={cx("ph-focus-o", s.control.focus === k && "on")} disabled={busy === "focus"} onClick={() => set({ focus: k }, "focus")}>
              <PIcon name={icon} size={20} />
              <b>{l}</b>
              <small>{d}</small>
            </button>
          ))}
        </div>

        <ClassesCard />

        <div className="ph-section-t">Make it yours</div>
        <div className="me-tiles">
          <button className="me-tile" onClick={() => pgo("studio")}>
            <PIcon name="book" size={22} />
            <b>Story Studio</b>
            <small>People, storylines, and the roles they need</small>
            {roleOpen > 0 && <i className="st-badge">{roleOpen} to fill</i>}
          </button>
          <button className="me-tile" onClick={() => pgo("texting")}>
            <PIcon name="chat" size={22} />
            <b>Texting</b>
            <small>Flirt lines and group chats</small>
          </button>
        </div>

        <div className="ph-section-t">How much story a day?</div>
        <div className="ph-card ph-pacing">
          <div className="ph-pace-row">
            {PACING.map(([k, l, d]) => (
              <button key={k} className={cx("ph-pace", (s.control.pacing || "dense") === k && "on")} disabled={busy === "pacing"}
                onClick={() => set({ pacing: k }, "pacing")}>
                <b>{l}</b><small>{d}</small>
              </button>
            ))}
          </div>
          <p className="ph-dim small">Storylines only bring scenes they actually have: nothing gets made up to fill a day, and nothing waits just to slow things down.
            Continue story on the Story tab plays the next one right away.</p>
          <button className="ph-link" onClick={() => pgo("schedule")}>Story schedule: play a storyline start to finish, add scenes, see what's coming</button>
        </div>

        <div className="ph-section-t">When should the story stop?</div>
        <div className="ph-card ph-toggles">
          {TOGGLES.map(([k, l, d]) => {
            const on = !!(s.control as any)[k];
            return (
              <button key={k} className="ph-toggle" disabled={busy === k} onClick={() => set({ [k]: !on }, k)}>
                <span><b>{l}</b><small>{d}</small></span>
                <span className={cx("ph-switch", on && "on")}><i /></span>
              </button>
            );
          })}
        </div>

        <div className="ph-section-t">Girls asking guys out</div>
        <div className="ph-card">
          <div className="ph-seg cs-seg wrap">
            {ASK_BAR.map(([v, l]) => (
              <button key={v} type="button" disabled={busy === "ask_bar"} className={cx(Math.round(s.control.girl_asks_guy ?? 1) === v && "on")}
                onClick={() => set({ girl_asks_guy: v }, "ask_bar")}>{l}</button>
            ))}
          </div>
          <p className="ph-dim small">{(ASK_BAR.find(([v]) => v === Math.round(s.control.girl_asks_guy ?? 1)) || ASK_BAR[1])[2]} Asking someone out
            yourself works the same either way.</p>
        </div>

        <StoryFilesCard hasStory={!!state.active} />

        {!STANDALONE && (
          <div className="ph-links">
            <a className="ph-btn soft block" href="#/story"><PIcon name="laptop" size={17} /> Full dashboard (best on a computer)</a>
            <a className="ph-link center" href="#/overview">Back to the lab</a>
          </div>
        )}
        <EngineLine />
      </div>
    </div>
  );
}

function Stat({ icon, label, value, tone }: { icon: string; label: string; value: React.ReactNode; tone?: string }) {
  return (
    <div className={cx("ph-stat", tone)}>
      <PIcon name={icon} size={17} />
      <b>{value}</b>
      <small>{label}</small>
    </div>
  );
}


/** Your seven years as one show: seasons, episodes, what you chose, and what's coming up. */
function EpisodeGuideView({ g }: { g: EpisodeGuide }) {
  return (
    <div className="ph-eg">
      {g.coming_up.length > 0 && (
        <div className="ph-eg-next">
          <div className="ph-section-t">Coming up</div>
          {g.coming_up.map((c) => (
            <div key={c.storyline} className="ph-eg-up"><b>{c.next.replace(/\{(\w+)\}/g, "…")}</b><small>{c.storyline} · Chapter {c.chapter} of {c.of}</small></div>
          ))}
        </div>
      )}
      {g.seasons.length === 0 && <p className="ph-dim">Nothing's aired yet. Your first episode is coming.</p>}
      {[...g.seasons].reverse().map((s) => (
        <div key={s.n} className="ph-eg-season">
          <div className="ph-section-t">Season {s.n} · {s.label}{s.n === g.now.season ? " (now)" : ""}</div>
          {[...s.episodes].reverse().map((e) => (
            <div key={e.number} className={cx("ph-eg-ep", (e.premiere || e.finale) && "big")}>
              <span className="ph-eg-n">E{e.number}</span>
              <span className="ph-eg-m">
                <b>{e.title}</b>
                <small>{e.storyline} · {e.date}{e.premiere ? " · Premiere" : e.finale ? " · Finale" : ""}</small>
                {e.choices.length > 0 && <em>You: {e.choices.join(" → ")}</em>}
                {e.said && <span className="ph-eg-said">{e.said}</span>}
              </span>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
