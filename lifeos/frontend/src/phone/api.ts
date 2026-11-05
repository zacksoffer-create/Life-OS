// Phone app API: typed wrappers around /api/phone/* and the story endpoints the phone uses.
import { api } from "../api";

export type Look = {
  skin: string; hair: string; hair_color: string; eyes: string; facial_hair: string; glasses: boolean; freckles: boolean;
};
export type Mood = "happy" | "neutral" | "sad" | "angry" | "flirty" | "surprised" | "tired";

export type Scene = { art: string; title: string; line: string; phase: string; season: string; weekend: boolean; break: string | null; time: string };
export type FeedItem = { id: number; date: string; slot: string; type: string; outcome: string; text: string; with: string[]; importance: number };
export type EdMini = { id: string; name: string; first: string; color: string; look: Look; year: string; role: string };
export type EdRel = { affection: number; attraction: number; trust: number; respect: number; rivalry: number; familiarity: number; perceived: number;
  label: string; crush: boolean };
export type EdPersonRow = EdMini & { grade: number | null; me: boolean; family: boolean; known: boolean; label: string | null; close: number };
export type EdSchema = { traits: string[]; aptitudes: string[]; motives: string[]; needs: string[]; skills: { id: string; label: string }[];
  interests: { id: string; label: string }[]; rel_fields: { id: string; label: string; min: number; max: number }[]; crush_at: number; friend_at: number };
export type EdPerson = EdMini & { last: string; bio: string; gender: string; grade: number | null; is_me: boolean; look_locked: Partial<Look>;
  traits: Record<string, number>; aptitudes: Record<string, number>; motives: Record<string, number>; skills: Record<string, number>;
  interests: Record<string, number>; needs: Record<string, number>; mood: number; popularity: number; money: number; gpa: number; student: boolean;
  partner: string | null; with_me: { ab: EdRel | null; ba: EdRel | null } | null;
  flirt?: { styles: { style: string; label: string; value: number; say: string; set: boolean; personality: number }[]; custom: boolean };
  pronouns: string; attracted_to: string[]; birthday: [number, number]; archetype: string; body: { height_in?: number; build?: string };
  positions: Record<string, string>; jersey: number | null; path: { kind?: string; college?: string; sport?: string }; staff: boolean; role?: string;
  rels: (EdMini & { roles: string[]; ab: EdRel | null; ba: EdRel | null })[] };
export type EdPair = { a: EdMini; b: EdMini; ab: EdRel | null; ba: EdRel | null; roles: string[]; dating: boolean; presets: { id: string; label: string }[] };
export type SceneMini = { id: string; name: string; first: string; color: string; look: Look; year: string };
export type LadderRow = SceneMini & {
  rank: number | null; scope_rank?: number; move: number | null; pop?: number; grade?: number | null; known_for: string; tags: string[];
  storylines: string[]; label?: string | null; via?: SceneMini | null; why?: string | null;
};
export type LadderPart = { key: string; label: string; score: number; line: string; value?: number; of?: number };
export type Superlative = { key: string; label: string; winner: SceneMini & { you: boolean }; partner?: SceneMini; runners: SceneMini[]; you: number | null };
export type LadderView = {
  you: LadderRow & { of: number; tier: string; grade_rank: number; grade_of: number; grade_label: string;
    history: { day: number; date: string; rank: number; of: number }[]; next_up: (LadderRow & { gap: number }) | null;
    this_week: { text: string; date: string; imp: number }[]; parts: LadderPart[]; tip: string };
  movers: { up: LadderRow[]; down: LadderRow[] }; rows: LadderRow[]; scope: string; of: number; storyline_people: LadderRow[];
  week_of: string | null; superlatives: Superlative[];
};
export type SceneView = {
  me: { rank: number; of: number; grade_rank: number; grade_of: number; tier: string; popularity: number; group: string | null; reputation: string[]; friends: number };
  groups: { id: string; name: string; size: number; mine: boolean; members: (SceneMini & { friend: boolean; me: boolean; family: boolean })[]; friends: number;
    way_in: SceneMini | null; vibe: string; standing: string; since: string }[];
  couples: { a: SceneMini; b: SceneMini; since: string; new: boolean; you: boolean }[];
  breakups: { a: SceneMini; b: SceneMini; when: string }[];
  popular: (SceneMini & { you: boolean })[];
  meet: (SceneMini & { mutual: string[]; n: number; via: SceneMini })[];
  intro_today: boolean;
  talk: Rumor[];
  fights: { a: string; b: string; reason: string; when: string }[];
};
export type Rumor = { id: string; text: string; about_you: boolean; true: boolean | null; about: { id: string; first: string; color: string; look: Look } | null;
  from: string | null; known: number; spread: string; when: string; new: boolean; acted: string | null; origin: string | null };
