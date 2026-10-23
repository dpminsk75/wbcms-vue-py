<template>
  <div class="wb-scard" :class="{ 'wb-scard--ours': card.is_ours }" @click="$emit('open', card)">
    <!-- фото во всю ширину блока; бейджи — поверх фото, снизу слева (как на WB) -->
    <div class="wb-scard__img">
      <img v-if="img" :src="img" :alt="card.title || ''" loading="lazy" />
      <div v-else class="wb-scard__noimg">без фото</div>

      <span class="wb-scard__pos">{{ card.position_api || card.position }}</span>
      <span v-if="card.is_ours" class="wb-scard__ours">наша</span>

      <div v-if="card.badges && card.badges.length" class="wb-scard__badges">
        <span
          v-for="(b, i) in card.badges"
          :key="i"
          class="wb-scard__badge"
          :class="badgeClass(b)"
        >{{ b }}</span>
      </div>
    </div>

    <div class="wb-scard__body">
      <div class="wb-scard__title">{{ card.title || ('nm ' + card.nm_id) }}</div>

      <div class="wb-scard__seller">{{ card.seller || card.brand || '—' }}</div>

      <div class="wb-scard__price">
        <b>{{ money(card.price) }}</b>
        <s v-if="card.old_price">{{ money(card.old_price) }}</s>
        <span v-if="!card.price && card.price_api" class="wb-scard__note">
          без кошелька: {{ money(card.price_api) }}
        </span>
      </div>

      <!-- звезда — это рейтинг отзывов (review_rating), а не средняя оценка товара:
           средняя у WB почти всегда 5, а рейтинг отзывов — 4.8/4.9 -->
      <div class="wb-scard__rating">
        <span v-if="rate" class="wb-scard__star">★</span>
        <span v-if="rate" class="wb-scard__rating-num">{{ rate }}</span>
        <span v-if="reviews">· {{ reviews }} отзывов</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useMoneyFmt } from '@/composables/useMoneyFmt'
import type { PositionsItem } from '@/api/competitorsPositions'

const props = defineProps<{ card: PositionsItem }>()
defineEmits<{ (e: 'open', card: PositionsItem): void }>()

const { fmt0 } = useMoneyFmt()

function money(v: any): string {
  if (v == null || v === '' || Number(v) === 0) return '—'
  return `${fmt0(v)} ₽`
}

/* Фото WB: в выдаче мы берём мелкий размер (c246x328) — для карточки enlarge'им
   до c516x688, иначе картинка мыльная. */
const img = computed(() => {
  const raw = props.card.image_url || ''
  if (!raw) return ''
  let u = raw.split('?')[0]
  u = u.replace(/\/images\/[^/]+\//, '/images/c516x688/')
  if (u.startsWith('//')) u = 'https:' + u
  return u
})

/* Бейджи WB: «−50%» — красный, «Хорошая цена» — жёлтый, «11.11» — розовый,
   «ПРЕМУМ…» — тёмный, «с кэшбэком» — фиолетовый. */
function badgeClass(b: string): string {
  const s = String(b || '').toLowerCase()
  if (/%/.test(s) || /^[-−]/.test(s)) return 'wb-scard__badge--sale'
  if (/кэшбэк|cashback/.test(s)) return 'wb-scard__badge--cash'
  if (/цена|выгод|дешев/.test(s)) return 'wb-scard__badge--price'
  if (/11\.11|черн|день|распродаж|акци/.test(s)) return 'wb-scard__badge--promo'
  if (/премиум|руководител|эксклюзив|вкус/.test(s)) return 'wb-scard__badge--vip'
  return 'wb-scard__badge--plain'
}

const rate = computed(() => props.card.review_rating ?? props.card.rating ?? null)
const reviews = computed(() => props.card.reviews ?? props.card.feedbacks ?? 0)
</script>

<style scoped>
/* Карточка товара — как на WB: фото во всю ширину блока, бейджи поверх фото,
   название целиком, продавец, крупная цена, рейтинг отзывов. */
.wb-scard {
  width: 210px;
  flex: 0 0 210px;
  border: 1px solid #e6e8ec;
  border-radius: 12px;
  background: #fff;
  overflow: hidden;
  cursor: pointer;
  display: flex;
  flex-direction: column;
}
.wb-scard:hover { border-color: #9db8e8; box-shadow: 0 3px 12px rgba(30, 64, 175, .1); }
.wb-scard--ours {
  border: 2px solid #1f6fd0;
  background: #f3f7ff;
}

.wb-scard__img {
  position: relative;
  width: 100%;
  aspect-ratio: 1 / 1;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.wb-scard__img img { width: 100%; height: 100%; object-fit: contain; }
.wb-scard__noimg { color: #b6bcc7; font-size: 13px; }

.wb-scard__pos {
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
.wb-scard__ours {
  position: absolute;
  top: 6px;
  right: 6px;
  padding: 1px 8px;
  border-radius: 6px;
  background: #1f6fd0;
  color: #fff;
  font-size: 12px;
}

/* бейджи — поверх фото, снизу слева */
.wb-scard__badges {
  position: absolute;
  left: 6px;
  bottom: 6px;
  right: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.wb-scard__badge {
  padding: 1px 7px;
  border-radius: 5px;
  font-size: 12px;
  line-height: 18px;
  font-weight: 600;
  background: #eef0f4;
  color: #4b5563;
}
.wb-scard__badge--sale { background: #e8344f; color: #fff; }
.wb-scard__badge--price { background: #ffcf3d; color: #4a3200; }
.wb-scard__badge--promo { background: #dd3a93; color: #fff; }
.wb-scard__badge--vip { background: #3d4451; color: #fff; }
.wb-scard__badge--cash { background: #7c3aed; color: #fff; }

.wb-scard__body { padding: 8px 10px 10px; display: flex; flex-direction: column; gap: 4px; }

.wb-scard__title {
  font-size: 14px;
  line-height: 18px;
  color: #1f2937;
  font-weight: 500;
  /* название целиком, без обрезки */
  overflow-wrap: anywhere;
}
.wb-scard__seller { font-size: 13px; color: #9ca3af; }
.wb-scard__price { font-size: 17px; color: #111827; font-weight: 700; }
.wb-scard__price s { color: #9ca3af; font-size: 13px; font-weight: 400; margin-left: 6px; }
.wb-scard__note { display: block; font-size: 12px; color: #9ca3af; font-weight: 400; }
.wb-scard__rating { font-size: 13px; color: #9ca3af; }
.wb-scard__star { color: #f59e0b; }
.wb-scard__rating-num { color: #374151; font-weight: 600; }
</style>
