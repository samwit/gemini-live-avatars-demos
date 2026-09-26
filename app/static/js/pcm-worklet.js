/**
 * AudioWorklet that turns microphone audio into what the Live API wants:
 * 16 kHz, 16-bit, little-endian, mono PCM.
 *
 * Browsers capture at 44.1 or 48 kHz, so we resample here (simple linear
 * interpolation, which is plenty for speech) and post 100 ms chunks
 * (1600 samples) back to the page, along with a peak level for the mic meter.
 *
 * This file runs on the audio rendering thread, not the page.
 */
class Pcm16kProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.step = sampleRate / 16000; // how far to move in the input per output sample
    this.pos = 0;                   // fractional read position in the current input block
    this.out = new Int16Array(1600);
    this.n = 0;
    this.peak = 0;
  }

  process(inputs) {
    const input = inputs[0] && inputs[0][0];
    if (!input) return true;

    for (; this.pos < input.length; this.pos += this.step) {
      const i = Math.floor(this.pos);
      const frac = this.pos - i;
      const a = input[i];
      const b = i + 1 < input.length ? input[i + 1] : a;
      const s = Math.max(-1, Math.min(1, a + (b - a) * frac));
      this.peak = Math.max(this.peak, Math.abs(s));
      this.out[this.n++] = s * 0x7fff;

      if (this.n === this.out.length) {
        this.port.postMessage({ pcm: this.out.buffer, level: this.peak }, [this.out.buffer]);
        this.out = new Int16Array(1600);
        this.n = 0;
        this.peak = 0;
      }
    }
    this.pos -= input.length;
    return true; // keep running
  }
}

registerProcessor("pcm-16k", Pcm16kProcessor);
