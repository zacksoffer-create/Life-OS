// The Sports tab: your season, your playing time, the league, the awards race and recruiting, for each team you're on.
// The league is real: every school in the conference has its own team, record and stars, and they all play every week.
import React, { useEffect, useState } from "react";
import { pgo, phoneApi, SportsView } from "./api";
import { PIcon } from "./icons";
import { cx, errText } from "./kit";
import { usePhone } from "./PhoneContext";
import LeagueView from "./LeagueView";
import ProSports from "./ProSports";

const SECTIONS = [["season", "Season"], ["league", "League"], ["awards", "Awards"], ["recruiting", "Recruiting"]] as const;

function Move({ m }: { m: number | null | undefined }) {
  if (m === null || m === undefined || m === 0) return null;
  return <span className={cx("sp-move", m > 0 ? "up" : "down")}>{m > 0 ? "▲" : "▼"}{Math.abs(m)}</span>;
}

function Side({ on }: { on: "school" | "pro" | "college" }) {
  return (
    <div className="sp-side">
      <button className={cx(on === "school" && "on")} onClick={() => pgo("sports")}>School</button>
      <button className={cx(on === "pro" && "on")} onClick={() => pgo("sports/pro")}>Pro</button>
      <button className={cx(on === "college" && "on")} onClick={() => pgo("sports/college")}>College</button>
    </div>
  );
}

const PRO = [["mlb", "MLB"], ["nfl", "NFL"], ["nba", "NBA"], ["soccer", "Soccer"]];
const SOCCER = [["epl", "Premier League"], ["laliga", "La Liga"], ["seriea", "Serie A"], ["bund", "Bundesliga"], ["ligue1", "Ligue 1"],
  ["ucl", "Champions League"], ["ballon", "Ballon d'Or"]];
const COLLEGE = [["cfb", "Football"], ["mbb", "Men's hoops"], ["wbb", "Women's hoops"], ["cbase", "Baseball"], ["msoc", "Men's soccer"], ["wsoc", "Women's soccer"]];

export default function SportsTab({ route }: { route: string[] }) {
  if (route[0] === "pro") {
    const lg = route[1] === "nfl" || route[1] === "nba" || route[1] === "soccer" ? route[1] : "mlb";
    const sub = SOCCER.some(([k]) => k === route[2]) ? route[2] : "epl";
    return (
      <div className="sp">
        <div className="sp-top"><h1 className="sp-h1">Sports</h1><Side on="pro" /></div>
        <div className="sp-teams">{PRO.map(([k, l]) => <button key={k} className={cx(lg === k && "on")} onClick={() => pgo(k === "mlb" ? "sports/pro" : `sports/pro/${k}`)}>{l}</button>)}</div>
        {lg === "soccer" && (
          <div className="sp-teams sp-sub">{SOCCER.map(([k, l]) => <button key={k} className={cx(sub === k && "on")} onClick={() => pgo(`sports/pro/soccer/${k}`)}>{l}</button>)}</div>
        )}
        {lg === "mlb" ? <ProSports route={route.slice(1)} /> : <LeagueView key={lg === "soccer" ? sub : lg} lg={lg === "soccer" ? sub : lg} />}
        <div style={{ height: 30 }} />
      </div>
    );
  }
  if (route[0] === "college") {
    return <College lg={route[1]} />;
  }
  return <SchoolSports route={route} />;
}

function College({ lg }: { lg?: string }) {
  const [def, setDef] = useState<string | null>(lg || null);
  useEffect(() => {
    if (lg) return;
    // start on whatever's in season in the story: football in the fall, basketball in the winter
    phoneApi.leagues().then((r) => {
      const on = r.leagues.find((l) => l.kind === "college" && l.in_season);
      setDef(on ? on.league : "cfb");
    }).catch(() => setDef("cfb"));
  }, [lg]);
  const cur = lg || def;
  return (
    <div className="sp">
      <div className="sp-top"><h1 className="sp-h1">Sports</h1><Side on="college" /></div>
      <div className="sp-teams">{COLLEGE.map(([k, l]) => <button key={k} className={cx(cur === k && "on")} onClick={() => pgo(`sports/college/${k}`)}>{l}</button>)}</div>
      {cur ? <LeagueView key={cur} lg={cur} /> : <div className="pm-empty"><span className="ph-spinner" /></div>}
      <div style={{ height: 30 }} />
    </div>
  );
}

