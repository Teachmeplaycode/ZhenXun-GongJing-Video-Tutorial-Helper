import { useCallback, useEffect, useMemo, useState } from 'react'
import { getSession } from './client'
import { conversationTurns, withSavedIds } from '../lib/conversationTurns'

// Refresh on completion or an explicit retry, never for streaming tokens. The shared state lives
// in ChatStage, so closing the directory or changing workbench tabs retains the person's choices.
export function useConversationSelection(sessionId, messages) {
  const [saved, setSaved] = useState({ sessionId: null, rows: [] })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [refresh, setRefresh] = useState(0)
  const [selection, setSelection] = useState({ sessionId, keys: new Set(), selecting: false })
  const statusKey = messages.map((m) => `${m.id}:${m.status || 'done'}`).join('|')
  useEffect(() => {
    setSelection({ sessionId, keys: new Set(), selecting: false })
    setError('')
  }, [sessionId])
  useEffect(() => {
    if (!sessionId || !statusKey) { setLoading(false); return undefined }
    const controller = new AbortController()
    setLoading(true)
    setError('')
    getSession(sessionId, { signal: controller.signal }).then((session) => {
      if (!controller.signal.aborted) setSaved({ sessionId, rows: session.messages || [] })
    }).catch((err) => {
      if (err.name !== 'AbortError') setError(err.message || '读取消息失败')
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [sessionId, statusKey, refresh])
  const turns = useMemo(() => conversationTurns(withSavedIds(messages, saved.sessionId === sessionId ? saved.rows : [])), [messages, saved, sessionId])
  const current = selection.sessionId === sessionId ? selection : { sessionId, keys: new Set(), selecting: false }
  const selectedKeys = current.keys
  const chosen = turns.filter((turn) => turn.selectable && selectedKeys.has(turn.key))
  const onToggle = useCallback((key) => {
    if (!turns.some((turn) => turn.key === key && turn.selectable)) return
    setSelection((old) => {
      const keys = new Set(old.sessionId === sessionId ? old.keys : [])
      if (keys.has(key)) keys.delete(key)
      else keys.add(key)
      return { sessionId, keys, selecting: old.sessionId === sessionId ? old.selecting : true }
    })
  }, [sessionId, turns])
  const onSelectAll = useCallback(() => setSelection({ sessionId, keys: new Set(turns.filter((turn) => turn.selectable).map((turn) => turn.key)), selecting: true }), [sessionId, turns])
  const onClear = useCallback(() => setSelection((old) => ({ sessionId, keys: new Set(), selecting: old.sessionId === sessionId && old.selecting })), [sessionId])
  const onSelectingChange = useCallback((selecting) => setSelection((old) => ({ sessionId, keys: old.sessionId === sessionId ? old.keys : new Set(), selecting })), [sessionId])
  const onRefresh = useCallback(() => setRefresh((n) => n + 1), [])
  return { turns, selectedKeys, chosen, messageIds: chosen.flatMap((turn) => turn.ids), selecting: current.selecting,
    onToggle, onSelectAll, onClear, onSelectingChange, loading, error, onRefresh }
}
