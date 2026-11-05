import React, { useMemo, useState } from "react";
import { go, useApi, useStore } from "../store";
import { Avatar, Empty, EventRow, LineChart, Loading, Name, Names, Panel, Stat, Tabs, Tag, fmt } from "../ui";

const FEEDS: Record<string, (t: string) => boolean> = {
  all: () => true,
  social: (t) => /^(interact|lunch|milestone|clique|party|dance|exclusion|gossip|rumor)/.test(t),
  romance: (t) => /^(ask_|break_up|milestone|dance|party)/.test(t),
  conflict: (t) => /^(confront|tease|spread_rumor|rumor_reached|exclusion|apologize|party)/.test(t),
  school: (t) => /^(tryout|audition|game|show|election|exam|household|practice|job|sign_up|graduation|new_year|season_end)/.test(t),
};

const TREND_SETS: Record<string, [string, string, string][]> = {
  social: [["mutual_friendships", "Mutual friendships", "#57d9c3"], ["couples", "Couples", "#ff8fc7"], ["cliques", "Cliques", "#9b8cff"]],
  wellbeing: [["avg_mood", "Average mood", "#66d98f"], ["avg_stress", "Average stress", "#ff6b81"]],
  friction: [["conflicts", "Conflicts (total)", "#ff6b81"], ["exclusions", "Exclusions (total)", "#ffb547"], ["rumors", "Rumors (total)", "#9b8cff"]],
  standing: [["popularity_gini", "Popularity inequality (Gini)", "#ffb547"], ["isolated_students", "Students without a mutual friend", "#6bb6ff"]],
  school: [["avg_gpa", "Average GPA", "#6bb6ff"]],
};

