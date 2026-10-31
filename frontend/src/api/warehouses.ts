// Справочник своих складов (our_warehouse) — /wb-warehouses

export interface Warehouse {
  id: number
  company_id: number
  name: string
  code: string | null
  is_central: number
  is_fbs: number
  consider_orders: number
  is_active: number
  address: string | null
}

export interface WarehousesResponse {
  rows: Warehouse[]
  central_id: number | null
  fbs_id: number | null
  company_id: number | null
}

export const WAREHOUSE_TOGGLES = ['is_central', 'is_fbs', 'consider_orders', 'is_active'] as const
export type WarehouseToggle = typeof WAREHOUSE_TOGGLES[number]

export const TOGGLE_LABELS: Record<WarehouseToggle, string> = {
  is_central: 'Центральный',
  is_fbs: 'FBS (оперативный)',
  consider_orders: 'Учитывать заказы',
  is_active: 'Активен',
}
