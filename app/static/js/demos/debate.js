// Copyright 2026 Sam Witteveen
// SPDX-License-Identifier: Apache-2.0
// Avatar Debate Club: two AvatarPlayers on ONE WebSocket.
// Binary frames start with a stream byte (0 = "for", 1 = "against"), and
// LiveClient routes each chunk to the right <video>. The turn-taking itself
// happens on the server (app/demos/debate.py). This page just shows it.
import { AvatarPlayer } from "../avatar-player.js";
import { LiveClient } from "../live-client.js";
import { setStatus, Transcript } from "../shell.js";

const $ = (id) => document.getElementById(id);
const cat = await (await fetch("/api/catalog")).json();

const players = [new AvatarPlayer($("avatarA")), new AvatarPlayer($("avatarB"))];
const transcript = new Transcript($("transcript"));
let client = null;
let names = ["Leo", "Carmen"];

// --- setup form ----------------------------------------------------------------
for (const name of Object.keys(cat.avatars)) {
  $("avatarA_sel").append(new Option(name, name));
  $("avatarB_sel").append(new Option(name, name));
}
$("avatarA_sel").value = "Leo";
$("avatarB_sel").value = "Carmen";
const syncPosters = () => {
  names = [$("avatarA_sel").value, $("avatarB_sel").value];
  ["A", "B"].forEach((s, i) => {
    $(`poster${s}`).src = `/img/avatars/${names[i].toLowerCase()}.jpg`;
    $(`name${s}`).textContent = names[i];
  });
};
$("avatarA_sel").onchange = $("avatarB_sel").onchange = syncPosters;
syncPosters();

const IDEAS = [
  "This house believes pineapple belongs on pizza",
  "Cats are better than dogs",
  "A hot dog is a sandwich",
  "Socks with sandals should be celebrated",
  "Time travel would be a terrible idea",
  "Breakfast is overrated",
];
for (const idea of IDEAS) {
  const b = document.createElement("button");
  b.className = "btn small";
  b.textContent = idea.replace("This house believes ", "");
  b.onclick = () => ($("motion").value = idea);
  $("motionIdeas").append(b);
}

// --- start / stop ----------------------------------------------------------------
$("startBtn").onclick = () => (client ? stop() : start());

function start() {
  transcript.clear();
  setStatus("connecting", "Connecting…");
  $("startBtn").textContent = "Stop";
  players.forEach((p) => p.start()); // inside the click so audio may autoplay

  client = new LiveClient("debate", players);
  client.addEventListener("ready", (e) => {
    setStatus("live", "Live");
    $("setup").classList.add("hidden");
    $("liveMotion").classList.remove("hidden");
    $("liveMotion").textContent = `“${e.detail.motion}”`;
    $("overlayA").classList.add("hidden");
    $("overlayB").classList.add("hidden");
  });
  client.addEventListener("transcript", (e) => {
    if (e.detail.role === "model") transcript.add(`s${e.detail.stream}`, e.detail.text, names[e.detail.stream]);
  });
  client.addEventListener("turn_complete", () => transcript.endTurn());
  client.addEventListener("ui", (e) => onUi(e.detail.event, e.detail.data));
  client.addEventListener("error", (e) => {
    setStatus("error", "Error");
    transcript.note("⚠️ " + e.detail.message, "error");
    stop(true);
  });
  client.addEventListener("closed", () => client && stop());

  client.connect({
    motion: $("motion").value,
    rounds: $("rounds").value,
    avatar_a: names[0],
    avatar_b: names[1],
  });
}

function stop(keepStatus = false) {
  const c = client;
  client = null;
  c?.close();
  $("startBtn").textContent = "Start debate";
  $("setup").classList.remove("hidden");
  $("liveMotion").classList.add("hidden");
  $("verdictBox").classList.add("hidden");
  $("overlayA").classList.remove("hidden");
  $("overlayB").classList.remove("hidden");
  $("turnInfo").textContent = "";
  highlight(null);
  if (!keepStatus) setStatus("idle", "Idle");
}

// --- events from the server's debate loop --------------------------------------------
function onUi(event, data) {
  if (event === "speaker") {
    highlight(data.stream);
    $("turnInfo").textContent = data.turn === "verdict" ? "Reactions…" : data.turn ? `Turn ${data.turn} of ${data.of}` : "";
  } else if (event === "interjection_queued") {
    transcript.note(`🎤 Moderator: “${data.text}” (the next speaker will respond)`);
  } else if (event === "debate_over") {
    highlight(null);
    $("turnInfo").textContent = "Debate over";
    $("winAName").textContent = names[0];
    $("winBName").textContent = names[1];
    $("verdictBox").classList.remove("hidden");
  }
}

function highlight(stream) {
  $("frameA").classList.toggle("speaking", stream === 0);
  $("frameB").classList.toggle("speaking", stream === 1);
}

// --- moderator controls ----------------------------------------------------------------
$("composer").onsubmit = (e) => {
  e.preventDefault();
  const text = $("textInput").value.trim();
  if (text && client) client.sendText(text);
  $("textInput").value = "";
};
$("winA").onclick = () => verdict(0);
$("winB").onclick = () => verdict(1);
function verdict(winner) {
  client?.action({ action: "verdict", winner });
  $("verdictBox").classList.add("hidden");
  transcript.note(`🏆 The moderator declares ${names[winner]} the winner!`);
}
