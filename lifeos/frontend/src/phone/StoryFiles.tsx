// Your story as a file: start one from a cast file, back it up, restore it, or move it to the lab on a computer.
import React, { useState } from "react";
import { api } from "../api";
import { pgo } from "./api";
import { PIcon } from "./icons";
import { cx, errText, Sheet } from "./kit";
import StartOver from "./StartOver";
import { usePhone } from "./PhoneContext";

/** True in the phone app (the game runs on the phone, no computer). */
export const STANDALONE = typeof window !== "undefined" && (window as any).__LIFEOS_STANDALONE__ === true;

export function pickFile(accept: string): Promise<File | null> {
  return new Promise((resolve) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = accept;
    input.style.display = "none";
    input.onchange = () => {
      resolve(input.files?.[0] || null);
      input.remove();
    };
    document.body.appendChild(input);
    input.click();
  });
}

async function postRaw(path: string, data: ArrayBuffer) {
  const res = await fetch(path, { method: "POST", body: data, headers: { "Content-Type": "application/octet-stream" } });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error([body.detail, ...(body.errors || [])].filter(Boolean).join(" · ") || res.statusText);
  return body;
}

/** Start a story from a file: a backup (.lifeos), a worksheet (.xlsx) or a cast file (.json / ChatGPT's answer as .txt). */
export async function startFromFile(f: File): Promise<string> {
  if (/\.lifeos$/i.test(f.name)) {
    const r = await postRaw("/api/phone/restore", await f.arrayBuffer());
    return [r.name ? `Welcome back, ${r.name.split(" ")[0]}. Picking up on ${r.date}.` : "Backup restored.", r.said, r.newer]
      .filter(Boolean).join(" ");
  }
  let spec: any;
  if (/\.xlsx$/i.test(f.name)) {
    spec = (await postRaw("/api/story/import-sheet", await f.arrayBuffer())).spec;
  } else {
    const text = await f.text();
    const m = text.match(/\{[\s\S]*\}/);
    if (!m) throw new Error("That file doesn't have a story cast in it.");
    const j = JSON.parse(m[0]);
    spec = j.spec || j;
  }
  if (!spec?.protagonist) throw new Error("That file doesn't have a story cast in it.");
  await api.post("/api/story/new", { spec });
  return `${spec.title || "Your story"} is ready. First day of school.`;
}

/** Save the story to a file. On a phone this opens the share sheet (Save to Files, AirDrop, email...). */
export async function backupStory(): Promise<string> {
  const res = await fetch("/api/phone/backup");
  if (!res.ok) throw new Error("Couldn't make a backup right now.");
  const cd = res.headers.get("content-disposition") || "";
  const name = (cd.match(/filename="?([^"]+)"?/) || [])[1] || "LIFE OS story.lifeos";
  const blob = await res.blob();
  const file = new File([blob], name, { type: "application/octet-stream" });
  const nav: any = navigator;
  if (nav.canShare && nav.canShare({ files: [file] })) {
    try {
      await nav.share({ files: [file], title: name });
      return "Backup saved.";
    } catch (e: any) {
      if (e?.name === "AbortError") return "Backup canceled.";
    }
  }
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    URL.revokeObjectURL(a.href);
    a.remove();
  }, 1000);
  return `Downloaded ${name}.`;
}

export const SAMPLE_SPEC = {
  title: "A Sample Story",
  students_per_grade: 10,
  protagonist: {
    first: "Alex", last: "Rivera", gender: "m", grade: 9, archetype: "athlete", attracted_to: ["f"],
    traits: { competitiveness: 80, discipline: 65, sociability: 66 }, aptitudes: { athletic: 80 },
    interests: { football: 78, basketball: 72, baseball: 88 }, skills: { football: 42, basketball: 44, baseball: 50 },
    body: { height_in: 70, build: "athletic" }, positions: { football: "WR", basketball: "SG", baseball: "SS" }, jersey: 7,
  },
  family: { last: "Rivera", guardians: ["Maria", "Dave"], style: "warm", income: "middle", pet: { species: "dog", name: "Scout" } },
  siblings: [{ key: "S1", first: "Nico", gender: "m", grade: 11, archetype: "leader" }],
  cast: [
    { key: "P1", first: "Jordan", last: "Park", gender: "m", grade: 9, archetype: "athlete", relationships: [{ to: "me", type: "best_friend" }] },
    { key: "P2", first: "Maya", last: "Chen", gender: "f", grade: 9, relationships: [{ to: "me", type: "mutual_crush" }] },
  ],
};

