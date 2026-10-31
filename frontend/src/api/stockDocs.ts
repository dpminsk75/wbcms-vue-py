// Документы склада (/wb-doc) — порт WbDocController

export type DocType = 'RECEIPT' | 'EXPENSE' | 'TRANSFER' | 'INVENTORY' | 'ADJUSTMENT'
export type DocStatus = 'draft' | 'posted' | 'canceled'

export const DOC_TYPES: { value: DocType, label: string }[] = [
  { value: 'RECEIPT', label: 'Приход' },
  { value: 'EXPENSE', label: 'Расход' },
  { value: 'TRANSFER', label: 'Перемещение' },
  { value: 'INVENTORY', label: 'Инвентаризация' },
  { value: 'ADJUSTMENT', label: 'Корректировка' },
]

export const DOC_STATUS_LABELS: Record<DocStatus, string> = {
  draft: 'Черновик',
  posted: 'Проведен',
  canceled: 'Отменен',
}

export interface DocItem {
  id?: number
  sku: string
  nm_id?: number | null
  chrt_id?: number | null
  qty: number
  qty_before?: number | null
  qty_fact?: number | null
  price?: number | null
  vendorCode?: string | null
  title?: string | null
}

export interface StockDoc {
  id: number
  company_id?: number
  type: DocType
  type_label: string
  status: DocStatus
  status_label: string
  warehouseId: number
  to_warehouseId?: number | null
  warehouse_name?: string | null
  to_warehouse_name?: string | null
  date: string
  comment?: string | null
  user_id?: number | null
  items_count?: number
  items?: DocItem[]
}

export interface WarehouseOption {
  id: number
  name: string
  code?: string | null
  is_central: number
  is_fbs: number
  is_active: number
}

export interface DocMeta {
  warehouses: WarehouseOption[]
  types: { value: DocType, label: string }[]
}

export interface DocListResponse {
  rows: StockDoc[]
  total: number
  page: number
  page_size: number
}

export interface ParseResponse {
  success: boolean
  matched: { sku: string, nm_id: number | null, chrt_id: number | null, qty: number }[]
  skipped: string[]
}
