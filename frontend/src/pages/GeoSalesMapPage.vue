<template>
  <div class="container-xxl page-geo-sales-map">
    <h1 class="page-title">Продажи на карте</h1>
    <p class="text-muted page-geo-sales-map__lede">Точки — ПВЗ из <code>pvz_all</code> по <code>detail_by_period.ppvz_office_id</code>. Пустой товар = все продажи. Таблица внизу — то же, что видно на карте (тот же запрос, фильтр по вьюпорту).</p>

    <div class="row">
      <div class="col-md-12"><WbUniversalFilter v-model:product="filters.product" v-model:date-from="filters.date_from" v-model:date-to="filters.date_to" v-model:brand="filters.brand" v-model:category="filters.category" :brands="brands" :categories="categories" category-label="Категория (предмет)" preset-end="yesterday" @apply="fetchData()" @reset="onReset()" /></div>
    </div>

    <div class="card page-geo-sales-map__map-card">
      <div class="card-header text-white d-flex justify-content-between align-items-center wb-card-header">
        <span>Карта: {{ levelLabel }} ({{ items.length }} точек · зум {{ zoom }})</span>
        <span class="page-geo-sales-map__map-tools">
          <span class="page-geo-sales-map__metric">
            <button class="page-geo-sales-map__metric-btn" :class="{'is-active': metric==='qty'}" @click="metric='qty'; fetchData()">Штуки</button>
            <button class="page-geo-sales-map__metric-btn" :class="{'is-active': metric==='sum'}" @click="metric='sum'; fetchData()">Сумма</button>
          </span>
          <select v-model="levelMode" class="form-select form-select-sm page-geo-sales-map__level" title="Фикс уровня: Авто меняет разрез с зумом" @change="fetchData()">
            <option value="auto">Авто</option>
            <option value="country">Страны</option>
            <option value="okrug">Округа</option>
            <option value="region">Регионы</option>
            <option value="city">Города</option>
            <option value="pvz">ПВЗ</option>
          </select>
          <span class="page-geo-sales-map__map-hint">Клик по кругу — провалиться глубже</span>
          <button class="btn btn-sm btn-light" @click="toggleFull" :title="isFull ? 'Свернуть карту' : 'Карта на весь экран'">
            <i class="bi" :class="isFull ? 'bi-fullscreen-exit' : 'bi-arrows-fullscreen'"></i>
          </button>
        </span>
      </div>
        <div id="geo-map" class="page-geo-sales-map__map"></div>
        <div v-if="isLoading" class="page-geo-sales-map__map-loader">
          <div class="spinner-border" role="status"><span class="visually-hidden">Загрузка...</span></div>
          <span>Загрузка данных...</span>
        </div>
      </div>

    <div class="page-geo-sales-map__body">
      <div class="page-geo-sales-map__crumbs">
        <button class="page-geo-sales-map__crumb" :class="{'is-current': !crumbs.country}" @click="goWorld()">Мир</button>
        <template v-if="crumbs.country">
          <span class="page-geo-sales-map__crumb-sep">›</span>
          <button class="page-geo-sales-map__crumb" :class="{'is-current': crumbs.country && !crumbs.okrug}" @click="goCountry()">{{ crumbs.country }}</button>
        </template>
        <template v-if="crumbs.okrug">
          <span class="page-geo-sales-map__crumb-sep">›</span>
          <button class="page-geo-sales-map__crumb" :class="{'is-current': crumbs.okrug && !crumbs.region}" @click="goOkrug()">{{ crumbs.okrug }}</button>
        </template>
        <template v-if="crumbs.region">
          <span class="page-geo-sales-map__crumb-sep">›</span>
          <button class="page-geo-sales-map__crumb" :class="{'is-current': crumbs.region && !crumbs.city}" @click="goRegion()">{{ crumbs.region }}</button>
        </template>
        <template v-if="crumbs.city">
          <span class="page-geo-sales-map__crumb-sep">›</span>
          <button class="page-geo-sales-map__crumb is-current">{{ crumbs.city }}</button>
        </template>
      </div>

      <div class="page-geo-sales-map__summary">
        Видно: <b>{{ items.length }}</b> · Продаж: <b>{{ fmt0(total.qty) }}</b> · {{ metric === 'sum' ? 'Со ск' : 'К оплате' }}: <b>{{ fmt0(metric === 'sum' ? total.sum_amount : total.sum_for_pay) }} ₽</b>
        <span> · период <b>{{ filters.date_from }} — {{ filters.date_to }}</b></span>
        <span v-if="!world && bboxNote"> · вьюпорт {{ bboxNote }}</span>
        <span v-if="resolvedIds !== null"> · товаров: <b>{{ resolvedIds }}</b></span>
      </div>
      <div v-if="hint && !isLoading" class="alert alert-warning page-geo-sales-map__hint">{{ hint }}</div>

      <div class="card">
        <div class="card-header text-white d-flex justify-content-between align-items-center wb-card-header">
          <span>{{ tableTitle }}</span>
          <span class="page-geo-sales-map__table-tools">
            <label class="page-geo-sales-map__world page-geo-sales-map__world--light"><input type="checkbox" v-model="world" @change="fetchData()" /> Весь мир</label>
            <button class="btn btn-sm btn-light wb-excel-btn" :disabled="!items.length" @click="exportExcel"><i class="bi bi-file-earmark-excel me-1"></i> Excel</button>
          </span>
        </div>
        <div v-if="isLoading" class="p-4 text-center text-muted">Загрузка...</div>
        <div v-else class="page-geo-sales-map__table-wrap">
          <table class="table table-bordered table-striped table-hover kv-grid-table mb-0 page-geo-sales-map__table">
            <thead>
              <tr>
                <th>{{ nameCol }}</th>
                <th>{{ subCol }}</th>
                <th>Кол-во</th>
                <th>Сумма, ₽</th>
                <th>Цена со ск, ₽</th>
                <th>СПП, %</th>
                <th>К оплате, ₽</th>
              </tr>
            </thead>
            <tbody>
              <tr class="kv-totals">
                <td></td><td></td>
                <td>{{ fmt0(sumQty) }}</td><td>{{ fmt2(sumRetail) }}</td><td>{{ fmt2(sumAmount) }}</td><td>{{ fmt2(avgSpp) }}</td><td>{{ fmt2(sumPay) }}</td>
              </tr>
              <tr v-for="r in tableRows" :key="r.key" class="page-geo-sales-map__row" @click="focusRow(r)" @mouseenter="hlName(level === 'city' ? r.sub : r.name)" @mouseleave="unhl()" :title="'Показать на карте: ' + r.name">
                <td>{{ r.name }}</td>
                <td class="page-geo-sales-map__addr">{{ r.sub }}</td>
                <td>{{ fmt0(r.qty) }}</td>
                <td>{{ fmt2(r.sum_retail) }}</td>
                <td>{{ fmt2(r.sum_amount) }}</td>
                <td>{{ fmt2(r.spp) }}</td>
                <td class="page-geo-sales-map__pay">{{ fmt2(r.sum_for_pay) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import '@/assets/css/pages/page-geo-sales-map.css'
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { fetchGeoSales, geoStem, okrugStems, gadmCanon, visualCenter } from '../api/geoSales'
import { api } from '../api/client'
import WbUniversalFilter from '../components/common/WbUniversalFilter.vue'

const fmt0 = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))
const fmt2 = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(v) || 0)
const fmtD = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

