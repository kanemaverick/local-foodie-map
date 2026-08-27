<script setup>
import { computed, ref, watch } from 'vue'
import { useAppStore, precClass } from '../store/app'

const store = useAppStore()
const r = computed(() => store.detailRestaurant)

const expanded = ref(new Set())
function toggleCmt(id) {
  const s = new Set(expanded.value)
  s.has(id) ? s.delete(id) : s.add(id)
  expanded.value = s
}

const openReplies = ref(new Set())
function toggleReplies(rootId) {
  const s = new Set(openReplies.value)
  s.has(rootId) ? s.delete(rootId) : s.add(rootId)
  openReplies.value = s
}

watch(() => store.detailId, () => {
  expanded.value = new Set()
  openReplies.value = new Set()
})

const repliesByRoot = computed(() => {
  const m = {}
  for (const rep of r.value?.threadReplies || []) m[rep.id] = rep
  return m
})

/* 每条主评论挂其楼中楼(按 root 匹配所有 threadReplies) */
const repliesForRootList = computed(() => r.value?.threadReplies || [])

const amapUrl = computed(() => {
  if (!r.value) return '#'
  const q = encodeURIComponent(
    `${r.value.areaFull || ''}${r.value.locationClues[0] || ''} ${r.value.name}`.trim())
  return `https://www.amap.com/search?query=${q}`
})

function fmt(n) { return Number(n || 0).toLocaleString('zh-CN') }
function imgFallback(e) { e.target.style.display = 'none' }
</script>

