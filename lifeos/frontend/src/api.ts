// Thin client for the LIFE OS API. Every call returns parsed JSON or throws ApiError.

export class ApiError extends Error {
  status: number;
  errors: string[];
  data: any; // the whole answer (some carry more than errors: what didn't go in, a fix-it message)
  constructor(status: number, message: string, errors: string[] = [], data: any = null) {
    super(message);
    this.status = status;
    this.errors = errors;
    this.data = data;
  }
}

async function request(method: string, path: string, body?: any, raw = false): Promise<any> {
  const init: RequestInit = { method, headers: {} };
  if (body !== undefined) {
    if (body instanceof Blob || body instanceof ArrayBuffer) {
      init.body = body as any;
      (init.headers as any)["Content-Type"] = "application/octet-stream";
    } else {
      init.body = JSON.stringify(body);
      (init.headers as any)["Content-Type"] = "application/json";
    }
  }
  const res = await fetch(path, init);
  if (!res.ok) {
    let msg = res.statusText;
    let errors: string[] = [];
    let data: any = null;
    try {
      const j = await res.json();
      data = j;
      if (typeof j.detail === "string") msg = j.detail;
      else if (Array.isArray(j.detail)) msg = j.detail.map((d: any) => d.msg).join("; ");
      // always words (an error can come as {line, text})
      if (Array.isArray(j.errors)) errors = j.errors.map((e: any) => (typeof e === "string" ? e : e && e.text ? `${e.line ? `line ${e.line}: ` : ""}${e.text}` : JSON.stringify(e)));
    } catch {
      /* not json */
    }
    throw new ApiError(res.status, msg, errors, data);
  }
  if (raw) return res;
  return res.json();
}

export const api = {
  get: (p: string) => request("GET", p),
  post: (p: string, b: any = {}) => request("POST", p, b),
  put: (p: string, b: any) => request("PUT", p, b),
  patch: (p: string, b: any) => request("PATCH", p, b),
  del: (p: string) => request("DELETE", p),
  upload: (p: string, file: Blob) => request("POST", p, file),
};

export function qs(params: Record<string, any>): string {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  return parts.length ? "?" + parts.join("&") : "";
}

export interface CharSummary {
  id: string;
  name: string;
  first: string;
  last: string;
  short: string;
  role: string;
  grade: number | null;
  archetype: string;
  color: string;
  pronouns: string;
  featured: boolean;
  status: string;
  mood: number;
  stress: number;
  energy: number;
  popularity: number;
  friends: number;
  clique: { id: string; name: string } | null;
  memberships: { id: string; name: string; kind: string }[];
  partner: string | null;
  title: string;
  role_label: string;
  interests: [string, number][];
  reputation: [string, number][];
  bio: string;
  gpa: number;
  household: string | null;
  grounded: boolean;
  goals: string[];
}

export interface WorldInfo {
  name: string;
  town: any;
  school: any;
  day: number;
  date: string;
  iso: string;
  weekday: string;
  term: string;
  school_day: boolean;
  year: number;
  phase: string;
  phases: string[];
  seed: number;
  gen_seed: number;
  population: Record<string, number>;
  rules_version: string;
  events: number;
  traces: number;
  folded: number;
  job: any;
  busy: boolean;
  action_overrides: string[];
}

export interface EventLite {
  id: number;
  day: number;
  date: string;
  slot: string;
  type: string;
  outcome: string;
  actors: string[];
  targets: string[];
  involved: string[];
  group: string | null;
  importance: number;
  text: string;
  trace: number | null;
  has_calc: boolean;
  n_changes: number;
  causes: number[];
}
