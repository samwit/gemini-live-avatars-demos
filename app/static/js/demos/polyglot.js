// The Polyglot Café: city buttons (teleport mid-session), vocab and correction cards, receipt.
import { h, mountDemo } from "../shell.js";

const $ = (id) => document.getElementById(id);
const { cities } = await (await fetch("/api/catalog")).json();
let city = "paris";

const FLAGS = { paris: "🇫🇷", tokyo: "🇯🇵", mexico: "🇲🇽", rome: "🇮🇹", seoul: "🇰🇷", berlin: "🇩🇪", saopaulo: "🇧🇷", mumbai: "🇮🇳" };

for (const [key, c] of Object.entries(cities)) {
  const b = h("button", { "data-key": key }, `${FLAGS[key] || ""} ${c.city}`);
  b.onclick = () => {
    // Before Start this just picks the starting city. During a session it
    // asks the server to teleport the café; the server sends a stage direction.
    if (demo.client) demo.client.action({ action: "teleport", city: key });
    else selectCity(key);
  };
  $("cities").append(b);
}

function selectCity(key) {
  city = key;
  document.querySelectorAll("#cities button").forEach((b) => b.classList.toggle("active", b.dataset.key === key));
  $("cafeTag").textContent = `${cities[key].cafe} · ${cities[key].city}`;
}
selectCity(city);

function addCard(listId, card) {
  const list = $(listId);
  list.querySelector(".note")?.remove();
  list.prepend(card);
}

const demo = mountDemo({
  demoId: "polyglot",
  getOptions: () => ({ city, level: $("level").value }),
  onUi(event, data) {
    switch (event) {
      case "teleported":
        selectCity(data.key);
        demo.transcript.note(`✈️ The café teleported to ${data.city}!`);
        break;

      case "vocab": // add_vocab (SILENT async tool)
        addCard("vocab", h("div", { class: "vocab" },
          h("span", { class: "word" }, data.word),
          data.romanization && h("span", { class: "rom" }, data.romanization),
          h("div", {}, data.meaning),
          data.example && h("div", { class: "ex" }, data.example)));
        break;

      case "correction": // correct_me (SILENT async tool)
        addCard("corrections", h("div", { class: "correction" },
          h("s", {}, data.you_said), " → ", h("ins", {}, data.better),
          data.why && h("div", { class: "note", style: "text-align:left" }, data.why)));
        break;

      case "receipt": // ring_up_order
        addCard("corrections", h("div", { class: "receipt" },
          h("div", { style: "text-align:center;font-weight:bold" }, data.cafe),
          h("hr"),
          data.items.map((i) => h("div", { class: "line" }, h("span", {}, i.name), h("span", {}, `${i.price} ${data.currency}`))),
          h("hr"),
          h("div", { class: "line" }, h("b", {}, "TOTAL"), h("b", {}, `${data.total} ${data.currency}`))));
        break;
    }
  },
});
