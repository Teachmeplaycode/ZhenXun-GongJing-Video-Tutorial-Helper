import React, {useCallback} from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {clamp01, CONSOLE, easeOut, Fill, Glyphs, Head, INK, INK2, INK3, LIME, LINE2, PIXEL, pop, Sfx, SILK, SURFACE, Typed} from './kit';
import {Sculpture, SlatPose} from './Sculpture';

// 02 解析 → 切分 → 问答, played by the homepage's sculpture in its own colour (never tinted):
//   解析  the video lies as a strip of slats (its timeline); a scan runs along it, lifting the slat
//         it reads, and 画面 / 原声 / 文字 come off it; then the slats fly up, in order, into the
//         figure-eight
//   切分  the ribbon is cut into chapters — gaps open at the boundaries — and the chapter list
//         (with times) fills in beside it
//   问答  a question is typed; the slats of the chapter that answers it come forward out of the
//         ribbon, and the answer arrives with its time and evidence

const PARSE_END = 170;
const SPLIT_AT = 170;
const ASK_AT = 330;
const CUTS = [0, 0.18, 0.38, 0.6, 0.8];
const CHAPTERS = [
  {t: '00:00', name: '打开软件'},
  {t: '01:12', name: '新建项目'},
  {t: '03:05', name: '导出设置'},
  {t: '04:47', name: '调整画质'},
  {t: '06:30', name: '保存文件'},
];
const ANSWER = 2;
const TAGS = [{u: 0.22, word: '画面'}, {u: 0.5, word: '原声'}, {u: 0.78, word: '文字'}];
const chapterOf = (u: number) => CUTS.reduce((k, c, i) => (u >= c ? i : k), 0);
const marker = (k = 1): React.CSSProperties => ({backgroundImage: `linear-gradient(${LIME}, ${LIME})`, backgroundRepeat: 'no-repeat',
  backgroundSize: `${clamp01(k) * 100}% 38%`, backgroundPosition: '0 88%'});

