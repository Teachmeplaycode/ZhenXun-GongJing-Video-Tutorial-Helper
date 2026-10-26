import React, { useLayoutEffect, useRef, useState } from 'react'
import gsap from 'gsap'
import ThoughtLine from './react-bits/ThoughtLine'
import StepDetail from './StepDetail'
import { IconAlert, IconBook, IconChat, IconChevron, IconClock, IconCompass, IconEye, IconGlobe, IconSparkle, IconStop, IconText, IconWave } from './Icons'
import { describeStep, isVisibleStep, SKILL_NAMES, stepKind } from '../lib/steps'
import { prefersReducedMotion } from '../lib/motion'

const KIND_ICON = { look: IconEye, speech: IconWave, text: IconText, web: IconGlobe, paper: IconBook, audience: IconChat, skill: IconSparkle, wait: IconClock, think: IconCompass }

// One row per step: its kind (an icon), what was done, to what, outcome. A click opens its detail.
function StepRow({ call, onSeek }) {
  const [open, setOpen] = useState(false)
  const bodyRef = useRef(null)
  const first = useRef(true)
  const { verb, target, meta } = describeStep(call)
  const canOpen = call.status !== 'running'

  useLayoutEffect(() => {
    const el = bodyRef.current
    if (!el) return
    if (first.current || prefersReducedMotion()) {
      first.current = false
      gsap.set(el, { height: open ? 'auto' : 0, display: open ? 'block' : 'none' })
      return
    }
    if (open) {
      gsap.set(el, { display: 'block' })
      gsap.fromTo(el, { height: 0, opacity: 0 }, { height: 'auto', opacity: 1, duration: 0.24, ease: 'power2.out' })
    } else {
      gsap.to(el, { height: 0, opacity: 0, duration: 0.18, ease: 'power2.in', onComplete: () => gsap.set(el, { display: 'none' }) })
    }
  }, [open])

  return (
    <div className="step" data-status={call.status}>
      <button type="button" className="step__row" onClick={() => canOpen && setOpen((v) => !v)} aria-expanded={canOpen ? open : undefined}>
        <span className="step__mark" data-kind={stepKind(call)} aria-hidden="true">
          {call.status === 'running' ? <i className="thought-line__pulse" />
            : call.status === 'error' ? <IconAlert size={13} />
              : call.status === 'stopped' ? <IconStop size={13} /> : React.createElement(KIND_ICON[stepKind(call)], { size: 13 })}
        </span>
        <span className="step__verb">{verb}</span>
        {target ? <span className="step__target">{target}</span> : null}
        {meta ? <span className="step__meta mono-sm">{meta}</span> : null}
        {canOpen ? <span className={`step__chevron ${open ? 'is-open' : ''}`}><IconChevron size={11} /></span> : null}
      </button>
      <div ref={bodyRef} className="step__body">{open ? <StepDetail call={call} onSeek={onSeek} /> : null}</div>
    </div>
  )
}

/**
 * Consecutive tool calls as one collapsible line, like Claude's / Codex's activity: while working it
 * shimmers with the current step; when done it settles into "N 步 · 12.3s" and folds away.
 * working: this group is the latest part of a running answer. progress: the run's current step label.
 */
export default function StepGroup({ part, working, progress, onSeek }) {
  const calls = part.calls.filter((c) => isVisibleStep(c) && stepKind(c) !== 'skill') // skills have their own block (SkillBlock)
  const current = [...calls].reverse().find((c) => c.status === 'running')
  const failed = calls.filter((c) => c.status === 'error').length
  const live = current ? `${describeStep(current).verb}${describeStep(current).target ? ` ${describeStep(current).target}` : ''}…` : `${progress || '思考中'}…`
  const elapsed = part.from != null && part.to != null ? Math.max(0, part.to - part.from) : undefined
  const glyph = <span className={`step-glyph ${working ? 'is-working' : ''}`} />
  return (
    <ThoughtLine
      className="step-group"
      working={working}
      label={live}
      doneLabel={`${calls.length ? `执行了 ${calls.length} 步` : '思考'}${failed ? ` · ${failed} 步失败` : ''}`}
      glyph={glyph}
      steps={calls.map((c) => <StepRow key={c.id} call={c} onSeek={onSeek} />)}
      elapsed={working ? undefined : elapsed}
      showTimer={working || elapsed != null}
      fontSize={14}
      color="var(--text-secondary)"
      defaultOpen={working}
    />
  )
}

/** A skill the answer ran (科普核查, 反诈识别…) as its own block, not a row in the fold: you see that a skill
 *  ran, what it is doing while it runs, and its outcome; the full report follows the answer (SkillReports). */
export function SkillBlock({ call, progress }) {
  const { target, meta } = describeStep(call)
  const running = call.status === 'running'
  return (
    <div className="skill-block" data-status={call.status}>
      <span className="skill-block__icon" aria-hidden="true"><IconSparkle size={16} /></span>
      <span className="skill-block__body">
        <span className="skill-block__head">
          <span className="skill-block__tag mono-sm">技能</span>
          <strong>{SKILL_NAMES[call.tool] || call.tool}</strong>
          <span className="skill-block__target">{target}</span>
        </span>
        <span className="skill-block__status mono-sm">
          {running ? <><i className="thought-line__pulse" />{progress || '运行中'}…</> : call.status === 'error' ? '没有完成' : meta}
        </span>
      </span>
    </div>
  )
}
