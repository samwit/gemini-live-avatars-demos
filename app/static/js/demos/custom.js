// Be the Avatar: crop an uploaded photo to Google's spec, then start a session with it.
//
// Google's reference image requirements (Configure live avatars docs):
//   PNG, RGB, 9:16 portrait, at least 704x1280, under 5 MB, sharp,
//   head and shoulders filling >60% of the frame, facing the camera,
//   neutral expression, plain background, no hands or objects.
// The cropper below produces a 720x1280 PNG and checks what it can automatically.
import { h, mountDemo } from "../shell.js";

const $ = (id) => document.getElementById(id);
const OUT_W = 720, OUT_H = 1280;   // what we send: 9:16, above the 704x1280 minimum
const MIN_W = 704, MIN_H = 1280;
const MAX_BYTES = 5 * 1024 * 1024;

const canvas = $("cropper");
const ctx = canvas.getContext("2d");
let img = null;
let zoom = 1;
let cx = 0, cy = 0;   // the image point shown at the centre of the crop, in image pixels

// --- voices ---------------------------------------------------------------------
const cat = await (await fetch("/api/catalog")).json();
for (const [name, desc] of Object.entries(cat.voices)) $("voice").append(new Option(`${name} (${desc})`, name));
$("voice").value = "Aoede";
$("name").oninput = () => ($("nameTag").textContent = $("name").value.trim() || "Your avatar");

// --- loading a photo ------------------------------------------------------------
$("file").onchange = (e) => e.target.files[0] && load(e.target.files[0]);
const frame = document.querySelector(".avatar-frame");
frame.addEventListener("dragover", (e) => e.preventDefault());
frame.addEventListener("drop", (e) => {
  e.preventDefault();
  const file = e.dataTransfer.files[0];
  if (file && !demo.client) load(file);
});

function load(file) {
  if (!file.type.startsWith("image/")) return;
  const url = URL.createObjectURL(file);
  const next = new Image();
  next.onload = () => {
    img = next;
    zoom = 1;
    $("zoom").value = 1;
    $("zoom").disabled = false;
    cx = img.width / 2;
    cy = img.height * 0.45; // portraits usually have the face a little above centre
    $("dropHint").classList.add("hidden");
    draw();
  };
  next.src = url;
}

// --- cropping: drag to pan, slider to zoom ------------------------------------------
// "cover" scale makes the image just fill the 720x1280 frame; zoom goes further in.
const coverScale = () => Math.max(OUT_W / img.width, OUT_H / img.height);
const scale = () => coverScale() * zoom;

function clampCentre() {
  const s = scale();
  const halfW = OUT_W / s / 2, halfH = OUT_H / s / 2;
  cx = Math.min(Math.max(cx, halfW), img.width - halfW);
  cy = Math.min(Math.max(cy, halfH), img.height - halfH);
}

function draw() {
  if (!img) return;
  clampCentre();
  const s = scale();
  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, OUT_W, OUT_H); // flatten any transparency to white (RGB)
  ctx.drawImage(img, OUT_W / 2 - cx * s, OUT_H / 2 - cy * s, img.width * s, img.height * s);
  checks();
}

$("zoom").oninput = (e) => { zoom = Number(e.target.value); draw(); };

let dragging = null;
canvas.addEventListener("pointerdown", (e) => {
  if (!img) return;
  dragging = { x: e.clientX, y: e.clientY };
  canvas.setPointerCapture(e.pointerId);
});
canvas.addEventListener("pointermove", (e) => {
  if (!dragging) return;
  // Convert screen pixels → canvas pixels → image pixels.
  const k = OUT_W / canvas.clientWidth / scale();
  cx -= (e.clientX - dragging.x) * k;
  cy -= (e.clientY - dragging.y) * k;
  dragging = { x: e.clientX, y: e.clientY };
  draw();
});
canvas.addEventListener("pointerup", () => (dragging = null));

// --- automatic checks -------------------------------------------------------------
let pngBase64 = null;

function checks() {
  // How many real source pixels end up in the crop? Under 704 wide means we're
  // enlarging the photo, which makes it blurry, and Google asks for no blur.
  const s = scale();
  const srcW = Math.round(OUT_W / s), srcH = Math.round(OUT_H / s);
  const sharp = srcW >= MIN_W && srcH >= MIN_H;

  pngBase64 = canvas.toDataURL("image/png").split(",")[1];
  const bytes = Math.round(pngBase64.length * 0.75);

  const items = [
    [true, "Cropped to 9:16 portrait PNG, 720×1280"],
    [sharp, sharp
      ? `Sharp: uses ${srcW}×${srcH} real pixels`
      : `Low resolution: only ${srcW}×${srcH} real pixels (${MIN_W}×${MIN_H} recommended). ${zoom > 1 ? "Zoom out, or use" : "Use"} a larger portrait photo.`],
    [bytes < MAX_BYTES, `File size ${(bytes / 1e6).toFixed(1)} MB (limit 5 MB)`],
    [null, "Facing the camera, head level, neutral expression, no teeth"],
    [null, "Plain background, nobody else in shot, no hands or objects"],
  ];
  $("checks").replaceChildren(...items.map(([ok, text]) =>
    h("li", { class: ok === null ? "todo" : ok ? "ok" : "bad" }, text)));
  updateStart();
}

// --- consent + start ------------------------------------------------------------------
$("consent").onchange = updateStart;

function updateStart() {
  // While a session is running, the button is "Stop" and always enabled.
  $("startBtn").disabled = !demo?.client && !(img && pngBase64 && $("consent").checked);
  document.querySelector("#overlay span").textContent =
    !img ? "Upload a photo to begin" : !$("consent").checked ? "Tick the consent box, then Start" : "Ready: press Start";
}

const demo = mountDemo({
  demoId: "custom",
  getOptions: () => ({
    image: pngBase64,
    consent: $("consent").checked,
    name: $("name").value,
    voice: $("voice").value,
    persona: $("persona").value,
  }),
  onStop: () => setTimeout(updateStart), // re-apply our enable/disable rules
});
updateStart();
