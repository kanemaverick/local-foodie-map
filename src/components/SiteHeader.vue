<script setup>
import { useAppStore } from '../store/app'

const store = useAppStore()

const navItems = [
  { key: 'browse', label: '地图' },
  { key: 'hot', label: '热门' },
  { key: 'random', label: '随机' },
  { key: 'nearby', label: '附近' },
]

function cycleTheme() {
  const order = ['auto', 'light', 'dark']
  const next = order[(order.indexOf(store.theme) + 1) % order.length]
  store.setTheme(next)
}
function go(key) {
  store.setView(key)
  window.scrollTo({ top: 0 })
}
const themeLabel = { auto: '主题·自动', light: '主题·浅色', dark: '主题·深色' }
</script>

<template>
  <!-- 简约悬浮导航: 纯文字 + 衬线字标, 激活态为短下划线 -->
  <nav class="float-nav" aria-label="站点导航">
    <button class="logo" @click="go('browse')">Local Foodie Map</button>
    <span class="nav-divider" aria-hidden="true"></span>
    <div class="nav-scroll">
      <button v-for="item in navItems" :key="item.key"
              class="nav-link" :class="{ active: store.view === item.key }"
              @click="go(item.key)">{{ item.label }}</button>
      <button class="nav-link" @click="store.openFilters()">筛选</button>
      <button class="nav-link" @click="store.shareCurrent('页面')">分享</button>
    </div>
    <button class="nav-link theme-btn" @click="cycleTheme">{{ themeLabel[store.theme] }}</button>
  </nav>
</template>
