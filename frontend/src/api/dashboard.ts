/**
 * API клиент — замена Yii2 Url::to(['/site/dashboard-*']) из index_dashboard.php:58
 * Используется TanStack Query в компонентах
 */
import { api } from './client'

export type Period = 'today'|'yesterday'|'week_to_date'|'last_week'|'month_to_date'|'last_month'

export interface PeriodStats {
  granularity: 'hour'|'day'
  categories: string[]
  seriesMeta: {key:string, name:string}[]
  series: Record<string, {category:string, sum:number, cnt:number, spp:number, date?:string}[]>
  totals: Record<string, {cnt:number, sum:number, spp:number}>
  axisCaption?: string
}

export const dashboardApi = {
  shell: (p:{dateFrom?:string,dateTo?:string}) => api.get('/api/dashboard/shell', {params:p}).then(r=>r.data),
  topMetrics: () => api.get('/api/dashboard/top-metrics').then(r=>r.data),
  adv: (p:{dateFrom:string,dateTo:string}) => api.get('/api/dashboard/adv', {params:p}).then(r=>r.data),
  ordersSummary: () => api.get('/api/dashboard/orders-summary').then(r=>r.data),
  lastOrders: (p:{dateFrom:string,dateTo:string,page?:number}) => api.get('/api/dashboard/last-orders', {params:p}).then(r=>r.data),
  lastSales: (p:{dateFrom:string,dateTo:string}) => api.get('/api/dashboard/last-sales', {params:p}).then(r=>r.data),
  monthly: (refresh?:boolean) => api.get('/api/dashboard/monthly-finance', {params:{refresh: refresh?1:0}}).then(r=>r.data),
  todayStats: (period:Period, tab:'orders'|'sales') => api.get<PeriodStats>('/api/dashboard/today-stats', {params:{period,tab}}).then(r=>r.data),
  newCards: (p:{dateFrom?:string,dateTo?:string,title?:string,sort?:string}) => api.get('/api/dashboard/new-cards', {params:p}).then(r=>r.data),
  ordersFeed: (p:{nm_id?:number,date_from:string,date_to:string,status?:string,warehouse_name?:string,region_name?:string,page?:number}) => api.get('/api/orders/feed', {params:p}).then(r=>r.data),
  ordersFeedOptions: (p:any) => api.get('/api/orders/feed/options', {params:p}).then(r=>r.data),
  menu: (type:'top'|'side', role?:string) => api.get('/api/menu', {params:{type, role}}).then(r=>r.data),
  menuRaw: () => api.get('/api/config/menu').then(r=>r.data),
  saveMenu: (data:any[]) => api.put('/api/config/menu', data).then(r=>r.data),
  quickButtons: () => api.get('/api/config/quick-buttons').then(r=>r.data),
  saveQuickButtons: (items:any[]) => api.put('/api/config/quick-buttons', items).then(r=>r.data),
  wbCards: (q:string, limit?:number) => api.get('/api/wb/cards', {params:{q, limit: limit||50}}).then(r=>r.data),
  icons: () => api.get('/api/config/icons').then(r=>r.data),
}
