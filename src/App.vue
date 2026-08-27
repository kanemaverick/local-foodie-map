<script setup>
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { useAppStore } from './store/app'
import SiteHeader from './components/SiteHeader.vue'
import HeroOverview from './components/HeroOverview.vue'
import ChinaMap from './components/ChinaMap.vue'
import ProvincePanel from './components/ProvincePanel.vue'
import RestaurantCard from './components/RestaurantCard.vue'
import RestaurantDetail from './components/RestaurantDetail.vue'
import NearbyPanel from './components/NearbyPanel.vue'
import HotPanel from './components/HotPanel.vue'
import RandomPanel from './components/RandomPanel.vue'
import FilterDrawer from './components/FilterDrawer.vue'

const store = useAppStore()
onMounted(() => store.init())

/* 省份态(未选城市)时也展示该省全部餐馆卡片 */
const provinceAll = computed(() => {
  if (!store.selectedProvince || store.selectedCity) return []
  return store.resultList
    .filter(r => r.province === store.selectedProvince)
    .sort((a, b) => b.totalLikes - a.totalLikes)
})

/* 城市态: 全宽卡片网格 */
const cityAll = computed(() => {
  if (!store.selectedCity) return []
  return store.resultList
    .filter(r => r.province === store.selectedProvince && r.city === store.selectedCity)
    .sort((a, b) => b.totalLikes - a.totalLikes)
})

const searchList = computed(() => store.view === 'search' ? store.resultList : [])

/* ---- 翻页式滚动: 第一页(搜索) ⇄ 第二页(地图), 桌面滚轮驱动 ---- */
let flipLock = false
function flipTo(top) {
  flipLock = true
  window.scrollTo({ top, behavior: 'smooth' })
  setTimeout(() => { flipLock = false }, 800)
}
function onWheelFlip(e) {
  if (store.view !== 'browse' || flipLock || !store.overview) return
  const vh = window.innerHeight
  const y = window.scrollY
  if (e.deltaY > 30 && y < vh * 0.35) flipTo(vh)
  else if (e.deltaY < -30 && y > vh * 0.35 && y < vh * 1.02) flipTo(0)
}

function retry() { store.errMsg = ''; store.status = 'loading'; store.retry() }

onMounted(() => {
  store.init()
  window.addEventListener('wheel', onWheelFlip, { passive: true })
})
onBeforeUnmount(() => window.removeEventListener('wheel', onWheelFlip))
</script>

