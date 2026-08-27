/**
 * 餐馆检索: 分字段加权打分 + 信息完整度/热度加成
 */

let IDX = null

export function buildSearchIndex(restaurants) {
  IDX = restaurants.map(r => {
    const commentTexts = r.comments.map(c => c.msg).join('\n')
    return {
      r,
      nameLc: r.name.toLowerCase(),
      areaParts: [r.province, r.city, r.district].filter(Boolean),
      areaLc: r.areaFull.toLowerCase(),
      clueLc: r.locationClues.join('|').toLowerCase(),
      dishTextLc: r.dishes.join('|').toLowerCase(),
      typeLc: (r.type || '').toLowerCase(),
      msgLc: commentTexts.toLowerCase(),
    }
  })
  return IDX
}

function completeness(r) {
  let s = 0.5
  if (r.hasRealName) s += 0.12
  else s += 0.02
  if (r.district) s += 0.12
  if (r.rank >= 4) s += 0.10        // 明确地标附近及以上
  if (r.lat) s += 0.08
  if (r.dishes.length) s += 0.06
  if (r.type) s += 0.04
  return Math.min(s, 1)
}

function heat(r) {
  const like = Math.log10(Math.max(r.totalLikes, 1) + 2)
  const mention = Math.sqrt(Math.min(r.mentionCount, 6))
  const cred = r.credibility === '高' ? 1.15 : (r.credibility === '中' ? 1 : 0.9)
  return like * mention * cred
}

/* 单词命中得分 */
function termScore(t, it) {
  const q = t.toLowerCase()
  if (!q) return { score: 0, where: '' }
  let best = { score: 0, where: '' }
  const tryField = (text, weight, where) => {
    if (!text) return
    const i = text.indexOf(q)
    if (i < 0) return
    // 前缀命中加分
    let w = weight
    if (i === 0) w *= 1.35
    if (where === 'name' && text.length <= q.length + 2) w *= 1.3
    if (w > best.score) best = { score: w, where }
  }
  tryField(it.nameLc, 12, 'name')
  for (const part of it.areaParts) tryField(part.toLowerCase(), 8, 'area')
  tryField(it.areaLc, 6, 'area')
  tryField(it.dishTextLc, 8.5, 'dish')
  tryField(it.typeLc, 6, 'type')
  tryField(it.clueLc, 7, 'clue')
  tryField(it.msgLc, 2.6, 'msg')
  return best
}

/** 主搜索入口: 返回按相关性排序的餐馆数组 */
export function searchRestaurants(index, rawQuery) {
  if (!IDX) buildSearchIndex(index.map(x => x.r))
  const terms = splitTerms(rawQuery)
  if (!terms.length) return []
  const scored = []
  for (const it of index) {
    let total = 0
    let missing = 0
    const hits = []
    for (const t of terms) {
      const res = termScore(t, it)
      if (res.score <= 0) { missing++ } else { total += res.score; hits.push(res.where) }
    }
    if (missing === terms.length) continue           // 一个词都不沾边
    // 有未命中的词则整体降权
    total *= Math.pow(0.45, missing)
    total *= completeness(it.r) * heat(it.r)
    scored.push({ r: it.r, score: total, primaryField: hits[0] || '' })
  }
  scored.sort((a, b) => b.score - a.score ||
    b.r.totalLikes - a.r.totalLikes ||
    b.r.mentionCount - a.r.mentionCount)
  return scored.slice(0, 120).map(x => x.r)
}

export function splitTerms(q) {
  return String(q || '')
    .split(/[\s,，。.;；、!！?？·]+/)
    .map(s => s.trim())
    .filter(s => s.length > 0 && s.length <= 30)
    .slice(0, 8)
}
