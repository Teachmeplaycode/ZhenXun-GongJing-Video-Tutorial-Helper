import React from 'react'
import FactCheckReport from './FactCheckReport'
import AntifraudPanel from './AntifraudPanel'

const RISK = { high: '高', medium: '中', low: '低' }

// The reports of the skills an answer ran (backend modules/agent/skills.py), as cards under its
// text: the outcome in the title line, the full report a click away.
export function skillReports(message) {
  const out = []
  for (const part of message.parts || []) {
    if (part.kind !== 'steps') continue
    for (const c of part.calls) {
      if ((c.tool === 'skill.factcheck' || c.tool === 'skill.antifraud') && c.data?.report) out.push({ id: c.id, tool: c.tool, report: c.data.report })
    }
  }
  return out
}

export default function SkillReports({ reports, onSeek }) {
  if (!reports.length) return null
  return (
    <div className="skill-reports">
      {reports.map(({ id, tool, report }) => {
        const science = tool === 'skill.factcheck'
        const s = report.summary || {}
        const outcome = science
          ? `${s.total ?? (report.claims || []).length} 条说法 · 错误 ${s.wrong ?? 0} · 部分正确 ${s.partial ?? 0}`
          : `风险${RISK[report.assessment?.risk || report.score?.level] || '未知'}`
        return (
          <details key={id} className="skill-report" data-skill={science ? 'factcheck' : 'antifraud'}>
            <summary>
              <span className="skill-report__name">{science ? '科普核查报告' : '反诈识别报告'}</span>
              <span className="skill-report__outcome">{outcome}</span>
              <span className="skill-report__open">查看完整报告</span>
            </summary>
            <div className="skill-report__body">
              {science
                ? <FactCheckReport embedded readOnly report={report} video={report.video} onSeek={onSeek} />
                : <AntifraudPanel report={report} videoTitle={report.video?.title} />}
            </div>
          </details>
        )
      })}
    </div>
  )
}
