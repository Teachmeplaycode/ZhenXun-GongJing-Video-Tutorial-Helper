import React, {useCallback} from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {BG, BLUE, clamp01, CONSOLE, easeOut, Fill, Glyphs, LIME, PIXEL, pop, SC, Sfx, SILK, Typed, WHITE} from './kit';
import {Sculpture, SlatPose} from './Sculpture';

// 解析 → 切分 → 问答, played by the homepage's sculpture:
//   解析  the video lies as a strip of slats (its timeline); a scan runs along it reading 画面 /
//         原声 / 文字, then the slats fly up, in order, into the figure-eight
//   切分  the ribbon is cut into chapters: gaps open at the boundaries, each chapter takes a colour,
//         and the chapter list (with times) fills in beside it
//   问答  a question is typed; the slats of the chapter that answers it come forward, the rest dim,
//         and the answer arrives with its time and evidence

const PARSE_END = 170;
const SPLIT_AT = 170;
const ASK_AT = 330;
const CUTS = [0, 0.18, 0.38, 0.6, 0.8]; // chapter starts along the ribbon
const CHAPTER_COLORS = [LIME, WHITE, BLUE, '#8E9878', WHITE];
const CHAPTERS = [
  {t: '00:00', name: '打开软件'},
  {t: '01:12', name: '新建项目'},
  {t: '03:05', name: '导出设置'},
  {t: '04:47', name: '调整画质'},
  {t: '06:30', name: '保存文件'},
];
const ANSWER = 2;
const TAGS = [{u: 0.22, word: '画面', color: BLUE}, {u: 0.5, word: '原声', color: LIME}, {u: 0.78, word: '文字', color: WHITE}];
const chapterOf = (u: number) => CUTS.reduce((k, c, i) => (u >= c ? i : k), 0);

