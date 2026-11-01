<template>
  <div class="prod-cell" :class="{ 'prod-cell--compact': compact, 'prod-cell--muted': collected === false }">
    <!-- Фото: единая точка вывода (CardPhoto) — отдаёт локальную копию из кэша,
         302 на WB, если копии ещё нет. Размер и обрезка — как в ProductCell. -->
    <div class="prod-cell__img">
      <CardPhoto :src="photo" :alt="title" fit="cover" />
    </div>

    <div class="prod-cell__text">
      <!-- Заголовок: одна строка + многоточие, полный текст — в подсказке -->
      <div class="prod-cell__title" :title="title || ''">{{ title || '(нет карточки)' }}</div>

      <!-- Тип/Предмет • Продавец — одна строка + многоточие -->
      <div v-if="metaLine" class="prod-cell__sub">{{ metaLine }}</div>

      <!-- Третья строка: WB: nmId (клик — детальная информация) + копирование + бейджи -->
      <div v-if="hasActions" class="prod-cell__acts">
        <a
          v-if="showNm"
          class="prod-cell__nm"
          :href="`/wb/detail?nm_id=${nmId}`"
          :title="`Детальная информация по конкуренту ${nmId}`"
          @click.stop.prevent="$emit('open')"
        >WB: {{ nmId }}</a>

        <button
          v-if="copyNm"
          type="button"
          class="prod-cell__icon"
          :title="copied === 'nm' ? 'nmId скопирован' : 'Скопировать nmId'"
          @click.stop="doCopy('nm')"
        >
          <i class="bi" :class="copied === 'nm' ? 'bi-check2' : 'bi-clipboard'"></i>
        </button>

        <button
          v-if="copyWbLink"
          type="button"
          class="prod-cell__icon"
          :title="copied === 'link' ? 'Ссылка скопирована' : 'Скопировать ссылку на WB'"
          @click.stop="doCopy('link')"
        >
          <i class="bi" :class="copied === 'link' ? 'bi-check2' : 'bi-link-45deg'"></i>
        </button>

        <span
          v-for="(b, i) in badges"
          :key="i"
          class="badge"
          :class="badgeClass(b)"
        >{{ b.label ?? b }}</span>

        <a
          v-if="phrasesUrl"
          class="prod-cell__more"
          :href="phrasesUrl"
          target="_blank"
          rel="noopener"
          title="Поисковые запросы по карточке"
        >фразы</a>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * Строка товара/конкурента с фото — единый вид для таблиц и списков.
 *
 * Размеры и шрифты — как в `ProductCell.vue` (фото 50×66, в компактном виде
 * 30×40; заголовок 12,5px, мета и действия 11px, всё с множителем `var(--fs)`).
 * Отличие от `ProductCell` — третья строка: `WB: nmId` (клик открывает детальную
 * информацию по конкуренту), копирование nmId и ссылки на WB, бейджи статуса
 * и ссылка «фразы».
 *
 * Фото идёт через `CardPhoto` — локальный кэш робота (`/api/img`), без копии —
 * 302 на CDN WB.
 *
 * ── КАК ПЕРЕДАВАТЬ (строка товара/конкурента в таблице) ───────────────
 *   <CompetitorRow
 *     :nm-id="c.nm_id"                  <!-- артикул WB (обязательно) -->
 *     :title="c.title"                  <!-- название -->
 *     :subject="c.subject_name || ''"   <!-- тип/предмет: «Журналы» -->
 *     :seller="c.seller"                <!-- продавец: «АСТ» -->
 *     :photo="c.image_url"              <!-- фото (пусто — заглушка) -->
 *     :badges="c.badges || []"
 *     :collected="collectedFlag(c.is_collected, !!c.is_ours)" <!-- серая подложка -->
 *     :compact="true"                   <!-- 30×40 вместо 50×66 -->
 *     @open="..." @open-position="..."
 *   />
 *
 *   Подпись — ОДНА строка: Тип/Предмет • Продавец, без дублей
 *   (продавец = бренд → одно слово), с многоточием, если не влезает.
 *   `collected`: false → серая подложка #E9ECEF (карточка конкурента не
 *   собрана); null → как обычно. Хелпер `collectedFlag()` — в `competitorCard.ts`.
 * ──────────────────────────────────────────────────────────────────────
 */
