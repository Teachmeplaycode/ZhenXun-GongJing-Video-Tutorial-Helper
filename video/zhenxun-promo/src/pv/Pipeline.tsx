import React, {useCallback} from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {clamp01, CONSOLE, easeOut, Fill, Glyphs, Head, INK, INK2, INK3, LIME, LINE2, PIXEL, pop, Sfx, SILK, SURFACE, Typed} from './kit';
import {FLOOR_VIEW, floorSlat, project, Sculpture, SITE_VIEW, SlatPose} from './Sculpture';

// 02 解析 → 切分 → 问答, played by the homepage's sculpture in its own colour (never tinted), the
// camera close and moving with it:
//   解析  the video as the floor timeline (a curving, rolling deck of slats); a read runs along it,
//         lifting what it reads — 画面 / 原声 / 文字 come off it — then every slat flies up, in
//         order, into the figure-eight while the camera rises from the floor to the site's view
//   切分  the camera pushes in on the ribbon and travels along it from cut to cut: at each one a
//         blade line crosses, the slats at the boundary drop out and the gap opens, and the
//         chapter's time and name come up; then it pulls back to the whole, cut into five
//   问答  a question is typed; the slats of the chapter that answers it come forward out of the
//         ribbon, and the answer arrives with its time and evidence

const READ = [14, 74];
const ASSEMBLE = [80, 150];
const CUTS = [0.18, 0.38, 0.6, 0.8]; // chapter boundaries (the fifth wraps at 0)
const CUT_AT = (k: number) => 186 + k * 34; // each cut, the camera having arrived
const PULL = [CUT_AT(3) + 34, CUT_AT(3) + 64];
const ASK_AT = PULL[1] + 4;
const CHAPTERS = [
  {t: '00:00', name: '打开软件'},
  {t: '01:12', name: '新建项目'},
  {t: '03:05', name: '导出设置'},
  {t: '04:47', name: '调整画质'},
  {t: '06:30', name: '保存文件'},
];
const ANSWER = 2;
const TAGS = [{u: 0.3, word: '画面'}, {u: 0.48, word: '原声'}, {u: 0.66, word: '文字'}];
const BOUNDS = [0, ...CUTS];
const chapterOf = (u: number) => BOUNDS.reduce((k, c, i) => (u >= c ? i : k), 0);
const marker = (k = 1): React.CSSProperties => ({backgroundImage: `linear-gradient(${LIME}, ${LIME})`, backgroundRepeat: 'no-repeat',
  backgroundSize: `${clamp01(k) * 100}% 38%`, backgroundPosition: '0 88%'});
const lerp = (a: number, b: number, k: number) => a + (b - a) * k;