const filters = ref({ product: '', date_from: '', date_to: '', brand: '', category: '' })
const initDates = () => {
  const to = new Date(); to.setDate(to.getDate() - 1) // как getDPWidget: date_to по умолчанию вчера
  const from = new Date(to); from.setDate(from.getDate() - 30) // как GeoMapReportController: defaultDays 30
  filters.value.date_from = fmtD(from)
  filters.value.date_to = fmtD(to)
}
initDates()

const brands = ref<string[]>([])
const categories = ref<string[]>([])
const loadOptions = async () => {
  try {
    const { data } = await api.get('/api/geo/options')
    brands.value = data?.brands || []
    categories.value = data?.categories || []
  } catch { /* noop */ }
}

const metric = ref<'qty' | 'sum'>('qty')
const levelMode = ref<'auto' | 'country' | 'okrug' | 'region' | 'city' | 'pvz'>('auto')
const world = ref(false)
const crumbs = ref({ country: '', okrug: '', region: '', city: '' })
const level = ref<'country' | 'okrug' | 'region' | 'city' | 'pvz'>('region')
const items = ref<any[]>([])
const total = ref<any>({ qty: 0, sum_for_pay: 0 })
const hint = ref('')
const resolvedIds = ref<number | null>(null)
const zoom = ref(3)
const isLoading = ref(false)
const bboxNote = ref('')