function SchoolSports({ route }: { route: string[] }) {
  const { toast } = usePhone();
  const sec = (SECTIONS.find(([k]) => k === route[0]) || SECTIONS[0])[0];
  const [team, setTeam] = useState("");
  const [v, setV] = useState<SportsView | null>(null);
  useEffect(() => {
    phoneApi.sports(team).then(setV).catch((e) => toast(errText(e), "bad"));
  }, [team]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!v) return <div className="sp"><div className="pm-empty"><span className="ph-spinner" /></div></div>;
  if (!v.teams.length || !v.team) {
    return (
      <div className="sp">
        <div className="sp-top"><h1 className="sp-h1">Sports</h1><Side on="school" /></div>
        <div className="sp-card">
          <b>You're not on a team right now.</b>
          <p className="ph-dim small">Tryouts are on your calendar; make a team and this is where your season lives: the standings, your stats, your playing time, the awards race and recruiting.</p>
          {(v.tryouts || []).map((t) => <div key={t.name} className="sp-try"><PIcon name="ball" size={16} /> {t.name} · {t.date}</div>)}
        </div>
      </div>
    );
  }
  const t = v.team;
  return (
    <div className="sp">
      <div className="sp-top"><h1 className="sp-h1">Sports</h1><Side on="school" /></div>
      {v.teams.length > 1 && (
        <div className="sp-teams">
          {v.teams.map((x) => <button key={x.id} className={cx(x.id === t.id && "on")} onClick={() => setTeam(x.id)}>{x.name}{x.in_season ? "" : " · off"}</button>)}
        </div>
      )}
      <div className="sp-seg">
        {SECTIONS.map(([k, l]) => <button key={k} className={cx(sec === k && "on")} onClick={() => pgo(k === "season" ? "sports" : `sports/${k}`)}>{l}</button>)}
      </div>
      {sec === "season" && <Season v={v} />}
      {sec === "league" && <League v={v} />}
      {sec === "awards" && <Awards v={v} />}
      {sec === "recruiting" && <Recruiting v={v} />}
      <div style={{ height: 30 }} />
    </div>
  );
}

function TeamCard({ v }: { v: SportsView }) {
  const t = v.team!;
  return (
    <div className="sp-team">
      <div className="sp-team-top">
        <div className="sp-rec"><b>{t.record}</b><small>{t.rank ? `#${t.rank} of ${t.of} in the ${t.conference}` : t.conference}</small></div>
        <div className="sp-team-m">
          <b>{t.name}</b>
          <span>{t.streak ? `${t.streak[0] === "W" ? "Won" : "Lost"} ${t.streak.slice(1)} straight` : "Season's just starting"}{t.title ? ` · ${t.title === t.ours ? "Champions" : `${t.title} won the title`}` : ""}</span>
          {t.last && <span>Last: {t.last.win ? "beat" : "lost to"} {t.last.vs}, {t.last.score}</span>}
        </div>
      </div>
      {t.next && (
        <div className={cx("sp-next", t.next.rival && "rival")}>
          <div className="sp-next-h">{t.next.rival ? "Rivalry game" : "Next game"} · {t.next.in_days === 0 ? "today" : t.next.in_days === 1 ? "tomorrow" : t.next.date.replace(/, \d{4}$/, "")}</div>
          <b>vs {t.next.opponent}{t.next.their_record ? ` (${t.next.their_record}, #${t.next.their_rank})` : ""}</b>
          {t.next.stars.length > 0 && <small>Watch for {t.next.stars.map((s) => `${s.name} (${s.pos})`).join(" and ")}</small>}
        </div>
      )}
    </div>
  );
}

