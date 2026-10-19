// Platform names for display: the ids the backend reports (video.platform) and the hosts of pasted links.
export const PLATFORM_NAMES = {
  local: '上传', bilibili: 'B 站', wechat_channels: '视频号', redbook: '小红书', xiaohongshu: '小红书', douyin: '抖音',
  kuaishou: '快手', weibo: '微博', twitter: 'X', x: 'X', youtube: 'YouTube', tiktok: 'TikTok', instagram: 'Instagram',
  threads: 'Threads', facebook: 'Facebook', ixigua: '西瓜视频', acfun: 'AcFun', zhihu: '知乎', vimeo: 'Vimeo',
}

const HOSTS = [
  [/(^|\.)(bilibili\.com|b23\.tv)$/, 'bilibili'], [/(^|\.)channels\.weixin\.qq\.com$|(^|\.)weixin\.qq\.com$/, 'wechat_channels'],
  [/(^|\.)(xiaohongshu\.com|xhslink\.com)$/, 'redbook'], [/(^|\.)(douyin\.com|iesdouyin\.com)$/, 'douyin'],
  [/(^|\.)(kuaishou\.com|chenzhongtech\.com)$/, 'kuaishou'], [/(^|\.)(weibo\.com|weibo\.cn)$/, 'weibo'],
  [/(^|\.)(x\.com|twitter\.com)$/, 'x'], [/(^|\.)(youtube\.com|youtu\.be)$/, 'youtube'], [/(^|\.)tiktok\.com$/, 'tiktok'],
  [/(^|\.)instagram\.com$/, 'instagram'], [/(^|\.)ixigua\.com$/, 'ixigua'], [/(^|\.)acfun\.cn$/, 'acfun'],
  [/(^|\.)zhihu\.com$/, 'zhihu'], [/(^|\.)vimeo\.com$/, 'vimeo'], [/(^|\.)threads\.(net|com)$/, 'threads'],
]

export const platformName = (id) => PLATFORM_NAMES[id] || id || ''

// The platform of the first link in pasted text (share text often wraps the link in a sentence).
export function linkPlatform(text) {
  const m = (text || '').match(/https?:\/\/[^\s，。"'<>]+/i)
  if (!m) return null
  let host = ''
  try {
    host = new URL(m[0]).hostname.toLowerCase()
  } catch {
    return null
  }
  const hit = HOSTS.find(([re]) => re.test(host))
  return hit ? { id: hit[1], name: PLATFORM_NAMES[hit[1]] } : { id: '', name: host.replace(/^www\./, '') }
}