export type MomentGame = { id: string; title: string; secs?: number | null; icon: string };
export type Moment = { id: string; kind: string; day: number; title: string; text: string; ctx: any; choices: { label: string; hint: string; game?: MomentGame }[]; storyline?: string | null;
  episode_label?: string | null; previously?: string | null };
export type PetDuty = { id: string; label: string; hint: string; when: string; owner: string; today: string; due: boolean; done: boolean; done_by: string | null };
export type Pet = {
  id: string; name: string; species: "dog" | "cat" | "rabbit"; species_label: string; breed: string; coat: string; personality: string; age: number;
  pronoun: string; possessive: string; mood: string; happiness: number; fullness: number; energy: number; health: number; clean: number;
  bond: Record<string, number>; my_bond: number; tricks: { name: string; progress: number }[]; duties: PetDuty[]; setup_needed: boolean;
  streak: number; quick_left: Record<string, number>; activities: { id: string; label: string; quick: boolean }[]; adopted: string;
};
export type SportsRow = { rank: number; name: string; w: number; l: number; pct: number; pf: number; pa: number; diff: number; streak: string;
  ours: boolean; rival: boolean; power?: number | null; power_move?: number | null };
export type RaceRow = { id: string; name: string; team: string; ours: boolean; you: boolean; per: number; games: number; line: string };
export type SportsView = {
  teams: { id: string; name: string; sport: string; in_season: boolean }[];
  tryouts?: { name: string; date: string }[];
  team?: { id: string; name: string; sport: string; label: string; record: string; rank: number; of: number; streak: string;
    last: { day: number; vs: string; win: boolean; score: string } | null; conference: string; title: string | null; prestige: number;
    rival: string | null; ours: string;
    next: { date: string; in_days: number; opponent: string; rival: boolean; their_record: string | null; their_rank: number | null;
      stars: { name: string; pos: string }[] } | null };
  you?: { level: string; position: string | null; starter: boolean; spot: number; starters: number; of: number; rating: number;
    parts: { key: string; label: string; value: number }[]; tip: string; injured: boolean; missed: number;
    vs: { name: string; first: string; rating: number; gap: number; diff: Record<string, number>; line: string; how: string } | null;
    depth: { id: string; name: string; first: string; rating: number; pos: string | null; grade: number; you: boolean; starter: boolean }[];
    coach: { name: string; respect: number; label: string } | null; season: string | null; games: number; starts: number;
    log: { date: string; opponent: string; win: boolean; score: string; line: string; started: boolean; rivalry: boolean; play?: string | null; play_tier?: string | null }[]; awards: string[] };
  standings?: SportsRow[];
  leaders?: Record<string, { label: string; rows: { id: string; name: string; team: string; ours: boolean; value: number }[] }>;
  potw?: { name: string; team: string; text: string; week_of: string; ours?: boolean }[];
  race?: { all_conf: RaceRow[]; you: number | null; cut: number; mvp: RaceRow[] };
  recruiting?: { grade: number | null; score: number | null; interest: { name: string; level: number; tier: string }[];
    offers: { name: string; short: string; aid: string; conference: string }[] };
};
export type PhoneState = {
  active: boolean; day: number; date: string; weekday: string; term: string; scene: Scene; decision_ready: boolean;
  progress: { day: number; total: number; pct: number; year: number; complete: boolean }; title: string;
  me: any; moments: Moment[]; feed: FeedItem[]; last_event: number; unread: number; needs_reply: number;
  committed?: { kind: string; group: string; label: string } | null;
  pets: Pet[]; pet_setup_needed: boolean; pet_approved: { species: string; day: number } | null; queued: { label: string } | null;
  family: { name: string; guardians: { id: string; name: string; full: string }[]; siblings: { id: string; first: string; year_label: string; location: string; look: Look; path: any }[];
    younger?: { key: string; first: string; year_label: string; starts: string; look: Look }[]; style: string; trust: number };
  teams: { id: string; name: string; sport: string; record: { w: number; l: number }; mine?: { w: number; l: number }; level: string; position: string }[];
  squad?: { name: string; members: { id: string; first: string; look: Look }[]; cohesion: number; last: string | null;
    plan: { label: string; when: string; joined: boolean } | null; jokes: string[] } | null;
  control: { focus: string; girl_asks_guy?: number; ask_invites: boolean; ask_romance: boolean; stop_before_games: boolean; stop_on_big: boolean; auto_lunch?: boolean; class_games?: boolean; editor?: boolean;
    pacing?: string; auto_scenes?: boolean; binge?: boolean };
  stories?: { waiting: number; presented_today: number; target: number | null; pacing: string; label: string; played?: number; binge?: boolean };
  setting: { town: string; school: string; short: string; mascot: string };
};
export type Choice = { index: number; action: string; label: string; category: string; target: string | null; target_name: string | null; prob: number; risk: number; text: string; icon: string; why: string;
  group?: "should" | "want" | "could"; reason?: string; later?: string | null; gut?: boolean; key?: string; crew?: string[];
  section?: "people" | "solo" | "out" | "trouble"; act?: string; who?: string };
