<template>
  <div
    class="cmp-card"
    :class="{
      'cmp-card--ours': isOurs,
      'cmp-card--new': isNew,
      'cmp-card--price': priceChanged,
      'cmp-card--shelf': variant === 'shelf',
      'cmp-card--shelves': variant === 'shelves',
    }"
    :style="{ width: widthPx + 'px', flex: `0 0 ${widthPx}px` }"
    @click="$emit('open')"
  >
    <!-- фото во всю ширину блока; в модалке «Где мы на полках» — квадрат с обрезкой -->
    <div class="cmp-card__img" :class="{ 'cmp-card__img--square': variant === 'shelves' }">
      <CardPhoto :src="imageUrl" :alt="title" :fit="variant === 'shelves' ? 'cover' : 'contain'" />

      <template v-if="variant !== 'shelves'">
        <span v-if="position" class="cmp-card__pos">{{ position }}</span>
        <span v-if="isOurs" class="cmp-card__ours">наша</span>
        <span v-if="isNew" class="cmp-card__new-badge">новинка</span>

        <!-- наша позиция в чужой полке: клик по ней открывает полку -->
        <button
          v-if="ourPosition"
          type="button"
          class="cmp-card__mpos"
          :title="`наша позиция в полке: ${ourPosition} — открыть полку`"
          @click.stop="$emit('open-position')"
        >{{ ourPosition }}</button>
      </template>

      <span
        v-if="variant === 'shelves' && ourPosition"
        class="cmp-card__mpos-round"
        :title="`наша позиция в полке: ${ourPosition} — открыть полку`"
        @click.stop="$emit('open-position')"
      >{{ ourPosition }}</span>

      <div v-if="badges.length" class="cmp-card__badges">
        <span
          v-for="(b, i) in badges"
          :key="i"
          class="cmp-card__badge"
          :class="badgeClass(b)"
        >{{ b }}</span>
      </div>
    </div>

    <div class="cmp-card__body">
      <!-- полка конкурента (блок у конкурента, вложенная модалка): цена сверху -->
      <template v-if="variant === 'shelf'">
        <div v-if="price" class="cmp-card__price">
          <b>{{ money(price) }}</b>
          <s v-if="oldPrice && !priceChanged">{{ money(oldPrice) }}</s>
          <span v-if="priceNote" class="cmp-card__note">{{ priceNote }}</span>
          <span v-if="priceChanged" class="cmp-card__price-change" :title="priceHint">
            {{ money(pricePrev) }} → {{ money(price) }} ({{ pricePctText }})
          </span>
        </div>
        <div v-if="seller" class="cmp-card__seller">с {{ seller }}</div>
        <div v-if="brandLine" class="cmp-card__brand">{{ brandLine }}</div>
        <div class="cmp-card__title" :title="fullTitle">{{ title || ('nm ' + nmId) }}</div>
        <div class="cmp-card__rating">
          <span v-if="rate">★ {{ rate }}</span>
          <span v-if="reviews">· {{ reviews }} отзывов</span>
        </div>
        <div v-if="snapDate" class="cmp-card__snap">срез {{ snapDate }}</div>
      </template>

      <!-- модалка «Полки и баджи» → «Где мы на полках»: название блока над товаром -->
      <template v-else-if="variant === 'shelves'">
        <div v-if="shelfTitle" class="cmp-card__shelfblock">{{ shelfTitle }}</div>
        <div class="cmp-card__title" :title="fullTitle">{{ title || ('nm ' + nmId) }}</div>
        <div v-if="snapDate" class="cmp-card__snap">срез {{ snapDate }}</div>
      </template>

      <!-- выдача (лента /seo-watch и /competitor/positions) -->
      <template v-else>
        <div class="cmp-card__title" :title="fullTitle">{{ title || ('nm ' + nmId) }}</div>

        <div v-if="seller" class="cmp-card__seller">{{ seller }}</div>
        <div v-if="brandLine" class="cmp-card__brand">{{ brandLine }}</div>

        <div class="cmp-card__price">
          <b>{{ money(price) }}</b>
          <s v-if="oldPrice && !priceChanged">{{ money(oldPrice) }}</s>
          <span v-if="priceNote" class="cmp-card__note">{{ priceNote }}</span>
          <!-- цена изменилась против прошлого захода: коротко, было/стало — в подсказке -->
          <span v-if="priceChanged" class="cmp-card__price-change" :title="priceHint">
            {{ money(pricePrev) }} → {{ money(price) }} ({{ pricePctText }})
          </span>
        </div>

        <!-- звезда — это рейтинг отзывов (review_rating), а не средняя оценка:
             средняя у WB почти всегда 5, а рейтинг отзывов — 4.8/4.9 -->
        <div class="cmp-card__rating">
          <span v-if="rate">★ {{ rate }}</span>
          <span v-if="reviews">· {{ reviews }} отзывов</span>
        </div>

        <div v-if="snapDate" class="cmp-card__snap">срез {{ snapDate }}</div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * Карточка товара WB (конкурента или наша) — общий компонент.
 *
 * Три варианта: `feed` (выдача, ~WbSearchCard), `shelf` (блок полки
 * конкурента, ~ShelfItemCard) и `shelves` (модалка «Полки и баджи» →
 * «Где мы на полках»: квадратное фото с обрезкой, синий круг позиции,
 * название блока над товаром). Фото идёт через общий `CardPhoto`.
 */
