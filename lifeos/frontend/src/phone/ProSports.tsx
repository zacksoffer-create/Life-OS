// The pros, running in the background of your story. MLB first: real history through 2025, your team's season as of
// today, October, the leaders, the news, the what-ifs (history that almost went the other way) and every past season.
import React, { useEffect, useState } from "react";
import { MlbDiv, MlbSeries, MlbView, MlbWhatIf, MlbYear, pgo, phoneApi } from "./api";
import { cx, errText, Sheet } from "./kit";
import { usePhone } from "./PhoneContext";

const SECTIONS = [["team", "My team"], ["standings", "Standings"], ["whatifs", "What-ifs"], ["history", "History"]] as const;
const HOW: Record<string, string> = { flipped: "history changed", new: "never happened" };

type Names = Record<string, { nick: string; abbr: string }>;

export default function ProSports({ route }: { route: string[] }) {
  const { toast } = usePhone();
  const [v, setV] = useState<MlbView | null>(null);
  const load = () => phoneApi.mlb().then(setV).catch((e) => toast(errText(e), "bad"));
  useEffect(() => {
    load();
  }, [route.join("/")]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!v) return <div className="pm-empty"><span className="ph-spinner" /></div>;
  const names: Names = Object.fromEntries(v.teams.map((t) => [t.team, { nick: t.nick, abbr: t.abbr }]));
  if (route[0] === "whatif" && route[1]) return <WhatIf id={route[1]} onChanged={load} />;
  if (route[0] === "year" && route[1]) return <Year y={Number(route[1])} names={names} years={v.years} />;
  const sec = (SECTIONS.find(([k]) => k === route[0]) || SECTIONS[0])[0];
  return (
    <>
      <div className="sp-seg">
        {SECTIONS.map(([k, l]) => <button key={k} className={cx(sec === k && "on")} onClick={() => pgo(k === "team" ? "sports/pro" : `sports/pro/${k}`)}>{l}</button>)}
      </div>
      {sec === "team" && <MyTeam v={v} names={names} onTeam={setV} />}
      {sec === "standings" && <Standings v={v} names={names} />}
      {sec === "whatifs" && <WhatIfs v={v} />}
      {sec === "history" && <History v={v} />}
      <p className="ph-dim small pro-src">{v.source}</p>
    </>
  );
}

function MyTeam({ v, names, onTeam }: { v: MlbView; names: Names; onTeam: (v: MlbView) => void }) {
  const { toast } = usePhone();
  const t = v.my_team;
  const [pick, setPick] = useState(false);
  const extra = t.titles.world.filter((y) => !t.titles.real.includes(y));
  const lost = t.titles.real.filter((y) => !t.titles.world.includes(y));
  const choose = async (team: string) => {
    try {
      onTeam(await phoneApi.mlbTeam(team));
      setPick(false);
    } catch (e) {
      toast(errText(e), "bad");
    }
  };
  return (
    <>
      <div className={cx("pro-team", "t-" + t.team)}>
        <div className="pro-team-top">
          <div className="sp-rec"><b>{t.record || "0-0"}</b><small>{v.year} season</small></div>
          <div className="sp-team-m">
            <b>{t.name}</b>
            {t.place && <span>{t.place}</span>}
            {t.l10 && <span>Last 10: {t.l10}{t.streak ? ` · ${t.streak[0] === "W" ? "won" : "lost"} ${t.streak.slice(1)} straight` : ""}</span>}
          </div>
        </div>
        {t.status && <div className="pro-status">{t.status}</div>}
        <div className="pro-titles">
          <small>World Series titles</small>
          <b>{t.titles.world.length ? t.titles.world.join(", ") : "None since 1990"}</b>
          {(extra.length > 0 || lost.length > 0) && (
            <em>{extra.length > 0 && `In this world: +${extra.join(", ")}. `}{lost.length > 0 && `Really won, not here: ${lost.join(", ")}.`}</em>
          )}
        </div>
        <button className="pro-change" onClick={() => setPick(true)}>Not your team? Change it</button>
      </div>

      <div className="sp-h">Best players right now</div>
      <div className="sp-card">
        {t.stars.map((s) => (
          <div key={s.name} className="pro-star">
            <span className="pro-pos">{s.pos}</span>
            <span className="sp-dm"><b>{s.name}{s.moved ? <i className="pro-tag">what-if</i> : null}</b><small>{s.line || `${s.talent} wins${v.phase === "preseason" ? " a year (projected)" : ""}`} · age {s.age}</small></span>
          </div>
        ))}
      </div>

      {v.october.length > 0 && (
        <>
          <div className="sp-h">October {v.year}</div>
          <October series={v.october} names={names} you={t.team} />
        </>
      )}

      {v.leaders.length > 0 && <Leaders v={v} />}

      <div className="sp-h">Around the league</div>
      <div className="sp-card pro-news">
        {v.news.length === 0 && <p className="ph-dim small">Quiet so far. Results, signings and retirements show up here as they happen.</p>}
        {v.news.map((n, i) => <div key={i} className={cx("pro-n", n.mine && "mine")}><p>{n.text}</p><small>{n.date}</small></div>)}
      </div>

      <Sheet open={pick} onClose={() => setPick(false)} title="Your team">
        <p className="ph-dim small">It's whose October you feel, and who {"{my_team}"} is in your storylines.</p>
        <div className="pro-pick">
          {v.teams.map((x) => <button key={x.team} className={cx(x.team === t.team && "on")} onClick={() => choose(x.team)}>{x.name}</button>)}
        </div>
      </Sheet>
    </>
  );
}

