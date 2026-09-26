/**
 * LiveClient: the browser end of our WebSocket (see app/browser_link.py).
 *
 *   binary in   [stream index byte][fMP4 chunk] → the matching AvatarPlayer
 *   JSON in     re-dispatched as DOM events: "transcript", "ui", "tool",
 *               "turn_complete", "interrupted", "ready", "error", "notice"
 *   binary out  microphone PCM
 *   JSON out    start / text / image / action
 *
 * Echo gate: if you use speakers, the mic hears the avatar and the avatar
 * "interrupts itself". Unless headphones mode is on, we don't send mic audio
 * while the avatar is talking. Turn headphones mode on to barge in mid-sentence.
 */
export class LiveClient extends EventTarget {
  /**
   * @param {string} demoId
   * @param {import('./avatar-player.js').AvatarPlayer[]} players  one per stream
   */
  constructor(demoId, players) {
    super();
    this.demoId = demoId;
    this.players = players;
    this.headphones = false;
    this._speakingUntil = 0; // echo gate: timestamp until which the avatar is "speaking"
  }

  connect(options = {}) {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    this.ws = new WebSocket(`${proto}://${location.host}/ws/${this.demoId}`);
    this.ws.binaryType = "arraybuffer";

    this.ws.onopen = () => this._send({ type: "start", options });
    this.ws.onclose = () => this._emit("closed", {});
    this.ws.onerror = () => this._emit("error", { message: "WebSocket error. Is the server running?" });

    this.ws.onmessage = (e) => {
      if (e.data instanceof ArrayBuffer) {
        // Byte 0 says which avatar this chunk belongs to (0, or 0/1 in the debate).
        const stream = new Uint8Array(e.data, 0, 1)[0];
        this.players[stream]?.push(e.data.slice(1));
        return;
      }
      const msg = JSON.parse(e.data);
      const player = this.players[msg.stream ?? 0];

      if (msg.type === "transcript" && msg.role === "model") this._markSpeaking(player, 1.5);
      if (msg.type === "turn_complete") this._markSpeaking(player, 0.4);
      if (msg.type === "interrupted") {
        // The user barged in: drop the buffered (now stale) speech.
        player?.jumpToLive();
        this._speakingUntil = 0;
      }
      this._emit(msg.type, msg);
    };
  }

  get isOpen() { return this.ws?.readyState === WebSocket.OPEN; }

  /** Is the mic currently muted by the echo gate? */
  get gated() { return !this.headphones && performance.now() < this._speakingUntil; }

  sendAudio(pcm) { if (this.isOpen && !this.gated) this.ws.send(pcm); }
  sendImage(b64) { this._send({ type: "image", data: b64 }); }
  sendText(text) { this._send({ type: "text", text }); }
  action(payload) { this._send({ type: "action", ...payload }); }

  close() {
    this.ws?.close();
    this.players.forEach((p) => p.stop());
  }

  // --- internals -----------------------------------------------------------

  _markSpeaking(player, extraSeconds) {
    // Keep the gate shut until the buffered video (and its audio) has played out.
    const until = performance.now() + ((player?.lag ?? 0) + extraSeconds) * 1000;
    this._speakingUntil = Math.max(this._speakingUntil, until);
  }

  _send(obj) { if (this.isOpen) this.ws.send(JSON.stringify(obj)); }
  _emit(type, detail) { this.dispatchEvent(new CustomEvent(type, { detail })); }
}