import { computed } from 'vue'
import CardPhoto from './CardPhoto.vue'
import { useMoneyFmt } from '@/composables/useMoneyFmt'

const props = withDefaults(defineProps<{
  /** Где показываем: выдача / блок полки / модалка «Где мы на полках». */
  variant?: 'feed' | 'shelf' | 'shelves'
  /** Артикул WB. */
  nmId: number
  title?: string
  brand?: string
  seller?: string
  price?: number | null
  oldPrice?: number | null
  /** Цена из WB API (когда основной цены нет — «без кошелька»). */
  priceApi?: number | null
  rating?: number | null
  /** Рейтинг отзывов (не путать с средней оценкой). */
  reviewRating?: number | null
  reviews?: number | null
  badges?: string[]
  imageUrl?: string
  /** Позиция в выдаче. */
  position?: number | null
  /** Наша карточка. */
  isOurs?: boolean
  /** Новая карточка в выдаче. */
  isNew?: boolean
  /** Цена изменилась против прошлого захода. */
  priceChanged?: boolean
  pricePrev?: number | null
  pricePct?: number | null
  /** Наша позиция в полке конкурента. */
  ourPosition?: number | null
  /** Дата среза (полка). */
  snapDate?: string
  /** Подпись блока полки (например «Смотрите также»). */
  shelfTitle?: string
  /** Ширина карточки, px (0 = свой размер варианта). */
  width?: number
}>(), {
  variant: 'feed',
  title: '',
  brand: '',
  seller: '',
  price: null,
  oldPrice: null,
  priceApi: null,
  rating: null,
  reviewRating: null,
  reviews: null,
  badges: () => [],
  imageUrl: '',
  position: null,
  isOurs: false,
  isNew: false,
  priceChanged: false,
  pricePrev: null,
  pricePct: null,
  ourPosition: null,
  snapDate: '',
  shelfTitle: '',
  width: 0,
})

defineEmits<{ (e: 'open'): void; (e: 'open-position'): void }>()

const { fmt0 } = useMoneyFmt()

/** Свой размер по умолчанию: полка сужается на 196px. */
const defaultWidth = computed(() =>
  props.variant === 'shelf' ? 196 : props.variant === 'shelves' ? 250 : 210,
)
const widthPx = computed(() => props.width || defaultWidth.value)

function money(v: number | null | undefined): string {
  if (v === null || v === undefined || Number(v) === 0) return '—'
  return `${fmt0(v)} ₽`
}

const rate = computed(() => props.reviewRating ?? props.rating ?? null)

const brandLine = computed(() => (props.shelfTitle || props.brand || '').trim())

/** Полный текст названия — в подсказке, если обрезано до 2 строк. */
const fullTitle = computed(() => props.title || `nm ${props.nmId}`)

const priceNote = computed(() => {
  if (props.price && Number(props.price) !== 0) return ''
  if (props.priceApi && Number(props.priceApi) !== 0) return `без кошелька: ${money(props.priceApi)}`
  return ''
})

const pricePctText = computed(() => {
  const p = props.pricePct
  if (p === null || p === undefined) return ''
  return `${p > 0 ? '+' : ''}${Number(p).toFixed(1).replace('.', ',')}%`
})

const priceHint = computed(() => {
  if (props.pricePrev === null || props.pricePrev === undefined) return 'Цена изменилась'
  return `Было ${money(props.pricePrev)}, стало ${money(props.price)}`
})

/* Бейджи WB: «−50%» — красный, «Хорошая цена» — жёлтый, «11.11» — розовый,
   «ПРЕМУМ…» — тёмный, «с кэшбэком» — фиолетовый, «ресейл» — мятный. */
function badgeClass(b: string): string {
  const s = String(b || '').toLowerCase()
  if (/ресейл|resale/.test(s)) return 'cmp-card__badge--resale'
  if (/%/.test(s) || /^[-−]/.test(s)) return 'cmp-card__badge--sale'
  if (/кэшбэк|cashback/.test(s)) return 'cmp-card__badge--cash'
  if (/цена|выгод|дешев/.test(s)) return 'cmp-card__badge--price'
  if (/11\.11|черн|день|распродаж|акци/.test(s)) return 'cmp-card__badge--promo'
  if (/премиум|роводител|эксклюзив|вкус/.test(s)) return 'cmp-card__badge--vip'
  return 'cmp-card__badge--plain'
}
</script>

<style scoped>
/* Карточка товара — как на WB: фото во всю ширину блока, бейджи поверх фото,
   название двумя строками, продавец, крупная цена, рейтинг отзывов. */