export type DaySlot = { phase: string; label: string; icon: string; state: "done" | "now" | "later"; note: string; decide: boolean; kind?: string; plan?: string };
export type PlateItem = { id: string; kind: string; icon: string; title: string; sub: string; go?: string; cta?: string };
export type WeekDay = { n: number; dow: string; num: number; date: string; school: boolean; items: { icon: string; label: string; kind: string }[] };
export type Episode = { number: number; title: string; storyline: string; date: string; choices: string[]; said: string | null; who: string | null; premiere: boolean; finale: boolean };
export type EpisodeGuide = { now: { season: number; label: string }; seasons: { n: number; label: string; episodes: Episode[] }[];
  coming_up: { storyline: string; next: string; chapter: number; of: number }[] };
export type Today = { strip: DaySlot[]; plate: PlateItem[]; week: WeekDay[] };
export type Line = { id: number; type: string; outcome?: string; text: string; with?: string[]; calc?: any };
export type Chip = { label: string; delta: number; good: boolean; who?: string; kind?: string };
export type ThreadSummary = { id: string; kind: "dm" | "group"; title: string; members: string[]; unread: number; last: string; last_from: string; at: string; date: string; needs_reply: boolean };
export type Msg = { id: string; from: string; from_name: string; text: string; at: string; day: number; date: string; kind: string; read: boolean; replies: string[] | null; chosen: number | null; fast?: boolean };
export type ChatSuggestion = { text: string; intent: string; tone: string; style?: string; yn?: string };
export type ChatBar = { can_type: boolean; suggestions: ChatSuggestion[]; status: "new" | "open" | "done" | "no_number" | "none"; stage?: string; read?: string; tone?: string; romance?: boolean };
export type Thread = { id: string; kind: "dm" | "group"; title: string; members: string[]; msgs: Msg[]; can_text: boolean; text_options: { kind: string; label: string }[]; chat?: ChatBar;
  fresh?: number };
export type Vibe = { stage: number; stages: string[]; read: string; tone: string; level: number; signals: { text: string; good: boolean | null }[]; tip: string; romance: boolean;
  tastes?: { style: string; label: string; known: boolean; taste: number | null }[] };
export type ContactRow = {
  id: string; name: string; first: string; year_label: string; look: Look; color: string; label: string; crush: boolean; partner: boolean; roles: string[];
  affection: number; hearts: number; attraction: number; rivalry: number; perceived: number; has_number: boolean; unread: number;
  last: { text: string; at: string; from: string } | null; location: string; role: string; glance?: string;
};
export type WhoFact = { k: string; v: string; tone?: string };
export type Who = { level: "everyone" | "know" | "close"; glance: string; sections: { level: string; label: string; facts: WhoFact[] }[];
  hidden: number; unlock: string | null };
export type Contact = ContactRow & {
  bio: string; archetype: string; pronouns: string; teams: string[]; school: string; since: string | null; feel: string; seems: string;
  trust: number; respect: number; familiarity: number; memories: { text: string; date: string; valence: number }[];
  shared: { id: number; date: string; text: string }[]; text_options: { kind: string; label: string }[]; partner_of: string | null; vibe?: Vibe;
  who?: Who;
};

export type MiniGameRow = { id: string; title: string; label: string; blurb: string; icon: string; ready: boolean; available: boolean; why: string; rewarded_today: boolean; best: number | null };
export type ClassRow = { id: string; name: string; subject: string; teacher: string; honors: boolean; pct: number; letter: string; quizzes: number; quiz_avg: number | null;
  games: number; games_won: number };
export type ClassesView = { gpa: number; year: string; classes: ClassRow[]; upcoming: { name: string; date: string; in_days: number; weight: number }[]; tests_played: number };
export type ScheduleRow = { sid: string; pack: string; title: string; importance: string; window: any; window_rule: string | null; window_text: string;
  order: number; state: string; day?: number; date?: string; reason?: string; detail?: any; why: string; last?: any };
export type ScheduleView = { profile: string; profiles: Record<string, { label: string; about: string }>; auto_scenes: boolean; date: string;
  queue: { sid: string; title: string; phase: string; importance: string }[]; presented_today: number; target_today: number | null;
  backlog: number; overdue: number; majors_this_week: number;
  storylines: { pack: string; name: string; in_order: boolean; played: number; queued: number; eligible: number; waiting: number; unreachable: number; expired: number; presented: number }[];
  scenes: ScheduleRow[] };
