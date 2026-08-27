import { defineStore } from 'pinia'
import { buildSearchIndex, searchRestaurants } from '../lib/search'
import { computeNearby } from '../lib/nearby'

const DATA_BASE = import.meta.env.BASE_URL || '/'

function loadJSON(url) {
  return fetch(url).then(r => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.json()
  })
}

// 位置精度等级
export const PRECI_RANK = {
  精确门牌: 6, 道路或路口: 5, 明确地标附近: 4, 区县级位置: 3, 城市级位置: 2, 暂时无法确认: 1,
}
const PRECI_LABEL = {
  精确门牌: 'prec-high', 道路或路口: 'prec-high', 明确地标附近: 'prec-mid',
  区县级位置: 'prec-mid', 城市级位置: 'prec-low', 暂时无法确认: 'prec-low',
}
export function precClass(p) { return PRECI_LABEL[p] || 'prec-low' }

/* ---------- hash 路由 (分享深链) ---------- */
function encodeHash(st) {
  const p = new URLSearchParams()
  if (st.view === 'search') { p.set('v', 's'); if (st.query) p.set('q', st.query) }
  else if (st.view === 'hot') p.set('v', 'hot')
  else if (st.view === 'random') p.set('v', 'random')
  else if (st.view === 'nearby') p.set('v', 'nearby')
  else {
    if (st.selectedProvince) p.set('p', st.selectedProvince)
    if (st.selectedCity) p.set('c', st.selectedCity)
    if (st.detailId) p.set('r', st.detailId)
  }
  if (st.view !== 'browse' && st.detailId) p.set('r', st.detailId)
  const qs = p.toString()
  return qs ? `#/?${qs}` : '#/'
}
function decodeHash() {
  const h = location.hash
  const out = {}
  if (!h.startsWith('#/')) return out
  const qIndex = h.indexOf('?')
  if (qIndex < 0) return out
  const p = new URLSearchParams(h.slice(qIndex + 1))
  if (p.get('r')) out.detailId = p.get('r')
  const v = p.get('v')
  if (v === 's') { out.view = 'search'; out.query = p.get('q') || '' }
  else if (v === 'hot') out.view = 'hot'
  else if (v === 'random') out.view = 'random'
  else if (v === 'nearby') out.view = 'nearby'
  else {
    out.view = 'browse'
    if (p.get('p')) out.selectedProvince = p.get('p')
    if (p.get('c')) out.selectedCity = p.get('c')
  }
  return out
}