.cmp-card {
  border: 1px solid #e6e8ec;
  border-radius: 12px;
  background: #fff;
  overflow: hidden;
  cursor: pointer;
  display: flex;
  flex-direction: column;
}
.cmp-card:hover { border-color: #9db8e8; box-shadow: 0 3px 12px rgba(30, 64, 175, .1); }
/* «Наша» — постоянный ориентир: авточная синяя рамка БЕЗ заливки, чтобы не
   спорить с «новой» за внимание (у той свой цвет). */
.cmp-card--ours { border: 2px solid #1f6fd0; }
/* Новая карточка в выдаче: ЗЕЛЁНАЯ рамка 2px (влетело в выдачу = рост), чтобы
   не сливалась с синей «нашей» и розовыми скидочными бейджами на фото */
.cmp-card--new { border: 2px solid #16a34a; }
/* и наша, и новенькая: зелёная рамка побеждает, «наша» видна бейджем */
.cmp-card--new.cmp-card--ours { border: 2px solid #16a34a; }
/* модалка «Полки и баджи»: клик не на всю карточку, а только на круг позиции */
.cmp-card--shelves { cursor: pointer; }

.cmp-card__img {
  position: relative;
  width: 100%;
  /* 3:4 — родной кадр WB (516×688): фото заполняет рамку, полей и обрезки нет */
  aspect-ratio: 3 / 4;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
/* вариант модалки «Где мы на полках» — квадрат с обрезкой, как в бою */
.cmp-card__img--square { aspect-ratio: 1 / 1; }

.cmp-card__pos {
  position: absolute;
  top: 6px;
  left: 6px;
  min-width: 22px;
  padding: 1px 6px;
  border-radius: 6px;
  background: rgba(17, 24, 39, .78);
  color: #fff;
  font-size: 12px;
  text-align: center;
}
.cmp-card__ours {
  position: absolute;
  top: 6px;
  right: 6px;
  padding: 1px 8px;
  border-radius: 6px;
  background: #1f6fd0;
  color: #fff;
  font-size: 12px;
}
/* «новинка» в выдаче — зелёная, в тон рамки «новой» карточки */
.cmp-card__new-badge {
  position: absolute;
  top: 6px;
  right: 6px;
  padding: 1px 8px;
  border-radius: 6px;
  background: #16a34a;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
}
.cmp-card--ours .cmp-card__new-badge { right: 58px; }

/* наша позиция в полке конкурента — цифра размером с ценой (кликабельная) */
.cmp-card__mpos {
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
.cmp-card__mpos:hover { background: #1f6fd0; color: #fff; }
/* в модалке «Где мы на полках» — синий круг (как в бою) */
.cmp-card__mpos-round {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #1f6fd0;
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 1px 4px rgba(0, 0, 0, .18);
}
.cmp-card__mpos-round:hover { background: #124b96; }

/* бейджи — поверх фото, снизу слева; в модалке — столбиком (как в бою) */
.cmp-card__badges {
  position: absolute;
  left: 6px;
  bottom: 6px;
  right: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.cmp-card--shelves .cmp-card__badges {
  flex-direction: column;
  align-items: flex-start;
}
.cmp-card__badge {
  padding: 1px 7px;
  border-radius: 5px;
  font-size: 12px;
  line-height: 18px;
  font-weight: 600;
  background: #eef0f4;
  color: #4b5563;
}
.cmp-card__badge--sale { background: #e8344f; color: #fff; }
.cmp-card__badge--price { background: #ffcf3d; color: #4a3200; }
.cmp-card__badge--promo { background: #dd3a93; color: #fff; }
.cmp-card__badge--vip { background: #3d4451; color: #fff; }
.cmp-card__badge--cash { background: #7c3aed; color: #fff; }
/* Ресейл (товар от частного лица) — мятный, чтобы сразу видеть: это не наш
   конкурент, карточку не собираем. */
.cmp-card__badge--resale { background: #8bf7d0; color: #063d2c; }

.cmp-card__body { padding: 8px 10px 10px; display: flex; flex-direction: column; gap: 4px; }

.cmp-card__title {
  font-size: 14px;
  line-height: 18px;
  color: #1f2937;
  font-weight: 500;
  /* две строки + многоточие; полный текст — в title-подсказке */
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  overflow-wrap: anywhere;
}
.cmp-card__seller { font-size: 13px; color: #9ca3af; }
.cmp-card__brand {
  font-size: 11px;
  color: #9ca3af;
  text-transform: uppercase;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* название блока полки над товаром — в модалке «Где мы на полках» */
.cmp-card__shelfblock {
  font-size: 11px;
  color: #9ca3af;
  text-transform: uppercase;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cmp-card__price { font-size: 17px; color: #111827; font-weight: 700; }
.cmp-card__price s { color: #9ca3af; font-size: 13px; font-weight: 400; margin-left: 6px; }
.cmp-card__note { display: block; font-size: 12px; color: #9ca3af; font-weight: 400; }
/* изменилась цена — оранжевым */
.cmp-card--price .cmp-card__price b { color: #ea580c; }
.cmp-card__price-change {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #ea580c;
}
.cmp-card__rating { font-size: 13px; color: #9ca3af; }
/* дата среза — синяя: служебная строка, а не продолжение рейтинга */
.cmp-card__snap { font-size: 11px; color: #1f6fd0; }
</style>
