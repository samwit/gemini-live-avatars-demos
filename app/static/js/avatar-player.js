/**
 * AvatarPlayer: plays the avatar's live fragmented-MP4 stream in a <video>.
 *
 * Gemini sends one continuous fMP4 file in small chunks:
 *   chunk 1       init segment (ftyp + moov): H.264 704x1280 @24fps + AAC 24 kHz
 *   chunk 2..n    moof/mdat fragments, forever (the avatar idles between turns)
 *
 * Media Source Extensions (MSE) are built for exactly this: create a
 * MediaSource, add one SourceBuffer with the right codecs, and append every
 * chunk as it arrives. The speech audio is muxed into the same stream, so lip
 * sync is automatic and we don't need a separate audio player.
 *
 * The one extra thing a *live* player must do is stay near the live edge.
 * Network hiccups make the buffer grow, and then the avatar answers late.
 * `_chase()` nudges playback speed up a little when we fall behind, and jumps
 * ahead if we're far behind.
 */

// avc1.42c020 = H.264 Constrained Baseline, level 3.2. mp4a.40.2 = AAC-LC.
const MIME = 'video/mp4; codecs="avc1.42c020, mp4a.40.2"';

export class AvatarPlayer {
  /** @param {HTMLVideoElement} video */
  constructor(video) {
    this.video = video;
    this.queue = [];
    this.sourceBuffer = null;
    this.bytes = 0;
  }

  /** Call from a click handler so the browser allows playback with sound. */
  start() {
    this.stop();
    // Safari on iOS only has ManagedMediaSource; everything else has MediaSource.
    const MS = window.ManagedMediaSource || window.MediaSource;
    if (!MS || !MS.isTypeSupported(MIME)) {
      throw new Error("This browser can't play the avatar stream (needs MSE with H.264 + AAC).");
    }
    this.mediaSource = new MS();
    this.video.disableRemotePlayback = true; // required for ManagedMediaSource
    this.video.src = URL.createObjectURL(this.mediaSource);
    this.mediaSource.addEventListener("sourceopen", () => {
      this.sourceBuffer = this.mediaSource.addSourceBuffer(MIME);
      this.sourceBuffer.addEventListener("updateend", () => this._pump());
      this._pump();
    }, { once: true });

    this.video.play().catch(() => {}); // unlock autoplay while we have the user gesture
    this.timer = setInterval(() => this._chase(), 250);
  }

  /** Append one chunk (ArrayBuffer) from the server. */
  push(chunk) {
    this.queue.push(new Uint8Array(chunk));
    this.bytes += chunk.byteLength;
    this._pump();
  }

  /** Seconds of video buffered ahead of what's playing. */
  get lag() {
    const b = this.video.buffered;
    return b.length ? b.end(b.length - 1) - this.video.currentTime : 0;
  }

  /** Skip anything buffered and play the newest frames (e.g. after an interruption). */
  jumpToLive() {
    const b = this.video.buffered;
    if (b.length) this.video.currentTime = Math.max(b.start(b.length - 1), b.end(b.length - 1) - 0.1);
  }

  stop() {
    clearInterval(this.timer);
    this.queue = [];
    this.sourceBuffer = null;
    this.bytes = 0;
    if (this.video.src) {
      this.video.pause();
      URL.revokeObjectURL(this.video.src);
      this.video.removeAttribute("src");
      this.video.load();
    }
  }

  // --- internals -----------------------------------------------------------

  _pump() {
    const sb = this.sourceBuffer;
    if (!sb || sb.updating || this.queue.length === 0) return;

    // Chunks arrive every few milliseconds, so batch them into one append.
    const total = this.queue.reduce((n, c) => n + c.byteLength, 0);
    const data = new Uint8Array(total);
    let offset = 0;
    for (const c of this.queue) { data.set(c, offset); offset += c.byteLength; }
    this.queue = [];

    try {
      sb.appendBuffer(data);
    } catch (e) {
      if (e.name === "QuotaExceededError") {
        // Buffer full: put the data back and free old video first.
        this.queue.unshift(data);
        this._trim(true);
      } else {
        console.warn("appendBuffer failed", e);
      }
    }
    if (this.video.paused) this.video.play().catch(() => {});
  }

  _chase() {
    const v = this.video;
    const b = v.buffered;
    if (!b.length) return;
    const lastStart = b.start(b.length - 1);
    const lag = this.lag;

    if (v.currentTime < lastStart) v.currentTime = lastStart; // stuck before a gap
    if (lag > 2.0) this.jumpToLive();                       // far behind: jump
    else v.playbackRate = lag > 0.6 ? 1.08 : 1.0;           // a bit behind: catch up gently

    this._trim(false);
  }

  /** Drop video we've already watched so the buffer never fills up. */
  _trim(force) {
    const sb = this.sourceBuffer, v = this.video, b = v.buffered;
    if (!sb || sb.updating || !b.length) return;
    const keepFrom = v.currentTime - 5;
    if (keepFrom - b.start(0) > (force ? 0 : 30)) sb.remove(b.start(0), keepFrom);
  }
}
