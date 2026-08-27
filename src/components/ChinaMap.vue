<script setup>
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { useAppStore } from '../store/app'

const store = useAppStore()
const el = ref(null)
let chart = null
let disposed = false

const infoStrip = ref({ title: '全国概览', lines: [] })

function fetchGeo() {
  return fetch(`${import.meta.env.BASE_URL}geo/china.json`).then(r => r.json())
}

function maxCount() {
  return Math.max(6, ...store.provinceList.map(p => p.count || 0))
}

function baseData() {
  const known = new Map(store.provinceList.map(p => [p.name, p]))
  const data = []
  for (const p of store.provinceList) {
    data.push({
      name: p.name,
      value: p.count || 0,
      count: p.count || 0,
      cityCount: p.cityCount || 0,
      top: p.top || [],
    })
  }
  // GeoJSON 里存在但数据为 0 的省份也参与着色
  return { data, known }
}

function option() {
  const dark = document.documentElement.dataset.theme === 'dark'
  const { data } = baseData()
  return {
    animationDuration: 600,
    tooltip: {
      trigger: 'item',
      backgroundColor: dark ? 'rgba(30,28,34,.92)' : 'rgba(255,255,255,.94)',
      borderColor: 'rgba(150,130,110,.35)',
      textStyle: { color: dark ? '#ece7e0' : '#2b2620', fontSize: 12.5 },
      extraCssText: 'max-width:260px; white-space:normal;',
      formatter: params => {
        if (!params.data || params.name === '' ) return ''
        const d = params.data
        const rows = [`<b style="font-size:13.5px">${params.name}</b>`]
        rows.push(`收录餐馆 <b>${d.count}</b> 家 · 覆盖城市 <b>${d.cityCount}</b> 座`)
        if (d.top && d.top.length) {
          rows.push('<div style="margin-top:4px;color:#98908a">热门:</div>')
          d.top.slice(0, 3).forEach(t => {
            rows.push(`<div>🔥 ${t.name} <span style="color:#e8734a">👍${t.likes.toLocaleString()}</span></div>`)
          })
        }
        if (!d.count) rows.push('<div style="color:#98908a;margin-top:3px">暂无收录，欢迎看视频找补 😋</div>')
        else rows.push('<div style="color:#98908a;margin-top:4px">点击省份查看清单</div>')
        return rows.join('')
      },
    },
    visualMap: {
      type: 'continuous',
      min: 0, max: maxCount(),
      show: false,
      inRange: { color: dark
        ? ['#22242e', '#2e3a5c', '#4560b8', '#7c96ff']
        : ['#efede6', '#c4d0f2', '#7d95e9', '#2b48ff'] },
    },
    series: [{
      type: 'map',
      map: 'china',
      roam: true,
      zoom: 1.18,
      center: [104.5, 37.2],
      scaleLimit: { min: 0.6, max: 6 },
      selectedMode: false,
      emphasis: {
        label: { show: true, fontSize: 12 },
        itemStyle: {
          areaColor: dark ? '#7c96ff' : '#2b48ff',
          shadowBlur: 14, shadowColor: 'rgba(43,72,255,.5)',
        },
      },
      itemStyle: {
        borderColor: dark ? 'rgba(255,255,255,.28)' : 'rgba(255,255,255,.9)',
        borderWidth: 0.8,
      },
      label: { show: false, color: dark ? '#ece7e0' : '#5a4a3a', fontSize: 10.5 },
      data: data.map(d => ({ name: d.name, value: d.value, count: d.count, cityCount: d.cityCount, top: d.top })),
    }],
  }
}

function refreshStrip(name) {
  if (!name) {
    const ov = store.overview
    infoStrip.value = {
      title: '🇨🇳 全国美食速览',
      lines: ov ? [`共 ${ov.restaurantCount} 家馆子 · ${ov.provinceCount} 个省级地区 · ${ov.cityCount} 座城市`,
                  '鼠标移入/点按省份查看详情'].filter(Boolean) : ['载入中…'],
    }
    return
  }
  const p = store.provinceList.find(x => x.name === name)
  if (!p) { refreshStrip(null); return }
  const topNames = (p.top || []).map(t => t.name).slice(0, 2).join('、')
  infoStrip.value = {
    title: name,
    lines: [
      `收录 ${p.count} 家 · 城市 ${p.cityCount} 座`,
      topNames ? `热门: ${topNames}` : '',
    ].filter(Boolean),
  }
}

function render() {
  if (!chart) return
  chart.setOption(option(), { notMerge: true })
}

onMounted(async () => {
  try {
    const geo = await fetchGeo()
    if (disposed) return
    echarts.registerMap('china', geo)
    store.geoNames = geo.features.map(f => f.properties.name).filter(n => n && n !== '')
    chart = echarts.init(el.value)
    chart.on('click', params => {
      if (params.componentType === 'series') {
        store.selectProvince(params.name)
        refreshStrip(params.name)
      }
    })
    chart.on('mouseover', params => {
      if (params.componentType === 'series') {
        store.mapHovering = true
        refreshStrip(params.name)
      }
    })
    chart.getZr().on('mouseout', () => {
      store.mapHovering = false
      refreshStrip(null)
    })
    window.addEventListener('resize', onResize)
    render()
    refreshStrip(null)
  } catch (e) {
    console.error('地图加载失败', e)
    store.showToast('地图加载失败，请检查网络后刷新')
  }
})

function onResize() { chart && chart.resize() }

watch(() => store.theme, () => render())
watch(() => store.status, s => { if (s === 'ready') setTimeout(render, 60) })
watch(() => store.overview, () => {
  if (!store.mapHovering) refreshStrip(null)
})

onBeforeUnmount(() => {
  disposed = true
  window.removeEventListener('resize', onResize)
  chart && chart.dispose()
  chart = null
})
</script>

<template>
  <div class="glass map-card">
    <div class="map-legend">深浅 = 收录数量</div>
    <div ref="el" class="map-box"></div>
    <div class="map-info-strip">
      <b>{{ infoStrip.title }}</b>
      <div v-for="(line, i) in infoStrip.lines" :key="i">{{ line }}</div>
    </div>
  </div>
</template>