let map: L.Map | null = null
let layer: L.LayerGroup | null = null
let moveTimer: any = null
let reqSeq = 0
let geoFeats: any[] | null = null
let geoLoading: Promise<void> | null = null
let hlPoly: L.GeoJSON | null = null

// Подсветка региона: границы из public/geo/*.geojson (lazy, один раз).
// ru — сшивка по стему названия; by/kz — через таблицу GADM_RU (точное имя -> русское).
// Крым/Севастополь и новые области KZ в файлах отсутствуют — тихо нет.
async function ensureGeo() {
  if (geoFeats) return
  if (!geoLoading) geoLoading = (async () => {
    const all: any[] = []
    const files: Array<[string, string]> = [
      ['/geo/ru_regions_simple.geojson', 'ru'],
      ['/geo/by_regions_simple.geojson', 'by'],
      ['/geo/kz_regions_simple.geojson', 'kz'],
    ]
    for (const [url, src] of files) {
      try {
        const res = await fetch(url)
        const j = await res.json()
        for (const f of j.features || []) {
          f._canon = src === 'ru'
            ? geoStem(String(f?.properties?.name || ''))
            : geoStem(gadmCanon(f?.properties || {}))
          if (f._canon) all.push(f)
        }
      } catch { /* нет файла — пропускаем страну */ }
    }
    geoFeats = all
  })()
  await geoLoading
}
function unhl() {
  if (hlPoly) { if (map) hlPoly.removeFrom(map); hlPoly = null }
}
// Визуальные центры регионов (полюс недоступности): пузырь всегда внутри контура.
// Считается один раз на регион, дальше из кеша. Нет полигона — точка из API.
const centerCache = new Map<string, [number, number]>()
const posOf = (r: any): [number, number] => centerCache.get(r.key) || [r.lat, r.lon]
async function applyVisualCenters() {
  if (level.value !== 'region') return
  await ensureGeo()
  if (!map) return
  let changed = false
  for (const r of items.value) {
    if (r.lat == null || centerCache.has(r.key)) continue
    const f = (geoFeats || []).find((x: any) => x._canon === geoStem(r.name))
    if (!f) continue
    const c = visualCenter(f)
    if (c) { centerCache.set(r.key, c); changed = true }
  }
  if (changed) renderMarkers()
}
function hlName(name: string) {
  if (!map || !name || String(name).startsWith('Без ')) return
  if (level.value !== 'region' && level.value !== 'city' && level.value !== 'okrug') return
  void (async () => {
    await ensureGeo()
    if (!map) return
    unhl()
    if (level.value === 'okrug') {
      // чужие страны (C:) — полигонов пока нет, тихо нет
      if (!String(name).endsWith('ФО')) return
      const set = okrugStems(name)
      const list = (geoFeats || []).filter((x: any) => set.has(x._canon))
      if (!list.length) return
      hlPoly = L.geoJSON(list as any, {
        style: { color: '#7c1af8', weight: 2, fillColor: '#7c1af8', fillOpacity: 0.08 },
        interactive: false,
      } as any).addTo(map)
      return
    }
    const key = geoStem(name)
    const f = (geoFeats || []).find((x: any) => x._canon === key)
    if (!f) return
    hlPoly = L.geoJSON(f as any, {
      style: { color: '#7c1af8', weight: 3, fillColor: '#7c1af8', fillOpacity: 0.12 },
      interactive: false,
    } as any).addTo(map)
  })()
}
let inited = false
const isFull = ref(false)

