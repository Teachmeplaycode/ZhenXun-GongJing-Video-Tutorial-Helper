// Several links pasted at once (one per line, a space between, or run together: a text box drops the
// line breaks): each distinct one, in order. A share text's words around a link are left out.
const URL = /https?:\/\/[^\s【】「」（）()，,"'<>]+?(?=https?:\/\/|[\s【】「」（）()，,"'<>]|$)/gi
const BV = /\bBV[0-9A-Za-z]{10}\b/g

export function extractLinks(text) {
  const found = [...(text || '').matchAll(URL)].map((m) => m[0].replace(/[。.;；]+$/, ''))
  const bare = (text || '').replace(URL, ' ').match(BV) || [] // a BV id given alone
  return [...new Set([...found, ...bare.map((id) => `https://www.bilibili.com/video/${id}`)])]
}