function Season({ v }: { v: SportsView }) {
  const y = v.you!;
  const [depth, setDepth] = useState(false);
  const max = Math.max(...y.parts.map((p) => Math.abs(p.value)), 1);
  return (
    <>
      <TeamCard v={v} />

      <div className="sp-h">Your playing time</div>
      <div className="sp-card">
        <div className="sp-role">
          <span className={cx("sp-pill", y.injured ? "hurt" : y.starter ? "start" : "bench")}>{y.injured ? "Injured" : y.starter ? "Starting" : "Off the bench"}</span>
          <span>{y.level === "jv" ? "JV" : "Varsity"}{y.position ? ` · ${y.position}` : ""} · {y.spot === 1 ? "best" : `#${y.spot}`} of {y.of} on the team (top {y.starters} start)</span>
        </div>
        <div className="sp-rating"><b>{y.rating}</b><small>your rating: what the coach goes by</small></div>
        {y.parts.map((p) => (
          <div key={p.key} className="sp-part">
            <span>{p.label}</span>
            <i><s style={{ width: `${Math.max(3, (100 * Math.abs(p.value)) / max)}%` }} className={cx(p.value < 0 && "neg")} /></i>
            <em>{p.value > 0 ? "+" : ""}{p.value}</em>
          </div>
        ))}
        {y.vs && <p className="sp-vs">{y.vs.line}</p>}
        <div className="sp-tip"><b>Your next move</b>{y.tip}</div>
        {y.coach && <p className="ph-dim small">{y.coach.name} {y.coach.label}.{y.missed ? ` You've missed ${y.missed} practice${y.missed === 1 ? "" : "s"} or game${y.missed === 1 ? "" : "s"}: miss too many and you're off the team.` : ""}</p>}
        <button className="ph-link" onClick={() => setDepth(!depth)}>{depth ? "Hide" : "See"} the depth chart</button>
        {depth && (
          <div className="sp-depth">
            {y.depth.map((d, i) => (
              <React.Fragment key={d.id}>
                {i === y.starters && <div className="sp-cut">the starting line</div>}
                <div className={cx("sp-drow", d.you && "you")}>
                  <span className="sp-dn">{i + 1}</span>
                  <span className="sp-dm"><b>{d.you ? "You" : d.name}</b><small>{[d.pos, d.grade ? `grade ${d.grade}` : null].filter(Boolean).join(" · ")}</small></span>
                  <em>{d.rating}</em>
                </div>
              </React.Fragment>
            ))}
          </div>
        )}
      </div>

      <div className="sp-h">Your season</div>
      <div className="sp-card">
        <b className="sp-line">{y.season || "No games yet"}</b>
        <small className="ph-dim">{y.games} game{y.games === 1 ? "" : "s"}, {y.starts} start{y.starts === 1 ? "" : "s"}</small>
        {y.awards.length > 0 && <div className="sp-awards">{y.awards.map((a, i) => <span key={i}>{a}</span>)}</div>}
        {y.log.length > 0 && (
          <div className="sp-log">
            {y.log.map((g, i) => (
              <div key={i} className="sp-game">
                <span className={cx("sp-wl", g.win ? "w" : "l")}>{g.win ? "W" : "L"}</span>
                <span className="sp-gm"><b>{g.rivalry ? "Rivalry: " : ""}vs {g.opponent} · {g.score}</b><small>{g.line}{g.started ? "" : " · off the bench"} · {g.date.replace(/^\w+, /, "").replace(/, \d{4}$/, "")}</small>
                  {g.play && <i className={cx("sp-play", g.play_tier || "")}>⚡ {g.play}</i>}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}

function League({ v }: { v: SportsView }) {
  const t = v.team!;
  return (
    <>
      <div className="sp-h">{t.conference} standings{t.title ? <small> · {t.title} won the title</small> : null}</div>
      <div className="sp-table">
        <div className="sp-tr head"><span>#</span><span>Team</span><span>W-L</span><span>Diff</span><span>Streak</span></div>
        {(v.standings || []).map((r) => (
          <div key={r.name} className={cx("sp-tr", r.ours && "ours", r.rival && "rival")}>
            <span>{r.rank}</span>
            <span className="sp-tn">{r.name}{r.rival ? <i>rival</i> : null}<Move m={r.power_move} /></span>
            <span>{r.w}-{r.l}</span>
            <span>{r.diff > 0 ? "+" : ""}{r.diff}</span>
            <span>{r.streak}</span>
          </div>
        ))}
      </div>
      <p className="ph-dim small">Every school plays every week. Arrows are this week's moves in the power rankings.</p>
      <div className="sp-h">League leaders</div>
      {Object.entries(v.leaders || {}).length === 0 && <p className="ph-dim small">No games yet.</p>}
      {Object.entries(v.leaders || {}).map(([k, l]) => (
        <div key={k} className="sp-card sp-lead">
          <b>{l.label}</b>
          {l.rows.map((r, i) => (
            <div key={r.id} className={cx("sp-lrow", r.ours && "ours")}>
              <span className="sp-dn">{i + 1}</span><span className="sp-dm"><b>{r.name}</b><small>{r.team}</small></span><em>{r.value}</em>
            </div>
          ))}
        </div>
      ))}
    </>
  );
}

function Awards({ v }: { v: SportsView }) {
  const r = v.race!;
  const t = v.team!;
  return (
    <>
      <div className="sp-h">Player of the Week</div>
      {(v.potw || []).length === 0 && <p className="ph-dim small">Picked every week from every game in the {t.conference}. None yet.</p>}
      {(v.potw || []).map((p, i) => (
        <div key={i} className={cx("sp-card sp-potw", p.ours && "ours")}>
          <small>{p.week_of.replace(/^\w+, /, "").replace(/, \d{4}$/, "")}</small><b>{p.name}</b><span>{p.team}: {p.text}</span>
        </div>
      ))}
      <div className="sp-h">All-{t.conference} race{r.you ? <small> · you're #{r.you}</small> : null}</div>
      <div className="sp-card">
        <p className="ph-dim small" style={{ marginTop: 0 }}>Everyone in the league by impact per game. Starting most games at {r.cut}+ gets you named.</p>
        {r.all_conf.map((x, i) => (
          <div key={x.id} className={cx("sp-lrow", x.ours && "ours", x.you && "you")}>
            <span className="sp-dn">{i + 1}</span><span className="sp-dm"><b>{x.you ? "You" : x.name}</b><small>{x.team} · {x.line}</small></span>
            <em className={cx(x.per >= r.cut && "in")}>{x.per}</em>
          </div>
        ))}
      </div>
      <div className="sp-h">Team MVP race</div>
      <div className="sp-card">
        {r.mvp.length === 0 && <p className="ph-dim small">No games yet.</p>}
        {r.mvp.map((x, i) => (
          <div key={x.id} className={cx("sp-lrow", x.you && "you")}>
            <span className="sp-dn">{i + 1}</span><span className="sp-dm"><b>{x.you ? "You" : x.name}</b><small>{x.line}</small></span><em>{x.per}</em>
          </div>
        ))}
      </div>
    </>
  );
}

function Recruiting({ v }: { v: SportsView }) {
  const rc = v.recruiting!;
  return (
    <>
      <div className="sp-h">Recruiting</div>
      <div className="sp-card">
        <p className="ph-dim small" style={{ marginTop: 0 }}>College coaches look at your rating, what you produce in games, your awards and your grades. They start watching sophomore year; offers come junior and senior year.</p>
        {rc.score !== null && rc.score !== undefined && <div className="sp-rating"><b>{rc.score}</b><small>how you look to college coaches</small></div>}
        {(rc.grade || 0) < 10 && <p className="ph-dim small">You're a freshman: this fills up next year.</p>}
        {rc.offers.length > 0 && (
          <>
            <div className="sp-sub">Offers</div>
            {rc.offers.map((o, i) => <div key={i} className="sp-offer"><b>{o.name}</b><small>{o.aid} · {o.conference}</small></div>)}
          </>
        )}
        {rc.interest.length > 0 && (
          <>
            <div className="sp-sub">Who's interested</div>
            {rc.interest.map((c) => (
              <div key={c.name} className="sp-int"><span>{c.name}</span><i><s style={{ width: `${c.level}%` }} /></i></div>
            ))}
          </>
        )}
        {(rc.grade || 0) >= 10 && !rc.interest.length && <p className="ph-dim small">Nobody yet. Start, produce, win something.</p>}
      </div>
    </>
  );
}