const toggleFull = async () => {
  const el = document.querySelector('.page-geo-sales-map__map-card')
  if (!el) return
  try {
    if (document.fullscreenElement) await document.exitFullscreen()
    else await (el as HTMLElement).requestFullscreen()
  } catch { /* noop: Esc тоже выходит */ }
}
const onFullChange = () => {
  isFull.value = !!document.fullscreenElement
  setTimeout(() => { if (map) map.invalidateSize() }, 200) // пересчёт тайлов под новый размер
}

const route = useRoute()
const router = useRouter()
let syncing = false
let pendingView: { z: number; lat: number; lon: number } | null = null

const isoD = (s: any) => /^\d{4}-\d{2}-\d{2}$/.test(String(s || '')) ? String(s) : ''
function initFromQuery() {
  const q: any = route.query
  const df = isoD(q.date_from), dt = isoD(q.date_to)
  if (df) filters.value.date_from = df
  if (dt) filters.value.date_to = dt
  filters.value.product = String(q.product ?? q.q ?? q.nm_id ?? q.nmid ?? '')
  filters.value.brand = String(q.brand || '')
  filters.value.category = String(q.category || '')
  if (q.metric === 'qty' || q.metric === 'sum') metric.value = q.metric
  if (['auto', 'country', 'okrug', 'region', 'city', 'pvz'].includes(String(q.lvl || ''))) levelMode.value = (q.lvl || 'auto') as any
  const z = Number(q.z), la = Number(q.lat), lo = Number(q.lon)
  pendingView = (Number.isFinite(z) && Number.isFinite(la) && Number.isFinite(lo)
    && z >= 3 && z <= 18 && Math.abs(la) <= 90 && Math.abs(lo) <= 180)
    ? { z: Math.round(z), lat: la, lon: lo } : null
}

function syncRoute() {
  const q: Record<string, string> = {}
  if (filters.value.date_from) q.date_from = filters.value.date_from
  if (filters.value.date_to) q.date_to = filters.value.date_to
  if (filters.value.product) q.product = filters.value.product
  if (filters.value.brand) q.brand = filters.value.brand
  if (filters.value.category) q.category = filters.value.category
  if (metric.value !== 'qty') q.metric = metric.value
  if (levelMode.value !== 'auto') q.lvl = levelMode.value
  if (map) {
    const c = map.getCenter()
    q.z = String(map.getZoom())
    q.lat = c.lat.toFixed(4)
    q.lon = c.lng.toFixed(4)
  }
  syncing = true
  router.replace({ path: '/geo/sales-map', query: q }).finally(() => setTimeout(() => { syncing = false }, 50))
}

const levelByZoom = (z: number) => z <= 4 ? 'country' : z === 5 ? 'okrug' : z <= 7 ? 'region' : z <= 9 ? 'city' : 'pvz'
const levelLabel = computed(() => ({ country: 'страны', okrug: 'округа', region: 'регионы', city: 'города', pvz: 'ПВЗ' } as any)[level.value])
const nameCol = computed(() => ({ country: 'Страна', okrug: 'Округ', region: 'Регион', city: 'Город', pvz: 'ПВЗ' } as any)[level.value])
const subCol = computed(() => ({ country: '—', okrug: 'Страна', region: 'Страна', city: 'Регион', pvz: 'Адрес' } as any)[level.value])
const tableTitle = computed(() => level.value === 'pvz' ? 'ПВЗ в видимой области' : `Топ — ${levelLabel.value} в видимой области`)
const tableRows = computed(() => items.value.slice(0, 500))
const sumQty = computed(() => items.value.reduce((a, r) => a + (r.qty || 0), 0))
const sumRetail = computed(() => items.value.reduce((a, r) => a + (r.sum_retail || 0), 0))
const sumAmount = computed(() => items.value.reduce((a, r) => a + (r.sum_amount || 0), 0))
const sumPay = computed(() => items.value.reduce((a, r) => a + (r.sum_for_pay || 0), 0))
const avgSpp = computed(() => { const q = sumQty.value; return q ? items.value.reduce((a, r) => a + (r.spp || 0) * (r.qty || 0), 0) / q : 0 })

