import { api } from './client'

/** Полки и баджи НАШЕЙ карточки — /wb/detail → «Полки и баджи». */

/** Позиция в блоке WB (товар, который WB рекомендует рядом). */
export interface ShelfItem {
  nm_id: number
  position: number
  title: string
  brand: string
  seller: string
  price: number | null
  old_price: number | null
  rating: number | null
  review_rating: number | null
  feedbacks: number | null
  cashback: number | null
  is_new: number
  /** 1 = наша карточка (в блоке она помечена рамкой). */
  is_own: number
  image_url: string
  badges: string[]
}

/** Блок (полка) на карточке: «Смотрите также», «Продавец рекомендует». */
export interface ShelfBlock {
  shelf_id: number
  preset_id: number
  preset_type: string
  kind: string
  /** Подпись блока (из DOM страницы, иначе — из словаря пресетов). */
  title: string
  /** Подпись, выученная из DOM (пусто — если словарь). */
  title_fresh: string
  is_partial: number
  total_candidates: number | null
  last_seen_at: string | null
  /** Все даты срезов блока, свежие сверху. */
  dates: string[]
  /** Показанный срез. */
  date: string
  items_cnt: number
  items: ShelfItem[]
}

export interface OurCardData {
  nm_id: number
  title: string
  price: number | null
  old_price: number | null
  badges: string[]
  sold_out: number
  is_resale: number
  collected: boolean
  /** Полный сбор карточки расширением (не только лёгкая строка из выдачи). */
  full_collected: boolean
  collected_at: string | null
  in_queue: boolean
  queue_status: string
  blocks: ShelfBlock[]
}

/** Карточка конкурента, в чьей полке нас видели (наши собственные — нет). */
export interface ShelfAnchor {
  shelf_id: number
  anchor_nm: number
  /** Подпись полки, в которой нас видно («См. также»). */
  shelf_title: string
  preset_id: number
  kind: string
  /** Дата среза, в котором нас видели. */
  date: string
  /** Наша позиция в этой полке. */
  position: number
  title: string
  image_url: string
  badges: string[]
  price: number | null
  old_price: number | null
  seller: string
  brand: string
  rating: number | null
  review_rating: number | null
  feedbacks: number | null
}

export interface ShelfBlockData {
  shelf_id: number
  title: string
  preset_id: number
  anchor_nm: number
  anchor_title: string
  anchor_image_url: string
  dates: string[]
  date: string
  items: ShelfItem[]
}

/** Снимок набора бейджей карточки. */
export interface BadgeSnapshot {
  badges: string[]
  price: number | null
  at: string
}

export const ourCardApi = {
  /** Карточка: бейджи, цена, блоки полок. `date` — срез блоков. */
  card: (nmId: number, date?: string) =>
    api.get(`/api/wb/card/${nmId}/shelves`, { params: { date: date || undefined } })
      .then((r) => r.data as OurCardData),

  /** «Где мы на полках»: карточки конкурентов, в чьих полках нас видели. */
  where: (nmId: number, dateFrom: string, dateTo: string) =>
    api.get(`/api/wb/card/${nmId}/shelves/where`, { params: { date_from: dateFrom, date_to: dateTo } })
      .then((r) => r.data as { nm_id: number; date_from: string; date_to: string; items: ShelfAnchor[] }),

  /** Вся собранная полка конкурента (вложенная модалка). */
  block: (nmId: number, shelfId: number, date?: string) =>
    api.get(`/api/wb/card/${nmId}/shelves/block/${shelfId}`, { params: { date: date || undefined } })
      .then((r) => r.data as ShelfBlockData),

  /** История бейджей карточки. */
  badgeHistory: (nmId: number) =>
    api.get(`/api/wb/card/${nmId}/badges`)
      .then((r) => r.data as { nm_id: number; items: BadgeSnapshot[] }),

  /** Поставить карточку в очередь сбора. */
  collect: (nmId: number) =>
    api.post(`/api/wb/card/${nmId}/collect`)
      .then((r) => r.data as { ok: boolean; queued: boolean; status: string; detail?: string }),
}
