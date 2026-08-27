<script setup>
import { computed, ref, watch } from 'vue'
import { useAppStore } from '../store/app'
import RestaurantCard from './RestaurantCard.vue'

const store = useAppStore()

const mProv = ref('')
const mCity = ref('')
const mDist = ref('')

const provinceNames = computed(() => store.provinceList.filter(p => p.count > 0).map(p => p.name))
const cityNames = computed(() => {
  const p = store.provinceList.find(x => x.name === mProv.value)
  return p ? p.cities.map(c => c.name) : []
})
const distNames = computed(() => {
  const set = new Set()
  for (const r of store.restaurants) {
    if (r.city === mCity.value && r.district) set.add(r.district)
  }
  return [...set]
})

watch(mProv, () => { mCity.value = ''; mDist.value = '' })
watch(mCity, () => { mDist.value = '' })

function submitManual() {
  const ok = store.manualOrigin(mProv.value, mCity.value, mDist.value)
  if (!ok) store.showToast('未找到该区域的参考坐标，试试只选省市')
}

const topResults = computed(() => store.nearby.results.slice(0, 6))
</script>

<template>
  <div class="glass" style="padding:20px">
    <h2 style="font-size:18px">📍 推荐离我最近的馆子</h2>
    <p style="font-size:13px;color:var(--ink-soft);margin-top:6px">
      使用浏览器定位获取你附近被评论区推荐的餐馆（仅排除无法定位与疑似停业的店）。
    </p>

    <div class="near-actions" style="margin-top:14px">
      <button class="btn-primary" @click="store.locateMe()"
              :disabled="store.nearby.status === 'locating'">
        <span v-if="store.nearby.status === 'locating'" class="spin">⏳ </span>定位并找最近的馆子
      </button>
      <span v-if="store.nearby.status === 'denied'" style="font-size:12.5px;color:var(--red)">
        已拒绝授权，可用下方手动方式
      </span>
    </div>

    <!-- 手动回退 -->
    <div style="margin-top:16px">
      <details :open="['denied', 'failed'].includes(store.nearby.status)">
        <summary style="cursor:pointer;font-size:13.5px;color:var(--blue)">
          不方便定位？手动选择省 / 市 / 区县 👇
        </summary>
        <div class="manual-form">
          <div class="form-field">
            <label>省份</label>
            <select v-model="mProv">
              <option value="">全部</option>
              <option v-for="n in provinceNames" :key="n" :value="n">{{ n }}</option>
            </select>
          </div>
          <div class="form-field">
            <label>城市</label>
            <select v-model="mCity" :disabled="!mProv">
              <option value="">不限</option>
              <option v-for="n in cityNames" :key="n" :value="n">{{ n }}</option>
            </select>
          </div>
          <div class="form-field">
            <label>区县(可选)</label>
            <select v-model="mDist" :disabled="!mCity">
              <option value="">不限</option>
              <option v-for="n in distNames" :key="n" :value="n">{{ n }}</option>
            </select>
          </div>
          <div class="form-field" style="align-self:end">
            <button class="btn-ghost" style="width:100%" @click="submitManual">按此位置推荐 →</button>
          </div>
        </div>
      </details>
    </div>

    <!-- 说明 -->
    <ul class="notice-list">
      <li>🔐 你的位置信息<strong>仅用于本次附近推荐</strong>，不会被存储或上传。</li>
      <li>🗺️ 餐馆位置来自评论线索解析的估算坐标，<strong>可能存在误差</strong>。</li>
      <li>✅ 店铺实际地址和营业状态请<strong>出发前再次核实</strong>；疑似停业的店已自动排除。</li>
    </ul>

    <!-- 结果 -->
    <template v-if="store.nearby.status === 'ok' && store.nearby.origin">
      <p style="font-size:13px;color:var(--ink-faint);margin-top:16px">
        {{ store.nearby.note || '基于当前位置的推荐' }} · 距离为直线估算
      </p>

      <div style="margin-top:10px" v-if="topResults.length">
        <p style="font-size:13px;color:var(--accent);font-weight:700;margin-bottom:8px">
          🥇 离你最近的一家
        </p>
        <RestaurantCard :restaurant="topResults[0].r" :distance-km="topResults[0].distKm" rank-first />
        <p style="font-size:13px;color:var(--ink-faint);margin:16px 0 8px">其他附近备选</p>
        <div class="card-grid">
          <RestaurantCard v-for="(x, i) in topResults.slice(1)" :key="x.r.id"
                          :restaurant="x.r" :distance-km="x.distKm" />
        </div>
      </div>
      <div v-else class="empty-state">
        <div class="big">🌮</div>
        <p>附近（约500km内）没有足够可信的收录餐馆，换个手动区域或用搜索试试～</p>
      </div>
    </template>

    <div v-if="store.nearby.status === 'locating'" class="empty-state loading-dots">
      正在等待定位授权
    </div>
  </div>
</template>