export default function Overview() {
  const { data, error } = useApi("/api/overview");
  const { world, advance } = useStore();
  const [feed, setFeed] = useState("all");
  const [trend, setTrend] = useState("social");
  const recent = useMemo(() => (data ? data.recent.filter((e: any) => (FEEDS[feed] || FEEDS.all)(e.type)) : []), [data, feed]);
  if (error) return <div className="errorbox">{error}</div>;
  if (!data) return <Loading what="Reading the town" />;
  const m = data.metrics;
  const series = data.series || [];
  const isFresh = world && world.day < 3;
  const kindOrder: Record<string, number> = { team: 0, production: 1, council: 2, club: 3, job: 4 };
  return (
    <div className="stack">
      <div className="page-h">
        <div>
          <h1>{data.world.town?.name} <span className="muted" style={{ fontWeight: 500 }}>· {data.world.school?.name}</span></h1>
          <p>{data.world.town?.tagline}</p>
        </div>
        <div className="row">
          <button onClick={() => go("characters")}>Meet the people</button>
          <button onClick={() => go("social")}>See the social web</button>
        </div>
      </div>

      {isFresh && (
        <div className="banner">
          <div>
            <h3>A new world is waiting</h3>
            <div className="muted">
              {m.students} students and their teachers, families and rivalries. Nothing has happened yet. Advance time and they start living:
              deciding, meeting, falling out, trying out. Every choice they make is inspectable.
            </div>
          </div>
          <div className="row">
            <button className="primary" onClick={() => advance(7)}>Run the first week</button>
            <button onClick={() => advance(30)}>Run a month</button>
          </div>
        </div>
      )}

      <div className="stats">
        <Stat label="Students" value={m.students} sub={`${data.world.population.staff || 0} staff`} />
        <Stat label="Mutual friendships" value={m.mutual_friendships} sub={`${m.one_sided_friendships} one-sided`} tone="accent" onClick={() => go("social")} />
        <Stat label="Couples" value={m.couples} sub={`${m.relationships_started} started · ${m.breakups} breakups`} />
        <Stat label="Cliques" value={m.cliques} sub={`${Math.round(m.clique_coverage * 100)}% of students in one`} />
        <Stat label="Average mood" value={fmt(m.avg_mood)} tone={m.avg_mood >= 60 ? "good" : m.avg_mood < 40 ? "bad" : "warn"} />
        <Stat label="Average stress" value={fmt(m.avg_stress)} tone={m.avg_stress > 55 ? "bad" : undefined} />
        <Stat label="Conflicts" value={m.conflicts} sub={`${m.reconciliations} reconciliations`} tone={m.conflicts ? "bad" : undefined} />
        <Stat label="Exclusions" value={m.exclusions} sub={`${m.teasing} mockery incidents`} />
        <Stat label="Rumors" value={m.rumors} sub={`passed on ${m.rumor_spreads}x`} />
        <Stat label="Average GPA" value={fmt(m.avg_gpa, 2)} />
      </div>

      <div className="grid g-main">
        <Panel title="What's been happening" sub="Notable events, newest first. Click any one to see exactly why it happened."
          actions={<Tabs tabs={[["all", "All"], ["social", "Social"], ["romance", "Romance"], ["conflict", "Conflict"], ["school", "School"]]} active={feed} onChange={setFeed} />}>
          <div className="evlist scroll">
            {recent.length ? recent.map((e: any) => <EventRow key={e.id} ev={e} />) : <Empty>Nothing notable yet. Advance time.</Empty>}
          </div>
          <div className="row" style={{ marginTop: 10 }}>
            <button className="small" onClick={() => go("history")}>Open the History Explorer</button>
          </div>
        </Panel>
        <div className="stack">
          <Panel title="Coming up" sub="The next four weeks on the school calendar">
            {data.upcoming.length ? (
              <table className="mini">
                <tbody>
                  {data.upcoming.map((u: any, i: number) => (
                    <tr key={i}>
                      <td className="dim" style={{ whiteSpace: "nowrap" }}>{u.date}</td>
                      <td>{u.name}</td>
                      <td><Tag tone={u.kind === "tryout" || u.kind === "audition" ? "accent" : u.kind === "dance" ? "romance" : "dim"}>{u.kind}</Tag></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : <Empty>Nothing scheduled.</Empty>}
          </Panel>
          <Panel title="Spotlight" sub="Who to watch right now">
            {[["Most popular", data.spotlight.most_popular], ["Most stressed", data.spotlight.most_stressed], ["Loneliest right now", data.spotlight.loneliest]].map(([l, ids]: any) => (
              <div key={l} style={{ marginBottom: 10 }}>
                <div className="hint" style={{ marginBottom: 5 }}>{l}</div>
                <div className="row">{ids.map((id: string) => <Avatar key={id} id={id} size={32} />)}</div>
              </div>
            ))}
          </Panel>
        </div>
      </div>

      <Panel title="Trends" sub="Weekly snapshots of the whole world" actions={
        <Tabs tabs={[["social", "Social"], ["wellbeing", "Wellbeing"], ["friction", "Friction"], ["standing", "Status"], ["school", "School"]]} active={trend} onChange={setTrend} />}>
        <LineChart height={190} xLabels={series.map((s: any) => s.label)}
          series={TREND_SETS[trend].map(([k, l, c]) => ({ name: l, color: c, values: series.map((s: any) => s[k]) }))} />
      </Panel>

      <div className="grid g2">
        <Panel title="Cliques" sub="Detected weekly from mutual affection. Names come from what members have in common.">
          {data.cliques.length ? data.cliques.map((q: any) => (
            <div key={q.id} className="row between" style={{ padding: "8px 0", borderBottom: "1px solid var(--line)" }}>
              <div>
                <b>{q.name}</b> <span className="hint">avg popularity {fmt(q.popularity)}</span>
                <div className="small"><Names ids={q.members} max={7} /></div>
                <div className="chips" style={{ marginTop: 4 }}>{(q.interests || []).map(([k]: any) => <Tag key={k}>{k.replace(/_/g, " ")}</Tag>)}</div>
              </div>
              <div className="row" style={{ gap: 0 }}>{q.members.slice(0, 5).map((id: string) => <Avatar key={id} id={id} size={26} ring={false} />)}</div>
            </div>
          )) : <Empty>No cliques yet. They form as friendships become mutual.</Empty>}
        </Panel>
        <Panel title="Institutions" sub="Teams, productions, clubs, council and jobs">
          <table className="mini">
            <thead><tr><th>group</th><th>kind</th><th className="num">members</th><th>status</th></tr></thead>
            <tbody>
              {[...data.groups].sort((a: any, b: any) => kindOrder[a.kind] - kindOrder[b.kind]).map((g: any) => (
                <tr key={g.id} className="click" onClick={() => go("social/groups")}>
                  <td>{g.name}</td>
                  <td><Tag>{g.kind}</Tag></td>
                  <td className="num">{g.members}/{g.capacity}</td>
                  <td className="dim">
                    {g.kind === "team" ? (g.in_season ? `in season · ${g.record.w}-${g.record.l}` : "off season") : g.kind === "production" ? (g.production ? `rehearsing ${g.production}` : "between shows") : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      </div>
    </div>
  );
}
