import { api } from './client'

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
