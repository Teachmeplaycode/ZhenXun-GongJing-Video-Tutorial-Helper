// The camera that follows the recorded mouse (record/record.mjs writes the track): a zoom and a
// centre on the 3840×2160 recording for every frame of a shot, eased between keys.
export type Track = {width: number; height: number; track: {t: number; type: string; x: number; y: number; box?: {x: number; y: number; width: number; height: number} | null}[]};
export type Key = {t: number; zoom: number; x: number; y: number};

const ease = (k: number) => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2);

/** The camera at source time `t` (s) from keys (sorted by t): eased between the two around it. */
export function cameraAt(keys: Key[], t: number): Key {
  if (t <= keys[0].t) return keys[0];
  for (let i = 1; i < keys.length; i += 1) {
    const a = keys[i - 1];
    const b = keys[i];
    if (t <= b.t) {
      const k = ease((t - a.t) / Math.max(0.001, b.t - a.t));
      return {t, zoom: a.zoom + (b.zoom - a.zoom) * k, x: a.x + (b.x - a.x) * k, y: a.y + (b.y - a.y) * k};
    }
  }
  return keys[keys.length - 1];
}

/** CSS transform placing the recording (sw×sh) in a w×h frame, zoomed on (x, y) and kept inside the picture. */
export function frameTransform(cam: Key, sw: number, sh: number, w: number, h: number): string {
  const fit = w / sw; // the whole recording in the frame at zoom 1
  const scale = fit * Math.max(1, cam.zoom);
  const halfW = w / 2 / scale;
  const halfH = h / 2 / scale;
  const cx = Math.min(sw - halfW, Math.max(halfW, cam.x));
  const cy = Math.min(sh - halfH, Math.max(halfH, cam.y));
  return `translate(${w / 2 - cx * scale}px, ${h / 2 - cy * scale}px) scale(${scale})`;
}

/** Events of one kind between two source times. */
export const events = (rec: Track, type: string, from = -Infinity, to = Infinity) =>
  rec.track.filter((e) => e.type === type && e.t >= from && e.t <= to);
