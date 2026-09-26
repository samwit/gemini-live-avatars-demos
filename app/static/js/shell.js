/**
 * Shared wiring for the single-avatar demo pages.
 *
 * Each demo page has the same "stage" markup (avatar video, controls, text box,
 * transcript) plus its own side panel. `mountDemo()` hooks up the common
 * parts, so each demo's own JS only deals with its widgets via `onUi`.
 *
 * Elements it expects (by id):
 *   avatar, selfie, overlay, status, startBtn, micBtn, camBtn, hpToggle,
 *   composer, textInput, transcript, micLevel
 */
import { AvatarPlayer } from "./avatar-player.js";
import { LiveClient } from "./live-client.js";
import { Camera, Mic } from "./media.js";

const $ = (id) => document.getElementById(id);

export function mountDemo({
  demoId,
  getOptions = () => ({}),  // options sent in the "start" message
  onUi = () => {},          // (event, data) for demo widgets
  onReady = () => {},
  onStop = () => {},
  camera = "optional",      // "optional" | "auto" (turn on at start) | "off"
  mic = true,               // start the mic automatically
}) {
  const player = new AvatarPlayer($("avatar"));
  const transcript = new Transcript($("transcript"));
  const micIn = new Mic();
  const cam = new Camera();
  let client = null;

  if (camera === "off") $("camBtn")?.remove();

  // --- start / stop ---------------------------------------------------------
  $("startBtn").onclick = async () => {
    if (client) return stop();
    setStatus("connecting", "Connecting…");
    $("startBtn").textContent = "Stop";
    overlayText("Connecting…");
    transcript.clear();

    try {
      player.start(); // inside the click: unlocks autoplay with sound
    } catch (e) {
      return fail(e.message);
    }
    client = new LiveClient(demoId, [player]);
    client.headphones = $("hpToggle")?.checked ?? false;

    client.addEventListener("ready", async (e) => {
      setStatus("live", "Live");
      $("overlay").classList.add("hidden");
      onReady(e.detail);
      if (mic) await toggleMic(true);
      if (camera === "auto") await toggleCam(true);
    });
    client.addEventListener("transcript", (e) => transcript.add(e.detail.role, e.detail.text));
    client.addEventListener("turn_complete", () => transcript.endTurn());
    client.addEventListener("interrupted", () => transcript.note("⏸ interrupted"));
    client.addEventListener("tool", (e) => transcript.tool(e.detail.name, e.detail.args));
    client.addEventListener("ui", (e) => onUi(e.detail.event, e.detail.data));
    client.addEventListener("notice", (e) => transcript.note(e.detail.message));
    client.addEventListener("error", (e) => fail(e.detail.message));
    client.addEventListener("closed", () => client && stop());

    client.connect(getOptions());
  };

  function stop() {
    const c = client;
    client = null;
    c?.close();
    micIn.stop();
    cam.stop();
    $("micBtn").classList.remove("on");
    $("camBtn")?.classList.remove("on");
    $("selfie").classList.add("hidden");
    $("startBtn").textContent = "Start";
    $("overlay").classList.remove("hidden");
    overlayText("Press Start");
    if (!$("status").classList.contains("error")) setStatus("idle", "Idle");
    onStop();
  }

  function fail(message) {
    setStatus("error", "Error");
    transcript.note("⚠️ " + message, "error");
    if (client) stop();
  }

  // --- mic ------------------------------------------------------------------
  async function toggleMic(on = !$("micBtn").classList.contains("on")) {
    if (!client) return;
    if (on) {
      try {
        await micIn.start((pcm, level) => {
          client?.sendAudio(pcm);
          const meter = $("micLevel");
          if (meter) {
            meter.style.width = `${Math.min(100, level * 140)}%`;
            meter.classList.toggle("gated", !!client?.gated);
          }
        });
        $("micBtn").classList.add("on");
      } catch (e) {
        transcript.note("🎙️ Mic unavailable: " + e.message, "error");
      }
    } else {
      micIn.stop();
      $("micBtn").classList.remove("on");
      if ($("micLevel")) $("micLevel").style.width = "0%";
    }
  }
  $("micBtn").onclick = () => toggleMic();

  // --- camera ---------------------------------------------------------------
  async function toggleCam(on = !$("camBtn")?.classList.contains("on")) {
    if (!client || !$("camBtn")) return;
    if (on) {
      try {
        await cam.start($("selfie"), (b64) => client?.sendImage(b64));
        $("selfie").classList.remove("hidden");
        $("camBtn").classList.add("on");
      } catch (e) {
        transcript.note("📷 Camera unavailable: " + e.message, "error");
      }
    } else {
      cam.stop();
      $("selfie").classList.add("hidden");
      $("camBtn").classList.remove("on");
    }
  }
  if ($("camBtn")) $("camBtn").onclick = () => toggleCam();

  // --- headphones (echo gate) and typed messages ------------------------------
  $("hpToggle")?.addEventListener("change", (e) => { if (client) client.headphones = e.target.checked; });

  $("composer").onsubmit = (e) => {
    e.preventDefault();
    const text = $("textInput").value.trim();
    if (!text || !client) return;
    client.sendText(text);
    transcript.add("user", text);
    transcript.endTurn();
    $("textInput").value = "";
  };

  return {
    get client() { return client; },
    transcript,
    player,
  };
}

function overlayText(text) {
  const el = $("overlay");
  (el.querySelector("span") || el).textContent = text;
}

export function setStatus(kind, label) {
  const el = $("status");
  el.className = `status ${kind}`;
  el.textContent = label;
}

/** A chat-style transcript that merges streaming chunks into bubbles. */
export class Transcript {
  constructor(el) { this.el = el; this.current = null; }

  clear() { this.el.innerHTML = ""; this.current = null; }

  add(role, text, name) {
    if (!this.current || this.current.dataset.role !== role) {
      this.current = document.createElement("div");
      this.current.className = `bubble ${role}`;
      this.current.dataset.role = role;
      if (name) {
        const who = document.createElement("span");
        who.className = "who";
        who.textContent = name;
        this.current.append(who);
      }
      this.el.append(this.current);
    }
    this.current.append(document.createTextNode(text));
    this._scroll();
  }

  endTurn() { this.current = null; }

  tool(name, args) {
    const el = document.createElement("div");
    el.className = "tool-line";
    const summary = Object.entries(args || {})
      .map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`)
      .join(", ");
    el.textContent = `🔧 ${name}(${summary.length > 90 ? summary.slice(0, 90) + "…" : summary})`;
    this.el.append(el);
    this._scroll();
  }

  note(text, kind = "") {
    const el = document.createElement("div");
    el.className = `note ${kind}`;
    el.textContent = text;
    this.el.append(el);
    this.current = null;
    this._scroll();
  }

  _scroll() { this.el.scrollTop = this.el.scrollHeight; }
}

/** Tiny helper for building widgets: h("div", {class: "x"}, "text", child) */
export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") el.className = v;
    else if (k === "style") el.style.cssText = v;
    else el.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c == null || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}