import { computed, ref, watch } from 'vue'
import CardPhoto from './CardPhoto.vue'
import { copyText } from '@/utils/clipboard'

/** Бейдж: строка или {label, tone}. */
export type RowBadge = string | { label: string; tone?: 'warn' | 'green' | 'gray' | 'info' | 'blue' | 'dark' }

const props = withDefaults(defineProps<{
  /** Артикул WB. */
  nmId: number | string
  /** Название товара. */
  title?: string
  /** Фото: URL, массив URL или JSON-строка (как в ProductCell). */
  photo?: any
  /** Тип/предмет — первая часть подписи. */
  subject?: string
  /** Продавец — вторая часть подписи. */
  seller?: string
  /** Бейджи статуса: «без описания», «собран», «скрыт» и т.п. */
  badges?: RowBadge[]
  /** Ссылка «фразы» (например /wb-search/card?nm_id=…). */
  phrasesUrl?: string
  /** Плотный вариант: фото 30×40 (для широких реестров). */
  compact?: boolean
  /** Показывать «WB: nmId». */
  showNm?: boolean
  /** Кнопка «скопировать nmId». */
  copyNm?: boolean
  /** Кнопка «скопировать ссылку на WB». */
  copyWbLink?: boolean
  /** Ссылка на карточку WB (для копирования). */
  wbUrl?: string
  /** Собрана ли карточка конкурента (есть запись в wb_competitor_details).
   *  false — подложка серая; null/undefined — неизвестно, подложка как обычно. */
  collected?: boolean | null
}>(), {
  title: '',
  photo: null,
  subject: '',
  seller: '',
  badges: () => [],
  phrasesUrl: '',
  compact: false,
  showNm: true,
  copyNm: true,
  copyWbLink: true,
  wbUrl: '',
  collected: null,
})

const emit = defineEmits<{ (e: 'open'): void }>()

/** Подпись под названием — ОДНА строка: Тип/Предмет • Продавец.
 *  Без дублей: у конкурентов WB продавец часто = бренд («Издательство АСТ»).
 *  Бренд в подпись не входит — у конкурента он обычно = продавец. */
const metaLine = computed(() => {
  const out: string[] = []
  for (const raw of [props.subject, props.seller]) {
    const s = String(raw || '').trim()
    if (!s) continue
    if (out.some((x) => x.toLowerCase() === s.toLowerCase())) continue
    out.push(s)
  }
  return out.join(' • ')
})

const hasActions = computed(() =>
  props.showNm || props.copyNm || props.copyWbLink || props.badges.length > 0 || !!props.phrasesUrl,
)

/** Что скопировали последним — для галочки вместо иконки. */
const copied = ref<'nm' | 'link' | ''>('')
let copyTimer: ReturnType<typeof setTimeout> | null = null

function doCopy(what: 'nm' | 'link') {
  const text = what === 'nm' ? String(props.nmId) : wbLink()
  copyText(text).then((ok) => {
    if (!ok) return
    copied.value = what
    if (copyTimer) clearTimeout(copyTimer)
    copyTimer = setTimeout(() => { copied.value = '' }, 1500)
  })
}

function wbLink(): string {
  if (props.wbUrl) return props.wbUrl
  return `https://www.wildberries.ru/catalog/${props.nmId}/detail.aspx`
}

/* Бейджи WB: «−50%» — красный, «Хорошая цена» — жёлтый, «11.11» — розовый,
   «ПРЕМУМ…» — тёмный, «с кэшбэком» — фиолетовый, «ресейл» — мятный. */