export type ScheduleReport = { date: string; profile: string; counts: Record<string, number>; warnings: { sid: string; kind: string; text: string }[];
  deadline_misses: any[]; identity: { slot: string; who: string; name: string | null; problems: string[] }[];
  busiest_days: { date: string; scenes: number }[]; days_with_scenes: number; markdown?: string; coverage?: Coverage };
export type Coverage = { years: { label: string; key: string; months: number[]; total: number }[]; months: string[];
  quiet: { from: string; to: string; days: number; year: string }[] };
export type AddPreview = { ok: boolean; errors: string[]; warnings: string[]; name?: string; fix_prompt?: string | null;
  new?: { sid: string; title: string; state: string; date?: string; reason?: string; why?: string; detail?: any }[]; new_played?: number;
  changed?: { sid: string; title: string; state: string; date?: string; why?: string; reason?: string }[]; already_there?: string[];
  played_total?: number; before?: number | null; coverage?: Coverage; replaces?: string[]; script?: boolean };
export type ReadScene = { sid: string; title: string; storyline: string; pack: string; src: string; plays: boolean; date: string | null;
  day: number | null; why: string | null; detail: any; year: string | null; dated: boolean; unwritten?: boolean; summary?: string;
  when?: string; outline_n?: number | null; if?: string | null };
export type OutlineEntry = { n: number; title: string; when: string; summary: string; if: string | null; written: boolean; sid: string | null };
export type SkippedScene = { n: number; title: string; problems: string[] };
export type RolePerson = { id: string; name: string; first: string; year: string; why?: string; fix?: { sport?: string; pair?: string; label: string } };
export type RoleRow = { key: string; type: "slot" | "kind" | "req"; title: string; label: string; status: "missing" | "open" | "set";
  storylines: { id: string; name: string; scenes: number }[]; scenes: number; who: RolePerson | null; by: string | null;
  options: RolePerson[]; near: RolePerson[]; can_add: boolean; note: string | null; single?: boolean; after?: string };
export type RoleBoard = { roles: RoleRow[]; open: number };
export type GroundworkRow = { kind: string; key: string; title: string; what: string };
export type Groundwork = { rows: GroundworkRow[]; count: number };
export type OldVersion = { file: string; stem: string; title: string; why: string; at: number; scenes: number };
export type TextingBreakdown = { flirt: { label: string; n: number }[]; flirt_total: number; texting: number;
  group_chats: { chat: string; when: string[]; first: string; lines: number; replies: number }[] };
export type TextingCheck = { ok: boolean; breakdown: TextingBreakdown; notes: string[]; text: string; scenes: number };
export type OutlineCheck = { ok: boolean; title: string; expands: string | null; about: string | null; cast: { name: string; label: string }[];
  outline: OutlineEntry[]; notes: string[]; warnings: string[]; pack?: string };
export type ReviseScene = { key: string; n: number | null; title: string; problems: string[]; src?: string };
export type CastLine = { name: string; value: string; named: boolean };
export type ReviseView = { pack: string; name: string; outlined: boolean; scenes: ReviseScene[]; scene_count: number; warnings: string[];
  cast: CastLine[]; can_undo: boolean; roles: string[] };
export type ReviseResult = { ok: boolean; replaced: string[]; head: string[]; skipped: { title: string; problems: string[] }[]; notes: string[];
  still: ReviseScene[]; fix_prompt: string; errors: string[] };
export type WritingRow = { pack: string; name: string; written: number; total: number; played: number; needs_fixing: number; stuck: number;
  stuck_why: string | null; on: boolean };
export type Checkup = { pack: string; name: string; written: number; total: number; gaps: SkippedScene[]; fix_prompt: string };
export type BatchPrompt = { prompt?: string; chars?: number; first?: number; last?: number; total: number; written: number; titles?: string[]; done: boolean };
export type Timing = { years: string[]; months: number[]; spread: boolean; line: string };
export type StorylineRead = { title: string; pack: string; total: number; plays: number; unwritten?: number; scenes: ReadScene[]; coverage: Coverage;
  parts: { pack: string; name: string; expands: string | null; scenes: number; plays: number; timing: Timing | null }[];
  wont: { why: string; count: number; titles: string[] }[] };
export type UpNextRow = { sid: string; title: string; storyline: string; pack: string; day: number; date: string; in_days: number;
  importance: string; ready: boolean; waits_for: string[] };
export type UpNext = { now: { sid: string; title: string } | null; list: UpNextRow[]; date: string;
  changes: { sid: string; title: string; waits_for: { sid: string; title: string }[] }[]; note?: string | null; undid?: boolean };