const valOf = (r: any) => metric.value === 'qty' ? (r.qty || 0) : (r.sum_amount || 0)

const reset = () => { filters.value.product = ''; filters.value.brand = ''; filters.value.category = ''; crumbs.value = { country: '', okrug: '', region: '', city: '' }; initDates(); items.value = []; total.value = { qty: 0, sum_for_pay: 0 }; if (layer) layer.clearLayers() }
const onReset = () => { reset(); fetchData() }

const fetchData = async () => {
  if (!map) return
  syncRoute()
  const my = ++reqSeq
  isLoading.value = true
  try {
    level.value = levelMode.value === 'auto' ? levelByZoom(map.getZoom()) : levelMode.value
    let bbox = ''
    if (!world.value) {
      const b = map.getBounds()
      bbox = `${b.getSouth().toFixed(4)},${b.getWest().toFixed(4)},${b.getNorth().toFixed(4)},${b.getEast().toFixed(4)}`
      bboxNote.value = 'обрезан картой'
    } else bboxNote.value = ''
    const d = await fetchGeoSales({
      date_from: filters.value.date_from, date_to: filters.value.date_to,
      q: filters.value.product || undefined,
      brand: filters.value.brand || undefined, category: filters.value.category || undefined,
      metric: metric.value, level: level.value, bbox, world: world.value,
      parent_country: crumbs.value.country || undefined,
      parent_okrug: crumbs.value.okrug || undefined,
      parent_region: crumbs.value.region || undefined,
      parent_city: crumbs.value.city || undefined,
      limit: 2000,
    })
    items.value = (d.items || []).filter((r: any) => r.lat != null && r.lon != null)
    total.value = d.total || { qty: 0, sum_for_pay: 0 }
    hint.value = (d as any).hint || ''
    resolvedIds.value = (d as any).params?.resolved_ids ?? null
    if (items.value.length >= 2000) hint.value = (hint.value ? hint.value + ' · ' : '') + 'показаны первые 2000 — приблизьте карту'
    if (my !== reqSeq) return // протухший ответ: новее запрос уже летит
    unhl()
    renderMarkers()
    void applyVisualCenters()
  } catch { /* noop: ошибка видна в консоли api */ }
  if (my === reqSeq) isLoading.value = false
}

const bubbleCls = (v: number, max: number) => !max ? 'geo-bubble--s1' : v > max * 0.5 ? 'geo-bubble--s4' : v > max * 0.2 ? 'geo-bubble--s3' : v > max * 0.05 ? 'geo-bubble--s2' : 'geo-bubble--s1'

