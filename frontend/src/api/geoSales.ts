import { api } from './client'

// Стем как в бэке (_stem): нижний регистр, ё→е, минус служебные слова.
// Алиасы — расхождения Click-That-Hood (2013) с каноникой: прилагательное
// («Кабардино-Балкарская республика») против существительного («Кабардино-Балкария»).
const GEO_DROP = new Set(['область', 'обл', 'край', 'республика', 'респ',
  'автономный', 'автономная', 'ао', 'округ'])
const GEO_ALIASES: Record<string, string> = {
  'кабардино балкарская': 'кабардино балкария',
  'карачаево черкесская': 'карачаево черкесия',
  'саха якутия': 'якутия',
  'северная осетия алания': 'северная осетия',
  'удмуртская': 'удмуртия',
  'чувашская': 'чувашия',
  'чеченская': 'чечня',
  // новые нормы бэка (полные формы) против старых названий в GeoJSON 2013г
  'ханты мансийский югра': 'ханты мансийский',
  'еврейская': 'еврейская автономная',
}

export function geoStem(s: string): string {
  const toks = (s || '').toLowerCase().replace(/ё/g, 'е').split(/[^a-zа-я0-9]+/u)
    .filter(t => t && !GEO_DROP.has(t))
  const j = toks.join(' ')
  return GEO_ALIASES[j] || j
}

// GADM (BY/KZ): точное имя из файла + тип -> русское название как в отчете.
// Читается буквально: 'Minsk|City' -> 'Минск', 'Minsk|Oblast' -> 'Минская область'.
// Дальше сравнение идет по стемам (geoStem с обеих сторон), так что мелкие
// расхождения ('Могилевская'/'Могилёвская') не страшны.
const GADM_RU: Record<string, string> = {
  'Brest|Oblast': 'Брестская область',
  'Gomel|Oblast': 'Гомельская область',
  'Grodno|Oblast': 'Гродненская область',
  'Minsk|Oblast': 'Минская область',
  'Minsk|City': 'Минск',
  'Mogilev|Oblast': 'Могилевская область',
  'Vitebsk|Oblast': 'Витебская область',
  'Almaty': 'Алматинская область',
  'Aqmola': 'Акмолинская область',
  'Aqtöbe': 'Актюбинская область',
  'Atyrau': 'Атырауская область',
  'EastKazakhstan': 'Восточно-Казахстанская область',
  'Mangghystau': 'Мангистауская область',
  'NorthKazakhstan': 'Северо-Казахстанская область',
  'Pavlodar': 'Павлодарская область',
  'Qaraghandy': 'Карагандинская область',
  'Qostanay': 'Костанайская область',
  'Qyzylorda': 'Кызылординская область',
  // GADM 4.1 старый: SouthKazakhstan = нынешние Туркестанская обл + Шымкент.
  // Подсветка приблизительная (больше реальных границ), города Шымкент в файле нет.
  'SouthKazakhstan': 'Туркестанская область',
  'WestKazakhstan': 'Западно-Казахстанская область',
  'Zhambyl': 'Жамбылская область',
  // AM: марзы + Ереван (город с полигоном — матчится).
  'Aragatsotn': 'Арагацотнская область',
  'Ararat': 'Араратская область',
  'Armavir': 'Армавирская область',
  'Erevan': 'Ереван',
  'Gegharkunik': 'Гехаркуникская область',
  'Kotayk': 'Котайская область',
  'Lori': 'Лорийская область',
  'Shirak': 'Ширакская область',
  'Syunik': 'Сюникская область',
  'Tavush': 'Тавушская область',
  'VayotsDzor': 'Вайоцдзорская область',
  // GE.
  'Abkhazia': 'Абхазия',
  'Ajaria': 'Аджария',
  'Guria': 'Гурия',
  'Imereti': 'Имеретия',
  'Kakheti': 'Кахетия',
  'KvemoKartli': 'Квемо-Картли',
  'Mtskheta-Mtianeti': 'Мцхета-Мтианети',
  'Racha-Lechkhumi-KvemoSvaneti': 'Рача-Лечхуми и Квемо-Сванети',
  'Samegrelo-ZemoSvaneti': 'Самегрело-Земо Сванети',
  'Samtskhe-Javakheti': 'Самцхе-Джавахети',
  'ShidaKartli': 'Шида-Картли',
  'Tbilisi': 'Тбилиси',
  // KG: города без полигонов (Бишкек, Ош) тихо пропускаются.
  'Batken': 'Баткенская область',
  'Biškek': 'Бишкек',
  'Chüy': 'Чуйская область',
  'Jalal-Abad': 'Джалал-Абадская область',
  'Naryn': 'Нарынская область',
  'Osh': 'Ошская область',
  'Talas': 'Таласская область',
  'Ysyk-Köl': 'Иссык-Кульская область',
  // TJ.
  'DistrictsofRepublicanSubordin': 'Районы республиканского подчинения',
  'Dushanbe': 'Душанбе',
  'Gorno-Badakhshan': 'Горно-Бадахшанская автономная область',
  'Khatlon': 'Хатлонская область',
  'Sughd': 'Согдийская область',
  // UZ: Ташкент-город с полигоном (ToshkentShahri), область — Toshkent.
  'Andijon': 'Андижанская область',
  'Buxoro': 'Бухарская область',
  "Farg'ona": 'Ферганская область',
  'Jizzax': 'Джизакская область',
  'Namangan': 'Наманганская область',
  'Navoiy': 'Навоийская область',
  'Qaraqalpaqstan': 'Республика Каракалпакстан',
  'Qashqadaryo': 'Кашкадарьинская область',
  "Samarqand'": 'Самаркандская область',
  'Sirdaryo': 'Сырдарьинская область',
  'Surxondaryo': 'Сурхандарьинская область',
  'Toshkent': 'Ташкентская область',
  'ToshkentShahri': 'Ташкент',
  'Xorazm': 'Хорезмская область',
  // Новых областей (Абайская, Жетысу, Улытауская) и городов (Астана, Алматы, Шымкент)
  // в файле нет — для них тихо ничего не подсвечиваем.
};