/** The card: back up, restore, start a new story from a file. */
export function StoryFilesCard({ hasStory }: { hasStory: boolean }) {
  const { refresh, toast } = usePhone();
  const [busy, setBusy] = useState<string | null>(null);
  const [restart, setRestart] = useState(false);
  const run = async (key: string, fn: () => Promise<string | null>) => {
    setBusy(key);
    try {
      const msg = await fn();
      if (msg) toast(msg, "good");
      await refresh();
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setBusy(null);
    }
  };
  const load = () => run("load", async () => {
    if (hasStory && !window.confirm("Start a different story? Back up this one first if you want to keep it.")) return null;
    const f = await pickFile(".json,.txt,.xlsx,.lifeos,application/json,text/plain");
    return f ? startFromFile(f) : null;
  });
  return (
    <div className="ph-card">
      <div className="ph-card-t">{STANDALONE ? "Your story on this phone" : "Your story as a file"}</div>
      <p className="ph-dim small" style={{ marginTop: 0 }}>
        {STANDALONE
          ? "Your progress saves on this phone by itself. A backup is the whole story in one file: everyone, everything that's happened, and your storylines and texting. Back up now and then (Save to Files, iCloud or AirDrop)."
          : "Back up your story to move it to the phone app, or load a backup from your phone to look at it here."}
      </p>
      <div className="ph-filebtns">
        {hasStory && (
          <button className="ph-btn primary block" disabled={!!busy} onClick={() => run("backup", backupStory)}>
            {busy === "backup" ? <span className="ph-spinner small" /> : <PIcon name="download" size={17} />} Back up my story
          </button>
        )}
        {hasStory && (
          <button className="ph-btn soft block" disabled={!!busy} onClick={() => setRestart(true)}>
            <PIcon name="sparkle" size={17} /> Start over (keep my changes)
          </button>
        )}
        {hasStory && (
          <button className="ph-btn soft block" disabled={!!busy} onClick={() => pgo("create")}>
            <PIcon name="sparkle" size={17} /> Make a new story
          </button>
        )}
        <button className={cx("ph-btn block", hasStory ? "soft" : "primary")} disabled={!!busy} onClick={load}>
          {busy === "load" ? <span className="ph-spinner small" /> : <PIcon name="upload" size={17} />} {hasStory ? "Restore or start a different story" : "Load a cast file or backup"}
        </button>
      </div>
      {STANDALONE && <DesktopVersion />}
      <Sheet open={restart} onClose={() => setRestart(false)} title="Start over" full>
        {restart && <StartOver onDone={() => setRestart(false)} />}
      </Sheet>
    </div>
  );
}

/** Where to get the desktop version (the lab, for Mac and Windows): the same engine as this app, always the newest. */
export const DESKTOP_URL = (() => {
  try {
    return new URL("LIFE-OS-desktop.zip", window.location.href.split("#")[0]).href;
  } catch {
    return "LIFE-OS-desktop.zip";
  }
})();

function DesktopVersion() {
  const { toast } = usePhone();
  const copy = async () => {
    let ok = false;
    try {
      await navigator.clipboard.writeText(DESKTOP_URL);
      ok = true;
    } catch { /* not allowed */ }
    toast(ok ? "Copied. Open it on your computer (or AirDrop it to your Mac)." : DESKTOP_URL, ok ? "good" : undefined);
  };
  const share = async () => {
    try {
      await (navigator as any).share({ title: "LIFE OS desktop version", url: DESKTOP_URL });
    } catch { /* cancelled */ }
  };
  return (
    <div className="ph-desk">
      <b>See it on a computer</b>
      <ol>
        <li>Get the <b>desktop version</b> on the computer (link below). It's the same engine as this app, so it's always the newest: get it again after updates.</li>
        <li>Unzip it and double-click <b>Start LIFE OS</b> (Mac or Windows).</li>
        <li>On <b>My Story</b>, click <b>Load a cast file or backup</b> and pick your backup. Your storylines and texting come with it.</li>
      </ol>
      <code>{DESKTOP_URL.replace(/^https?:\/\//, "")}</code>
      <div className="ph-filebtns row">
        <button className="ph-btn soft block" onClick={copy}>Copy the link</button>
        {"share" in navigator && <button className="ph-btn soft block" onClick={share}>Send it to my computer</button>}
      </div>
      <p className="ph-dim small">Changed something there? Download its save (Saves &amp; Worlds → Download) and load it here with Restore.</p>
    </div>
  );
}
