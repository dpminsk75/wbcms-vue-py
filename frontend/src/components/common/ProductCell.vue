<template>
  <div class="prod-cell" :class="{ 'prod-cell--compact': compact }">
    <!-- Фото есть — картинка; фото нет — нейтральная заглушка (битой картинки с alt-текстом не показываем) -->
    <img v-if="photoUrl" class="prod-cell__img" :src="photoUrl" :alt="title || ''" loading="lazy" @error="onImgError" />
    <div v-else class="prod-cell__img prod-cell__img--none" aria-hidden="true"><i class="bi bi-image"></i></div>
    <div class="prod-cell__text">
      <!-- Плотный вариант: та же структура, что в обычной карточке, но мельче на 1px:
           название / «артикул • бренд • предмет» / ссылка WB -->
      <template v-if="compact">
        <div class="prod-cell__title" :title="fullTitle">{{ title || '(нет карточки)' }}</div>
        <div v-if="metaLine" class="prod-cell__sub">{{ metaLine }}</div>
        <a v-if="link" class="prod-cell__link" :href="link" target="_blank" rel="noopener">{{ linkLabel }}</a>
      </template>
      <template v-else>
        <div class="prod-cell__title" :title="title">{{ title || '(нет карточки)' }}</div>
        <div v-if="sub" class="prod-cell__sub">{{ sub }}</div>
        <div v-if="vendor" class="prod-cell__sub">{{ vendor }}</div>
        <a v-if="link" class="prod-cell__link" :href="link" target="_blank" rel="noopener">{{ linkLabel }}</a>
      </template>
    </div>
  </div>
</template>
<script setup lang="ts">
/**
 * Карточка товара в таблице — единый вывод для всех страниц.
 * Раньше каждая страница собирала его сама (`.fbs-product`, `.page-orders-feed__order`,
 * `.page-orders-feed-aggregated__order` …) и отдельно разбирала фото из JSON.
 */
import { computed, ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  /** Фото: URL, массив URL или JSON-строка (иногда дважды закодированная). */
  photo?: any
  /** Название товара. */
  title?: string
  /** Подпись под названием (бренд, предмет). */
  sub?: string
  /** Бренд — для плотного варианта (склеивается: название • бренд • предмет). */
  brand?: string
  /** Предмет — для плотного варианта. */
  subject?: string
  /** Плотный вариант: фото 30×40, кегль на 1px меньше обычного. */
  compact?: boolean
  /** Артикул продавца. */
  vendor?: string
  /** Ссылка на карточку WB. */
  link?: string
  /** Текст ссылки. */
  linkLabel?: string
  /** Картинка-заглушка (если файла нет — рисуем нейтральный блок). */
  fallback?: string
}>(), {
  photo: null,
  title: '',
  sub: '',
  brand: '',
  subject: '',
  compact: false,
  vendor: '',
  link: '',
  linkLabel: 'WB',
  fallback: '/images/no-photo.png',
})

const broken = ref(false)

/** Достаёт первый URL фото из строки/массива/JSON. Пусто — фото нет. */
function resolvePhoto(raw: any): string {
  try {
    let p: any = raw
    if (typeof p === 'string') p = JSON.parse(p)
    if (typeof p === 'string') p = JSON.parse(p)
    if (Array.isArray(p) && p[0]) {
      const first = p[0]
      if (typeof first === 'string') return first
      if (first && typeof first === 'object' && typeof first.photo === 'string') return first.photo
    }
    if (typeof p === 'string' && p) return p
  } catch {
    /* не JSON — считаем мусором */
  }
  return ''
}

const photoUrl = computed(() => (broken.value ? '' : resolvePhoto(props.photo)))

function onImgError(e: Event) {
  const el = e.target as HTMLImageElement
  if (el.src.endsWith(props.fallback)) { broken.value = true; return }
  broken.value = true
}

/**
 * Плотный вариант — та же структура, что в обычной карточке:
 *   название / «артикул продавца • бренд • предмет» / ссылка `WB: nm_id`.
 * Вторая строка — одной строкой (длинное обрезается многоточием).
 */
const metaLine = computed(() => {
  const parts: string[] = []
  if (props.vendor) parts.push(props.vendor)
  if (props.brand) parts.push(props.brand)
  if (props.subject) parts.push(props.subject)
  if (!parts.length && props.sub) parts.push(props.sub)
  return parts.join(' • ')
})

/** Полный текст карточки — в подсказке (в компакте всё не влезает в строку). */
const fullTitle = computed(() => {
  const parts = [props.title, metaLine.value].filter(Boolean)
  return parts.join(' — ')
})

watch(() => props.photo, () => { broken.value = false })
</script>
<style scoped>
.prod-cell { display: flex; gap: 10px; align-items: flex-start; }
.prod-cell__img {
  width: 50px; height: 66px; object-fit: cover;
  border-radius: var(--radius-sm); flex: none;
  border: 1px solid var(--line);
  background: var(--surface-2);
}
/* Нет фото — нейтральный блок вместо битой картинки */
.prod-cell__img--none {
  display: flex; align-items: center; justify-content: center;
  color: var(--ink-muted); font-size: 18px;
  background: color-mix(in srgb, var(--ink) 6%, var(--surface));
}
.prod-cell__text { min-width: 0; overflow: hidden; }
.prod-cell__title {
  font-weight: 700; font-size: calc(12.5px * var(--fs));
  color: var(--ink); line-height: 1.3;
  /* перенос по словам + обрезка с многоточием (как .product-name / .cart-item-title
     в оригинале): колонка не раздувает таблицу, длинное название не ломает строку.
     Без overflow-wrap: anywhere — слова не рвутся посредине, перенос идёт по пробелам. */
  display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 1;
  overflow: hidden;
}
.prod-cell__sub {
  font-size: calc(11px * var(--fs)); color: var(--ink-muted);
  display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 1;
  overflow: hidden;
}
.prod-cell__link {
  font-size: calc(11px * var(--fs)); font-weight: 600;
  color: var(--brand); text-decoration: none;
}
.prod-cell__link:hover { color: var(--brand-hover); text-decoration: underline; }

/* Плотный вариант: фото 30×40, кегль на 1px меньше обычного.
   Структура та же: название / «артикул • бренд • предмет» / ссылка WB.
   Высота строки падает с ~83px до ~60px — важно для широких реестров. */
.prod-cell--compact { gap: 8px; align-items: flex-start; }
.prod-cell--compact .prod-cell__img { width: 30px; height: 40px; font-size: 14px; }
.prod-cell--compact .prod-cell__title { font-size: calc(12px * var(--fs)); line-height: 1.3; }
.prod-cell--compact .prod-cell__sub { font-size: calc(11px * var(--fs)); }
.prod-cell--compact .prod-cell__link { font-size: calc(11px * var(--fs)); }
</style>