<template>
  <SiteHeader />

  <!-- 加载 / 错误 状态 -->
  <main v-if="store.status === 'error'" class="page-body">
    <div class="error-banner" role="alert">
      <span>😰 数据加载失败：{{ store.errMsg }}。请确认网络后重试。</span>
      <button class="retry-btn" @click="retry">重试</button>
    </div>
  </main>

  <template v-else>
    <HeroOverview />

    <main class="page-body">
      <!-- ========== 地图浏览 (含省市钻取) ========== -->
      <div id="results-anchor"></div>
      <template v-if="store.view === 'browse' || store.detailId">
        <section class="p2-section">
          <div class="section-head">
            <h2>中国美食地图</h2>
            <span class="hint" v-if="store.overview">
              {{ Number(store.overview.totalComments).toLocaleString() }} 条评论 ·
              {{ Number(store.overview.restaurantCount).toLocaleString() }} 家收录 ·
              {{ store.overview.provinceCount }} 省 {{ store.overview.cityCount }} 城 ·
              点赞 {{ Number(store.overview.totalLikes).toLocaleString() }}
            </span>
            <span class="hint" v-else>鼠标移入看概览 · 点击省份按城市浏览</span>
          </div>
          <div class="map-layout">
            <ChinaMap />
            <ProvincePanel />
          </div>
        </section>

        <!-- 城市餐馆网格 (全宽) -->
        <template v-if="store.selectedCity && cityAll.length">
          <span id="city-anchor"></span>
          <div class="section-head">
            <h2>{{ store.selectedProvince }} · {{ store.selectedCity }}</h2>
            <span class="hint">{{ cityAll.length }} 家 · 按点赞数排序</span>
            <button class="btn-ghost" style="margin-left:auto"
                    @click="store.shareCurrent('当前城市页')">🔗 分享本城</button>
          </div>
          <div class="card-grid">
            <RestaurantCard v-for="(r, i) in cityAll" :key="r.id" :restaurant="r"
                            :rank-first="i === 0" />
          </div>
        </template>

        <!-- 省份全部餐馆 -->
        <template v-if="provinceAll.length">
          <div class="section-head">
            <h2>{{ store.selectedProvince }}全部收录</h2>
            <span class="hint">{{ provinceAll.length }} 家 · 按点赞排序</span>
          </div>
          <div class="card-grid">
            <RestaurantCard v-for="(r, i) in provinceAll" :key="r.id" :restaurant="r"
                            :rank-first="false" />
          </div>
        </template>
      </template>

      <!-- ========== 搜索结果 ========== -->
      <template v-else-if="store.view === 'search'">
        <div class="section-head">
          <h2>🔍 “{{ store.searchedQuery }}” 的搜索结果</h2>
          <span class="hint">{{ searchList.length ? `找到 ${searchList.length} 家` : '' }}</span>
          <button class="btn-ghost" style="margin-left:auto"
                  @click="store.setView('browse'); store.syncHash()">← 返回地图</button>
        </div>

        <div v-if="!searchList.length" class="glass empty-state">
          <div class="big">🍽️</div>
          <p>没有找到和「{{ store.searchedQuery }}」相关的馆子。<br />
            换个关键词试试，比如：<b>成都、虎门、烧腊、冒菜、海椒市</b></p>
        </div>
        <div v-else class="card-grid">
          <RestaurantCard v-for="(r, i) in searchList" :key="r.id" :restaurant="r"
                          :highlight-query="store.searchedQuery"
                          :rank-first="i === 0" />
        </div>
      </template>

      <!-- ========== 热门 ========== -->
      <template v-else-if="store.view === 'hot'">
        <div class="section-head"><h2>🔥 热门餐馆</h2>
          <button class="btn-ghost" style="margin-left:auto"
                  @click="store.shareCurrent('热门榜')">🔗 分享榜单</button>
        </div>
        <HotPanel />
      </template>

      <!-- ========== 随机 ========== -->
      <template v-else-if="store.view === 'random'">
        <RandomPanel />
      </template>

      <!-- ========== 附近 ========== -->
      <template v-else-if="store.view === 'nearby'">
        <NearbyPanel />
      </template>
    </main>

    <!-- 页脚: 数据说明与免责声明 -->
    <footer class="footer-note">
      <p class="foot-serif" aria-hidden="true"><em>2026</em> · 8.20 – 8.26</p>
      <p><b>Local Foodie Map</b> — 数据来自 B站视频
        <a :href="store.meta?.videoUrl" target="_blank" rel="noopener">《当男生吃到好吃的店时》</a>
        的 {{ Number(store.overview?.totalComments || 0).toLocaleString() }} 条评论区留言，
        由规则程序整理出 {{ store.overview?.restaurantCount }} 家“可循迹”的餐馆。
      </p>
      <p>
        ⚠️ 餐馆推荐来自网友评论，非官方数据；点赞数为评论抓取时点的数据；部分店没有正式店名（使用描述性名称）；
        地址仅为评论中的位置线索，可能存在误差；店铺可能已搬迁或停业——出发前请自行核实。
      </p>
      <p>
        数据快照生成于 {{ store.meta?.generatedAt || '…' }} · 仅供觅食参考，祝吃好喝好 🍜
      </p>
    </footer>
  </template>

  <RestaurantDetail />
  <FilterDrawer />
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="store.toastMsg" class="toast">{{ store.toastMsg }}</div>
    </Transition>
  </Teleport>
</template>
