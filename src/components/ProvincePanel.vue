<script setup>
import { computed } from 'vue'
import { useAppStore } from '../store/app'

const store = useAppStore()

const provinceInfo = computed(() =>
  store.selectedProvince
    ? store.provinceList.find(p => p.name === store.selectedProvince)
    : null)

const cityGroups = computed(() => provinceInfo.value?.cities || [])

const provinceRestaurants = computed(() => {
  if (!store.selectedProvince) return []
  return store.resultList.filter(r => r.province === store.selectedProvince)
})

/* 当前城市下的餐馆列表(应用全局筛选, 点赞降序) */
const cityRestaurants = computed(() => {
  if (!store.selectedCity) return []
  return store.resultList
    .filter(r => r.province === store.selectedProvince && r.city === store.selectedCity)
    .sort((a, b) => b.totalLikes - a.totalLikes)
})
</script>

<template>
  <!-- 省 > 市 面包屑 -->
  <div class="glass prov-panel">
    <div class="panel-breadcrumb">
      <span class="crumb" :class="{ current: !store.selectedProvince }"
            @click="store.selectProvince('')">全国</span>
      <template v-if="store.selectedProvince">
        <span>›</span>
        <span class="crumb" :class="{ current: !store.selectedCity }"
              @click="store.selectCity('')">{{ store.selectedProvince }}</span>
      </template>
      <template v-if="store.selectedCity">
        <span>›</span>
        <span class="crumb current">{{ store.selectedCity }}</span>
      </template>
    </div>

    <!-- 全国态 -->
    <template v-if="!store.selectedProvince">
      <p style="font-size:13px;color:var(--ink-faint);padding:6px 8px 10px">
        👇 点击地图任意省份，按城市浏览被评论区翻牌的馆子
      </p>
      <div v-for="p in store.provinceList.slice(0, 12)" :key="p.name" class="city-group">
        <div class="city-row" @click="store.selectProvince(p.name)">
          <div>
            <div class="city-name">{{ p.name }}</div>
            <div class="meta">收录 {{ p.count }} 家 · {{ p.cityCount }} 座城市</div>
          </div>
          <span class="city-arrow">›</span>
        </div>
      </div>
      <p v-if="store.provinceList.length > 12"
         style="text-align:center;font-size:12px;color:var(--ink-faint);padding-top:6px">
        ……以及另外 {{ store.provinceList.length - 12 }} 个省份，点地图探索 ↖
      </p>
    </template>

    <!-- 省份态: 城市分组清单 -->
    <template v-else-if="!store.selectedCity">
      <div class="city-group" v-for="c in cityGroups" :key="c.name">
        <div class="city-row" @click="store.selectCity(c.name)">
          <div>
            <div class="city-name">{{ c.name }}</div>
            <div class="meta">{{ c.count }} 家馆子</div>
          </div>
          <span class="city-arrow">›</span>
        </div>
      </div>
      <p v-if="!cityGroups.length && !provinceRestaurants.length"
         style="padding:16px;font-size:13px;color:var(--ink-faint)">
        该省暂无收录。
      </p>
      <p v-else-if="!cityGroups.length" style="padding:10px 6px;font-size:12.5px;color:var(--ink-soft)">
        直辖市/未细分城市，全部馆子见下方卡片 ↓
      </p>
    </template>

    <!-- 城市态: 简要统计 -->
    <template v-else>
      <p style="font-size:12.5px;color:var(--ink-faint);padding:2px 4px 2px">
        共 {{ cityRestaurants.length }} 家 · 按点赞降序 · 详情见下方卡片
      </p>
      <p v-if="!cityRestaurants.length && store.filters.excludeClosed"
         style="padding:6px 4px;font-size:12.5px;color:var(--ink-soft)">
        当前筛选下没有可显示的馆子（疑似停业的默认隐藏，可在导航筛选中放开）。
      </p>
    </template>
  </div>
</template>
