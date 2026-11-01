import type { PositionsItem } from '@/api/competitorsPositions'
import type { ShelfItem } from '@/api/ourCard'

/**
 * Мапперы строк разных источников в общий вид карточки `CompetitorCard`.
 *
 * Источники различаются полями (выдача WB против позиции полки), а карточка
 * одна — значит, приводить их к одному виду надо в одном месте.
 */
export interface CompetitorCardData {
  nmId: number
  title: string
  brand: string
  seller: string
  /** Тип/предмет — первая часть подписи. */
  subject?: string
  price: number | null
  oldPrice: number | null
  priceApi: number | null
  rating: number | null
  reviewRating: number | null
  reviews: number | null
  badges: string[]
  imageUrl: string
  position: number | null
  isOurs: boolean
  isNew: boolean
  /** Наша позиция в полке конкурента (только для полок). */
  ourPosition?: number | null
  /** Собрана ли карточка конкурента (есть запись в wb_competitor_details).
   *  null — неизвестно: подложку не красим. */
  collected?: boolean | null
  /** Дата среза полки. */
  snapDate?: string
  /** Подпись блока полки (например «Смотрите также»). */
  shelfTitle?: string
}

/** Собрана ли карточка конкурента: есть запись в `wb_competitor_details`.
 *
 *  `null` — неизвестно (флага нет): подложку не красим.
 *  Наши карточки не гасим никогда — в `wb_competitor_details` их нет.
 */
export function collectedFlag(
  isCollected?: number | null,
  isOurs?: boolean,
): boolean | null {
  if (isOurs) return null
  if (isCollected === undefined || isCollected === null) return null
  return !!isCollected
}

/** Строка выдачи WB (`/api/competitors/positions`). */
export function fromPositionsItem(it: PositionsItem): CompetitorCardData {
  return {
    nmId: it.nm_id,
    title: it.title || '',
    brand: it.brand || '',
    seller: it.seller || '',
    subject: it.subject_name || '',
    price: it.price ?? null,
    oldPrice: it.old_price ?? null,
    priceApi: it.price_api ?? null,
    rating: it.rating ?? null,
    reviewRating: it.review_rating ?? null,
    reviews: it.reviews ?? it.feedbacks ?? null,
    badges: it.badges || [],
    imageUrl: it.image_url || '',
    position: it.position_api ?? it.position ?? null,
    isOurs: !!it.is_ours,
    isNew: false,
    collected: collectedFlag(it.is_collected, !!it.is_ours),
  }
}

/** Позиция полки WB (`/api/wb/card/{nm}/shelves/...`). */
export function fromShelfItem(it: ShelfItem): CompetitorCardData {
  return {
    nmId: it.nm_id,
    title: it.title || '',
    brand: it.brand || '',
    seller: it.seller || '',
    price: it.price ?? null,
    oldPrice: it.old_price ?? null,
    priceApi: null,
    rating: it.rating ?? null,
    reviewRating: it.review_rating ?? null,
    reviews: it.feedbacks ?? null,
    badges: it.badges || [],
    imageUrl: it.image_url || '',
    position: it.position ?? null,
    isOurs: !!it.is_own,
    isNew: !!it.is_new,
  }
}