export const Pipeline: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const scan = clamp01((frame - 16) / 90);
  const step = frame < SPLIT_AT ? 0 : frame < ASK_AT ? 1 : 2;
  const cutAt = (k: number) => SPLIT_AT + 16 + k * 16;
  const answered = frame >= ASK_AT + 70;
  const lift = easeOut((frame - ASK_AT - 70) / 30);
  const pose = useCallback((_i: number, u: number): SlatPose => {
    if (frame < PARSE_END) {
      const strip = 1 - easeOut((frame - 112 - u * 40) / 34);
      const near = 1 - Math.min(1, Math.abs(u - scan) / 0.025);
      return {strip, lift: scan < 1 ? near * 2.2 : 0};
    }
    const k = chapterOf(u);
    const cut = CUTS.some((c, j) => frame >= cutAt(j) && Math.min(Math.abs(u - c), Math.abs(u - c - 1)) < 0.012);
    return {size: cut ? 0 : 1, lift: answered && k === ANSWER ? lift * (5 + 2 * Math.sin(u * 40 + frame / 20)) : 0};
  }, [frame, scan, lift, answered]);
  const steps = ['解析', '切分', '问答'];
  return (
    <Fill>
      <Sfx name="glitch" at={16} volume={0.2} />
      {TAGS.map((t, i) => <Sfx key={i} name="pop" at={16 + t.u * 90} volume={0.35} />)}
      <Sfx name="whoosh" at={110} volume={0.45} />
      {CUTS.map((_, k) => <Sfx key={k} name="click" at={cutAt(k)} volume={0.5} rate={1 + k * 0.05} />)}
      <Sfx name="ping" at={ASK_AT + 70} volume={0.35} />
      <Sculpture pose={pose} phase={3} spin={frame < PARSE_END ? 0 : (frame - PARSE_END) * 0.0016}
        scale={0.86 - 0.12 * easeOut((frame - PARSE_END) / 40)} y={-0.8} x={frame < PARSE_END ? 0 : -6.5 * easeOut((frame - PARSE_END) / 40)} />
      <Head n="02" title="一条视频怎么被读懂" sub="解析 → 切分 → 问答" />
      {/* the three steps, the current one marked */}
      <div style={{position: 'absolute', right: 110, top: 112, display: 'flex', gap: 30, alignItems: 'center'}}>
        {steps.map((s, i) => (
          <React.Fragment key={s}>
            {i ? <span style={{fontFamily: SILK, fontWeight: 700, fontSize: 32, color: i <= step ? INK : LINE2}}>{'>>'}</span> : null}
            <span style={{fontFamily: PIXEL, fontSize: 60, color: i <= step ? INK : INK3, ...(i === step ? marker(easeOut((frame - [0, SPLIT_AT, ASK_AT][i]) / 12)) : {})}}>
              <span style={{fontFamily: CONSOLE, fontSize: 48, marginRight: 10, color: INK2}}>0{i + 1}</span>{s}
            </span>
          </React.Fragment>
        ))}
      </div>
      {/* 解析: what the scan reads comes off the strip */}
      {frame < PARSE_END + 10 ? TAGS.map((t, i) => {
        const at = 16 + t.u * 90;
        const k = pop(frame, at, fps, 220);
        const gone = 1 - clamp01((frame - 120) / 20);
        return frame >= at ? (
          <div key={i} style={{position: 'absolute', left: 960 + (t.u - 0.5) * 1640 - 100, top: 400 - k * 50, width: 200, textAlign: 'center', opacity: gone,
            fontFamily: PIXEL, fontSize: 60, color: INK, transform: `scale(${k})`}}>
            <span style={marker()}>{t.word}</span>
            <div style={{width: 2, height: 60 * k, background: INK, margin: '8px auto 0'}} />
          </div>
        ) : null;
      }) : null}
      {frame < PARSE_END ? (
        <div style={{position: 'absolute', left: 120, top: 760, fontFamily: CONSOLE, fontSize: 52, color: INK, opacity: 1 - clamp01((frame - 110) / 20)}}>
          ▶ 06:30 <span style={{color: INK2}}>{String(Math.round(scan * 390)).padStart(3, '0')}s</span>
        </div>
      ) : null}
      {/* 切分: the chapter list */}
      {frame >= SPLIT_AT ? (
        <div style={{position: 'absolute', right: 120, top: 290, display: 'flex', flexDirection: 'column', gap: 18}}>
          {CHAPTERS.map((c, k) => {
            const on = frame >= cutAt(k);
            const hot = answered && k === ANSWER;
            return (
              <div key={k} style={{display: 'flex', gap: 18, alignItems: 'center', opacity: on ? (answered && !hot ? 0.4 : 1) : 0,
                transform: `translateX(${(1 - pop(frame, cutAt(k), fps, 240)) * 120}px)`}}>
                <span style={{width: 6, height: 48, background: hot ? INK : LINE2}} />
                <span style={{fontFamily: CONSOLE, fontSize: 52, color: hot ? INK : INK2}}>{c.t}</span>
                <span style={{fontFamily: PIXEL, fontSize: 48, color: INK, ...(hot ? marker(lift) : {})}}>{c.name}</span>
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
      <div style={{position: 'absolute', left: 120, bottom: 110, opacity: frame >= ASK_AT ? 0 : 1}}>
        <span style={{fontFamily: PIXEL, fontSize: 60, color: INK}}>
          <span style={{fontFamily: SILK, fontWeight: 700, color: INK3, marginRight: 18}}>//</span>
          {frame < SPLIT_AT ? <Typed key="a" text="读画面、听原声、认文字" at={20} /> : <Typed key="b" text="按步骤切成章节" at={SPLIT_AT + 8} />}
        </span>
      </div>
      <Glyphs count={8} seed={27} opacity={0.5} />
    </Fill>
  );
};