export type PlayRead = {
  read: { title: string; text: string; storyline: string; chose: string }; lines: Line[]; moment: Moment | null; chapter_done: boolean;
};
export type PlayStep = {
  moment?: Moment; done?: boolean; chapter?: number; of: number; storyline: string; pack?: string;
  skipped: { sid: string; chapter: number; title: string; why: string }[];
  chapters?: { sid: string; title: string }[]; path?: { sid: string; title: string; picks: string[] }[];
};
export type MlbSeries = { round: string; label: string; lg: string; teams: string[]; wins: number[]; done: boolean; winner: string | null; how: string; next: string | null };
export type MlbRow = { team: string; nick: string; abbr: string; w: number; l: number; pct: string; gb: string; l10: string | null; streak: string | null; proj: number | null; you: boolean; in: boolean };
export type MlbDiv = { lg: string; div: string; label: string; rows: MlbRow[] };
export type MlbStar = { name: string; pos: string; age: number; talent: number; line: string | null; moved?: boolean };
export type MlbView = {
  year: number; phase: string; today: string;
  my_team: { team: string; name: string; nick: string; abbr: string; record: string | null; place: string | null; status: string | null; l10: string | null;
    streak: string | null; stars: MlbStar[]; titles: { real: number[]; world: number[] }; rival: string[] };
  standings: MlbDiv[]; october: MlbSeries[];
  leaders: { stat: string; label: string; lg: string; rows: { name: string; team: string; abbr: string; value: string | number }[] }[];
  news: { date: string; text: string; kind: string; mine: boolean }[];
  whatifs: { id: string; title: string; when: string; group: string; on: boolean }[];
  teams: { team: string; name: string; nick: string; abbr: string }[]; years: number[]; source: string;
};
export type MlbWhatIf = {
  id: string; title: string; when: string; real: string; group: string; on: boolean; how: string;
  moves: { name: string; to: string | null; years: string; wins: number; now: boolean }[];
  flat: { team: string; years: string; wins: number; why: string }[];
  seasons: { year: number; real: string; world: string; change: number; real_path: string[]; world_path: string[]; odds: { real: number; world: number } | null;
    champ: string | null; real_champ: string | null }[];
  titles: { real: number[]; world: number[] };
  later: { years: string; line: string } | null;
};
export type MlbYear = { year: number; standings: MlbDiv[]; october: MlbSeries[]; champ: string | null; real_champ: string | null; changed: boolean;
  awards: { label: string; name: string; team: string | null }[] };
