// One league behind the story (the NFL, the NBA, or a college sport), as it really happened, through today: your team,
// its games, the postseason so far, the table or this week's top 25, the champions, the news.
import React, { useEffect, useState } from "react";
import { LeagueView as LV, LgPost, phoneApi } from "./api";
import { cx, errText, Sheet } from "./kit";
import { usePhone } from "./PhoneContext";

export default function LeagueView({ lg }: { lg: string }) {
  const { toast } = usePhone();
  const [v, setV] = useState<LV | null>(null);
  const [pick, setPick] = useState(false);
  const [q, setQ] = useState("");
  useEffect(() => {
    setV(null);
    phoneApi.league(lg).then(setV).catch((e) => toast(errText(e), "bad"));
  }, [lg]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!v) return <div className="pm-empty"><span className="ph-spinner" /></div>;
  const follow = async (team: string) => {
    try {
      setV(await phoneApi.leagueFollow(lg, team));
      setPick(false);
    } catch (e) {
      toast(errText(e), "bad");
    }
  };
  const college = v.kind === "college";
  const soccer = v.kind === "soccer";

  if (v.award) {
    return (
      <>
        <div className="pro-team t-none">
          <div className="sp-team-m">
            <small className="lg-k">Ballon d'Or</small>
            <b>{v.winners && v.winners[0]?.winner ? v.winners[0].winner : "Ballon d'Or"}</b>
            <span>{v.winners && v.winners[0]?.club ? `${v.winners[0].year} · ${v.winners[0].club}` : ""}</span>
          </div>
          {v.next && <div className="pro-status">{v.next}</div>}
        </div>
        <div className="sp-h">Winners</div>
        <div className="sp-card">
          {(v.winners || []).map((a) => (
            <div key={a.year} className="lg-champ">
              <b>{a.year}</b>
              <span>{a.winner ? <>{a.winner} ({a.club}){a.women ? <><br />Women's: {a.women} ({a.women_club})</> : null}</> : a.note}</span>
            </div>
          ))}
        </div>
        <News v={v} />
        <p className="ph-dim small pro-src">{v.note}</p>
      </>
    );
  }

  if (v.titles_only) {
    return (
      <>
        <div className="pro-team t-none">
          <div className="sp-team-m">
            <small className="lg-k">{v.label}{soccer ? " · your clubs" : ""}</small>
            {soccer ? <span className="lg-clubs">{v.school}</span> : <b>{v.school}</b>}
            <span>{v.school_titles && v.school_titles.length ? `${v.event} titles: ${v.school_titles.join(", ")}` : `No ${v.event} titles yet.`}</span>
          </div>
          {v.next && <div className="pro-status">{v.next}</div>}
          {!soccer && <button className="pro-change" onClick={() => setPick(true)}>Follow a different school</button>}
        </div>
        <div className="sp-h">{soccer ? "Finals" : `${v.event} finals`}</div>
        <div className="sp-card">
          {(v.finals || []).length === 0 && <p className="ph-dim small">None yet.</p>}
          {(v.finals || []).map((f) => (
            <div key={f.season} className={cx("lg-champ", f.champ !== null && (v.school || "").split(", ").includes(f.champ) && "mine")}>
              <b>{f.label || f.season}</b>
              <span>{f.champ ? <>{f.champ} over {f.runner_up}{f.score ? `, ${f.score}` : ""}{f.note ? ` (${f.note})` : ""}</> : f.note}</span>
            </div>
          ))}
        </div>
        <News v={v} />
        <p className="ph-dim small pro-src">{v.note}</p>
        <SchoolPicker open={pick} onClose={() => setPick(false)} q={q} setQ={setQ} onPick={follow} />
      </>
    );
  }

  const m = v.my_team;
  const teams = (v.teams || []).filter((t) => !q || t.name.toLowerCase().includes(q.toLowerCase()));
  return (
    <>
      {m && (
        <div className={cx("pro-team", "lg-" + lg)}>
          <div className="pro-team-top">
            <div className="sp-rec"><b>{soccer ? `${m.points ?? 0} pts` : m.record || "0-0"}</b><small>{soccer && m.record ? `${m.record} (W-D-L)` : `${v.season} season`}</small></div>
            <div className="sp-team-m">
              <b>{m.rank ? <span className="lg-rank">#{m.rank}</span> : null}{m.name}</b>
              {m.place && <span>{m.place}{m.conf_record ? ` (${m.conf_record})` : ""}</span>}
            </div>
          </div>
          {m.status && <div className="pro-status">{m.status}</div>}
          {m.next && <div className="lg-next">Next: {m.next.home ? "vs" : "at"} {m.next.opp}, {m.next.date.replace(/, \d{4}$/, "")}{m.next.label ? ` · ${m.next.label}` : ""}</div>}
          <button className="pro-change" onClick={() => setPick(true)}>{college ? "Follow a different school" : soccer ? "Follow a different club" : "Not your team? Change it"}</button>
        </div>
      )}

      {m && m.last.length > 0 && (
        <>
          <div className="sp-h">Last games</div>
          <div className="sp-card">
            {m.last.map((g, i) => (
              <div key={i} className="lg-game">
                <span className={cx("sp-wl", g.result === "W" ? "w" : g.result === "T" ? "d" : "l")}>{soccer && g.result === "T" ? "D" : g.result}</span>
                <span className="sp-gm"><b>{g.home ? "vs" : "at"} {g.opp} · {g.score}</b><small>{g.date}{g.label ? ` · ${g.label}` : g.conf ? " · conference" : ""}</small></span>
              </div>
            ))}
          </div>
        </>
      )}

      {(v.postseason || []).length > 0 && (
        <>
          <div className="sp-h">{v.champ ? `${v.champ}: champions` : "The postseason so far"}</div>
          <Post post={v.postseason!} mine={m?.team} />
        </>
      )}

      {college && (v.top25 || []).length > 0 && (
        <>
          <div className="sp-h">Top 25 <small>from results</small></div>
          <div className="sp-card lg-top">
            {v.top25!.map((t) => (
              <div key={t.team} className={cx("lg-trow", t.team === m?.team && "mine")}><span>{t.rank}</span><b>{t.name}</b><em>{t.record}</em></div>
            ))}
          </div>
        </>
      )}

      {(v.standings || []).map((d) => (
        <div key={d.group} className="sp-table pro-table">
          {soccer ? (
            <>
              <div className="pro-tr head"><span>{d.label}</span><span>W</span><span>D</span><span>L</span><span>Pts</span></div>
              {d.rows.map((r, i) => (
                <div key={r.team} className={cx("pro-tr", r.team === m?.team && "ours")}>
                  <span className="sp-tn"><i className="lg-pos">{i + 1}</i>{r.name}</span><span>{r.w}</span><span>{r.t}</span><span>{r.l}</span><span><b>{r.pts}</b></span>
                </div>
              ))}
            </>
          ) : (
            <>
              <div className="pro-tr head"><span>{d.label}</span><span>W</span><span>L</span><span>{college ? "Conf" : ""}</span><span></span></div>
              {d.rows.map((r) => (
                <div key={r.team} className={cx("pro-tr", r.team === m?.team && "ours")}>
                  <span className="sp-tn">{r.name}</span><span>{r.w}</span><span>{r.l}{r.t ? `-${r.t}` : ""}</span><span>{college ? `${r.cw}-${r.cl}` : ""}</span><span></span>
                </div>
              ))}
            </>
          )}
        </div>
      ))}

      {(v.champions || []).length > 0 && (
        <>
          <div className="sp-h">Champions</div>
          <div className="sp-card">
            {v.champions!.map((c) => (
              <div key={c.season} className={cx("lg-champ", c.mine && "mine")}><b>{c.season}</b><span>{c.champ}{c.runner_up ? `${soccer ? ", ahead of" : " over"} ${c.runner_up}` : ""}</span></div>
            ))}
          </div>
        </>
      )}

      <News v={v} />
      <p className="ph-dim small pro-src">{v.note}</p>

      {college ? (
        <SchoolPicker open={pick} onClose={() => setPick(false)} q={q} setQ={setQ} onPick={follow} schools={(v.teams || []).map((t) => t.name)} />
      ) : (
        <Sheet open={pick} onClose={() => setPick(false)} title="Your team">
          <input className="lg-search" placeholder="Search" value={q} onChange={(e) => setQ(e.target.value)} />
          <div className="pro-pick">
            {teams.map((t) => <button key={t.team} className={cx(t.team === m?.team && "on")} onClick={() => follow(t.name)}>{t.name}</button>)}
          </div>
        </Sheet>
      )}
    </>
  );
}

function News({ v }: { v: LV }) {
  if (!v.news.length) return null;
  return (
    <>
      <div className="sp-h">News</div>
      <div className="sp-card pro-news">
        {v.news.map((n, i) => <div key={i} className={cx("pro-n", n.mine && "mine")}><p>{n.text}</p><small>{n.date}</small></div>)}
      </div>
    </>
  );
}

function Post({ post, mine }: { post: LgPost[]; mine?: number }) {
  const rounds = Array.from(new Set(post.map((p) => p.label)));
  return (
    <div className="pro-oct">
      {rounds.reverse().map((r) => {
        const games = post.filter((p) => p.label === r);
        const shown = games.filter((g) => mine === undefined || games.length <= 8 || g.teams.includes(mine) || g.label.includes("Final") || g.label.includes("champ"));
        return (
          <div key={r} className="pro-round">
            <small>{r}{shown.length < games.length ? ` · ${games.length} games` : ""}</small>
            {shown.map((g, i) => (
              <div key={i} className={cx("pro-ser", mine !== undefined && g.teams.includes(mine) && "mine")}>
                {g.teams.map((t, k) => (
                  <div key={t} className={cx("pro-st", g.winner === t && "won", g.done && g.winner !== t && "out")}>
                    <span>{g.names[k]}</span><b>{g.score[k]}</b>
                  </div>
                ))}
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}

const SCHOOLS = ["UConn", "Stanford", "UCLA", "LSU", "North Carolina", "Texas", "Oklahoma", "Florida State", "Miami", "Michigan"];

function SchoolPicker({ open, onClose, q, setQ, onPick, schools }: {
  open: boolean; onClose: () => void; q: string; setQ: (s: string) => void; onPick: (s: string) => void; schools?: string[];
}) {
  const all = Array.from(new Set([...SCHOOLS, ...(schools || [])]));
  const list = all.filter((s) => !q || s.toLowerCase().includes(q.toLowerCase()));
  return (
    <Sheet open={open} onClose={onClose} title="Your school">
      <p className="ph-dim small">One school for all of college sports. Once you're at a college yourself, it follows your school (unless you pick one here).</p>
      <button className="ph-btn block" onClick={() => onPick("")}>Follow my own college</button>
      <input className="lg-search" placeholder="Search schools" value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="pro-pick">
        {list.map((s) => <button key={s} onClick={() => onPick(s)}>{s}</button>)}
      </div>
    </Sheet>
  );
}