export const Pipeline: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const time = frame / fps;
  const head = frame >= READ[0] && frame < READ[1] + 6 ? 0.2 + 0.56 * easeOut((frame - READ[0]) / (READ[1] - READ[0])) : -1;
  const fly = (u: number) => easeOut((frame - ASSEMBLE[0] - u * 40) / 30);
  const viewK = easeOut((frame - ASSEMBLE[0] - 10) / 60);
  const view: [number, number, number] = [lerp(FLOOR_VIEW[0], SITE_VIEW[0], viewK), lerp(FLOOR_VIEW[1], SITE_VIEW[1], viewK), lerp(FLOOR_VIEW[2], SITE_VIEW[2], viewK)];
  // the camera along the ribbon: which cut it is at, gliding between them
  const leg = Math.max(0, Math.min(3, Math.floor((frame - CUT_AT(0) + 24) / 34)));
  const fromU = leg === 0 ? CUTS[0] : CUTS[leg - 1];
  const glide = easeOut((frame - (CUT_AT(leg) - 24)) / 22);
  const focusU = lerp(fromU, CUTS[leg], leg === 0 ? 1 : glide);
  const push = easeOut((frame - ASSEMBLE[1] + 4) / 30) * (1 - easeOut((frame - PULL[0]) / (PULL[1] - PULL[0])));
  const answered = frame >= ASK_AT + 70;
  const lift = easeOut((frame - ASK_AT - 70) / 30);
  const pose = useCallback((i: number, u: number): SlatPose => {
    if (frame < ASSEMBLE[1] + 40) {
      const f = floorSlat(u, time, head);
      const onFloor = i % 3 === 0; // the floor shows every third slat; the rest join as it assembles
      const k = fly(u);
      if (!onFloor && k <= 0) return {size: 0};
      return {to: f, mix: 1 - k, size: onFloor ? 1 : k};
    }
    // cut: the slats at a boundary drop out once the blade has crossed it, the gap opening
    const cut = CUTS.some((c, j) => frame >= CUT_AT(j) && Math.abs(u - c) < 0.014);
    const near = CUTS.reduce((m, c, j) => (frame >= CUT_AT(j) ? Math.max(m, 1 - Math.abs(u - c) / 0.05) : m), 0);
    const k = chapterOf(u);
    return {size: cut ? 0 : 1, lift: (answered && k === ANSWER ? lift * (5 + 2 * Math.sin(u * 40 + frame / 20)) : 0) + Math.max(0, near) * 0.8};
  }, [frame, time, head, answered, lift]);
  const steps = ['解析', '切分', '问答'];
  const step = frame < ASSEMBLE[1] ? 0 : frame < ASK_AT ? 1 : 2;
  return (
    <Fill>
      <Sfx name="glitch" at={READ[0]} volume={0.2} />
      {TAGS.map((t, i) => <Sfx key={i} name="pop" at={READ[0] + ((t.u - 0.2) / 0.56) * 60} volume={0.35} />)}
      <Sfx name="swish" at={ASSEMBLE[0]} volume={0.4} />
      {CUTS.map((_, k) => <React.Fragment key={k}><Sfx name="whoosh" at={CUT_AT(k) - 3} volume={0.3} rate={1.4} /><Sfx name="click" at={CUT_AT(k)} volume={0.55} rate={1 + k * 0.05} /></React.Fragment>)}
      <Sfx name="whoosh" at={PULL[0]} volume={0.35} rate={0.8} />
      <Sfx name="ping" at={ASK_AT + 70} volume={0.35} />
      <Sculpture pose={pose} phase={3} view={view} spin={frame < ASSEMBLE[1] ? 0 : (frame - ASSEMBLE[1]) * 0.0008}
        scale={lerp(1, 0.8, easeOut((frame - PULL[0]) / 30))} x={lerp(0, -6.5, easeOut((frame - PULL[0]) / 30))} y={lerp(-0.6, -0.8, viewK)}
        focus={{u: focusU, zoom: 2.1, mix: push}} />
      <Head n="02" title="一条视频怎么被读懂" sub="解析 → 切分 → 问答" />
      <div style={{position: 'absolute', right: 110, top: 112, display: 'flex', gap: 30, alignItems: 'center', background: 'rgba(245,243,239,0.85)', padding: '4px 12px'}}>
        {steps.map((s, i) => (
          <React.Fragment key={s}>
            {i ? <span style={{fontFamily: SILK, fontWeight: 700, fontSize: 32, color: i <= step ? INK : LINE2}}>{'>>'}</span> : null}
            <span style={{fontFamily: PIXEL, fontSize: 60, color: i <= step ? INK : INK3, ...(i === step ? marker(easeOut((frame - [0, ASSEMBLE[1], ASK_AT][i]) / 12)) : {})}}>
              <span style={{fontFamily: CONSOLE, fontSize: 48, marginRight: 10, color: INK2}}>0{i + 1}</span>{s}
            </span>
          </React.Fragment>
        ))}
      </div>
      {/* 解析: what the read lifts comes off the floor */}
      {frame < ASSEMBLE[0] + 10 ? TAGS.map((t, i) => {
        const at = READ[0] + ((t.u - 0.2) / 0.56) * 60;
        const k = pop(frame, at, fps, 220);
        const f = floorSlat(t.u, time, t.u);
        const p = project({x: f.x, y: f.y + 1.2, z: f.z}, FLOOR_VIEW);
        return frame >= at ? (
          <div key={i} style={{position: 'absolute', left: p.x - 80, top: p.y - 60 - k * 40, width: 160, textAlign: 'center', fontFamily: PIXEL, fontSize: 60, color: INK,
            transform: `scale(${k})`, opacity: 1 - clamp01((frame - ASSEMBLE[0]) / 10)}}>
            <span style={{...marker(), background: 'rgba(245,243,239,0.9)'}}>{t.word}</span>
          </div>
        ) : null;
      }) : null}
      {/* 切分: the blade crossing at each cut (the camera holds the cut at the centre), and the chapter it starts */}
      {CUTS.map((_, k) => {
        const t = frame - CUT_AT(k);
        if (t < -6 || t > 30 || frame > PULL[0]) return null;
        const b = clamp01((t + 6) / 8);
        const label = CHAPTERS[k + 1];
        return (
          <React.Fragment key={k}>
            <svg width={1920} height={1080} style={{position: 'absolute', inset: 0}}>
              <path d={`M${960 + 520 - 1040 * b} ${540 - 380 + 760 * b}L${960 + 520} ${540 - 380}`} stroke={INK} strokeWidth={4} opacity={1 - clamp01((t - 8) / 10)} />
              <path d={`M${960 + 540 - 1080 * b} ${540 - 390 + 780 * b}L${960 + 540} ${540 - 390}`} stroke={LIME} strokeWidth={10} opacity={0.9 * (1 - clamp01((t - 6) / 10))} />
            </svg>
            {t > 2 ? (
              <div style={{position: 'absolute', left: 1040, top: 640, display: 'flex', gap: 18, alignItems: 'baseline', transform: `translateY(${(1 - pop(t, 2, fps, 240)) * 40}px)`,
                opacity: 1 - clamp01((t - 24) / 6), background: 'rgba(245,243,239,0.9)', padding: '4px 14px'}}>
                <span style={{fontFamily: CONSOLE, fontSize: 64, color: INK, ...marker()}}>{label.t}</span>
                <span style={{fontFamily: PIXEL, fontSize: 60, color: INK}}>{label.name}</span>
              </div>
            ) : null}
          </React.Fragment>
        );
      })}
      {/* the whole, cut into chapters, once the camera pulls back */}
      {frame >= PULL[0] ? (
        <div style={{position: 'absolute', right: 120, top: 290, display: 'flex', flexDirection: 'column', gap: 18}}>
          {CHAPTERS.map((c, k) => {
            const on = frame >= PULL[0] + k * 5;
            const hot = answered && k === ANSWER;
            return (
              <div key={k} style={{display: 'flex', gap: 18, alignItems: 'center', opacity: on ? (answered && !hot ? 0.4 : 1) : 0,
                transform: `translateX(${(1 - pop(frame, PULL[0] + k * 5, fps, 240)) * 120}px)`}}>
                <span style={{width: 6, height: 48, background: hot ? INK : LINE2}} />
                <span style={{fontFamily: CONSOLE, fontSize: 52, color: hot ? INK : INK2}}>{c.t}</span>
                <span style={{fontFamily: PIXEL, fontSize: 48, color: INK, ...(hot ? marker(lift) : {})}}>{c.name}</span>
              </div>
            );
          })}
        </div>
      ) : null}
      {/* 问答 */}
      {frame >= ASK_AT ? (
        <AbsoluteFill style={{justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 110}}>
          <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 22, transform: `translateY(${(1 - pop(frame, ASK_AT, fps)) * 200}px)`}}>
            {frame >= ASK_AT + 74 ? (
              <div style={{display: 'flex', gap: 18, alignItems: 'center', fontFamily: PIXEL, fontSize: 60, color: INK, transform: `scale(${pop(frame, ASK_AT + 74, fps, 240)})`}}>
                <span style={{fontFamily: CONSOLE, fontSize: 56, ...marker()}}>03:05</span>
                <span style={{fontFamily: SILK, fontWeight: 700, fontSize: 40, color: INK3}}>◆</span>
                <Typed text="第 3 步：文件 → 导出设置" at={ASK_AT + 80} />
              </div>
            ) : null}
            <div style={{minWidth: 760, height: 92, borderRadius: 46, border: `2px solid ${INK}`, background: SURFACE, display: 'flex', alignItems: 'center', padding: '0 34px',
              fontFamily: PIXEL, fontSize: 48, color: INK, justifyContent: 'space-between', gap: 30}}>
              <Typed text="导出在第几步？" at={ASK_AT + 14} />
              <span style={{fontFamily: SILK, fontWeight: 700, color: INK, background: LIME, borderRadius: 30, width: 60, height: 60, display: 'grid', placeItems: 'center', fontSize: 32}}>{'>'}</span>
            </div>
          </div>
        </AbsoluteFill>
      ) : null}
      <div style={{position: 'absolute', left: 120, bottom: 110, opacity: frame >= ASK_AT ? 0 : 1, background: 'rgba(245,243,239,0.85)', padding: '4px 12px'}}>
        <span style={{fontFamily: PIXEL, fontSize: 60, color: INK}}>
          <span style={{fontFamily: SILK, fontWeight: 700, color: INK3, marginRight: 18}}>//</span>
          {frame < ASSEMBLE[1] ? <Typed key="a" text="读画面、听原声、认文字" at={18} /> : <Typed key="b" text="按步骤切成章节" at={ASSEMBLE[1] + 10} />}
        </span>
      </div>
      <Glyphs count={8} seed={27} opacity={0.5} />
    </Fill>
  );
};
