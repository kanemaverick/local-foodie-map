<script setup>
import { computed } from 'vue'
import { useAppStore, precClass } from '../store/app'
import { formatDistance } from '../lib/nearby'
import { splitTerms } from '../lib/search'

const props = defineProps({
  restaurant: { type: Object, required: true },
  highlightQuery: { type: String, default: '' },
  rankFirst: { type: Boolean, default: false },
  distanceKm: { type: Number, default: null },
})

const store = useAppStore()

const terms = computed(() => splitTerms(props.highlightQuery))
const SAFE_RE = /[&<>]/

function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}
function markText(s) {
  if (!terms.value.length || !s) return escapeHtml(s)
  let out = escapeHtml(s)
  for (const t of terms.value) {
    const safe = escapeHtml(t).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    out = out.replace(new RegExp(safe, 'gi'), m => `<mark>${m}</mark>`)
  }
  return out
}

const excerptSrc = computed(() => {
  const c = props.restaurant.topComment
  return c ? c.msg.replace(/\s+/g, ' ').slice(0, 120) : ''
})
const excerptHtml = computed(() => markText(excerptSrc.value))

const dishChips = computed(() => props.restaurant.dishes.slice(0, 4))

const amapUrl = computed(() => {
  const r = props.restaurant
  const q = encodeURIComponent(`${r.areaFull || ''}${r.locationClues[0] || ''} ${r.name}`)
  return `https://www.amap.com/search?query=${q}`
})

function fmt(n) { return Number(n || 0).toLocaleString('zh-CN') }

/* hover 3D 倾斜: 玻璃卡片随鼠标微倾, 模拟实体玻璃块的立体感 */
function onTilt(e) {
  const el = e.currentTarget
  const r = el.getBoundingClientRect()
  const x = (e.clientX - r.left) / r.width - 0.5
  const y = (e.clientY - r.top) / r.height - 0.5
  el.style.transition = 'transform .12s ease-out, box-shadow .25s ease'
  el.style.transform =
    `translateY(-4px) rotateX(${(-y * 4.5).toFixed(2)}deg) rotateY(${(x * 5.5).toFixed(2)}deg)`
}
function offTilt(e) {
  const el = e.currentTarget
  el.style.transition = 'transform .45s cubic-bezier(.2,.8,.3,1), box-shadow .25s ease'
  el.style.transform = ''
}
</script>

<template>
  <article class="glass r-card" :class="{ 'rank-first': rankFirst }"
           @click="store.openDetail(restaurant.id)"
           @mousemove="onTilt" @mouseleave="offTilt">
    <div class="r-card-top">
      <div>
        <h3 class="r-name" v-html="markText(restaurant.name)"></h3>
        <span v-if="!restaurant.hasRealName" class="no-name-tag">描述性名称</span>
      </div>
      <span class="badge" :class="precClass(restaurant.precision)">{{ restaurant.precision }}</span>
    </div>

    <div class="r-region">
      <span v-html="markText([restaurant.province, restaurant.city, restaurant.district].filter(Boolean).join(' · ') || '位置待确认')"></span>
    </div>

    <div class="chip-row" v-if="dishChips.length || restaurant.type">
      <span v-if="restaurant.type" class="chip type">{{ restaurant.type }}</span>
      <span v-for="d in dishChips" :key="d" class="chip dish"
            v-html="'🥢 ' + markText(d)"></span>
    </div>

    <p class="r-excerpt" v-html="excerptHtml"></p>

    <div class="r-closed-banner" v-if="restaurant.suspectedClosed">
      ⚠️ 评论提及可能已关门/搬走<span v-if="restaurant.closedEvidence?.length">：「{{ restaurant.closedEvidence[0].slice(0, 30) }}」</span>
    </div>

    <div class="r-stats">
      <span title="来源评论点赞合计">👍 <b>{{ fmt(restaurant.totalLikes) }}</b></span>
      <span v-if="restaurant.mentionCount > 1">🔁 {{ restaurant.mentionCount }} 人推荐</span>
      <span>可信度 {{ restaurant.credibility }}</span>
      <span v-if="distanceKm != null" class="dist-pill">{{ formatDistance(distanceKm) }}</span>
    </div>
  </article>
</template>