const renderMarkers = () => {
  if (!map || !layer) return
  layer.clearLayers()
  const max = items.value.reduce((a, r) => Math.max(a, valOf(r)), 0)
  // «Без региона/города/округа» на карту не ставим: их центроид — среднее
  // по всей стране и вводит в заблуждение; в таблице и итогах они есть
  const dots = items.value.filter((r: any) => r.lat != null && r.lon != null
    && (level.value === 'country' || level.value === 'pvz' || !String(r.name || '').startsWith('Без '))).slice(0, 2000)
  for (const r of dots) {
    const ll: L.LatLngExpression = posOf(r)
    const popup = `<b>${r.name}</b>${r.sub ? '<br>' + r.sub : ''}<br>Продаж: <b>${fmt0(r.qty)}</b> · ПВЗ: <b>${fmt0(r.pvz_count)}</b><br>Цена со ск: <b>${fmt2(r.sum_amount)}</b> ₽<br>К оплате: ${fmt2(r.sum_for_pay)} ₽${world.value ? '' : '<br><small>в видимой области</small>'}`
    // тултип при наведении (кратко) + попап по клику (подробно)
    const tip = `<b>${r.name}</b>${r.sub ? ' · ' + r.sub : ''}<br>Продаж: <b>${fmt0(r.qty)}</b> · ПВЗ: <b>${fmt0(r.pvz_count)}</b> · Со ск: <b>${fmt2(r.sum_amount)}</b> ₽`
    // мелкие поверх крупных: zIndexOffset обратно значению
    const zOff = 1000 - Math.min(1000, Math.round(valOf(r)))
    if (level.value === 'pvz') {
      // больше 1 продажи — нумерованный бейдж, одиночные — точки
      if ((r.qty || 0) > 1) {
        const icon = L.divIcon({ className: 'geo-bubble-wrap', html: `<div class="geo-bubble geo-bubble--pvz">${metric.value === 'qty' ? fmt0(valOf(r)) : fmt0(valOf(r) / 1000) + 'к'}</div>`, iconSize: [28, 28], iconAnchor: [14, 14] })
        L.marker(ll, { icon, zIndexOffset: 2000 }).bindTooltip(tip, { sticky: true, direction: 'top' }).bindPopup(popup).addTo(layer)
        continue
      }
      const rad = 5 + (max ? 9 * Math.sqrt(valOf(r) / max) : 0)
      // микро-джиттер по хешу wb_id: дубли ПВЗ на одном адресе видно раздельно
      const h = [...r.key].reduce((a, c) => (a * 31 + c.charCodeAt(0)) | 0, 7)
      const jl: L.LatLngExpression = [Number(r.lat) + ((h % 7) - 3) * 0.0004, Number(r.lon) + ((Math.floor(h / 7) % 7) - 3) * 0.0004]
      L.circleMarker(jl, { radius: rad, color: '#7c1af8', weight: 2, fillColor: '#7c1af8', fillOpacity: 0.55 }).bindTooltip(tip, { sticky: true, direction: 'top' }).bindPopup(popup).addTo(layer)
    } else {
      const icon = L.divIcon({ className: 'geo-bubble-wrap', html: `<div class="geo-bubble ${bubbleCls(valOf(r), max)}">${metric.value === 'qty' ? fmt0(valOf(r)) : fmt0(valOf(r) / 1000) + 'к'}</div>`, iconSize: [70, 70], iconAnchor: [35, 35] })
      L.marker(ll, { icon, zIndexOffset: zOff }).bindTooltip(tip, { sticky: true, direction: 'top' }).bindPopup(popup)
        .on('click', () => drillDown(r))
        .on('mouseover', () => hlName(level.value === 'city' ? r.sub : r.name))
        .on('mouseout', unhl)
        .addTo(layer)
    }
  }
}

const drillDown = (r: any) => {
  if (!map) return
  const to = posOf(r)
  if (level.value === 'country') { crumbs.value = { country: r.key, okrug: '', region: '', city: '' }; map.flyTo(to, 5, { duration: 0.6 }) }
  else if (level.value === 'okrug') {
    if (String(r.key).startsWith('C:')) { crumbs.value = { country: String(r.key).slice(2), okrug: '', region: '', city: '' }; map.flyTo(to, 6, { duration: 0.6 }) }
    else { crumbs.value.okrug = r.name; crumbs.value.region = ''; crumbs.value.city = ''; map.flyTo(to, 7, { duration: 0.6 }) }
  }
  else if (level.value === 'region') { crumbs.value.region = r.name === 'Без региона' ? '__none__' : r.name; crumbs.value.city = ''; map.flyTo(to, 9, { duration: 0.6 }) }
  else if (level.value === 'city') { crumbs.value.city = r.name === 'Без города' ? '__none__' : r.name; map.flyTo(to, 11, { duration: 0.6 }) }
}