function badgeClass(b: RowBadge): string {
  if (b && typeof b === 'object') {
    switch (b.tone) {
      case 'warn': return 'bg-warning text-dark'
      case 'green': return 'bg-success'
      case 'gray': return 'bg-secondary'
      case 'info': return 'bg-info text-dark'
      case 'blue': return 'bg-primary'
      case 'dark': return 'bg-dark'
    }
  }
  const s = String(b || '').toLowerCase()
  if (/ресейл|resale/.test(s)) return 'bg-info text-dark'
  if (/скрыт|исключ/.test(s)) return 'bg-secondary'
  if (/собран|собрано/.test(s)) return 'bg-success'
  if (/наша/.test(s)) return 'bg-warning text-dark'
  if (/описани/.test(s)) return 'bg-warning text-dark'
  return 'bg-light text-dark'
}

watch(() => props.nmId, () => { copied.value = '' })
</script>

<style scoped>
/* Размеры, шрифты и отступы — 1-в-1 из ProductCell.vue. */
.prod-cell { display: flex; gap: 10px; align-items: flex-start; }
.prod-cell__img {
  width: 50px; height: 66px;
  border-radius: var(--radius-sm); flex: none;
  border: 1px solid var(--line);
  background: var(--surface-2);
  overflow: hidden;
}
/* Плотный вариант: фото 30×40, кегль на 1px меньше обычного. */
.prod-cell--compact { gap: 8px; align-items: flex-start; }
.prod-cell--compact .prod-cell__img { width: 30px; height: 40px; }
.prod-cell--compact .prod-cell__title { font-size: calc(12px * var(--fs)); line-height: 1.3; }
.prod-cell--compact .prod-cell__sub { font-size: calc(11px * var(--fs)); }
.prod-cell--compact .prod-cell__acts { font-size: calc(11px * var(--fs)); }

/* Карточка конкурента НЕ собрана (нет записи в wb_competitor_details) —
   серая подложка: фото и текст не трогаем. Наши карточки сюда не попадают
   (у них записей в wb_competitor_details нет).
   В таблице строка лежит внутри <td>: саму ячейку красит глобальное правило
   `.tbl td:has(> .prod-cell--muted)` — тогда серый заливает ячейку с полями
   и не раздувает колонку (в отличие от отрицательных отступов). */
.prod-cell--muted { background: #E9ECEF; }

/* text-align: left — строка не зависит от выравнивания контейнера
   (в таблицах ячейка может быть отцентрирована). */
.prod-cell__text { min-width: 0; overflow: hidden; text-align: left; }
.prod-cell__title {
  font-weight: 700; font-size: calc(12.5px * var(--fs));
  color: var(--ink); line-height: 1.3;
  display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 1;
  overflow: hidden;
}
.prod-cell__sub {
  font-size: calc(11px * var(--fs)); color: var(--ink-muted);
  display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 1;
  overflow: hidden;
}

/* третья строка — действия */
.prod-cell__acts {
  display: flex; align-items: center; gap: 6px;
  flex-wrap: nowrap; overflow: hidden;
  font-size: calc(11px * var(--fs)); line-height: 1.3;
}
.prod-cell__nm {
  font-size: calc(11px * var(--fs)); font-weight: 600;
  color: var(--brand); text-decoration: none;
  border-bottom: 1px dashed var(--line-strong);
  white-space: nowrap; cursor: pointer;
}
.prod-cell__nm:hover { color: var(--brand-hover); background: var(--brand-tint); }
.prod-cell__icon {
  font-size: calc(11px * var(--fs)); color: var(--ink-muted);
  background: none; border: 1px solid transparent; border-radius: 4px;
  padding: 0 2px; cursor: pointer; line-height: 1.3;
}
.prod-cell__icon:hover { color: var(--brand); border-color: var(--line-strong); background: var(--surface-2); }
.prod-cell__more {
  font-size: calc(11px * var(--fs)); font-weight: 600;
  color: var(--brand); text-decoration: none;
  border-bottom: 1px dashed var(--line-strong);
  white-space: nowrap;
}
.prod-cell__more:hover { color: var(--brand-hover); background: var(--brand-tint); }
</style>