<template>
  <teleport to="body">
    <template v-if="store.detailId && r">
      <div class="drawer-mask" @click="store.closeDetail()"></div>
      <aside class="drawer" role="dialog" aria-modal="true">
        <header class="drawer-head">
          <div style="flex:1">
            <h2 style="font-size:19px;line-height:1.4;word-break:break-all">
              {{ r.name }}
              <span v-if="!r.hasRealName"
                    style="font-size:11px;color:var(--amber);border:1px dashed var(--amber);border-radius:6px;padding:1px 6px;vertical-align:2px">
                描述性名称·非正式店名</span>
            </h2>
            <p style="font-size:12.5px;color:var(--ink-faint);margin-top:3px">
              {{ [r.province, r.city, r.district].filter(Boolean).join(' · ') || '位置待确认' }}
              <span v-if="r.type"> · {{ r.type }}</span>
            </p>
          </div>
          <button class="close-x" @click="store.closeDetail()" aria-label="关闭">✕</button>
        </header>

        <div class="drawer-body">
          <!-- 状态徽章 -->
          <div class="chip-row" style="margin-bottom:4px">
            <span class="badge" :class="precClass(r.precision)">📍 {{ r.precision }}</span>
            <span class="badge prec-mid">可信度 {{ r.credibility }}</span>
            <span v-if="r.hasRealName" class="badge prec-high">有店名</span>
            <span v-else class="badge prec-low">无正式店名</span>
            <span class="badge prec-low">提及 {{ r.mentionCount }} 次</span>
          </div>

          <div class="r-closed-banner" v-if="r.suspectedClosed" style="margin-top:10px">
            ⚠️ 有评论提到这家店可能已关门或搬走：<br />
            <span v-for="(ev, i) in r.closedEvidence" :key="i">「{{ ev }}」 </span>
            前往前请务必核实！
          </div>

          <!-- 关键信息 -->
          <div class="detail-grid glass-strong" style="padding:13px 15px;border-radius:16px;margin-top:12px">
            <div class="kv"><span class="k">推荐菜品</span><span class="v">{{ r.dishes.join('、') || '评论未明确' }}</span></div>
            <div class="kv"><span class="k">餐馆类型</span><span class="v">{{ r.type || '未分类' }}</span></div>
            <div class="kv"><span class="k">推荐次数</span><span class="v">{{ r.mentionCount }}</span></div>
            <div class="kv"><span class="k">点赞合计</span><span class="v">👍 {{ fmt(r.totalLikes) }}</span></div>
            <div class="kv"><span class="k">位置精度</span><span class="v">{{ r.precision }}</span></div>
            <div class="kv"><span class="k">信息可信度</span><span class="v">{{ r.credibility }}（{{ r.credScore }} 分）</span></div>
          </div>

          <!-- 位置线索 -->
          <h3 style="font-size:14.5px;margin-top:18px">📌 原始位置线索</h3>
          <div class="clue-quote" v-if="r.rawLocationText">{{ r.rawLocationText }}</div>
          <div class="chip-row" v-if="r.locationClues.length">
            <span v-for="c in r.locationClues.slice(0, 8)" :key="c" class="chip">{{ c }}</span>
          </div>
          <p style="font-size:12px;color:var(--ink-faint);margin-top:8px">
            🧭 以上来自网友口述，非精确地址。
            <a :href="amapUrl" target="_blank" rel="noopener">在高德地图搜索这家店 ↗</a>
          </p>

          <!-- 来源评论 -->
          <h3 style="font-size:14.5px;margin:20px 0 4px">💬 网友推荐评论（{{ r.comments.length }}）</h3>
          <div v-for="c in r.comments" :key="c.id" class="cmt-item">
            <div class="cmt-head">
              <span class="avatar">{{ (c.user || '匿')[0] }}</span>
              <span class="cmt-user">{{ c.user }}</span>
              <span class="cmt-time">{{ c.time }}</span>
              <span v-if="c.isReply" class="chip">楼中楼</span>
              <span class="cmt-likes">👍 {{ fmt(c.likes) }}</span>
            </div>
            <p class="cmt-msg" :class="{ clamped: !expanded.has(c.id) && c.msg.length > 90 }">{{ c.msg }}</p>
            <button v-if="c.msg.length > 90" class="expand-btn" @click="toggleCmt(c.id)">
              {{ expanded.has(c.id) ? '收起 ▲' : '展开全文 ▼' }}
            </button>
            <div class="cmt-pics" v-if="c.pics?.length">
              <img v-for="p in c.pics" :key="p" :src="p" loading="lazy" @error="imgFallback" alt="评论配图" />
            </div>
          </div>

          <!-- 楼中楼讨论 -->
          <template v-if="repliesForRootList.length">
            <h3 style="font-size:14.5px;margin:18px 0 2px">🧵 相关讨论（{{ repliesForRootList.length }}）</h3>
            <p style="font-size:12px;color:var(--ink-faint)">同一评论串里的其他回复</p>
            <div v-for="rep in repliesForRootList" :key="rep.id" class="cmt-item">
              <div class="cmt-head">
                <span class="avatar">{{ (rep.user || '匿')[0] }}</span>
                <span class="cmt-user">{{ rep.user }}</span>
                <span class="cmt-time">{{ rep.time }}</span>
                <span class="cmt-likes">👍 {{ fmt(rep.likes) }}</span>
              </div>
              <p class="cmt-msg">{{ rep.msg }}</p>
              <p v-if="rep.flag === 'closed_hint'" style="font-size:12px;color:var(--red)">⚠️ 该回复提到店铺可能已停业</p>
            </div>
          </template>

          <!-- 数据来源 -->
          <div class="src-note">
            数据来源：B站视频《当男生吃到好吃的店时》评论区，由程序结合规则从评论中整理，非官方商家数据。<br />
            点赞数为评论区抓取时点的数据；地址是评论中的位置线索，可能存在误差；店铺可能已搬迁或停业。
            出发前请自行核实实际地址与营业状态。<br />
            原视频：<a :href="r.videoUrl" target="_blank" rel="noopener">{{ r.videoUrl }}</a><br />
            评论ID：<code>{{ r.id }}</code> ·
            <button class="btn-ghost" style="padding:3px 10px;font-size:12px"
                    @click="store.shareRestaurant(r.id)">🔗 复制本店分享链接</button>
          </div>
        </div>
      </aside>
    </template>
  </teleport>
</template>
