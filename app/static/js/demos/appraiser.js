// Copyright 2026 Sam Witteveen
// SPDX-License-Identifier: Apache-2.0
// The Appraiser: renders the widgets that the professor's tool calls drive.
import { h, mountDemo } from "../shell.js";

const $ = (id) => document.getElementById(id);
const usd = (n) => "$" + Number(n || 0).toLocaleString("en-US");

mountDemo({
  demoId: "appraiser",
  camera: "auto", // this demo is all about showing things to the camera

  onUi(event, data) {
    switch (event) {
      // begin_appraisal → the item goes "on the table"
      case "appraisal_started":
        $("onTable").replaceChildren(
          h("div", { class: "on-table" }, data.item_name),
          data.first_impression && h("div", { class: "note", style: "text-align:left" }, data.first_impression),
        );
        $("archives").textContent = "Not consulted yet.";
        break;

      // consult_auction_archives started: it runs for ~6s in the background
      case "archives_searching":
        $("archives").replaceChildren(h("span", { class: "spinner" }), `Searching archives for "${data.item_name}"…`);
        break;

      // …and finished. The professor mentions it at the next pause (WHEN_IDLE).
      case "archives_result":
        $("archives").replaceChildren(
          h("ul", { class: "sales" },
            data.comparable_sales.map((s) =>
              h("li", {}, h("span", {}, `${s.house}, ${s.year}`), h("b", {}, usd(s.hammer_price_usd))))),
        );
        break;

      // issue_certificate → the big finish
      case "certificate":
        $("certificate").replaceChildren(
          h("div", { class: "certificate" },
            h("h3", {}, "Certificate of Appraisal"),
            h("div", { class: "item" }, data.item_name),
            h("div", { class: "era" }, data.era),
            h("div", {}, data.provenance),
            h("div", { class: "value" }, `${usd(data.low_estimate_usd)} – ${usd(data.high_estimate_usd)}`),
            h("div", { class: "stars" }, "★".repeat(data.rarity || 1) + "☆".repeat(5 - (data.rarity || 1))),
            data.remark && h("div", { class: "remark" }, `“${data.remark}”`),
            h("div", { class: "seal" }, "🏅"),
          ),
        );
        break;
    }
  },
});