export function gadmCanon(props: any): string {
  const n = String(props?.NAME_1 || ''), t = String(props?.TYPE_1 || '')
  return GADM_RU[n + '|' + t] ?? GADM_RU[n] ?? ''
}

// Округ -> названия регионов. Формы — как НОРМЫ бэка (полные: «Ханты-Мансийский
// автономный округ»), сравнение через geoStem, варианты схлопываются.
export const OKRUG_REGIONS: Record<string, string[]> = {
  'Центральный ФО': ['Белгородская область', 'Брянская область', 'Владимирская область',
    'Воронежская область', 'Ивановская область', 'Калужская область', 'Костромская область',
    'Курская область', 'Липецкая область', 'Москва', 'Московская область', 'Орловская область',
    'Рязанская область', 'Смоленская область', 'Тамбовская область', 'Тверская область',
    'Тульская область', 'Ярославская область'],
  'Северо-Западный ФО': ['Карелия', 'Коми', 'Архангельская область', 'Вологодская область',
    'Калининградская область', 'Ленинградская область', 'Мурманская область',
    'Новгородская область', 'Псковская область', 'Санкт-Петербург', 'Ненецкий АО'],
  'Южный ФО': ['Адыгея', 'Калмыкия', 'Республика Крым', 'Краснодарский край',
    'Астраханская область', 'Волгоградская область', 'Ростовская область', 'Севастополь'],
  'Северо-Кавказский ФО': ['Дагестан', 'Ингушетия', 'Кабардино-Балкария', 'Карачаево-Черкесия',
    'Северная Осетия', 'Чечня', 'Ставропольский край'],
  'Приволжский ФО': ['Башкортостан', 'Марий Эл', 'Мордовия', 'Татарстан', 'Удмуртия', 'Чувашия',
    'Кировская область', 'Нижегородская область', 'Оренбургская область', 'Пензенская область',
    'Пермский край', 'Самарская область', 'Саратовская область', 'Ульяновская область'],
  'Уральский ФО': ['Курганская область', 'Свердловская область', 'Тюменская область',
    'Челябинская область', 'Ханты-Мансийский автономный округ', 'Ямало-Ненецкий автономный округ'],
  'Сибирский ФО': ['Республика Алтай', 'Алтайский край', 'Иркутская область', 'Кемеровская область',
    'Красноярский край', 'Новосибирская область', 'Омская область', 'Томская область',
    'Тыва', 'Хакасия'],
  'Дальневосточный ФО': ['Бурятия', 'Якутия', 'Забайкальский край', 'Камчатский край',
    'Приморский край', 'Хабаровский край', 'Амурская область', 'Магаданская область',
    'Сахалинская область', 'Еврейская автономная область', 'Чукотский АО'],
}

export function okrugStems(okrug: string): Set<string> {
  return new Set((OKRUG_REGIONS[okrug] || []).map(geoStem))
}

