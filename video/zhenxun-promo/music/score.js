// The PV's music: an original electronic track at 128 BPM in F minor, sixty seconds, composed as
// code with Tone.js and rendered offline in a browser (music/render.mjs). Its form follows the
// film (music/cues.json): an arpeggio and a build for the opening, a drop on bar 4 as the title
// lands, a funky groove (four-on-the-floor, offbeat hats, a syncopated bass, Fm–Db–Eb–Cm stabs)
// with a lead hook, a crash on every cut, a filtered dip and a second build, and the final drop on
// bar 30 under the closing lockup.
/* global Tone */

window.compose = async (cues) => {
  const BEAT = 60 / cues.bpm;
  const BAR = BEAT * 4;
  const S = BEAT / 4; // a sixteenth
  const at = (bar, sixteenth = 0) => bar * BAR + sixteenth * S;
  const DURATION = cues.bars * BAR;

  const buffer = await Tone.Offline(async () => {
    // ---------------------------------------------------------------- the desk
    const limiter = new Tone.Limiter(-1.2).toDestination();
    const master = new Tone.Compressor({threshold: -14, ratio: 3, attack: 0.01, release: 0.2}).connect(limiter);
    const reverb = new Tone.Reverb({decay: 2.6, wet: 1});
    await reverb.ready;
    const verb = new Tone.Gain(0.22).connect(reverb);
    reverb.connect(master);
    const delay = new Tone.FeedbackDelay({delayTime: BEAT * 0.75, feedback: 0.32, wet: 1});
    const echo = new Tone.Gain(0.18).connect(delay);
    delay.connect(master);
    const bus = (gain, {rev = 0, del = 0} = {}) => {
      const g = new Tone.Gain(gain).connect(master);
      if (rev) g.connect(new Tone.Gain(rev).connect(verb));
      if (del) g.connect(new Tone.Gain(del).connect(echo));
      return g;
    };

    // ---------------------------------------------------------------- instruments
    const kick = new Tone.MembraneSynth({pitchDecay: 0.035, octaves: 7, envelope: {attack: 0.001, decay: 0.32, sustain: 0, release: 0.1}}).connect(bus(0.95));
    const boom = new Tone.MembraneSynth({pitchDecay: 0.5, octaves: 5, envelope: {attack: 0.001, decay: 2.2, sustain: 0, release: 0.4}}).connect(bus(0.8, {rev: 0.3}));
    const clapFilter = new Tone.Filter(1700, 'bandpass').connect(bus(0.55, {rev: 0.6}));
    const clap = new Tone.NoiseSynth({noise: {type: 'white'}, envelope: {attack: 0.002, decay: 0.16, sustain: 0}}).connect(clapFilter);
    const hatFilter = new Tone.Filter(8000, 'highpass').connect(bus(0.22));
    const hat = new Tone.NoiseSynth({noise: {type: 'white'}, envelope: {attack: 0.001, decay: 0.035, sustain: 0}}).connect(hatFilter);
    const openHat = new Tone.NoiseSynth({noise: {type: 'white'}, envelope: {attack: 0.002, decay: 0.22, sustain: 0}}).connect(hatFilter);
    const crashFilter = new Tone.Filter(3500, 'highpass').connect(bus(0.32, {rev: 0.8}));
    const crash = new Tone.NoiseSynth({noise: {type: 'pink'}, envelope: {attack: 0.001, decay: 1.8, sustain: 0}}).connect(crashFilter);

    const bassFilter = new Tone.Filter({frequency: 900, type: 'lowpass', Q: 2}).connect(bus(0.62));
    const bass = new Tone.MonoSynth({oscillator: {type: 'sawtooth'}, envelope: {attack: 0.004, decay: 0.18, sustain: 0.35, release: 0.08},
      filterEnvelope: {attack: 0.002, decay: 0.12, sustain: 0.2, release: 0.1, baseFrequency: 120, octaves: 3.2}}).connect(bassFilter);
    const sub = new Tone.Synth({oscillator: {type: 'sine'}, envelope: {attack: 0.005, decay: 0.2, sustain: 0.6, release: 0.1}}).connect(bus(0.45));

    const stabFilter = new Tone.Filter({frequency: 2400, type: 'lowpass'}).connect(bus(0.2, {rev: 0.5, del: 0.35}));
    const stab = new Tone.PolySynth(Tone.Synth, {oscillator: {type: 'fatsawtooth', count: 3, spread: 22},
      envelope: {attack: 0.004, decay: 0.16, sustain: 0.05, release: 0.12}}).connect(stabFilter);
    const padFilter = new Tone.Filter({frequency: 1600, type: 'lowpass'}).connect(bus(0.12, {rev: 1.2}));
    const pad = new Tone.PolySynth(Tone.Synth, {oscillator: {type: 'fatsawtooth', count: 3, spread: 30},
      envelope: {attack: 0.6, decay: 0.4, sustain: 0.8, release: 1.6}}).connect(padFilter);
    const arpFilter = new Tone.Filter({frequency: 600, type: 'lowpass', Q: 3}).connect(bus(0.2, {rev: 0.4, del: 0.6}));
    const arp = new Tone.PolySynth(Tone.Synth, {oscillator: {type: 'triangle'}, envelope: {attack: 0.002, decay: 0.12, sustain: 0, release: 0.08}}).connect(arpFilter);
    const leadFilter = new Tone.Filter({frequency: 3000, type: 'lowpass'}).connect(bus(0.14, {rev: 0.5, del: 0.5}));
    const lead = new Tone.MonoSynth({oscillator: {type: 'square'}, portamento: 0.03, envelope: {attack: 0.01, decay: 0.2, sustain: 0.5, release: 0.2},
      filterEnvelope: {attack: 0.01, decay: 0.3, sustain: 0.4, release: 0.2, baseFrequency: 600, octaves: 2.5}}).connect(leadFilter);

    // a white-noise riser: swept band-pass, swelling in
    const riser = (from, to, peak = 0.35) => {
      const g = new Tone.Gain(0).connect(bus(1, {rev: 0.4}));
      const f = new Tone.Filter({frequency: 300, type: 'bandpass', Q: 1.4}).connect(g);
      const n = new Tone.Noise('white').connect(f);
      n.start(at(from)).stop(at(to));
      g.gain.setValueAtTime(0, at(from));
      g.gain.linearRampToValueAtTime(peak, at(to) - 0.02);
      g.gain.linearRampToValueAtTime(0, at(to));
      f.frequency.setValueAtTime(300, at(from));
      f.frequency.exponentialRampToValueAtTime(9000, at(to));
    };

    // Tone wants each instrument's notes scheduled in time order; the form below is written by
    // section, so every note is queued and the queue is played back sorted at the end.
    const queue = [];
    const defer = (inst, timeArg) => {
      const play = inst.triggerAttackRelease.bind(inst);
      inst.triggerAttackRelease = (...args) => { queue.push([args[timeArg], queue.length, () => play(...args)]); return inst; };
    };
    [kick, boom, bass, sub, stab, pad, arp, lead].forEach((i) => defer(i, 2));
    [clap, hat, openHat, crash].forEach((i) => defer(i, 1));

    // ---------------------------------------------------------------- harmony
    const CHORDS = [
      {bass: 'F1', notes: ['F3', 'Ab3', 'C4', 'Eb4', 'G4']}, // Fm9
      {bass: 'Db2', notes: ['Db3', 'F3', 'Ab3', 'C4']}, // Dbmaj7
      {bass: 'Eb2', notes: ['Eb3', 'G3', 'Bb3', 'Db4']}, // Eb7
      {bass: 'C2', notes: ['C3', 'Eb3', 'G3', 'Bb3']}, // Cm7
    ];
    const chordAt = (bar) => CHORDS[Math.floor(bar) % 4];
    const up = (note, oct) => Tone.Frequency(note).transpose(12 * oct).toNote();

    // ---------------------------------------------------------------- parts
    const drums = (bar, {kicks = true, claps = true, hats = true, open = true} = {}) => {
      for (let b = 0; b < 4; b += 1) {
        if (kicks) kick.triggerAttackRelease('F1', '8n', at(bar, b * 4), 1);
        if (claps && (b === 1 || b === 3)) clap.triggerAttackRelease(0.12, at(bar, b * 4), 0.9);
        if (open) openHat.triggerAttackRelease(0.16, at(bar, b * 4 + 2), 0.5);
      }
      if (hats) for (let s = 0; s < 16; s += 1) if (s % 4 !== 2) hat.triggerAttackRelease(0.03, at(bar, s), s % 2 ? 0.35 : 0.6);
    };
    const BASS = [[0, 0], [3, 1], [6, 0], [8, 0], [10, 1], [11, 0], [14, 0]]; // [sixteenth, octave up]
    const bassBar = (bar, vel = 0.9) => {
      const c = chordAt(bar);
      for (const [s, o] of BASS) bass.triggerAttackRelease(up(c.bass, o + 1), S * 1.6, at(bar, s), vel);
      sub.triggerAttackRelease(up(c.bass, 1), BEAT * 1.5, at(bar), 0.7);
      sub.triggerAttackRelease(up(c.bass, 1), BEAT * 1.5, at(bar, 8), 0.6);
    };
    const stabBar = (bar, vel = 0.6) => {
      const c = chordAt(bar);
      for (const s of [2, 7, 10]) stab.triggerAttackRelease(c.notes, S * 1.5, at(bar, s), vel);
    };
    const arpBar = (bar, vel = 0.45, octave = 1) => {
      const notes = chordAt(bar).notes.map((n) => up(n, octave));
      for (let s = 0; s < 16; s += 1) arp.triggerAttackRelease(notes[(s * 3) % notes.length], S * 0.9, at(bar, s), vel * (s % 4 === 0 ? 1 : 0.7));
    };
    const HOOK = [ // [bar in the 4-bar phrase, sixteenth, note, length in sixteenths]
      [0, 0, 'C5', 2], [0, 3, 'Eb5', 1], [0, 4, 'F5', 3], [0, 8, 'Eb5', 2], [0, 10, 'C5', 4],
      [1, 0, 'Ab4', 3], [1, 4, 'C5', 2], [1, 7, 'Bb4', 1], [1, 8, 'Ab4', 6],
      [2, 0, 'Bb4', 3], [2, 4, 'Eb5', 2], [2, 7, 'F5', 1], [2, 8, 'G5', 4], [2, 12, 'F5', 2],
      [3, 0, 'Eb5', 4], [3, 6, 'C5', 2], [3, 8, 'Bb4', 2], [3, 10, 'C5', 6],
    ];
    const hook = (bar) => { for (const [b, s, n, l] of HOOK) lead.triggerAttackRelease(n, S * l * 0.95, at(bar + b, s), 0.7); };
    const hit = (bar, big = false) => {
      crash.triggerAttackRelease(big ? 2.4 : 1.4, at(bar), big ? 0.9 : 0.55);
      if (big) boom.triggerAttackRelease('F1', 1.8, at(bar), 1);
    };
    const roll = (from, to) => { // a snare roll in 16ths, getting louder
      const n = Math.round((to - from) * 16);
      for (let i = 0; i < n; i += 1) clap.triggerAttackRelease(0.06, at(from) + i * S, 0.2 + 0.7 * (i / n));
    };

    // ---------------------------------------------------------------- the form
    arpFilter.frequency.setValueAtTime(1100, 0);
    arpFilter.frequency.exponentialRampToValueAtTime(4200, at(4));
    // 0–4: the opening — arpeggio over a low pad, then hats and sub, then the build into the title
    for (let bar = 0; bar < 4; bar += 1) arpBar(bar, bar < 2 ? 0.8 : 0.65);
    pad.triggerAttackRelease(CHORDS[0].notes, BAR * 2.4, 0, 0.55);
    pad.triggerAttackRelease(CHORDS[1].notes, BAR * 1.4, at(2.5), 0.45);
    for (let b = 0; b < 6; b += 1) openHat.triggerAttackRelease(0.1, at(0, 2 + b * 4), 0.25);
    for (let s = 0; s < 16 * 2.5; s += 2) hat.triggerAttackRelease(0.03, at(1.5) + s * S, 0.35);
    for (let s = 0; s < 8; s += 4) sub.triggerAttackRelease('F2', BEAT, at(1.5, s), 0.6);
    for (let b = 0; b < 6; b += 1) kick.triggerAttackRelease('F1', '8n', at(2.5) + b * BEAT, 0.8);
    roll(3, 3.75);
    riser(2.5, 4, 0.3);
    // 4: the title lands
    hit(4, true);
    stab.triggerAttackRelease(CHORDS[0].notes, BEAT * 1.5, at(4), 0.8);
    pad.triggerAttackRelease(CHORDS[0].notes, BAR * 1.3, at(4), 0.5);
    // 4–24: the groove
    for (let bar = 4; bar < 24; bar += 1) {
      drums(bar, {claps: bar >= 5, open: bar >= 5});
      bassBar(bar);
      if (bar >= 5) stabBar(bar, bar >= 12 ? 0.6 : 0.45);
      if (bar >= 19 && bar < 24) arpBar(bar, 0.35, 1);
    }
    for (const b of [12, 16, 20]) hook(b);
    roll(15.5, 16); // a fill into the giant type
    // 24–27.5: the dip — filtered, kick and bass only, a riser into the slogan
    bassFilter.frequency.setValueAtTime(900, at(24));
    bassFilter.frequency.linearRampToValueAtTime(380, at(25));
    bassFilter.frequency.linearRampToValueAtTime(900, at(27.5));
    for (let bar = 24; bar < 27.5; bar += 1) {
      for (let b = 0; b < 4; b += 1) kick.triggerAttackRelease('F1', '8n', at(bar, b * 4), 0.85);
      bassBar(bar, 0.75);
      if (bar >= 25) for (let s = 2; s < 16; s += 4) openHat.triggerAttackRelease(0.12, at(bar, s), 0.35);
    }
    pad.triggerAttackRelease(CHORDS[1].notes, BAR * 3, at(24.5), 0.35);
    riser(26.5, 27.5, 0.3);
    // 27.5–30: the slogan — hits on 看见 and 再求证, then the last build
    hit(27.5, true);
    stab.triggerAttackRelease(CHORDS[2].notes, BEAT, at(27.5), 0.8);
    hit(28);
    stab.triggerAttackRelease(CHORDS[3].notes, BEAT, at(28), 0.8);
    for (let b = 0; b < 4; b += 1) kick.triggerAttackRelease('F1', '8n', at(28, b * 4), 0.9);
    for (let s = 0; s < 16; s += 2) kick.triggerAttackRelease('F1', '16n', at(29, s), 0.75);
    roll(28.5, 29.75);
    riser(28, 29.85, 0.4);
    // 30–32: the lockup — the last drop, then it settles
    hit(30, true);
    pad.triggerAttackRelease(CHORDS[0].notes, BAR * 1.6, at(30), 0.6);
    stab.triggerAttackRelease(CHORDS[0].notes.map((n) => up(n, 1)), BEAT * 2, at(30), 0.7);
    for (let bar = 30; bar < 31; bar += 1) { drums(bar, {open: false}); bassBar(bar, 0.8); }
    arpBar(30, 0.35, 1);
    arpBar(31, 0.25, 1);
    kick.triggerAttackRelease('F1', '8n', at(31), 0.9);
    boom.triggerAttackRelease('F1', 1.6, at(31), 0.6);
    // a crash on every cut (the drops have their own)
    for (const c of cues.cuts) if (!cues.drops.includes(c) && c !== 27.5) hit(c);
    for (const h of cues.hits) if (h !== 28) stab.triggerAttackRelease(chordAt(h).notes, S * 2, at(h), 0.7);
    queue.sort((x, y) => x[0] - y[0] || x[1] - y[1]).forEach(([, , play]) => play());
  }, DURATION, 2, 48000);

  // ---------------------------------------------------------------- WAV (16-bit), as base64
  const channels = buffer.toArray();
  const left = channels[0];
  const right = channels[1] || channels[0];
  const n = left.length;
  const bytes = new DataView(new ArrayBuffer(44 + n * 4));
  const str = (o, s) => [...s].forEach((ch, i) => bytes.setUint8(o + i, ch.charCodeAt(0)));
  str(0, 'RIFF'); bytes.setUint32(4, 36 + n * 4, true); str(8, 'WAVE'); str(12, 'fmt ');
  bytes.setUint32(16, 16, true); bytes.setUint16(20, 1, true); bytes.setUint16(22, 2, true); bytes.setUint32(24, 48000, true);
  bytes.setUint32(28, 48000 * 4, true); bytes.setUint16(32, 4, true); bytes.setUint16(34, 16, true); str(36, 'data'); bytes.setUint32(40, n * 4, true);
  for (let i = 0; i < n; i += 1) {
    bytes.setInt16(44 + i * 4, Math.max(-1, Math.min(1, left[i])) * 32767, true);
    bytes.setInt16(46 + i * 4, Math.max(-1, Math.min(1, right[i])) * 32767, true);
  }
  let bin = '';
  const u8 = new Uint8Array(bytes.buffer);
  for (let i = 0; i < u8.length; i += 0x8000) bin += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000));
  return btoa(bin);
};
