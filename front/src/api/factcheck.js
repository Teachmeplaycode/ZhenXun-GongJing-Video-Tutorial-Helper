/** 核查报告 API 客户端。 */

import { apiUrl, readEventStream } from './client'

/**
 * 启动核查并流式返回事件。事件类型见 modules/factcheck/run.py：
 *   factcheck.started / claims_extracted / claim.verifying / claim.done / completed / error
 * 返回 Promise<{report}>（completed 后 resolve 报告）+ onEvent 回调。
 */
export async function streamFactCheck(jobId, { web = true, papers = true, onEvent, signal } = {}) {
  let response
  try {
    response = await fetch(apiUrl(`/api/link-jobs/${jobId}/factcheck`), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({ web, papers }),
      signal,
    })
  } catch (err) {
    if (err.name === 'AbortError') throw err
    throw new Error('无法连接核查服务，请确认后端已启动')
  }
  if (!response.ok || !response.body) throw new Error(`核查请求失败（HTTP ${response.status}）`)

  let report = null
  let failure = null
  await readEventStream(response, (ev) => {
    if (ev.type === 'factcheck.completed') report = ev.report
    if (ev.type === 'factcheck.error') failure = new Error(ev.message || '核查失败')
    onEvent?.(ev)
  })
  if (failure) throw failure
  if (!report) throw new Error('核查连接已结束，未收到完整报告，请重试')
  return report
}

/**
 * 取会话里最近一次保存的核查报告（如有）。
 */
export async function getFactCheck(jobId, { signal } = {}) {
  const response = await fetch(apiUrl(`/api/link-jobs/${jobId}/factcheck`), { signal })
  if (!response.ok) {
    if (response.status === 404) return null
    throw new Error(`获取报告失败（HTTP ${response.status}）`)
  }
  return response.json()
}
