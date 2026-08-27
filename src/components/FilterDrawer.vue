<script setup>
import { computed } from 'vue'
import { useAppStore } from '../store/app'

const store = useAppStore()
const f = computed(() => store.filters)

function toggleIn(list, val) {
  const i = list.indexOf(val)
  i >= 0 ? list.splice(i, 1) : list.push(val)
}
function chipStyle(active) {
  return active ? 'border-color:var(--accent);color:#fff;background:var(--accent)' : ''
}
</script>

<template>
  <teleport to="body">
    <template v-if="store.filterOpen">
      <div class="drawer-mask" @click="store.closeFilters()"></div>
      <aside class="slide-over">
        <header class="drawer-head">
          <h3 style="flex:1">⚙️ 筛选 (影响所有列表)</h3>
          <button class="close-x" @click="store.closeFilters()" aria-label="关闭">✕</button>
        </header>
        <div class="filter-body">
          <!-- 地区 -->
          <section class="filter-section">
            <h4>地区</h4>
            <select v-model="f.province" @change="f.city = ''"
                    style="width:100%;padding:9px 12px;border-radius:12px;background:var(--glass-strong);border:1px solid var(--glass-border);outline:none;margin-bottom:8px">
              <option value="">全部省份</option>
              <option v-for="n in store.provinceList.filter(p => p.count > 0).map(p => p.name)"
                      :key="n" :value="n">{{ n }}</option>
            </select>
            <select v-model="f.city" :disabled="!f.province"
                    style="width:100%;padding:9px 12px;border-radius:12px;background:var(--glass-strong);border:1px solid var(--glass-border);outline:none">
              <option value="">全部城市</option>
              <template v-if="f.province">
                <option v-for="c in store.provinceList.find(p => p.name === f.province)?.cities || []"
                        :key="c.name" :value="c.name">{{ c.name }}</option>
              </template>
            </select>
          </section>

          <!-- 菜品 -->
          <section class="filter-section">
            <h4>菜品 (多选)</h4>
            <div class="chip-row">
              <button v-for="d in store.dishOptions.slice(0, 24)" :key="d" class="chip dish"
                      :style="chipStyle(f.dishes.includes(d))"
                      @click="toggleIn(f.dishes, d)">{{ d }}</button>
            </div>
          </section>

          <!-- 类型 -->
          <section class="filter-section">
            <h4>餐馆类型 (多选)</h4>
            <div class="chip-row">
              <button v-for="t in store.typeOptions" :key="t" class="chip type"
                      :style="chipStyle(f.types.includes(t))"
                      @click="toggleIn(f.types, t)">{{ t }}</button>
            </div>
          </section>

          <!-- 定位精度 -->
          <section class="filter-section">
            <h4>定位精度</h4>
            <div class="chip-row">
              <button v-for="p in ['精确门牌', '道路或路口', '明确地标附近', '区县级位置', '城市级位置']"
                      :key="p" class="chip"
                      :style="chipStyle(f.precisions.includes(p))"
                      @click="toggleIn(f.precisions, p)">{{ p }}</button>
            </div>
          </section>

          <!-- 数值门槛 -->
          <section class="filter-section">
            <h4>点赞数 ≥ {{ f.minLikes }}</h4>
            <input type="range" min="0" max="3000" step="50" v-model.number="f.minLikes"
                   style="width:100%" />
            <h4 style="margin-top:10px">推荐次数 ≥ {{ f.minMentions }}</h4>
            <input type="range" min="1" max="4" step="1" v-model.number="f.minMentions"
                   style="width:100%" />
          </section>

          <!-- 开关 -->
          <section class="filter-section">
            <h4>其他</h4>
            <div class="toggle-row">
              只看有正式店名
              <button class="switch" :class="{ on: f.onlyNamed }" @click="f.onlyNamed = !f.onlyNamed"></button>
            </div>
            <div class="toggle-row">
              只看可靠定位(地标级以上+有坐标)
              <button class="switch" :class="{ on: f.reliableOnly }" @click="f.reliableOnly = !f.reliableOnly"></button>
            </div>
            <div class="toggle-row">
              排除疑似停业
              <button class="switch" :class="{ on: f.excludeClosed }" @click="f.excludeClosed = !f.excludeClosed"></button>
            </div>
          </section>

          <button class="btn-ghost" style="width:100%" @click="store.resetFilters()">重置全部筛选</button>
        </div>
      </aside>
    </template>
  </teleport>
</template>
