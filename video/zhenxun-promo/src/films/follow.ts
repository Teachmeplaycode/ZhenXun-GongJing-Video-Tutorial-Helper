import {Key, Track} from '../camera';

// Camera keys for a stretch of a recording, Screen Studio–style: before each thing the script
// does (a move's target, a click, typing) the camera eases in on it; across a long pause it eases
// back out a little; it starts and ends wide. `extra` keys (e.g. on an answer appearing, where the
// mouse isn't) are merged in. All in recording pixels and source seconds.
export function follow(rec: Track, from: number, to: number, {zoom = 2, wide = 1.12, gap = 1.8, extra = [] as Key[]} = {}): Key[] {
  const W = rec.width;
  const H = rec.height;
  const centre = {x: W / 2, y: H / 2};
  type Ev = (typeof rec.track)[number] & {to?: {x: number; y: number}};
  const evs = (rec.track as Ev[]).filter((e) => e.t >= from - 0.2 && e.t <= to && ['move', 'click', 'key', 'press', 'scroll'].includes(e.type));
  const keys: Key[] = [{t: from, zoom: wide, ...centre}];
  evs.forEach((e, i) => {
    const p = e.type === 'move' && e.to ? e.to : {x: e.x, y: e.y};
    const z = e.type === 'scroll' ? Math.min(zoom, 1.4) : zoom;
    keys.push({t: Math.max(from + 0.05, e.t - 0.35), zoom: z, x: p.x, y: p.y});
    const next = evs[i + 1];
    if (!next || next.t - e.t > gap) {
      keys.push({t: e.t + 0.9, zoom: z, x: p.x, y: p.y});
      if (next) keys.push({t: next.t - 0.7, zoom: wide + 0.15, x: (p.x + centre.x) / 2, y: (p.y + centre.y) / 2});
    }
  });
  keys.push(...extra);
  keys.sort((a, b) => a.t - b.t);
  // drop keys that crowd each other (keep the later)
  const out: Key[] = [];
  for (const k of keys) {
    if (out.length && k.t - out[out.length - 1].t < 0.12) out[out.length - 1] = k;
    else out.push(k);
  }
  if (out[out.length - 1].t < to) out.push({...out[out.length - 1], t: to});
  return out;
}

/** Find a mark's time in a track. */
export const markAt = (rec: Track, label: string) => (rec.track as {t: number; type: string; label?: string}[]).find((e) => e.type === 'mark' && e.label === label)?.t ?? 0;