export const useAppStore = defineStore('app', {
  state: () => ({
    status: 'loading',        // loading | error | ready
    errMsg: '',
    restaurants: [],
    searchIndex: [],
    meta: null,
    theme: localStorage.getItem('lfm-theme') || 'auto',

    view: 'browse',           // browse | search | hot | random | nearby
    query: '',
    searchedQuery: '',
    selectedProvince: '',
    selectedCity: '',
    detailId: '',

    filterOpen: false,
    filters: {
      province: '', city: '',
      dishes: [], types: [], precisions: [],
      minLikes: 0, minMentions: 1,
      onlyNamed: false, reliableOnly: false, excludeClosed: true,
    },

    nearby: { status: 'idle', origin: null, results: [], note: '' },
    mapInfo: null,
    mapHovering: false,
    toastMsg: '',
  }),

  getters: {
    overview(state) {
      return state.meta?.overview || null
    },
    provinceList(state) {
      const list = (state.meta?.provinces || []).filter(p => p.name !== '未识别省份')
      // 地图数据里出现的省份也要有零计数项
      if (state.geoNames) {
        for (const gn of state.geoNames) {
          if (!list.some(x => x.name === gn)) list.push({ name: gn, count: 0, cities: [], top: [] })
        }
      }
      return list
    },
    unknownProvinceCount(state) {
      const u = (state.meta?.provinces || []).find(p => p.name === '未识别省份')
      return u ? u.count : 0
    },
    restaurantById(state) {
      const m = {}
      for (const r of state.restaurants) m[r.id] = r
      return m
    },
    detailRestaurant(state) {
      return state.detailId ? this.restaurantById[state.detailId] : null
    },

    /* 组合检索+筛选后的主列表 */
    resultList(state) {
      let list
      if (state.view === 'search' && state.searchedQuery.trim()) {
        list = searchRestaurants(state.searchIndex, state.searchedQuery)
      } else {
        list = state.restaurants.slice()
      }
      return applyFilters(list, state.filters)
    },
    hotByLikes(state) {
      const l = applyFilters(state.restaurants.filter(r => !r.suspectedClosed), state.filters)
      return [...l].sort((a, b) => b.totalLikes - a.totalLikes)
    },
    hotByMentions(state) {
      const l = applyFilters(state.restaurants.filter(r => !r.suspectedClosed), state.filters)
      return [...l].sort((a, b) => b.mentionCount - a.mentionCount || b.totalLikes - a.totalLikes)
    },
    dishOptions(state) { return state.meta?.topDishes || [] },
    typeOptions(state) { return state.meta?.types || [] },
  },

  actions: {
    async init() {
      window.addEventListener('hashchange', () => this.applyHash())
      this.initTheme()
      try {
        const [rest, meta] = await Promise.all([
          loadJSON(`${DATA_BASE}data/restaurants.json`),
          loadJSON(`${DATA_BASE}data/meta.json`),
        ])
        this.restaurants = rest.restaurants.map(normalizeRestaurant)
        this.meta = meta
        this.searchIndex = buildSearchIndex(this.restaurants)
        this.status = 'ready'
        this.applyHash()
      } catch (e) {
        this.errMsg = String(e && e.message || e)
        this.status = 'error'
      }
    },
    retry() { this.status = 'loading'; this.init() },

    applyHash() {
      const h = decodeHash()
      if (!h.detailId && !h.view && !h.selectedProvince && location.hash && location.hash.length > 2) {
        // 空哈希导航则忽略
      }
      if (h.view) this.view = h.view
      if (h.query !== undefined) { this.query = h.query; this.searchedQuery = h.query }
      if (h.selectedProvince) this.selectProvince(h.selectedProvince, false)
      if (h.selectedCity) this.selectCity(h.selectedCity, false)
      if (h.detailId && this.restaurantById[h.detailId]) this.openDetail(h.detailId, false)
    },

    syncHash() {
      const next = encodeHash(this.$state)
      if (next !== location.hash) history.replaceState(null, '', next)
    },

    setView(v) {
      this.view = v
      this.detailId = ''
      if (v !== 'browse') { this.syncHash() }
    },

    doSearch(q) {
      this.query = q
      this.searchedQuery = q
      this.setView('search')
      this.syncHash()
      requestAnimationFrame(() => document.getElementById('results-anchor')?.scrollIntoView({ behavior: 'smooth' }))
    },

    selectProvince(name, sync = true) {
      this.selectedProvince = name
      this.selectedCity = ''
      if (sync) this.syncHash()
    },
    selectCity(name, sync = true) {
      this.selectedCity = name
      if (sync) this.syncHash()
      requestAnimationFrame(() => document.getElementById('city-anchor')?.scrollIntoView({ behavior: 'smooth' }))
    },
    openDetail(id, sync = true) {
      this.detailId = id
      if (sync) this.syncHash()
    },
    closeDetail() {
      this.detailId = ''
      this.syncHash()
    },
    setMapInfo(info) { this.mapInfo = info },

    /* ---- 筛选 ---- */
    openFilters() { this.filterOpen = true },
    closeFilters() { this.filterOpen = false },
    resetFilters() {
      this.filters = {
        province: '', city: '', dishes: [], types: [], precisions: [],
        minLikes: 0, minMentions: 1, onlyNamed: false, reliableOnly: false,
        excludeClosed: this.filters.excludeClosed,
      }
      this.showToast('筛选已重置')
    },

    /* ---- 附近推荐 ---- */
    async locateMe() {
      this.setView('nearby')
      this.nearby.status = 'locating'
      this.nearby.note = ''
      if (!navigator.geolocation) {
        this.nearby.status = 'failed'
        this.nearby.note = '当前浏览器不支持定位，请使用下方手动选择地区。'
        return
      }
      navigator.geolocation.getCurrentPosition(pos => {
        this.nearby.origin = { lat: pos.coords.latitude, lng: pos.coords.longitude }
        this.nearby.results = computeNearby(this.restaurants, this.nearby.origin)
        this.nearby.status = 'ok'
      }, err => {
        this.nearby.status = err.code === err.PERMISSION_DENIED ? 'denied' : 'failed'
        this.nearby.note = err.code === err.PERMISSION_DENIED
          ? '未获得定位授权。可以选择省市区手动获取附近推荐 👇'
          : '定位失败（超时或信号不佳）。可以选择省市区手动获取附近推荐 👇'
      }, { enableHighAccuracy: true, timeout: 9000, maximumAge: 60000 })
    },
    manualOrigin(province, city, district) {
      const pt = resolveCentroid(this.meta?.regions || [], province, city, district)
      if (!pt) return false
      this.setView('nearby')
      this.nearby.origin = pt
      this.nearby.results = computeNearby(this.restaurants, pt)
      this.nearby.status = 'ok'
      this.nearby.note = `以「${[district, city, province].filter(Boolean).join(' ')}」中心点作为参考位置`
      return true
    },

    /* ---- 主题 ---- */
    initTheme() { this.applyTheme(this.theme) },
    setTheme(t) {
      this.theme = t
      localStorage.setItem('lfm-theme', t)
      this.applyTheme(t)
    },
    applyTheme(t) {
      const dark = t === 'dark' || (t === 'auto' && matchMedia('(prefers-color-scheme: dark)').matches)
      document.documentElement.dataset.theme = dark ? 'dark' : 'light'
    },

    showToast(msg) {
      this.toastMsg = msg
      clearTimeout(this._tt)
      this._tt = setTimeout(() => { this.toastMsg = '' }, 2200)
    },
    async shareCurrent(label) {
      try {
        await navigator.clipboard.writeText(location.href)
        this.showToast(`已复制${label || '页面'}链接 🔗`)
      } catch {
        this.showToast('复制失败，请手动复制地址栏链接')
      }
    },
    async shareRestaurant(id) {
      this.openDetail(id)
      const url = `${location.origin}${location.pathname}#/?r=${id}`
      try {
        await navigator.clipboard.writeText(url)
        this.showToast('已复制餐馆分享链接 🔗')
      } catch {
        this.showToast('复制失败，请手动复制地址栏链接')
      }
    },
  },
})

