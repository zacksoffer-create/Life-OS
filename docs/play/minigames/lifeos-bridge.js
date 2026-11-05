/* LifeOS mini game bridge. Drop this into any standalone HTML game (inline it, or <script src="lifeos-bridge.js">).
 *
 *   LifeOS.onStart(config => { ...start your game with config... });
 *   LifeOS.finish({ score: 4, max: 5, summary: "4 of 5", stats: { anything } });   // when the round is over
 *   LifeOS.quit();                                                                   // if the player backs out
 *
 * config: { skill 0-100 (the character's relevant skill), difficulty 0-100, mode ("free" | "clutch" | "quiz" | ...),
 *           seed (use it for your random numbers), me (first name), them, sport, opponent, college (true in college) }
 *
 * Opened on its own (not inside the app), the game still works: onStart fires with defaults or ?skill=&difficulty=&seed= from
 * the URL, and finish/quit do nothing. So the same file can live in Google Drive and in the app.
 */
const LifeOS = (() => {
  const embedded = window.parent !== window;
  const qs = new URLSearchParams(location.search);
  const config = { skill: +(qs.get("skill") || 55), difficulty: +(qs.get("difficulty") || 50), mode: qs.get("mode") || "free",
                   me: qs.get("me") || "You", seed: +(qs.get("seed") || Date.now() % 100000) };
  let started = false, cb = null;
  const fire = () => { if (!started && cb) { started = true; cb(config); } };
  window.addEventListener("message", (e) => {
    if (e.data && e.data.type === "lifeos:init") { Object.assign(config, e.data.config || {}); fire(); }
  });
  const post = (event, data) => { if (embedded) parent.postMessage(Object.assign({ type: "lifeos:minigame", event }, data || {}), "*"); };
  return {
    embedded, config,
    onStart(f) { cb = f; post("ready"); setTimeout(fire, embedded ? 2500 : 0); },
    finish(result) { post("finish", { result }); },
    quit() { post("quit"); },
  };
})();
