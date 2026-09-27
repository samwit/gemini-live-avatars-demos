// Copyright 2026 Sam Witteveen
// SPDX-License-Identifier: Apache-2.0
// The Note Taker: renders each note-taking-tool call as a handwritten block on a notepad.
import { h, mountDemo } from "../shell.js";

const $ = (id) => document.getElementById(id);
const blocks = []; // everything written so far, for Copy / Download

$("notepadDate").textContent = new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });

// --- drawing one block of notes -----------------------------------------------------
// Each line gets a "being written" animation: it's revealed left-to-right with a
// clip-path, staggered so the lines appear one after another like a pen moving.
let lineDelay = 0;
function written(el) {
  el.classList.add("ink");
  el.style.animationDelay = `${lineDelay}s`;
  lineDelay += 0.35;
  return el;
}

function addBlock(note) {
  $("notes").querySelector(".notepad-empty")?.remove();
  blocks.push(note);
  lineDelay = 0;

  const block = h("div", { class: "note-block", style: `transform: rotate(${(Math.random() - 0.5) * 0.8}deg)` });
  if (note.title) block.append(written(h("h3", { class: "note-title" }, note.title)));

  if (note.points?.length) {
    block.append(h("ul", { class: "note-points" }, note.points.map((p) => {
      // Underline the key phrase with a highlighter wherever it appears.
      const li = h("li", {});
      if (note.key_phrase && p.toLowerCase().includes(note.key_phrase.toLowerCase())) {
        const i = p.toLowerCase().indexOf(note.key_phrase.toLowerCase());
        li.append(p.slice(0, i), h("mark", {}, p.slice(i, i + note.key_phrase.length)), p.slice(i + note.key_phrase.length));
      } else {
        li.append(p);
      }
      return written(li);
    })));
  }

  if (note.key_phrase && !note.points?.some((p) => p.toLowerCase().includes(note.key_phrase.toLowerCase()))) {
    block.append(written(h("p", { class: "note-key" }, "★ ", h("mark", {}, note.key_phrase))));
  }

  if (note.action_items?.length) {
    block.append(h("ul", { class: "note-todos" }, note.action_items.map((a) => {
      const li = written(h("li", {}, a));
      li.onclick = () => li.classList.toggle("done"); // tick things off
      return li;
    })));
  }

  $("notes").append(block);
  $("notepad").scrollTo({ top: $("notepad").scrollHeight, behavior: "smooth" });
}

// --- export -------------------------------------------------------------------------
function markdown() {
  const out = [`# Notes: ${$("notepadDate").textContent}`, ""];
  for (const b of blocks) {
    if (b.title) out.push(`## ${b.title}`, "");
    for (const p of b.points || []) out.push(`- ${p}`);
    if (b.key_phrase) out.push(`- **Key:** ${b.key_phrase}`);
    for (const a of b.action_items || []) out.push(`- [ ] ${a}`);
    out.push("");
  }
  return out.join("\n");
}

$("copyBtn").onclick = async () => {
  await navigator.clipboard.writeText(markdown());
  $("copyBtn").textContent = "✅ Copied";
  setTimeout(() => ($("copyBtn").textContent = "📋 Copy"), 1500);
};
$("downloadBtn").onclick = () => {
  const a = h("a", { href: URL.createObjectURL(new Blob([markdown()], { type: "text/markdown" })), download: "notes.md" });
  a.click();
};
$("clearBtn").onclick = () => {
  blocks.length = 0;
  $("notes").replaceChildren(h("p", { class: "notepad-empty" }, "Your notes will appear here as you talk…"));
};

// --- the live session -----------------------------------------------------------------
const demo = mountDemo({
  demoId: "notetaker",
  getOptions: () => ({ mode: $("mode").value }),
  onUi(event, data) {
    if (event === "note") addBlock(data); // one note-taking-tool call = one block
  },
});

// "Tidy up": the server sends a stage direction asking for a Summary block.
$("tidyBtn").onclick = () => demo.client?.action({ action: "tidy" });
