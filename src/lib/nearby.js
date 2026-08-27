import { PRECI_RANK } from '../store/app'

/**
 * 附近推荐: haversine 距离估算
 * 排除: 无坐标 / 精度低于区县级 / 疑似停业
 */
const R_EARTH = 6371

function haversine(lat1, lng1, lat2, lng2) {
  const rad = Math.PI / 180
  const dLat = (lat2 - lat1) * rad
  const dLng = (lng2 - lng1) * rad
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLng / 2) ** 2
  return R_EARTH * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

export function formatDistance(km) {
  if (km == null) return ''
  if (km < 1) return `${Math.round(km * 1000)} m`
  if (km < 20) return `${km.toFixed(1)} km`
  return `${Math.round(km)} km`
}

export function computeNearby(restaurants, origin, limit = 6) {
  const eligible = restaurants.filter(r =>
    r.lat && r.lng &&
    (PRECI_RANK[r.precision] || 0) >= 3 &&
    !r.suspectedClosed &&
    r.coordSource !== '')
  const list = eligible.map(r => ({
    r,
    distKm: haversine(origin.lat, origin.lng, r.lat, r.lng),
  }))
  list.sort((a, b) => a.distKm - b.distKm)
  return list.slice(0, limit)
}