// Центр видимости полигона (упрощенный polylabel): самая внутренняя точка —
// гарантированно внутри контура, в отличие от центроида (у вогнутых областей
// вроде Актюбинской тот падает за границу). Только внешние кольца, без дыр.
export function visualCenter(feature: any): [number, number] | null {
  const geom = feature?.geometry
  const polys: number[][][] = geom?.type === 'Polygon' ? [geom.coordinates[0]]
    : geom?.type === 'MultiPolygon' ? geom.coordinates.map((p: any) => p[0]) : []
  let rings = polys.filter(r => r && r.length > 2)
  if (!rings.length) return null
  // Антимеридиан (Чукотка): разворачиваем -180..180 в непрерывную шкалу,
  // иначе середина bbox падает в Атлантику. В конце сворачиваем обратно.
  let shift = false
  {
    let ax0 = 180, ax1 = -180
    for (const r of rings) for (const p of r) {
      if (p[0] < ax0) ax0 = p[0]
      if (p[0] > ax1) ax1 = p[0]
    }
    if (ax1 - ax0 > 180) {
      shift = true
      rings = rings.map(r => r.map(p => [p[0] < 0 ? p[0] + 360 : p[0], p[1]]))
    }
  }
  const boxes = rings.map(r => {
    let a0 = 1e9, b0 = 1e9, a1 = -1e9, b1 = -1e9
    for (const p of r) {
      if (p[0] < a0) a0 = p[0]
      if (p[0] > a1) a1 = p[0]
      if (p[1] < b0) b0 = p[1]
      if (p[1] > b1) b1 = p[1]
    }
    return [a0, b0, a1, b1]
  })
  let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9
  for (const b of boxes) {
    if (b[0] < x0) x0 = b[0]
    if (b[2] > x1) x1 = b[2]
    if (b[1] < y0) y0 = b[1]
    if (b[3] > y1) y1 = b[3]
  }
  const segD = (px: number, py: number, ax: number, ay: number, bx: number, by: number) => {
    const dx = bx - ax, dy = by - ay
    const t = dx === 0 && dy === 0 ? 0 : Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return Math.hypot(px - (ax + dx * t), py - (ay + dy * t))
  }
  const minD = (px: number, py: number) => {
    let m = Infinity
    for (const r of rings) for (let i = 0; i < r.length; i++) {
      const a = r[i], b = r[(i + 1) % r.length]
      const d = segD(px, py, a[0], a[1], b[0], b[1])
      if (d < m) m = d
    }
    return m
  }
  const inRing = (px: number, py: number, r: number[][], b: number[]) => {
    if (px < b[0] || px > b[2] || py < b[1] || py > b[3]) return false
    let ins = false
    for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
      const xi = r[i][0], yi = r[i][1], xj = r[j][0], yj = r[j][1]
      if ((yi > py) !== (yj > py) && px < ((xj - xi) * (py - yi)) / (yj - yi + 1e-12) + xi) ins = !ins
    }
    return ins
  }
  const insideAny = (px: number, py: number) => rings.some((r, k) => inRing(px, py, r, boxes[k]))
  let bx = (x0 + x1) / 2, by = (y0 + y1) / 2
  let bd = insideAny(bx, by) ? minD(bx, by) : -1
  let step = Math.max(x1 - x0, y1 - y0) / 16
  // NB1: сетка раунда заякорена на центр (nbx/nby отдельно) — иначе hill-climbing
  // с движущимся центром уходит в бесконечность (дальше от границы = «лучше»).
  // NB2: точки клипятся bbox'ом и обязаны лежать внутри колец — иначе выигрывают
  // далекие точки за границей и море между островами.
  for (let round = 0; round < 3; round++) {
    let nbx = bx, nby = by, nbd = bd
    for (let ix = -8; ix <= 8; ix++) for (let iy = -8; iy <= 8; iy++) {
      const px = bx + ix * step, py = by + iy * step
      if (px < x0 || px > x1 || py < y0 || py > y1) continue
      if (!insideAny(px, py)) continue
      const d = minD(px, py)
      if (d > nbd) { nbd = d; nbx = px; nby = py }
    }
    bx = nbx; by = nby; bd = nbd
    step /= 8
  }
  if (bd < 0) return null
  if (shift && bx > 180) bx -= 360
  return [by, bx]
}

export interface GeoSalesItem {
  key: string
  name: string
  sub: string
  addr: string
  lat: number | null
  lon: number | null
  qty: number
  sum_retail: number
  sum_amount: number
  sum_for_pay: number
  spp: number
  pvz_count: number
}

export interface GeoSalesParams {
  date_from: string
  date_to: string
  nm_id?: string
  q?: string
  brand?: string
  category?: string
  metric: 'qty' | 'sum'
  level: 'country' | 'okrug' | 'region' | 'city' | 'pvz'
  bbox?: string
  world?: boolean
  parent_country?: string
  parent_okrug?: string
  parent_region?: string
  parent_city?: string
  limit?: number
}

export async function fetchGeoSales(p: GeoSalesParams) {
  const q = new URLSearchParams({
    date_from: p.date_from,
    date_to: p.date_to,
    metric: p.metric,
    level: p.level,
  })
  if (p.nm_id) q.set('nm_id', p.nm_id)
  if (p.q) q.set('q', p.q)
  if (p.brand) q.set('brand', p.brand)
  if (p.category) q.set('category', p.category)
  if (p.bbox && !p.world) q.set('bbox', p.bbox)
  if (p.world) q.set('world', 'true')
  if (p.parent_country) q.set('parent_country', p.parent_country)
  if (p.parent_okrug) q.set('parent_okrug', p.parent_okrug)
  if (p.parent_region) q.set('parent_region', p.parent_region)
  if (p.parent_city) q.set('parent_city', p.parent_city)
  if (p.limit) q.set('limit', String(p.limit))
  const { data } = await api.get(`/api/geo/sales-map?${q}`)
  return data as { level: string; metric: string; items: GeoSalesItem[]; total: any; bbox_applied: boolean }
}
