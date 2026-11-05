// Home: your family, your pets, the chores, and time together.
import React, { useEffect, useState } from "react";
import { Chip, Line, Pet, PetDuty, phoneApi, pgo } from "./api";
import { PetArt, Portrait, Scene } from "./art";
import { PIcon } from "./icons";
import { Bar, buzz, cx, errText, Lines, Sheet, StatChips } from "./kit";
import { usePhone } from "./PhoneContext";

type PetsInfo = Awaited<ReturnType<typeof phoneApi.pets>>;

const COAT: Record<string, string> = {
  golden: "#e2a74f", black: "#2c2a2e", chocolate: "#6b4226", cream: "#f1dfbf", tricolor: "linear-gradient(135deg,#2c2a2e 0 35%,#c8823d 35% 65%,#f6efe4 65%)",
  brindle: "repeating-linear-gradient(120deg,#7b5434 0 6px,#3f2a1c 6px 10px)", gray: "#9aa0a8", white: "#f7f4ef", orange: "#e98b3a",
  calico: "linear-gradient(135deg,#f7f4ef 0 33%,#e98b3a 33% 60%,#2c2a2e 60%)", tabby: "repeating-linear-gradient(90deg,#b07a45 0 5px,#7a5230 5px 9px)",
  brown: "#8a5a3b", spotted: "radial-gradient(circle at 30% 35%,#5a4636 0 18%,transparent 19%),radial-gradient(circle at 70% 70%,#5a4636 0 16%,transparent 17%),#f7f4ef",
};
const QUICK_ICON: Record<string, string> = { cuddle: "heart", treat: "bone", feed: "bowl", brush: "brush", walk: "walk", park: "tree", play: "ballplay", train: "wand", clean: "sparkle" };
const TIMED_ICON: Record<string, string> = { walk: "walk", park: "tree", play: "ballplay", train: "wand" };
const DUTY_ICON: Record<string, string> = { feed_am: "bowl", feed_pm: "bowl", walk: "walk", bath: "sparkle", litter: "sparkle", brush: "brush", cage: "home" };
// when each longer activity is possible (the same windows the simulation uses)
const WINDOWS: Record<string, string[]> = { walk: ["after_school", "day", "evening"], park: ["after_school", "day"], play: ["after_school", "day", "evening"], train: ["after_school", "day", "evening"] };
const PHASE_WORD: Record<string, string> = { dawn: "It's early", classes: "You're in class", lunch: "It's lunch at school", night: "It's late", evening: "It's evening" };
function nowState(act: string, phase: string, ready: boolean, home: boolean): { now: boolean; why: string } {
  if (!home) return { now: false, why: "You're away from home right now." };
  if (!(WINDOWS[act] || []).includes(phase)) {
    const when = act === "park" ? "after school or on a free day" : "after school or tonight";
    return { now: false, why: `${PHASE_WORD[phase] || "Not right now"}. You'll do it ${when}.` };
  }
  if (!ready) return { now: false, why: "You're in the middle of something. It'll happen at your next free moment." };
  return { now: true, why: "" };
}
const SPECIES_WORD: Record<string, [string, string]> = { dog: ["Dog", "Walks, fetch, endless love."], cat: ["Cat", "Independent. Loves you on their terms."], rabbit: ["Rabbit", "Quiet, soft, secretly hilarious."] };

