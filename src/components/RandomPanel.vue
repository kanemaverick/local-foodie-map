<script setup>
import { computed, ref } from 'vue'
import { useAppStore } from '../store/app'
import RestaurantCard from './RestaurantCard.vue'

const store = useAppStore()

const fProv = ref('')
const fCity = ref('')
const fDish = ref('')
const fType = ref('')

const provinceNames = computed(() => store.provinceList.filter(p => p.count > 0).map(p => p.name))
const cityNames = computed(() => {
  const p = store.provinceList.find(x => x.name === fProv.value)
  return p ? p.cities.map(c => c.name) : []
})

const pool = computed(() =>
  store.restaurants.filter(r => !r.suspectedClosed &&
    (!fProv.value || r.province === fProv.value) &&
    (!fCity.value || r.city === fCity.value) &&
    (!fDish.value || r.dishes.includes(fDish.value)) &&
    (!fType.value || r.type === fType.value)))

const result = ref(null)
const rolling = ref(false)
let rollTimer = null

function roll() {
  if (!pool.value.length) { result.value = null; return }
  rolling.value = true
  clearInterval(rollTimer)
  let ticks = 0
  rollTimer = setInterval(() => {
    result.value = pool.value[Math.floor(Math.random() * pool.value.length)]
    if (++ticks >= 8) {
      clearInterval(rollTimer)
      rolling.value = false
    }
  }, 70)
}
</script>

<template>
  <div class="glass random-hero">
    <h2 style="font-size:20px">🎲 今天吃什么？</h2>
    <p style="font-size:13px;color:var(--ink-soft);max-width:420px">
      选择范围（可留空=全国），交给命运决定今晚去吃评论区哪家的安利。
    </p>

    <div class="manual-form" style="width:100%;max-width:640px">
      <div class="form-field">
        <label>省份</label>
        <select v-model="fProv" @change="fCity = ''">
          <option value="">全国都行</option>
          <option v-for="n in provinceNames" :key="n" :value="n">{{ n }}</option>
        </select>
      </div>
      <div class="form-field">
        <label>城市</label>
        <select v-model="fCity" :disabled="!fProv">
          <option value="">不限</option>
          <option v-for="n in cityNames" :key="n" :value="n">{{ n }}</option>
        </select>
      </div>
      <div class="form-field">
        <label>想吃点啥</label>
        <select v-model="fDish">
          <option value="">随便</option>
          <option v-for="d in store.dishOptions.slice(0, 40)" :key="d" :value="d">{{ d }}</option>
        </select>
      </div>
      <div class="form-field">
        <label>餐馆类型</label>
        <select v-model="fType">
          <option value="">不限</option>
          <option v-for="t in store.typeOptions" :key="t" :value="t">{{ t }}</option>
        </select>
      </div>
    </div>

    <button class="dice-btn" @click="roll" :disabled="rolling">
      {{ rolling ? '翻牌中…' : '🎰 随机抽一家' }}
    </button>

    <p v-if="!pool.length" style="font-size:13px;color:var(--red)">这个组合下没有可选的馆子，放宽条件试试～</p>

    <div class="random-result fade-enter-active" v-if="result" :key="result.id"
         style="animation:fadeIn .3s ease">
      <p v-if="!rolling" style="font-size:13.5px;color:var(--accent);font-weight:700;margin-bottom:8px">
        🎉 今晚就去这家！
      </p>
      <RestaurantCard :restaurant="result" />
    </div>
  </div>
</template>
