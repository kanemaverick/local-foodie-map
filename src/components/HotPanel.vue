<script setup>
import { computed, ref } from 'vue'
import { useAppStore } from '../store/app'
import RestaurantCard from './RestaurantCard.vue'

const store = useAppStore()
const tab = ref('likes')

const likeTop = computed(() => store.hotByLikes.slice(0, 12))
const mentionTop = computed(() => store.hotByMentions.slice(0, 12))

/* 各城市热门: 选省后每城 No.1 */
const hotProv = ref('')
const cityList = computed(() => {
  const p = store.provinceList.find(x => x.name === hotProv.value)
  return p ? p.cities : []
})
function cityChampion(cityName) {
  const list = store.restaurants
    .filter(r => r.province === hotProv.value && r.city === cityName && !r.suspectedClosed)
    .sort((a, b) => b.totalLikes - a.totalLikes)
  return list[0] || null
}
</script>

<template>
  <div>
    <div class="hot-tabs">
      <button class="tag-chip" @click="tab = 'likes'"
              :style="tab === 'likes' ? 'border-color:var(--accent);color:var(--accent)' : ''">
        👍 点赞最高</button>
      <button class="tag-chip" @click="tab = 'mentions'"
              :style="tab === 'mentions' ? 'border-color:var(--accent);color:var(--accent)' : ''">
        🔁 推荐次数最多</button>
      <button class="tag-chip" @click="tab = 'cities'"
              :style="tab === 'cities' ? 'border-color:var(--accent);color:var(--accent)' : ''">
        🏙️ 各城市热门</button>
    </div>

    <template v-if="tab !== 'cities'">
      <div class="card-grid">
        <RestaurantCard v-for="(r, i) in (tab === 'likes' ? likeTop : mentionTop)"
                        :key="r.id" :restaurant="r" :rank-first="i === 0" />
      </div>
      <p style="text-align:center;color:var(--ink-faint);font-size:12px;margin-top:14px">
        已默认排除疑似停业的店
      </p>
    </template>

    <template v-else>
      <div class="manual-form" style="max-width:420px">
        <div class="form-field">
          <label>选择省份查看各城市 No.1</label>
          <select v-model="hotProv">
            <option value="">请选择…</option>
            <option v-for="n in store.provinceList.filter(p => p.count > 0).map(p => p.name)"
                    :key="n" :value="n">{{ n }}</option>
          </select>
        </div>
      </div>
      <div v-if="!hotProv" class="empty-state"><div class="big">🏙️</div><p>选个省份，看看每座城市评论区最捧场的馆子</p></div>
      <div v-else class="card-grid" style="margin-top:14px">
        <article v-for="c in cityList" :key="c.name" class="glass r-card" style="cursor:pointer"
                 @click="cityChampion(c.name) && store.openDetail(cityChampion(c.name).id)">
          <h3 class="r-name">{{ c.name }} No.1 🏆</h3>
          <template v-if="cityChampion(c.name)">
            <div class="r-region">{{ cityChampion(c.name).name }}</div>
            <div class="r-stats">
              <span>👍 <b>{{ cityChampion(c.name).totalLikes.toLocaleString() }}</b></span>
              <span>{{ cityChampion(c.name).dishes.slice(0, 2).join(' / ') }}</span>
            </div>
          </template>
          <p v-else style="font-size:12.5px;color:var(--ink-faint)">该城暂无在营收录</p>
        </article>
      </div>
    </template>
  </div>
</template>