export default function HomeTab() {
  const { state, refresh, toast } = usePhone();
  const [info, setInfo] = useState<PetsInfo | null>(null);
  const [setupFor, setSetupFor] = useState<Pet | null>(null);
  const [setupDismissed, setSetupDismissed] = useState<Record<string, boolean>>({});
  const [action, setAction] = useState<{ pet: Pet; act: string } | null>(null);
  const [outcome, setOutcome] = useState<{ lines: Line[]; chips: Chip[]; title: string } | null>(null);
  const [ask, setAsk] = useState(false);
  const [adopt, setAdopt] = useState<string | null>(null);
  const [bubble, setBubble] = useState<Record<string, { text: string; n: number }>>({});
  const [busy, setBusy] = useState(false);

  const loadInfo = () => phoneApi.pets().then(setInfo).catch(() => undefined);
  useEffect(() => {
    loadInfo();
  }, [state?.pets.length]); // eslint-disable-line react-hooks/exhaustive-deps

  // the one-time chores setup opens by itself for a pet nobody has set up yet
  useEffect(() => {
    if (!state || setupFor) return;
    const p = state.pets.find((x) => x.setup_needed && !setupDismissed[x.id]);
    if (p) setSetupFor(p);
  }, [state?.pets.map((p) => p.id + p.setup_needed).join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!state) return null;
  const s = state;
  const meId = s.me.id;
  const parentsLabel = s.family.guardians.length ? s.family.guardians.map((g) => g.name).join(" & ") : "Your parents";
  const nameOf = (id: string | null | undefined) => {
    if (!id) return "";
    if (id === meId || id === "me") return "You";
    if (id === "parents") return parentsLabel;
    if (id === "rotate") return "Taking turns";
    const sib = s.family.siblings.find((x) => x.id === id);
    return sib ? sib.first : id;
  };
  const isNight = ["evening", "night"].includes(s.scene.phase);

  const quick = async (pet: Pet, act: string) => {
    if (busy) return;
    setBusy(true);
    try {
      buzz();
      const r = await phoneApi.petDo(pet.id, act);
      setBubble((b) => ({ ...b, [pet.id]: { text: r.text, n: (b[pet.id]?.n || 0) + 1 } }));
      await refresh();
    } catch (e) {
      toast(errText(e), "info");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="ph-home">
      <div className="ph-hero short">
        <Scene art={isNight ? "bedroom" : "home_morning"} season={s.scene.season} phase={s.scene.phase} className="ph-hero-art" />
        <div className="ph-hero-fade" />
        <div className="ph-hero-text">
          <div className="ph-kicker">Home</div>
          <h1>{s.family.name || "Your family"}</h1>
          {s.family.style && <p>{s.family.style}</p>}
        </div>
      </div>

      <div className="ph-pad">
        <div className="ph-section-t">Family</div>
        <div className="ph-family">
          {s.family.guardians.map((g) => (
            <button key={g.id} className="ph-fam" onClick={() => pgo("phone/thread/family")}>
              <span className="ph-fam-parent">{g.name.slice(0, 1)}</span>
              <b>{g.name}</b>
              <span className="ph-dim">{g.full.split(" ")[0] === g.name ? "Parent" : g.full.split(" ")[0]}</span>
            </button>
          ))}
          {s.family.siblings.map((sib) => (
            <button key={sib.id} className="ph-fam" onClick={() => pgo(`phone/contact/${sib.id}`)}>
              <Portrait look={sib.look} size={58} name={sib.first} />
              <b>{sib.first}</b>
              <span className="ph-dim">{where(sib)}</span>
            </button>
          ))}
          {(s.family.younger || []).map((y) => (
            <div key={y.key} className="ph-fam later" title={y.starts}>
              <Portrait look={y.look} size={58} name={y.first} />
              <b>{y.first}</b>
              <span className="ph-dim">{y.year_label}</span>
            </div>
          ))}
        </div>
        <div className="ph-card ph-trust">
          <Bar label={`How much ${parentsLabel} trust you`} value={s.family.trust} />
          <p className="ph-dim small">Keeping up with chores and answering their texts builds it. Blowing them off doesn't.</p>
          <button className="ph-btn soft block" onClick={() => pgo("phone/thread/family")}><PIcon name="chat" size={17} /> Family group chat</button>
        </div>

        {s.pet_approved && !s.pets.some((p) => p.species === s.pet_approved!.species && p.adopted === s.date) && (
          <div className="ph-card ph-approved">
            <PetArt species={s.pet_approved.species} size={64} mood="happy" />
            <div>
              <b>{parentsLabel} said yes!</b>
              <p className="ph-dim">Time to bring your {s.pet_approved.species} home.</p>
            </div>
            <button className="ph-btn primary" onClick={() => setAdopt(s.pet_approved!.species)}>Let's go</button>
          </div>
        )}

        <div className="ph-section-t">{s.pets.length ? (s.pets.length === 1 ? s.pets[0].name : "Your pets") : "Pets"}</div>
        {s.pets.map((p) => (
          <PetCard key={p.id} pet={p} nameOf={nameOf} bubble={bubble[p.id]} busy={busy} phase={s.scene.phase} home={s.me.location === "hollow_creek"} decisionReady={s.decision_ready}
            onQuick={(a) => quick(p, a)} onTimed={(a) => setAction({ pet: p, act: a })} onSetup={() => setSetupFor(p)} />
        ))}
        {s.pets.length === 0 ? (
          <div className="ph-card ph-nopet">
            <div className="ph-nopet-art"><PetArt species="dog" size={86} mood="happy" coat="golden" /><PetArt species="cat" size={70} mood="neutral" coat="orange" /></div>
            <h3>No pets. Yet.</h3>
            <p className="ph-dim">Ask {parentsLabel}. Their answer depends on them, your grades, and how much they trust you.</p>
            <button className="ph-btn primary block" onClick={() => setAsk(true)}><PIcon name="paw" size={17} /> Ask for a pet</button>
          </div>
        ) : (
          <button className="ph-link center" onClick={() => setAsk(true)}>Ask for another pet</button>
        )}
      </div>

      {setupFor && info && (
        <ChoreSetup key={`${setupFor.id}:${info.kids.length}`} pet={state.pets.find((p) => p.id === setupFor.id) || setupFor} info={info} meId={meId} parentsLabel={parentsLabel}
          onClose={() => { setSetupDismissed((d) => ({ ...d, [setupFor.id]: true })); setSetupFor(null); }}
          onSaved={async (pet) => { setSetupFor(null); await refresh(); toast(`Chores are set. ${pet.name} is counting on you.`, "good"); }} />
      )}

      <TimedSheet sel={action} phase={s.scene.phase} home={s.me.location === "hollow_creek"} decisionReady={s.decision_ready} onClose={() => setAction(null)}
        onDone={async (r, label) => {
          setAction(null);
          if (r.done) {
            setOutcome({ lines: r.lines || [], chips: r.chips || [], title: label });
          } else {
            toast(r.note || "Planned for your next free time.", "good");
          }
          await refresh();
        }} />

      <Sheet open={!!outcome} onClose={() => setOutcome(null)} title={outcome?.title} className="ph-outcome">
        {outcome && (
          <>
            <Lines lines={outcome.lines.length ? outcome.lines : [{ id: -1, type: "pet", text: "Time well spent." }]} />
            <StatChips chips={outcome.chips} />
            <button className="ph-btn primary block" onClick={() => setOutcome(null)}>Continue</button>
          </>
        )}
      </Sheet>

      <AskSheet open={ask} parentsLabel={parentsLabel} onClose={() => setAsk(false)}
        onYes={(species) => { setAsk(false); refresh(); setAdopt(species); }} />

      {info && (
        <AdoptSheet species={adopt} info={info} onClose={() => setAdopt(null)}
          onAdopted={async (pet) => { setAdopt(null); await refresh(); await loadInfo(); setSetupFor(pet); }} />
      )}
    </div>
  );
}

function where(sib: { location: string; path: any }) {
  if (sib.location === "hollow_creek") return "Home";
  if (sib.path?.kind === "college" && sib.path?.name) return `At ${sib.path.name.replace("University of ", "U")}`;
  if (sib.location === "college") return "At college";
  return "Away";
}

function PetCard({ pet, nameOf, bubble, busy, phase, home, decisionReady, onQuick, onTimed, onSetup }: {
  pet: Pet; nameOf: (id: string | null) => string; bubble?: { text: string; n: number }; busy: boolean; phase: string; home: boolean; decisionReady: boolean;
  onQuick: (a: string) => void; onTimed: (a: string) => void; onSetup: () => void;
}) {
  const happy = pet.happiness >= 65 ? "happy" : pet.happiness >= 40 ? "neutral" : "sad";
  const quick = pet.activities.filter((a) => a.quick);
  const timed = pet.activities.filter((a) => !a.quick);
  return (
    <div className="ph-pet">
      <div className="ph-pet-top">
        <div className={cx("ph-pet-art", bubble && "bounce")} key={bubble?.n || 0}>
          <PetArt species={pet.species} coat={pet.coat} breed={pet.breed} mood={happy} size={124} />
        </div>
        <div className="ph-pet-id">
          <h2>{pet.name}</h2>
          <div className="ph-dim">{pet.breed} · {pet.age === 0 ? "baby" : `${pet.age} yr${pet.age === 1 ? "" : "s"}`} · {pet.personality}</div>
          <div className="ph-pet-tags">
            <span className={cx("ph-tag", "mood-" + pet.mood)}>{pet.mood}</span>
            {pet.streak > 1 && <span className="ph-tag warm"><PIcon name="flame" size={12} /> {pet.streak}-day streak</span>}
          </div>
          <div className="ph-bond">
            <PIcon name="heart" size={15} fill="currentColor" stroke={0} />
            <span>Your bond</span>
            <div className="ph-bond-t"><i style={{ width: `${pet.my_bond}%` }} /></div>
            <b>{pet.my_bond}</b>
          </div>
        </div>
      </div>

      {bubble && <div className="ph-pet-bubble" key={bubble.n}>{bubble.text}</div>}

      <div className="ph-pet-bars">
        <Bar label="Happy" value={pet.happiness} />
        <Bar label="Fed" value={pet.fullness} />
        <Bar label="Energy" value={pet.energy} tone="sky" />
        <Bar label="Health" value={pet.health} />
      </div>

      <div className="ph-subt">Spend time with {pet.name}</div>
      <p className="ph-dim small ph-pet-free">Quick taps, anytime. Nothing here uses up your free time.</p>
      <div className="ph-pet-quick">
        {quick.map((a) => {
          const left = pet.quick_left[a.id] ?? 0;
          return (
            <button key={a.id} className="ph-qbtn" disabled={busy || left <= 0} onClick={() => onQuick(a.id)}>
              <PIcon name={QUICK_ICON[a.id] || "heart"} size={22} />
              <b>{a.label.replace(/^(Give a |Go for a |Take to the |Teach a |Clean the )/, "")}</b>
              <small>{left > 0 ? `${left} left today` : "done for today"}</small>
            </button>
          );
        })}
      </div>
      <div className="ph-pet-timed">
        {timed.map((a) => (
          <button key={a.id} className="ph-tbtn" disabled={busy} onClick={() => onTimed(a.id)}>
            <span className="ph-icon-bubble"><PIcon name={TIMED_ICON[a.id] || "star"} size={20} /></span>
            <span><b>{a.label}</b><small>{nowState(a.id, phase, decisionReady, home).now ? "You're free right now" : "Plan it for later"}</small></span>
          </button>
        ))}
      </div>

      <div className="ph-subt row">
        <span>Today's chores</span>
        {!pet.setup_needed && <button className="ph-link" onClick={onSetup}>Change who does what</button>}
      </div>
      {pet.setup_needed ? (
        <button className="ph-btn soft block" onClick={onSetup}><PIcon name="paw" size={17} /> Decide who takes care of {pet.name}</button>
      ) : (
        <div className="ph-chores">
          {pet.duties.map((d) => <ChoreRow key={d.id} d={d} nameOf={nameOf} />)}
        </div>
      )}
    </div>
  );
}

function ChoreRow({ d, nameOf }: { d: PetDuty; nameOf: (id: string | null) => string }) {
  const who = d.owner === "rotate" ? `Taking turns · ${nameOf(d.today)} today` : nameOf(d.today);
  const mine = nameOf(d.today) === "You";
  return (
    <div className={cx("ph-chore", d.done && "done", !d.due && "off", mine && "mine")}>
      <span className="ph-chore-i">{d.done ? <PIcon name="check" size={16} stroke={3} /> : <PIcon name={DUTY_ICON[d.id] || "paw"} size={16} />}</span>
      <span className="ph-chore-m">
        <b>{d.label}</b>
        <small>{d.due ? who : `${d.hint} · ${nameOf(d.today)}`}</small>
      </span>
      <span className="ph-chore-s">{!d.due ? "Sunday" : d.done ? (d.done_by ? `Done${nameOf(d.done_by) === "You" ? " by you" : ""}` : "Done") : mine ? "Your turn" : "Not yet"}</span>
    </div>
  );
}

function ChoreSetup({ pet, info, meId, parentsLabel, onClose, onSaved }: {
  pet: Pet; info: PetsInfo; meId: string; parentsLabel: string; onClose: () => void; onSaved: (p: Pet) => void;
}) {
  const { toast } = usePhone();
  const sibs = info.kids.filter((k) => !k.me);
  const initial: Record<string, string> = {};
  for (const d of pet.duties) {
    if (!pet.setup_needed) initial[d.id] = d.owner === meId ? "me" : d.owner;
    else initial[d.id] = d.id === "walk" || d.id === "litter" ? "me" : d.id === "feed_pm" && sibs.length ? "rotate" : "parents";
  }
  const [pick, setPick] = useState<Record<string, string>>(initial);
  const [saving, setSaving] = useState(false);
  const opts: [string, string][] = [["me", "Me"], ...sibs.map((k) => [k.id, k.first] as [string, string]), ["parents", parentsLabel], ...(sibs.length ? [["rotate", "Take turns"] as [string, string]] : [])];
  const mine = pet.duties.filter((d) => pick[d.id] === "me").map((d) => d.label.toLowerCase());
  const save = async () => {
    setSaving(true);
    try {
      const p = await phoneApi.petSetup(pet.id, pick);
      onSaved(p);
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setSaving(false);
    }
  };
  return (
    <Sheet open full onClose={onClose} className="ph-setup">
      <div className="ph-setup-h">
        <PetArt species={pet.species} coat={pet.coat} breed={pet.breed} mood="happy" size={110} />
        <h2>Who takes care of {pet.name}?</h2>
        <p className="ph-dim">Decide once as a family. Every day after that, whoever's on it does it (or forgets), and everyone notices.</p>
      </div>
      <div className="ph-setup-list">
        {pet.duties.map((d) => (
          <div key={d.id} className="ph-setup-duty">
            <div className="ph-setup-dh">
              <span className="ph-icon-bubble"><PIcon name={DUTY_ICON[d.id] || "paw"} size={18} /></span>
              <div><b>{d.label}</b><small>{d.hint}</small></div>
            </div>
            <div className="ph-seg">
              {opts.map(([v, l]) => (
                <button key={v} className={cx(pick[d.id] === v && "on")} onClick={() => setPick({ ...pick, [d.id]: v })}>{l}</button>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="ph-setup-f">
        <p className="ph-dim small">{mine.length ? `You're signing up for: ${mine.join(", ")}.` : "You're leaving it all to the family. Bold."}</p>
        <button className="ph-btn primary block big" onClick={save} disabled={saving}>{saving ? "Saving…" : "That's the plan"}</button>
      </div>
    </Sheet>
  );
}

function TimedSheet({ sel, phase, home, decisionReady, onClose, onDone }: {
  sel: { pet: Pet; act: string } | null; phase: string; home: boolean; decisionReady: boolean; onClose: () => void; onDone: (r: any, label: string) => void;
}) {
  const { toast } = usePhone();
  const [trick, setTrick] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (sel?.act === "train") setTrick(sel.pet.tricks.find((t) => t.progress < 100)?.name || sel.pet.tricks[0]?.name || null);
  }, [sel?.pet.id, sel?.act]); // eslint-disable-line react-hooks/exhaustive-deps
  const pet = sel?.pet;
  const act = sel?.act || "";
  const label = pet ? ({ walk: `Walk ${pet.name}`, park: `Take ${pet.name} to the park`, play: `Play with ${pet.name}`, train: `Teach ${pet.name} a trick` } as Record<string, string>)[act] || act : "";
  const blurb: Record<string, string> = {
    walk: "A loop around the neighborhood. Counts as the walk for today.",
    park: "The Guilford Green (or the beach in summer). You never know who you'll run into.",
    play: "Burn some energy, laugh a lot.",
    train: "Patience and treats. Some pets learn faster than others.",
  };
  const go = async (now: boolean) => {
    if (!pet) return;
    setBusy(true);
    try {
      buzz();
      const r = await phoneApi.petDo(pet.id, act, { now, trick: act === "train" && trick ? trick : undefined });
      onDone(r, label);
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setBusy(false);
    }
  };
  return (
    <Sheet open={!!sel} onClose={onClose} title={label} className="ph-timed">
      {pet && (
        <>
          <div className="ph-timed-art"><PetArt species={pet.species} coat={pet.coat} breed={pet.breed} mood="happy" size={96} /></div>
          <p className="ph-dim center">{blurb[act]}</p>
          {act === "train" && (
            <div className="ph-tricks">
              {pet.tricks.map((t) => (
                <button key={t.name} className={cx("ph-trick", trick === t.name && "on", t.progress >= 100 && "learned")} onClick={() => setTrick(t.name)}>
                  <span className="ph-trick-n">{t.name}</span>
                  {t.progress >= 100 ? <span className="ph-tag good">learned</span> : <span className="ph-trick-t"><i style={{ width: `${t.progress}%` }} /></span>}
                </button>
              ))}
            </div>
          )}
          {nowState(act, phase, decisionReady, home).now ? (
            <>
              <button className="ph-btn primary block big" disabled={busy} onClick={() => go(true)}>Do it now</button>
              <p className="ph-dim small center">Uses the free time you have right now.</p>
              <button className="ph-link center" disabled={busy} onClick={() => go(false)}>Plan it for later instead</button>
            </>
          ) : (
            <>
              <button className="ph-btn primary block big" disabled={busy} onClick={() => go(false)}>Plan it for my next free time</button>
              <p className="ph-dim small center">{nowState(act, phase, decisionReady, home).why}</p>
            </>
          )}
        </>
      )}
    </Sheet>
  );
}

function AskSheet({ open, parentsLabel, onClose, onYes }: { open: boolean; parentsLabel: string; onClose: () => void; onYes: (species: string) => void }) {
  const [species, setSpecies] = useState("dog");
  const [answer, setAnswer] = useState<{ yes: boolean; text: string; reason: string | null } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (open) {
      setAnswer(null);
      setErr(null);
    }
  }, [open]);
  const doAsk = async () => {
    setBusy(true);
    setErr(null);
    try {
      const r = await phoneApi.petAsk(species);
      setAnswer(r);
    } catch (e) {
      setErr(errText(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Sheet open={open} onClose={onClose} title={answer ? (answer.yes ? "They said yes!" : "Not right now") : "Ask for a pet"} className="ph-ask">
      {!answer ? (
        <>
          <div className="ph-species">
            {Object.entries(SPECIES_WORD).map(([k, [l, d]]) => (
              <button key={k} className={cx("ph-species-o", species === k && "on")} onClick={() => setSpecies(k)}>
                <PetArt species={k} size={70} mood="happy" />
                <b>{l}</b>
                <small>{d}</small>
              </button>
            ))}
          </div>
          {err && <div className="ph-note bad">{err}</div>}
          <button className="ph-btn primary block big" disabled={busy} onClick={doAsk}>{busy ? "Asking…" : `Ask ${parentsLabel}`}</button>
          <p className="ph-dim small center">You can only ask every few weeks, so make it count.</p>
        </>
      ) : (
        <div className="ph-answer">
          <PetArt species={species} size={110} mood={answer.yes ? "happy" : "sad"} />
          {answer.yes ? (
            <p>{answer.text.replace(/^You asked for a \w+\. /, "")}</p>
          ) : (
            <div className="ph-quote">
              <p>“{answer.reason || "Not right now."}”</p>
              <small>— {parentsLabel}</small>
            </div>
          )}
          {answer.yes ? (
            <button className="ph-btn primary block big" onClick={() => onYes(species)}>Bring them home</button>
          ) : (
            <>
              {answer.reason && <div className="ph-note">Try again in a few weeks. Better grades and keeping up with your responsibilities help.</div>}
              <button className="ph-btn soft block" onClick={onClose}>Okay</button>
            </>
          )}
        </div>
      )}
    </Sheet>
  );
}

function AdoptSheet({ species, info, onClose, onAdopted }: { species: string | null; info: PetsInfo; onClose: () => void; onAdopted: (p: Pet) => void }) {
  const { toast } = usePhone();
  const spec = species ? info.species[species] : null;
  const [name, setName] = useState("");
  const [breed, setBreed] = useState("");
  const [coat, setCoat] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (spec) {
      setBreed(spec.breeds[0]);
      setCoat(spec.coats[0]);
      setName("");
    }
  }, [species]); // eslint-disable-line react-hooks/exhaustive-deps
  const go = async () => {
    if (!species) return;
    setBusy(true);
    try {
      const p = await phoneApi.petAdopt(species, name.trim(), breed, coat);
      buzz(30);
      onAdopted(p);
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setBusy(false);
    }
  };
  const baby = species === "dog" ? "puppy" : species === "cat" ? "kitten" : "bunny";
  return (
    <Sheet open={!!species} onClose={onClose} title={`Your new ${baby}`} full className="ph-adopt">
      {spec && (
        <>
          <div className="ph-adopt-art">
            <PetArt species={species!} coat={coat} breed={breed} mood="happy" size={150} />
            <div className="ph-adopt-name">{name.trim() || "?"}</div>
          </div>
          <label className="ph-field">
            <span>Name</span>
            <input className="ph-input" type="text" maxLength={20} placeholder={species === "dog" ? "Buster, Luna, Moose…" : species === "cat" ? "Miso, Pickles, Clementine…" : "Thistle, Bun…"}
              value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <div className="ph-field">
            <span>Breed</span>
            <div className="ph-pills">
              {spec.breeds.map((b) => <button key={b} className={cx("ph-pill", breed === b && "on")} onClick={() => setBreed(b)}>{b}</button>)}
            </div>
          </div>
          <div className="ph-field">
            <span>Coat</span>
            <div className="ph-swatches">
              {spec.coats.map((c) => (
                <button key={c} className={cx("ph-swatch", coat === c && "on")} onClick={() => setCoat(c)} title={c}>
                  <i style={{ background: COAT[c] || "#ccc" }} />
                  <small>{c}</small>
                </button>
              ))}
            </div>
          </div>
          <button className="ph-btn primary block big" disabled={busy || !name.trim()} onClick={go}>
            {busy ? "Heading home…" : `Bring ${name.trim() || "them"} home`}
          </button>
        </>
      )}
    </Sheet>
  );
}