export const Pipeline: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const scan = clamp01((frame - 16) / 90);
  const step = frame < SPLIT_AT ? 0 : frame < ASK_AT ? 1 : 2;
  const cutAt = (k: number) => SPLIT_AT + 16 + k * 16; // the k-th boundary opens
  const lift = easeOut((frame - ASK_AT - 70) / 30);
  const pose = useCallback((i: number, u: number): SlatPose => {
    if (frame < PARSE_END) {
      const strip = 1 - easeOut((frame - 112 - u * 40) / 34);
      const head = Math.abs(u - scan) < 0.02 && scan < 1;
      return {strip, color: head ? LIME : u < scan ? WHITE : '#6E7560', lift: head ? 1.5 : 0};
    }
    const k = chapterOf(u);
    const coloured = frame >= cutAt(k);
    // a gap at every boundary once it has been cut
    const edge = Math.min(...CUTS.map((c) => Math.min(Math.abs(u - c), Math.abs(u - c - 1), Math.abs(u - c + 1))));
    const cut = CUTS.some((c, j) => frame >= cutAt(j) && Math.min(Math.abs(u - c), Math.abs(u - c - 1)) < 0.011);
    const size = cut ? 0 : 1;
    let color = coloured ? CHAPTER_COLORS[k] : WHITE;
    let out = 0;
    if (frame >= ASK_AT + 70) {
      if (k === ANSWER) out = lift * (6 + 3 * Math.sin(u * 40 + frame / 20));
      else color = '#2C3124';
    }
    return {color, size: edge < 0.03 && cut ? 0 : size, lift: out};
  }, [frame, scan, lift]);
  const steps = ['解析', '切分', '问答'];
  const chips = frame >= SPLIT_AT;
  return (
    <Fill>
      <Sfx name="glitch" at={16} volume={0.25} />
      {TAGS.map((t, i) => <Sfx key={i} name="pop" at={16 + t.u * 90} volume={0.35} />)}
      <Sfx name="whoosh" at={110} volume={0.45} />
      {CUTS.map((_, k) => <Sfx key={k} name="click" at={cutAt(k)} volume={0.5} rate={1 + k * 0.05} />)}
      <Sfx name="ping" at={ASK_AT + 70} volume={0.35} />
      <Sculpture pose={pose} phase={3} spin={frame < PARSE_END ? 0 : (frame - PARSE_END) * 0.0016}
        scale={0.86 - 0.12 * easeOut((frame - PARSE_END) / 40)} y={-0.8} x={frame < PARSE_END ? 0 : -6.5 * easeOut((frame - PARSE_END) / 40)} />
      {/* the three steps, the current one lit */}
      <div style={{position: 'absolute', top: 64, left: 0, right: 0, display: 'flex', justifyContent: 'center'}}>
        <div style={{display: 'flex', gap: 22, alignItems: 'center', background: BG, padding: '6px 22px'}}>
        {steps.map((s, i) => (
          <React.Fragment key={s}>
            {i ? <span style={{fontFamily: SILK, fontWeight: 700, fontSize: 36, color: i <= step ? LIME : '#3A3F2C'}}>{'>>'}</span> : null}
            <span style={{fontFamily: PIXEL, fontSize: 60, padding: '2px 18px', color: i === step ? BG : i < step ? WHITE : '#4A5040',
              background: i === step ? LIME : 'transparent', transform: `scale(${i === step ? 1 + (1 - pop(frame, [0, SPLIT_AT, ASK_AT][i], fps, 260)) * 0.3 : 1})`}}>
              <span style={{fontFamily: CONSOLE, marginRight: 12}}>0{i + 1}</span>{s}
            </span>
          </React.Fragment>
        ))}
        </div>
      </div>
      {/* 解析: tags rise off the strip where the scan reads them */}
      {frame < PARSE_END + 10 ? TAGS.map((t, i) => {
        const at = 16 + t.u * 90;
        const k = pop(frame, at, fps, 220);
        const gone = 1 - clamp01((frame - 120) / 20);
        return frame >= at ? (
          <div key={i} style={{position: 'absolute', left: 960 + (t.u - 0.5) * 1640 - 80, top: 400 - k * 40, width: 160, textAlign: 'center', opacity: gone,
            fontFamily: PIXEL, fontSize: 60, color: t.color === WHITE ? BG : t.color === LIME ? BG : WHITE, background: t.color, transform: `scale(${k})`}}>{t.word}</div>
        ) : null;
      }) : null}
      {frame < PARSE_END ? (
        <div style={{position: 'absolute', left: 120, top: 760, fontFamily: CONSOLE, fontSize: 52, color: WHITE, opacity: 1 - clamp01((frame - 110) / 20)}}>
          ▶ 06:30 <span style={{color: LIME}}>{String(Math.round(scan * 390)).padStart(3, '0')}s</span>
        </div>
      ) : null}
      {/* 切分: the chapter list */}
      {chips ? (
        <div style={{position: 'absolute', right: 120, top: 250, display: 'flex', flexDirection: 'column', gap: 18}}>
          {CHAPTERS.map((c, k) => {
            const on = frame >= cutAt(k);
            const hot = frame >= ASK_AT + 70 && k === ANSWER;
            const dim = frame >= ASK_AT + 70 && k !== ANSWER;
            return (
              <div key={k} style={{display: 'flex', gap: 18, alignItems: 'center', opacity: on ? (dim ? 0.35 : 1) : 0,
                transform: `translateX(${(1 - pop(frame, cutAt(k), fps, 240)) * 120}px) scale(${hot ? 1.08 : 1})`, transformOrigin: '100% 50%'}}>
                <span style={{width: 18, height: 52, background: CHAPTER_COLORS[k]}} />
                <span style={{fontFamily: CONSOLE, fontSize: 52, color: hot ? LIME : WHITE}}>{c.t}</span>
                <span style={{fontFamily: PIXEL, fontSize: 48, color: hot ? BG : WHITE, background: hot ? LIME : 'transparent', padding: '0 10px'}}>{c.name}</span>
              </div>
            );
          })}
        </div>
      ) : null}
      {/* 问答: the question, then the answer */}
      {frame >= ASK_AT ? (
        <AbsoluteFill style={{justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 110}}>
          <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 22, transform: `translateY(${(1 - pop(frame, ASK_AT, fps)) * 200}px)`}}>
            {frame >= ASK_AT + 74 ? (
              <div style={{display: 'flex', gap: 16, alignItems: 'center', fontFamily: PIXEL, fontSize: 60, color: WHITE, background: BG, padding: '6px 20px',
                transform: `scale(${pop(frame, ASK_AT + 74, fps, 240)})`}}>
                <span style={{fontFamily: CONSOLE, fontSize: 56, background: LIME, color: BG, padding: '0 12px'}}>03:05</span>
                <span style={{fontFamily: SC, fontWeight: 900, color: BLUE, fontSize: 52}}>◆</span>
                <Typed text="第 3 步：文件 → 导出设置" at={ASK_AT + 80} />
              </div>
            ) : null}
            <div style={{minWidth: 760, height: 92, borderRadius: 46, border: `3px solid ${LIME}`, background: '#14170F', display: 'flex', alignItems: 'center', padding: '0 34px',
              fontFamily: PIXEL, fontSize: 48, color: WHITE, justifyContent: 'space-between', gap: 30}}>
              <Typed text="导出在第几步？" at={ASK_AT + 14} />
              <span style={{fontFamily: SILK, fontWeight: 700, color: LIME}}>{'>'}</span>
            </div>
          </div>
        </AbsoluteFill>
      ) : null}
      <div style={{position: 'absolute', left: 120, bottom: 110, opacity: frame >= ASK_AT ? 0 : 1}}>
        <span style={{fontFamily: PIXEL, fontSize: 60, color: WHITE, background: BG, padding: '4px 16px'}}>
          <span style={{fontFamily: SILK, fontWeight: 700, color: LIME, marginRight: 18}}>//</span>
          {frame < SPLIT_AT ? <Typed key="a" text="读画面、听原声、认文字" at={20} /> : <Typed key="b" text="按步骤切成章节" at={SPLIT_AT + 8} />}
        </span>
      </div>
      <Glyphs count={8} seed={27} opacity={0.6} />
    </Fill>
  );
};
