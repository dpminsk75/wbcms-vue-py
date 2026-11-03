<template>
  <div class="prod-cell" :class="{ 'prod-cell--compact': compact }">
    <!-- Фото — через общий CardPhoto: локальная копия робота (/api/img), нет копии — 302 на WB.
         Формат источника (URL / массив / JSON) разбирает сам CardPhoto. -->
    <div class="prod-cell__img">
      <CardPhoto :src="photo" :alt="title || ''" fit="cover" :placeholder="fallback" />
    </div>
    <div class="prod-cell__text">
      <!-- Плотный вариант: та же структура, что в обычной карточке, но мельче на 1px:
           название / «артикул • бренд • предмет» / ссылка WB -->
      <template v-if="compact">
        <div class="prod-cell__title" :title="fullTitle">{{ title || '(нет карточки)' }}</div>
        <div v-if="metaLine" class="prod-cell__sub">{{ metaLine }}</div>
        <div class="prod-cell__acts">
          <a v-if="link" class="prod-cell__link" :href="link" target="_blank" rel="noopener">{{ linkLabel }}</a>
          <button
            v-if="copyNm && nmId !== null && nmId !== undefined"
            type="button"
            class="prod-cell__icon"
            :title="copied === 'nm' ? 'nmID скопирован' : 'Скопировать nmID'"
            @click.stop="doCopy('nm')"
          >
            <i class="bi" :class="copied === 'nm' ? 'bi-check2' : 'bi-clipboard'"></i>
          </button>
          <button
            v-if="copyLink && link"
            type="button"
            class="prod-cell__icon"
            :title="copied === 'link' ? 'Ссылка скопирована' : (wbLink ? 'Скопировать ссылку на WB' : 'Скопировать ссылку')"
            @click.stop="doCopy('link')"
          >
            <i class="bi" :class="copied === 'link' ? 'bi-check2' : 'bi-link-45deg'"></i>
          </button>
        </div>
      </template>
      <template v-else>
        <div class="prod-cell__title" :title="title">{{ title || '(нет карточки)' }}</div>
        <!-- Подпись — тот же порядок, что в компактном виде: артикул • бренд • предмет.
             Если страница передала `sub` — это её подпись (переопределение), и артикул
             идёт отдельной строкой, как раньше. Иначе — metaLine (артикул внутри). -->
        <div v-if="sub" class="prod-cell__sub">{{ sub }}</div>
        <div v-else-if="metaLine" class="prod-cell__sub">{{ metaLine }}</div>
        <div v-if="sub && vendor" class="prod-cell__sub">{{ vendor }}</div>
        <div class="prod-cell__acts">
          <a v-if="link" class="prod-cell__link" :href="link" target="_blank" rel="noopener">{{ linkLabel }}</a>
          <button
            v-if="copyNm && nmId !== null && nmId !== undefined"
            type="button"
            class="prod-cell__icon"
            :title="copied === 'nm' ? 'nmID скопирован' : 'Скопировать nmID'"
            @click.stop="doCopy('nm')"
          >
            <i class="bi" :class="copied === 'nm' ? 'bi-check2' : 'bi-clipboard'"></i>
          </button>
          <button
            v-if="copyLink && link"
            type="button"
            class="prod-cell__icon"
            :title="copied === 'link' ? 'Ссылка скопирована' : (wbLink ? 'Скопировать ссылку на WB' : 'Скопировать ссылку')"
            @click.stop="doCopy('link')"
          >
            <i class="bi" :class="copied === 'link' ? 'bi-check2' : 'bi-link-45deg'"></i>
          </button>
        </div>
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
import CardPhoto from './CardPhoto.vue'
import { copyText } from '@/utils/clipboard'

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
  /** nmID карточки — нужен для копирования. */
  nmId?: number | string | null
  /** Показывать кнопку копирования nmID. */
  copyNm?: boolean
  /** Показывать кнопку копирования ссылки. */
  copyLink?: boolean
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
  nmId: null,
  copyNm: false,
  copyLink: false,
  fallback: '/images/no-photo.png',
})