const goWorld = () => { crumbs.value = { country: '', okrug: '', region: '', city: '' }; if (map) { map.flyTo([56, 38], 3, { duration: 0.6 }); } fetchData() }
const goCountry = () => { crumbs.value.okrug = ''; crumbs.value.region = ''; crumbs.value.city = ''; if (map) map.setZoom(5); fetchData() }
const goOkrug = () => { crumbs.value.region = ''; crumbs.value.city = ''; if (map) map.setZoom(7); fetchData() }
const goRegion = () => { crumbs.value.city = ''; if (map) map.setZoom(9); fetchData() }

const focusRow = (r: any) => {
  if (!map || r.lat == null) return
  const to = posOf(r)
  const z = level.value === 'pvz' ? Math.max(map.getZoom(), 12) : map.getZoom()
  map.flyTo(to, z, { duration: 0.6 })
}

const exportExcel = async () => {
  if (!items.value.length) return
  const XLSX = await import('xlsx')
  const data = items.value.map((r: any) => ({
    [nameCol.value]: r.name, [subCol.value === '—' ? 'Страна' : subCol.value]: r.sub,
    'Кол-во': r.qty, 'Сумма, ₽': r.sum_retail, 'Цена со ск, ₽': r.sum_amount, 'СПП, %': r.spp, 'К оплате, ₽': r.sum_for_pay,
  }))
  const ws = XLSX.utils.json_to_sheet(data)
  ws['!cols'] = [{ wch: 30 }, { wch: 30 }, { wch: 10 }, { wch: 14 }, { wch: 14 }, { wch: 9 }, { wch: 14 }]
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, 'Гео')
  XLSX.writeFile(wb, `geo_${level.value}_${filters.value.date_from}_${filters.value.date_to}.xlsx`)
}

const onMoveEnd = () => {
  if (!inited) return
  if (map) zoom.value = map.getZoom()
  clearTimeout(moveTimer)
  moveTimer = setTimeout(fetchData, 350)
}

watch(() => route.query, () => {
  if (syncing) return
  const q: any = route.query
  const cur: any = {
    date_from: filters.value.date_from || '', date_to: filters.value.date_to || '',
    product: filters.value.product || '', brand: filters.value.brand || '',
    category: filters.value.category || '', metric: metric.value,
    lvl: levelMode.value === 'auto' ? '' : levelMode.value,
  }
  const changed = ['date_from', 'date_to', 'product', 'brand', 'category', 'metric', 'lvl']
    .some(k => String(q[k] || '') !== String(cur[k] || ''))
  let viewSame = true
  if (map && q.z !== undefined) {
    const c = map.getCenter()
    viewSame = Math.abs(c.lat - Number(q.lat)) < 1e-4
      && Math.abs(c.lng - Number(q.lon)) < 1e-4 && map.getZoom() === Number(q.z)
  }
  if (changed || !viewSame) {
    initFromQuery()
    if (map && pendingView) map.setView([pendingView.lat, pendingView.lon], pendingView.z)
    fetchData()
  }
})

onMounted(() => {
  if (!document.getElementById('geo-map')) return // контейнер всегда в DOM, страховка от HMR
  initFromQuery()
  if (pendingView) map = L.map('geo-map', { worldCopyJump: true }).setView([pendingView.lat, pendingView.lon], pendingView.z)
  else map = L.map('geo-map', { worldCopyJump: true }).setView([56, 38], 3)
  zoom.value = map.getZoom()
  const osm = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  })
  const sat = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 19, attribution: '&copy; <a href="https://www.esri.com">Esri</a>',
  })
  osm.addTo(map)
  L.control.layers({ 'Карта': osm, 'Спутник': sat }).addTo(map)
  L.control.scale({ imperial: false }).addTo(map)
  layer = L.layerGroup().addTo(map)
  map.on('moveend', onMoveEnd)
  map.on('zoomend', onMoveEnd)
  document.addEventListener('fullscreenchange', onFullChange)
  inited = true
  loadOptions()
  fetchData()
})
onBeforeUnmount(() => { clearTimeout(moveTimer); document.removeEventListener('fullscreenchange', onFullChange); unhl(); if (map) { map.off('moveend', onMoveEnd); map.off('zoomend', onMoveEnd); map.remove(); map = null } })
</script>
