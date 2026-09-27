// Copyright 2026 Sam Witteveen
// SPDX-License-Identifier: Apache-2.0
/**
 * Microphone and camera capture.
 *
 *   Mic     getUserMedia → AudioWorklet (pcm-worklet.js) → 16 kHz PCM chunks
 *   Camera  getUserMedia → <canvas> → JPEG, once per second
 *
 * The Live API takes camera input as a sequence of still JPEG frames at about
 * 1 fps (768x768 or smaller works best). It isn't a video stream, so the
 * canvas snapshot approach below is all you need.
 */

export class Mic {
  /** @param {(pcm: ArrayBuffer, level: number) => void} onChunk */
  async start(onChunk) {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    this.ctx = new AudioContext();
    await this.ctx.audioWorklet.addModule("/js/pcm-worklet.js");

    const source = this.ctx.createMediaStreamSource(this.stream);
    this.node = new AudioWorkletNode(this.ctx, "pcm-16k");
    this.node.port.onmessage = (e) => onChunk(e.data.pcm, e.data.level);

    // Worklets only run when connected to the graph; a muted gain keeps it
    // running without playing your own voice back to you.
    const mute = this.ctx.createGain();
    mute.gain.value = 0;
    source.connect(this.node).connect(mute).connect(this.ctx.destination);
  }

  stop() {
    this.stream?.getTracks().forEach((t) => t.stop());
    this.ctx?.close();
    this.stream = this.ctx = this.node = null;
  }
}

export class Camera {
  /**
   * @param {HTMLVideoElement} preview  shows your own camera (picture-in-picture)
   * @param {(jpegBase64: string) => void} onFrame
   */
  async start(preview, onFrame, { fps = 1, maxSide = 768 } = {}) {
    this.stream = await navigator.mediaDevices.getUserMedia({ video: { width: 960, height: 720 } });
    preview.srcObject = this.stream;
    await preview.play().catch(() => {});

    const canvas = document.createElement("canvas");
    this.timer = setInterval(() => {
      const w = preview.videoWidth, h = preview.videoHeight;
      if (!w) return;
      const scale = Math.min(1, maxSide / Math.max(w, h));
      canvas.width = Math.round(w * scale);
      canvas.height = Math.round(h * scale);
      canvas.getContext("2d").drawImage(preview, 0, 0, canvas.width, canvas.height);
      // "data:image/jpeg;base64,XXXX" → just the XXXX part
      onFrame(canvas.toDataURL("image/jpeg", 0.75).split(",")[1]);
    }, 1000 / fps);
  }

  stop() {
    clearInterval(this.timer);
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
  }
}
