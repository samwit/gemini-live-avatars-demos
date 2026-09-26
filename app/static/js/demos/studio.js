// Avatar Studio: choose avatar + voice + persona, then talk.
import { mountDemo } from "../shell.js";

const $ = (id) => document.getElementById(id);
const cat = await (await fetch("/api/catalog")).json();
let avatar = "Kira";

// Avatar picker (thumbnails)
for (const [name, a] of Object.entries(cat.avatars)) {
  const b = document.createElement("button");
  b.innerHTML = `<img src="/img/avatars/${name.toLowerCase()}.jpg" alt=""><span>${name}</span>`;
  b.title = a.look;
  b.onclick = () => selectAvatar(name);
  b.dataset.name = name;
  $("picker").append(b);
}

// Voice dropdown: "Puck (Upbeat)"
for (const [name, desc] of Object.entries(cat.voices)) {
  $("voice").append(new Option(`${name} (${desc})`, name));
}

// Persona presets
for (const name of Object.keys(cat.personas)) $("preset").append(new Option(name, name));
$("preset").onchange = () => ($("persona").value = cat.personas[$("preset").value]);
$("persona").value = Object.values(cat.personas)[0];

function selectAvatar(name) {
  avatar = name;
  document.querySelectorAll("#picker button").forEach((b) => b.classList.toggle("selected", b.dataset.name === name));
  $("voice").value = cat.avatars[name].voice; // suggested voice; change it freely
  $("avatarLook").textContent = `· ${name}: ${cat.avatars[name].look}`;
  $("poster").src = `/img/avatars/${name.toLowerCase()}.jpg`;
}
selectAvatar(avatar);

mountDemo({
  demoId: "studio",
  getOptions: () => ({
    avatar,
    voice: $("voice").value,
    persona: $("persona").value,
    search: $("search").checked,
  }),
});