/** Что скопировали последним — для галочки вместо иконки. */
const copied = ref<'nm' | 'link' | ''>('')
let copyTimer: ReturnType<typeof setTimeout> | null = null

/** Ссылка на карточку WB — из nmID (или переданная `link`, если nmID нет). */
const wbLink = computed(() => {
  if (props.nmId !== null && props.nmId !== undefined && props.nmId !== '') {
    return `https://www.wildberries.ru/catalog/${props.nmId}/detail.aspx`
  }
  return String(props.link || '')
})

function doCopy(what: 'nm' | 'link') {
  const text = what === 'nm' ? String(props.nmId ?? '') : (wbLink.value || String(props.link || ''))
  if (!text) return
  copyText(text).then((ok) => {
    if (!ok) return
    copied.value = what
    if (copyTimer) clearTimeout(copyTimer)
    copyTimer = setTimeout(() => { copied.value = '' }, 1500)
  })
}

watch(() => props.nmId, () => { copied.value = '' })

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
</script>
<style scoped>
.prod-cell { display: flex; gap: 10px; align-items: flex-start; margin-bottom: 5px; }
.prod-cell__img {
  width: 50px; height: 66px; object-fit: cover;
  border-radius: var(--radius-sm); flex: none;
  border: 1px solid var(--line);
  background: var(--surface-2);
}
.prod-cell__text { min-width: 0; overflow: hidden; }
.prod-cell__title {
  font-weight: 700; font-size: calc(12.5px * var(--fs));
  color: var(--ink); line-height: 1.3;
  /* перенос по словам + обрезка с многоточием (как .product-name / .cart-item-title
     в оригинале): колонка не раздувает таблицу, длинное название не ломает строку.
     Без overflow-wrap: anywhere — слова не рвутся посредине, перенос идёт по пробелам.
     Полный вид — название в 2 строки; компактный — в одну (см. .prod-cell--compact). */
  display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2;
  overflow: hidden;
}
.prod-cell__sub {
  font-size: calc(11px * var(--fs)); color: var(--ink-muted);
  display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 1;
  overflow: hidden;
}
.prod-cell__acts { display: flex; align-items: center; gap: 6px; flex-wrap: nowrap; overflow: hidden; }
.prod-cell__link {
  font-size: calc(11px * var(--fs)); font-weight: 600;
  color: var(--brand); text-decoration: none;
}
.prod-cell__link:hover { color: var(--brand-hover); text-decoration: underline; }
.prod-cell__icon {
  font-size: calc(11px * var(--fs)); color: var(--ink-muted);
  background: none; border: 1px solid transparent; border-radius: 4px;
  padding: 0 2px; cursor: pointer; line-height: 1.3; flex: none;
}
.prod-cell__icon:hover { color: var(--brand); border-color: var(--line-strong); background: var(--surface-2); }

/* Плотный вариант: фото 30×40, кегль на 1px меньше обычного.
   Структура та же: название / «артикул • бренд • предмет» / ссылка WB.
   Высота строки падает с ~83px до ~60px — важно для широких реестров.
   Название — в одну строку и без отступа снизу (в полном виде — 2 строки). */
.prod-cell--compact { gap: 8px; align-items: flex-start; margin-bottom: 0; }
.prod-cell--compact .prod-cell__img { width: 30px; height: 40px; font-size: 14px; }
.prod-cell--compact .prod-cell__title {
  font-size: calc(12px * var(--fs)); line-height: 1.3; -webkit-line-clamp: 1;
}
.prod-cell--compact .prod-cell__sub { font-size: calc(11px * var(--fs)); }
.prod-cell--compact .prod-cell__link { font-size: calc(11px * var(--fs)); }
</style>
