<script setup>
import { ref } from 'vue'
import { useAppStore } from '../store/app'

const store = useAppStore()
const input = ref('')

const QUICK = ['成都', '虎门', '烧腊', '冒菜', '海椒市']

function submit() {
  if (!input.value.trim()) return
  store.doSearch(input.value.trim())
}

function scrollDown() {
  window.scrollTo({ top: window.innerHeight, behavior: 'smooth' })
}
</script>

<template>
  <!-- 第一页: 只有居中的搜索框 -->
  <section class="p1" :class="{ fullscreen: store.view === 'browse' }">
    <p class="p1-brand">Local Foodie Map</p>

    <div class="search-zone">
      <div class="search-bar glass">
        <input v-model="input" type="search" enterkeyhint="search"
               placeholder="搜地名、店名、菜品… 例如：成都 / 虎门 / 烧腊 / 冒菜"
               @keydown.enter="submit" />
        <button class="search-go" @click="submit">搜索</button>
      </div>
      <div class="search-tags">
        <span class="search-hint">试试</span>
        <button v-for="t in QUICK" :key="t" class="tag-chip" @click="input = t; submit()">{{ t }}</button>
      </div>
    </div>

    <button class="scroll-hint" v-if="store.view === 'browse'" @click="scrollDown"
            aria-label="向下翻页查看地图">
      <span>下滑查看地图</span>
      <span class="chevron">↓</span>
    </button>
  </section>
</template>
