import { api } from './client'

export interface WbSaleRow {
  saleID: string
  date: string | null
  nmId: number | null
  supplierArticle: string | null
  cardTitle: string | null
  totalPrice: number | null
  discountPercent: number | null
  priceWithDisc: number | null
  spp: number | null
  finishedPrice: number | null
  forPay: number | null
  warehouseName: string | null
  warehouseType: string | null
  countryName: string | null
  oblastOkrugName: string | null
  regionName: string | null
  [k: string]: unknown
}

export interface WbSaleListParams {
  date_from?: string
  date_to?: string
  nm_id?: number
  income_id?: number
  is_supply?: number | string
  is_realization?: number | string
  total_price?: number
  finished_price?: number
  sale_id?: string
  srid?: string
  number?: string
  supplier_article?: string
  barcode?: string
  warehouse_name?: string
  warehouse_type?: string
  country_name?: string
  oblast_name?: string
  region_name?: string
  subject?: string
  category?: string
  brand?: string
  card_title?: string
  geo?: string
  sort?: string
  page?: number
  page_size?: number
}

export const wbSalesApi = {
  async list(params: WbSaleListParams): Promise<{ items: WbSaleRow[]; total: number; page: number; page_size: number }> {
    const { data } = await api.get('/api/wb-sales', { params })
    return data
  },
  async get(saleID: string): Promise<WbSaleRow> {
    const { data } = await api.get(`/api/wb-sales/${encodeURIComponent(saleID)}`)
    return data
  },
}