/* ---------- helpers ---------- */

function normalizeRestaurant(raw) {
  raw.rank = PRECI_RANK[raw.precision] || 1
  return raw
}

function applyFilters(list, f) {
  const reliableRank = 4 // 明确地标附近及以上
  return list.filter(r => {
    if (f.province && r.province !== f.province) return false
    if (f.city && r.city !== f.city) return false
    if (f.dishes.length && !f.dishes.some(d => r.dishes.includes(d))) return false
    if (f.types.length && !f.types.includes(r.type)) return false
    if (f.precisions.length && !f.precisions.includes(r.precision)) return false
    if (f.minLikes && r.totalLikes < f.minLikes) return false
    if ((f.minMentions ?? 1) > r.mentionCount) return false
    if (f.onlyNamed && !r.hasRealName) return false
    if (f.reliableOnly && (r.rank < reliableRank || !r.lat)) return false
    if (f.excludeClosed && r.suspectedClosed) return false
    return true
  })
}

export function regionCentroid(regions, name, levelFirstChar) {
  const hit = regions.find(r => r.l === levelFirstChar && (r.n === name))
  if (hit) return { lat: hit.y, lng: hit.x }
  return null
}

export function resolveCentroid(regions, province, city, district) {
  const tries = []
  if (district) tries.push([district, 'd'])
  if (city) tries.push([city, 'c'])
  if (province) tries.push([province, 'p'])
  for (const [n, lvl] of tries) {
    const c = regionCentroid(regions, n, lvl)
    if (c) return c
  }
  // 直辖市回退: 省=北京市 → city级查找
  for (const [n] of tries) {
    const c = regionCentroid(regions, n, 'c') || regionCentroid(regions, n, 'd')
    if (c) return c
  }
  return null
}