function October({ series, names, you }: { series: MlbSeries[]; names: Names; you?: string }) {
  const rounds = Array.from(new Set(series.map((s) => s.label)));
  return (
    <div className="pro-oct">
      {rounds.map((r) => (
        <div key={r} className="pro-round">
          <small>{r}</small>
          {series.filter((s) => s.label === r).map((s, i) => (
            <div key={i} className={cx("pro-ser", s.teams.includes(you || "") && "mine")}>
              {s.teams.map((t, k) => (
                <div key={t} className={cx("pro-st", s.winner === t && "won", s.done && s.winner !== t && "out")}>
                  <span>{names[t]?.nick || t}</span><b>{s.wins[k]}</b>
                </div>
              ))}
              {(s.next || HOW[s.how]) && <em>{s.next ? `Next: ${s.next.replace(/, \d{4}$/, "")}` : HOW[s.how]}</em>}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

function Leaders({ v }: { v: MlbView }) {
  const [lg, setLg] = useState(v.standings.find((d) => d.rows.some((r) => r.you))?.lg || "AL");
  return (
    <>
      <div className="sp-h">Leaders <small>{["AL", "NL"].map((x) => <button key={x} className={cx("pro-lg", lg === x && "on")} onClick={() => setLg(x)}>{x}</button>)}</small></div>
      <div className="pro-leaders">
        {v.leaders.filter((l) => l.lg === lg).map((l) => (
          <div key={l.stat} className="sp-card pro-lead">
            <b>{l.label}</b>
            {l.rows.slice(0, 3).map((r, i) => <div key={i} className="pro-lrow"><span>{r.name} <small>{r.abbr}</small></span><em>{r.value}</em></div>)}
          </div>
        ))}
      </div>
    </>
  );
}

function Table({ d, you }: { d: MlbDiv; you?: string }) {
  const proj = d.rows.some((r) => r.w + r.l === 0 && r.proj);
  return (
    <div className="sp-table pro-table">
      <div className="pro-tr head"><span>{d.label}</span><span>W</span><span>L</span><span>{proj ? "Proj" : "GB"}</span><span>L10</span></div>
      {d.rows.map((r) => (
        <div key={r.team} className={cx("pro-tr", (r.you || r.team === you) && "ours")}>
          <span className="sp-tn">{r.nick}{r.in ? <i className="pro-in">in</i> : null}</span>
          <span>{r.w}</span><span>{r.l}</span><span>{proj ? r.proj : r.gb}</span><span>{r.l10 || ""}</span>
        </div>
      ))}
    </div>
  );
}

function Standings({ v, names }: { v: MlbView; names: Names }) {
  const mine = v.standings.find((d) => d.rows.some((r) => r.you))?.lg || "AL";
  const [lg, setLg] = useState(mine);
  return (
    <>
      <div className="sp-teams">{["AL", "NL"].map((x) => <button key={x} className={cx(lg === x && "on")} onClick={() => setLg(x)}>{x === "AL" ? "American League" : "National League"}</button>)}</div>
      {v.standings.filter((d) => d.lg === lg).map((d) => <Table key={d.label} d={d} />)}
      {v.phase === "preseason" && <p className="ph-dim small">Before Opening Day: "Proj" is what the roster projects to win.</p>}
      {v.october.length > 0 && <><div className="sp-h">October</div><October series={v.october} names={names} you={v.my_team.team} /></>}
    </>
  );
}

function WhatIfs({ v }: { v: MlbView }) {
  const groups = Array.from(new Set(v.whatifs.map((w) => w.group)));
  const on = v.whatifs.filter((w) => w.on).length;
  return (
    <>
      <div className="sp-card">
        <b>History that almost went the other way</b>
        <p className="ph-dim small">Each of these was really on the table. Turn one on and your world's history replays from that day: the standings, every October since, and the players who are still playing move now. {on ? `${on} on in your world.` : "Your world is real history right now."}</p>
      </div>
      {groups.map((g) => (
        <React.Fragment key={g}>
          <div className="sp-h">{g === "Yours" ? "The big four" : g === "Arms" ? "Arms" : "Bats"}</div>
          {v.whatifs.filter((w) => w.group === g).map((w) => (
            <button key={w.id} className={cx("pro-wi", w.on && "on")} onClick={() => pgo(`sports/pro/whatif/${w.id}`)}>
              <span><b>{w.title}</b><small>{w.when}</small></span>
              <i>{w.on ? "On" : "Off"}</i>
            </button>
          ))}
        </React.Fragment>
      ))}
    </>
  );
}

function WhatIf({ id, onChanged }: { id: string; onChanged: () => void }) {
  const { toast, refresh } = usePhone();
  const [w, setW] = useState<MlbWhatIf | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    phoneApi.mlbWhatIf(id).then(setW).catch((e) => toast(errText(e), "bad"));
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!w) return <div className="pm-empty"><span className="ph-spinner" /></div>;
  const flip = async () => {
    setBusy(true);
    try {
      const r = await phoneApi.mlbSetWhatIf(id, !w.on);
      setW(r.view);
      toast(r.view.on ? `On in your world.${r.moved.length ? " " + r.moved.join(" ") : ""}` : `Off: real history.${r.moved.length ? " " + r.moved.join(" ") : ""}`, "good");
      onChanged();
      refresh();
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setBusy(false);
    }
  };
  const total = w.seasons.reduce((a, s) => a + s.change, 0);
  return (
    <>
      <button className="pro-back" onClick={() => pgo("sports/pro/whatifs")}>‹ What-ifs</button>
      <div className={cx("pro-wi-head", w.on && "on")}>
        <small>{w.when}</small>
        <b>{w.title}</b>
        <p>{w.real}</p>
        <button className={cx("ph-btn block", w.on ? "" : "primary")} disabled={busy} onClick={flip}>{w.on ? "Turn it off (back to real history)" : "Make it happen in my world"}</button>
      </div>

      <div className="sp-h">What moves</div>
      <div className="sp-card">
        {w.moves.map((m, i) => (
          <div key={i} className="pro-move">
            <b>{m.name}</b>
            <span>{m.to ? `to the ${m.to}` : "somewhere else"}, {m.years}{m.now ? " and on" : ""}</span>
            <em>{m.wins > 0 ? "+" : ""}{m.wins} wins</em>
          </div>
        ))}
        {w.flat.map((f, i) => (
          <div key={"f" + i} className="pro-move flat">
            <b>{f.team}</b><span>{f.why}, {f.years}</span><em>{f.wins > 0 ? "+" : ""}{f.wins}/yr</em>
          </div>
        ))}
        {w.seasons.length > 0 && <p className="ph-dim small">For the Yankees, about {total > 0 ? "+" : ""}{total.toFixed(1)} wins across {w.seasons.length} season{w.seasons.length === 1 ? "" : "s"}. Values are estimates in wins, like WAR.</p>}
      </div>

      {w.later && <div className="sp-card"><b>{w.seasons.length ? "Still to come" : "In the future"}</b><p className="ph-dim small">{w.later.line} Turn it on now and it happens when the story gets to {w.later.years.split("-")[0]}.</p></div>}
      {w.seasons.length > 0 && <div className="sp-h">Season by season <small>with this one alone</small></div>}
      {w.seasons.map((s) => (
        <div key={s.year} className="sp-card pro-yr">
          <div className="pro-yr-h">
            <b>{s.year}</b>
            <span>{s.real} → <strong>{s.world}</strong></span>
            {s.odds && <em>Title odds {Math.round(s.odds.real * 100)}% → {Math.round(s.odds.world * 100)}%</em>}
          </div>
          <div className="pro-paths">
            <div><small>Really</small>{s.real_path.map((p, i) => <span key={i}>{p}</span>)}</div>
            <div className="w"><small>This world</small>{s.world_path.map((p, i) => <span key={i}>{p}</span>)}</div>
          </div>
          {s.champ !== s.real_champ && <p className="pro-champ">World Series: the {s.champ} (really the {s.real_champ})</p>}
        </div>
      ))}
      {w.seasons.length > 0 && (
        <div className="sp-card">
          <b>Titles in those seasons</b>
          <p className="small">Really: {w.titles.real.join(", ") || "none"}. With this: {w.titles.world.join(", ") || "none"}.</p>
        </div>
      )}
      <p className="ph-dim small">{w.how}</p>
    </>
  );
}

function History({ v }: { v: MlbView }) {
  return (
    <>
      <div className="sp-card"><b>Every season since 1990</b><p className="ph-dim small">Real history, changed wherever your what-ifs changed it, and every season your story has lived through since.</p></div>
      <div className="pro-years">
        {[...v.years].reverse().map((y) => <button key={y} onClick={() => pgo(`sports/pro/year/${y}`)}>{y}</button>)}
      </div>
    </>
  );
}

function Year({ y, names, years }: { y: number; names: Names; years: number[] }) {
  const { toast } = usePhone();
  const [v, setV] = useState<MlbYear | null>(null);
  const [lg, setLg] = useState("AL");
  useEffect(() => {
    setV(null);
    phoneApi.mlbYear(y).then(setV).catch((e) => toast(errText(e), "bad"));
  }, [y]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!v) return <div className="pm-empty"><span className="ph-spinner" /></div>;
  const i = years.indexOf(y);
  return (
    <>
      <div className="pro-yhead">
        <button className="pro-back" onClick={() => pgo("sports/pro/history")}>‹ History</button>
        <span>
          {i > 0 && <button onClick={() => pgo(`sports/pro/year/${years[i - 1]}`)}>‹ {years[i - 1]}</button>}
          {i < years.length - 1 && <button onClick={() => pgo(`sports/pro/year/${years[i + 1]}`)}>{years[i + 1]} ›</button>}
        </span>
      </div>
      <div className="pro-team t-none">
        <div className="pro-team-top"><div className="sp-rec"><b>{y}</b></div>
          <div className="sp-team-m">
            <b>{v.champ ? `${v.champ} win the World Series` : y === 1994 ? "The strike: no World Series" : "No champion"}</b>
            {v.changed && v.champ !== v.real_champ && <span>Really: the {v.real_champ}</span>}
            {v.changed && <span>Your what-ifs changed this season.</span>}
          </div>
        </div>
      </div>
      {v.awards.length > 0 && (
        <div className="sp-card">
          {v.awards.map((a, k) => <div key={k} className="pro-award"><small>{a.label}</small><b>{a.name}</b>{a.team && <span>{a.team}</span>}</div>)}
        </div>
      )}
      {v.october.length > 0 && <><div className="sp-h">October</div><October series={v.october} names={names} /></>}
      <div className="sp-h">Final standings</div>
      <div className="sp-teams">{["AL", "NL"].map((x) => <button key={x} className={cx(lg === x && "on")} onClick={() => setLg(x)}>{x === "AL" ? "American League" : "National League"}</button>)}</div>
      {v.standings.filter((d) => d.lg === lg).map((d) => <Table key={d.label} d={d} />)}
    </>
  );
}
