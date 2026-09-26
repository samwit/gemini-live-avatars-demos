// The Interrogation Room: case file, evidence board, composure meter, verdict.
import { h, mountDemo } from "../shell.js";

const $ = (id) => document.getElementById(id);
const CLUE_SLOTS = 4;

function resetBoard() {
  $("board").replaceChildren(...Array.from({ length: CLUE_SLOTS }, () => h("div", { class: "clue" }, "?")));
  $("clueCount").textContent = `(0/${CLUE_SLOTS})`;
  $("composure").style.width = "90%";
  $("tells").replaceChildren();
  $("verdict").replaceChildren();
}
resetBoard();

mountDemo({
  demoId: "interrogation",
  onUi(event, data) {
    switch (event) {
      case "case_file":
        resetBoard();
        $("caseFile").replaceChildren(
          h("dt", {}, "Case"), h("dd", {}, data.case),
          h("dt", {}, "What happened"), h("dd", {}, data.summary),
          h("dt", {}, "Suspect"), h("dd", {}, data.suspect),
          h("dt", {}, "His alibi"), h("dd", {}, data.alibi),
        );
        break;

      // reveal_clue: fill the next empty slot on the board
      case "clue": {
        const slot = [...$("board").children].find((c) => !c.classList.contains("found"));
        if (slot) {
          slot.className = "clue found";
          slot.replaceChildren(h("b", {}, data.title), data.text);
        }
        $("clueCount").textContent = `(${data.count}/${data.total})`;
        break;
      }

      // update_composure: the meter and a log of his nervous tells
      case "composure":
        $("composure").style.width = `${data.level}%`;
        if (data.tell) $("tells").prepend(h("li", {}, `${data.tell} (${data.level})`));
        break;

      // confess: only fires if the server agreed there's enough evidence
      case "confession":
        $("composure").style.width = "0%";
        $("verdict").replaceChildren(
          h("div", { class: "verdict" }, h("h3", {}, "🔓 Case closed: confession"), data.statement),
        );
        break;
    }
  },
});
