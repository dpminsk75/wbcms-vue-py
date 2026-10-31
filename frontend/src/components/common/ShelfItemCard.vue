<template>
  <div class="wbsc" :class="{ 'wbsc--ours': item.is_own }">
    <div class="wbsc__img">
      <!-- draggable=false обязателен: иначе браузер начинает нативный drag
           картинки, перехватывает pointermove — и лента не скроллится мышью. -->
      <img v-if="img" :src="img" :alt="item.title || ''" loading="lazy" draggable="false" />
      <div v-else class="wbsc__noimg">без фото</div>

      <!-- наша позиция в чужой полке: клик по ней открывает полку -->
      <button
        v-if="ourPosition"
        type="button"
        class="wbsc__mpos"
        :title="`наша позиция в полке: ${ourPosition} — открыть полку`"
        @click.stop="$emit('open-position', item)"
      >{{ ourPosition }}</button>

      <div v-if="badges.length" class="wbsc__badges">
        <span v-for="(b, i) in badges" :key="i" class="wbsc__badge" :class="badgeClass(b)">{{ b }}</span>
      </div>
    </div>

    <div class="wbsc__body">
      <div v-if="item.price" class="wbsc__price">
        <b>{{ money(item.price) }}</b>
        <s v-if="item.old_price && item.old_price !== item.price">{{ money(item.old_price) }}</s>
      </div>
      <div v-if="item.seller" class="wbsc__seller">с {{ item.seller }}</div>
      <div v-if="brandLine" class="wbsc__brand">{{ brandLine }}</div>
      <div v-if="item.title" class="wbsc__title">{{ item.title }}</div>
      <div class="wbsc__rating">
        <span v-if="rate">★ {{ rate }}</span>
        <span v-if="reviews">· {{ reviews }} отзывов</span>
      </div>
      <div v-if="snapDate" class="wbsc__snap">срез {{ snapDate }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ShelfItem } from '@/api/ourCard'

/** Карточка позиции полки WB — вид как в блоке «Смотрите также» на WB.
 *
 *  Отличие от карточки выдачи (/seo-watch): подпись «наша» не рисуем —
 *  нашу карточку и так видно по синей рамке.
 */
const props = defineProps<{
  item: ShelfItem
  /** Наша позиция в полке конкурента (крупная цифра в углу). */
  ourPosition?: number | null
  /** Дата среза — под оценками. */
  snapDate?: string
  /** Подпись блока (например «Смотрите также») — строкой бренда. */
  shelfTitle?: string
}>()
defineEmits<{ (e: 'open-position', item: ShelfItem): void }>()

const img = computed(() => {
  const raw = props.item.image_url || ''
  if (!raw) return ''
  let u = raw.split('?')[0]
  u = u.replace(/\/images\/[^/]+\//, '/images/c516x688/')
  if (u.startsWith('//')) u = 'https:' + u
  return u
})

const rate = computed(() => props.item.review_rating ?? props.item.rating ?? null)
const reviews = computed(() => props.item.feedbacks ?? 0)
const brandLine = computed(() => (props.shelfTitle || props.item.brand || '').trim())

/** Бейджи позиции: из DOM полки («−48%», «за отзыв 200») + из реестра
 *  конкурентов («Хорошая цена» из выдачи). Если бейджа скидки нет (старые
 *  данные) — считаем скидку из цен. */
const badges = computed<string[]>(() => {
  const out: string[] = []
  for (const x of props.item.badges || []) {
    const s = String(x).trim();
    if (s && out.indexOf(s) < 0) out.push(s)
  }
  const hasSale = out.some((b) => /%/.test(b))
  const p = Number(props.item.price || 0)
  const b = Number(props.item.old_price || 0)
  if (!hasSale && p > 0 && b > p) {
    const pct = Math.round((1 - p / b) * 100)
    if (pct > 0) out.unshift(`−${pct}%`)
  }
  return out
})

function badgeClass(b: string): string {
  const s = String(b || '').toLowerCase()
  if (/ресейл|resale/.test(s)) return 'wbsc__badge--resale'
  if (/%/.test(s) || /^[-−]/.test(s)) return 'wbsc__badge--sale'
  if (/кэшбэк|cashback/.test(s)) return 'wbsc__badge--cash'
  if (/цена|выгод|дешев/.test(s)) return 'wbsc__badge--price'
  if (/11\.11|черн|день|распродаж|акци/.test(s)) return 'wbsc__badge--promo'
  if (/премиум|руководител|эксклюзив|вкус/.test(s)) return 'wbsc__badge--vip'
  return 'wbsc__badge--plain'
}

function money(v?: number | string | null): string {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  if (!isFinite(n)) return String(v)
  return `${n.toLocaleString('ru-RU')} ₽`
}
</script>

<style scoped>
/* Карточка товара в блоке WB: фото во всю ширину, бейджи поверх фото,
   цена красным, продавец, бренд/название, рейтинг. */
.wbsc {
  flex: 0 0 196px;
  width: 196px;
  border: 1px solid #e6e8ec;
  border-radius: 12px;
  background: #fff;
  overflow: hidden;
}
.wbsc--ours {
  border: 2px solid #1f6fd0;
}
.wbsc__img {
  position: relative;
  width: 100%;
  aspect-ratio: 1 / 1;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.wbsc__img img { width: 100%; height: 100%; object-fit: contain; }
.wbsc__noimg { color: #b6bcc7; font-size: 13px; }

/* наша позиция в полке конкурента — цифра размером с ценой (кликабельная) */
.wbsc__mpos {
  position: absolute;
  top: 6px;
  right: 6px;
  background: #fff;
  color: #1f6fd0;
  font-size: 14px;
  font-weight: 800;
  padding: 1px 8px;
  border-radius: 7px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, .18);
  border: 0;
  cursor: pointer;
}
.wbsc__mpos:hover { background: #1f6fd0; color: #fff; }

/* бейджи — поверх фото, снизу слева (как на WB) */
.wbsc__badges {
  position: absolute;
  left: 6px;
  bottom: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: flex-start;
  max-width: calc(100% - 12px);
}
.wbsc__badge {
  font-size: 11px;
  font-weight: 700;
  padding: 1px 7px;
  border-radius: 5px;
  color: #fff;
  background: #9aa1ad;
  white-space: nowrap;
}
.wbsc__badge--sale { background: #e8344f; }
.wbsc__badge--cash { background: #7d4bc4; }
.wbsc__badge--price { background: #e0a800; color: #3a2c00; }
.wbsc__badge--promo { background: #e04b8c; }
.wbsc__badge--vip { background: #2f3640; }
.wbsc__badge--resale { background: #8bf7d0; color: #063d2c; }
.wbsc__badge--plain { background: #eef1f6; color: #4b5563; }

.wbsc__body { padding: 8px 9px 11px; }
.wbsc__price { color: #c4122e; font-weight: 800; font-size: 14px; }
.wbsc__price s { color: #9ca3af; font-weight: 400; margin-left: 5px; font-size: 12px; }
.wbsc__seller { color: #c4122e; font-size: 11.5px; margin-top: 2px; }
.wbsc__brand {
  color: #9ca3af;
  font-size: 11px;
  text-transform: uppercase;
  margin-top: 5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.wbsc__title {
  color: #111827;
  font-size: 12.5px;
  margin-top: 1px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.wbsc__rating { color: #374151; font-size: 11.5px; margin-top: 5px; }
.wbsc__snap { color: #9ca3af; font-size: 11px; margin-top: 3px; }
</style>