export type LgGame = { date: string; opp: string; home: boolean; label: string; conf: boolean; score?: string; result?: string };
export type LgPost = { round: string; label: string; teams: number[]; names: string[]; score: number[]; done: boolean; winner: number | null };
export type LeagueView = {
  league: string; label: string; kind: string; today: string; news: { date: string; text: string; mine: boolean }[]; note?: string;
  season?: string | null; champ?: string | null;
  my_team?: { team: number; name: string; short: string; record: string | null; conf_record: string | null; conf: string | null; place: string | null; points?: number | null;
    rank: number | null; last: LgGame[]; status: string | null; next: LgGame | null } | null;
  standings?: { group: string; label: string; rows: { team: number; name: string; w: number; l: number; t: number; cw: number; cl: number; pts?: number; gd?: number }[] }[];
  top25?: { rank: number; team: number; name: string; record: string }[];
  postseason?: LgPost[];
  champions?: { season: string; champ: string; runner_up: string | null; mine: boolean }[];
  teams?: { team: number; name: string }[];
  titles_only?: boolean; event?: string; school?: string; school_titles?: string[]; next?: string | null;
  finals?: { season: number; label?: string; date: string | null; champ: string | null; runner_up: string | null; score: string | null; note: string }[];
  award?: boolean; winners?: { year: number; date: string | null; winner: string | null; club: string | null; women: string | null; women_club: string | null; note?: string }[];
};
export type LeagueLine = { league: string; label: string; kind: string; line: string | null; in_season?: boolean };
export const phoneApi = {
  state: (since?: number): Promise<PhoneState> => api.get(`/api/phone/state${since !== undefined ? `?since=${since}` : ""}`),
  choices: (): Promise<{ ready: boolean; slot?: string; scene?: Scene; options?: Choice[]; busy?: { id: string; first: string; what: string }[] }> =>
    api.get("/api/phone/choices"),
  choose: (index: number, crew?: string[], act?: string): Promise<{ lines: Line[]; chips: Chip[] }> =>
    api.post("/api/phone/choose", crew ? { index, crew, act } : { index }),
  today: (): Promise<Today> => api.get("/api/phone/today"),
  episodes: (): Promise<EpisodeGuide> => api.get("/api/phone/episodes"),
  scene: (): Promise<SceneView> => api.get("/api/phone/scene"),
  sports: (team = ""): Promise<SportsView> => api.get(`/api/phone/sports${team ? `?team=${encodeURIComponent(team)}` : ""}`),
  mlb: (): Promise<MlbView> => api.get("/api/phone/mlb"),
  leagues: (): Promise<{ leagues: LeagueLine[] }> => api.get("/api/phone/leagues"),
  league: (lg: string): Promise<LeagueView> => api.get(`/api/phone/league?lg=${encodeURIComponent(lg)}`),
  leagueFollow: (lg: string, team: string): Promise<LeagueView> => api.post("/api/phone/league/follow", { lg, team }),
  mlbWhatIf: (id: string): Promise<MlbWhatIf> => api.get(`/api/phone/mlb/whatif?id=${encodeURIComponent(id)}`),
  mlbSetWhatIf: (id: string, on: boolean): Promise<{ whatifs: string[]; moved: string[]; view: MlbWhatIf }> => api.post("/api/phone/mlb/whatif", { id, on }),
  mlbYear: (y: number): Promise<MlbYear> => api.get(`/api/phone/mlb/year?y=${y}`),
  mlbTeam: (team: string): Promise<MlbView> => api.post("/api/phone/mlb/team", { team }),
  ladder: (scope = "school"): Promise<LadderView> => api.get(`/api/phone/ladder?scope=${encodeURIComponent(scope)}`),
  sceneIntro: (via: string, to: string): Promise<{ lines: Line[]; chips: Chip[]; scene: SceneView }> => api.post("/api/phone/scene/intro", { via, to }),
  scenePlan: (id: string): Promise<{ note: string }> => api.post("/api/phone/scene/plan", { with: id }),
  sceneRumor: (id: string, what: string): Promise<{ lines: Line[]; chips: Chip[]; scene: SceneView }> => api.post("/api/phone/scene/rumor", { id, what }),
  // the editor (only while it's on)
  editor: (): Promise<{ schema: EdSchema; people: EdPersonRow[] }> => api.get("/api/phone/editor"),
  editorPerson: (id: string): Promise<EdPerson> => api.get(`/api/phone/editor/person/${encodeURIComponent(id)}`),
  editorSavePerson: (id: string, body: any): Promise<EdPerson> => api.post(`/api/phone/editor/person/${encodeURIComponent(id)}`, body),
  editorNew: (body: any): Promise<{ id: string; name: string }> => api.post("/api/phone/editor/new", body),
  editorFit: (slot: string): Promise<{ id: string; name: string; fits: boolean }> => api.post("/api/phone/editor/fit", { slot }),
  roles: (): Promise<RoleBoard> => api.get("/api/phone/roles"),
  rolePick: (role: string, char: string | null): Promise<RoleBoard> => api.post("/api/phone/roles/pick", { role, char }),
  roleFix: (role: string, char: string, how: any): Promise<RoleBoard> => api.post("/api/phone/roles/fix", { role, char, how }),
  roleAdd: (role: string): Promise<{ id: string; name: string; board: RoleBoard }> => api.post("/api/phone/roles/add", { role }),
  groundwork: (): Promise<Groundwork> => api.get("/api/story/groundwork"),
  groundworkRemove: (kind: string, key: string): Promise<Groundwork> => api.post("/api/story/groundwork/remove", { kind, key }),
  restart: (keep: boolean): Promise<{ carried?: { done: number; skipped: string[] } }> => api.post("/api/story/restart", { keep }),
  editorPair: (a: string, b: string): Promise<EdPair> => api.get(`/api/phone/editor/pair/${encodeURIComponent(a)}/${encodeURIComponent(b)}`),
  editorSavePair: (a: string, b: string, body: any): Promise<EdPair> =>
    api.post(`/api/phone/editor/pair/${encodeURIComponent(a)}/${encodeURIComponent(b)}`, body),
  later: (index: number): Promise<{ queued: string; note: string }> => api.post("/api/phone/later", { index }),
  moment: (id: string, index: number | null, extra: Record<string, any> = {}): Promise<{ lines: Line[]; chips: Chip[]; minigame?: any }> =>
    api.post(`/api/phone/moment/${id}`, index === null ? { ...extra } : { index, ...extra }),
  minigames: (): Promise<{ games: MiniGameRow[]; recent: any[] }> => api.get("/api/phone/minigames"),
  minigameStart: (game: string): Promise<any> => api.post("/api/phone/minigame/start", { game }),
  minigameFinish: (session: string, score: number, max: number, stats?: any): Promise<{ result: any; rewarded: boolean; lines: Line[]; chips: Chip[] }> =>
    api.post("/api/phone/minigame/finish", { session, score, max, stats }),
  minigameQuit: () => api.post("/api/phone/minigame/quit", {}),
  classes: (): Promise<ClassesView> => api.get("/api/phone/classes"),
  // time: until = "decision" (next choice), "moment" (live until something happens), "day" | "week"
  advance: (until: string): Promise<any> => api.post("/api/story/advance", { until }),
  job: (): Promise<any> => api.get("/api/sim/job"),
  control: (patch: any) => api.post("/api/story/control", patch),
  storyContinue: (): Promise<{ moment: Moment | null; note: string | null }> => api.post("/api/story/schedule/continue", {}),
  // your episode order: what's up next, move one ahead of another, play one next, undo
  order: (): Promise<UpNext> => api.get("/api/story/order"),
  orderMove: (sid: string, before: string): Promise<UpNext> => api.post("/api/story/order/move", { sid, before }),
  orderNext: (sid: string): Promise<{ ok: boolean }> => api.post("/api/story/order/next", { sid }),
  orderClear: (sid?: string): Promise<UpNext> => api.post("/api/story/order/clear", sid ? { sid } : {}),
  schedule: (): Promise<ScheduleView> => api.get("/api/story/schedule"),
  scheduleReport: (days: number): Promise<ScheduleReport> => api.get(`/api/story/schedule/report?days=${days}&fmt=both`),
  addPrompt: (ask: string, size = ""): Promise<{ prompt: string; chars: number; suggestions: string[]; ideas: string[]; sizes: Record<string, string>;
    checked: boolean; last_check: { coverage: Coverage } | null }> =>
    api.get(`/api/story/add/prompt?ask=${encodeURIComponent(ask)}&size=${encodeURIComponent(size)}`),
  expand: (pack: string, ask: string, size: string): Promise<{ prompt: string; chars: number; title: string; pack: string; expansions: string[];
    ideas: string[]; sizes: Record<string, string> }> =>
    api.get(`/api/story/add/expand?pack=${encodeURIComponent(pack)}&ask=${encodeURIComponent(ask)}&size=${encodeURIComponent(size)}`),
  readStoryline: (pack: string): Promise<StorylineRead> => api.get(`/api/story/storyline/read?pack=${encodeURIComponent(pack)}`),
  outlinePrompt: (ask: string, size: string, expand?: string): Promise<{ prompt: string; chars: number }> =>
    api.get(`/api/story/build/outline-prompt?ask=${encodeURIComponent(ask)}&size=${encodeURIComponent(size)}&expand=${encodeURIComponent(expand || "")}`),
  outline: (text: string, save: boolean, expand?: string): Promise<OutlineCheck> =>
    api.post("/api/story/build/outline", { text, save, expand: expand || undefined }),
  history: (): Promise<{ versions: OldVersion[] }> => api.get("/api/dialogue/history"),
  restore: (file: string): Promise<{ restored: string }> => api.post("/api/dialogue/history/restore", { file }),
  textingPrompt: (what: string, ask: string, size: string, parts: string[] = [], style = "all"):
    Promise<{ prompt: string; chars: number; sections: number; lines: number; group_chats: number }> =>
    api.get(`/api/texting/prompt?what=${encodeURIComponent(what)}&ask=${encodeURIComponent(ask)}&size=${encodeURIComponent(size)}`
      + `&parts=${encodeURIComponent(parts.join(","))}&style=${encodeURIComponent(style)}`),
  textingCheck: (text: string): Promise<TextingCheck> => api.post("/api/texting/check", { text }),
  textingAdd: (text: string): Promise<{ ok: boolean; pack: string; breakdown: TextingBreakdown; notes: string[];
    skipped: { header: string; why: string }[]; fix_prompt: string | null }> => api.post("/api/texting/add", { text }),
  revise: (pack: string): Promise<ReviseView> => api.get(`/api/story/revise?pack=${encodeURIComponent(pack)}`),
  reviseFixPrompt: (pack: string): Promise<{ prompt: string }> => api.get(`/api/story/revise/fix-prompt?pack=${encodeURIComponent(pack)}`),
  reviseChangePrompt: (pack: string, ask: string): Promise<{ prompt: string }> => api.post("/api/story/revise/change-prompt", { pack, ask }),
  reviseApply: (pack: string, text: string): Promise<ReviseResult> => api.post("/api/story/revise/apply", { pack, text }),
  reviseUndo: (pack: string): Promise<ReviseView> => api.post("/api/story/revise/undo", { pack }),
  reviseCast: (pack: string, name: string, value: string): Promise<{ cast: CastLine[] }> => api.post("/api/story/revise/cast", { pack, name, value }),
  writing: (): Promise<{ storylines: WritingRow[] }> => api.get("/api/story/build/writing"),
  checkup: (pack: string): Promise<Checkup> => api.get(`/api/story/build/checkup?pack=${encodeURIComponent(pack)}`),
  batchPrompt: (pack: string, count = 3): Promise<BatchPrompt> =>
    api.get(`/api/story/build/batch-prompt?pack=${encodeURIComponent(pack)}&count=${count}`),
  addScenes: (pack: string, text: string): Promise<{ ok: boolean; got: number[]; notes: string[]; written: number; total: number; outline: OutlineEntry[];
    skipped: SkippedScene[]; gaps: SkippedScene[]; fix_prompt: string }> =>
    api.post("/api/story/build/scenes", { pack, text }),
  setTiming: (pack: string, years: string[], seasons: string[], spread: boolean, keepMonths = true) =>
    api.post(`/api/dialogue/packs/${encodeURIComponent(pack)}/timing`, { years, seasons, spread, keep_months: keepMonths }),
  moveScene: (pack: string, sid: string, year: string, month: number) =>
    api.post(`/api/dialogue/packs/${encodeURIComponent(pack)}/scene-timing`, { sid, year, month }),
  addPreview: (text: string, target?: { pack: string; after: string | null }): Promise<AddPreview> =>
    api.post("/api/story/add/preview", target ? { text, pack: target.pack, after: target.after || "" } : { text }),
  addInsert: (pack: string, after: string | null, text: string) => api.post("/api/story/add/insert", { pack, after: after || "", text }),
  weave: (pack: string, after: string | null, ask: string): Promise<{ prompt: string; chars: number; pack_name: string; where: string; after: string | null; next: string | null }> =>
    api.get(`/api/story/add/weave?pack=${encodeURIComponent(pack)}&after=${encodeURIComponent(after || "")}&ask=${encodeURIComponent(ask)}`),
  // play a storyline start to finish, on a copy of your story
  playStart: (pack: string, from?: string): Promise<PlayStep> => api.post("/api/story/playline/start", { pack, from }),
  playChoose: (index: number | null): Promise<PlayRead> => api.post("/api/story/playline/choose", { index }),
  playNext: (): Promise<PlayStep> => api.post("/api/story/playline/next", {}),
  playStop: () => api.post("/api/story/playline/stop", {}),
  addPack: (text: string, expand?: string) => api.post("/api/dialogue/packs", { text, expand: expand || undefined }),
  threads: (): Promise<{ threads: ThreadSummary[] }> => api.get("/api/phone/threads"),
  thread: (tid: string): Promise<Thread> => api.get(`/api/phone/thread/${encodeURIComponent(tid)}`),
  reply: (tid: string, msg: string, index: number): Promise<{ thread: Thread }> => api.post(`/api/phone/thread/${encodeURIComponent(tid)}/reply`, { msg, index }),
  text: (to: string, kind: string): Promise<{ thread: Thread; result: string; plans: boolean }> => api.post("/api/phone/text", { to, kind }),
  say: (tid: string, body: { text?: string; suggestion?: number }): Promise<{ thread: Thread; result: string; why: string | null; plans: boolean }> =>
    api.post(`/api/phone/thread/${encodeURIComponent(tid)}/say`, body),
  flirting: (): Promise<{ guide: { t: string; d: string }[]; stages: string[] }> => api.get("/api/phone/flirting"),
  contacts: (): Promise<{ groups: { name: string; people: ContactRow[] }[]; parents: { id: string; name: string; full: string; parent: boolean }[] }> => api.get("/api/phone/contacts"),
  contact: (cid: string): Promise<Contact> => api.get(`/api/phone/contact/${encodeURIComponent(cid)}`),
  pets: (): Promise<{ pets: Pet[]; kids: { id: string; first: string; me: boolean }[]; approved: any; asked: number | null;
    species: Record<string, { label: string; breeds: string[]; coats: string[]; duties: { id: string; label: string; hint: string; when: string }[] }> }> => api.get("/api/phone/pets"),
  petSetup: (pid: string, duties: Record<string, string>): Promise<Pet> => api.post(`/api/phone/pet/${pid}/setup`, { duties }),
  // quick activities (cuddle, treat, feed, brush) happen now; timed ones (walk, park, play, train) happen now if it's your move ({now:true}), else get planned
  petDo: (pid: string, activity: string, opts: { now?: boolean; trick?: string } = {}): Promise<any> => api.post(`/api/phone/pet/${pid}/do`, { activity, ...opts }),
  petAsk: (species: string): Promise<{ yes: boolean; p: number; reason: string | null; text: string }> => api.post("/api/phone/pet/ask", { species }),
  petAdopt: (species: string, name: string, breed?: string, coat?: string): Promise<Pet> => api.post("/api/phone/pet/adopt", { species, name, breed, coat }),
  net: (): Promise<{ lan: boolean; port: number; urls: string[]; host: string }> => api.get("/api/net"),
};

/** Navigate inside the phone app: pgo("phone/thread/family") -> #/m/phone/thread/family */
export function pgo(path: string) {
  window.location.hash = `#/m${path ? "/" + path : ""}`;
}
