<template>
  <!-- Карточка акции — по образцу ЛК WB: описание, бейджи преимуществ, счётчики,
       «+N% к выдаче» и действия. Стоит первым блоком страницы подбора.

       Шапка — две части: слева всё про акцию (название, даты, статус, описание,
       преимущества, счётчики), справа управление расчётом и таблицей. -->
  <div class="wb-panel promo-card">
    <!-- заголовок блока: слева суть, справа управление -->
    <div class="promo-card__hd">
      <div class="promo-card__main">
        <div>
          <h2 class="promo-card__title">
            <span v-if="showType" class="promo-card__type">{{ typeWord }}</span>
            {{ promo?.name || '—' }}
          </h2>
          <div class="promo-card__dates">{{ datesText }}</div>
          <div class="promo-card__st">
            <span class="badge" :class="statusClass">{{ statusText }}</span>
          </div>
        </div>

        <div class="promo-card__bd">
          <p v-if="promo?.description" class="promo-card__desc">{{ promo.description }}</p>

          <div v-if="advantages.length" class="promo-card__h">Преимущества акции</div>
          <div v-if="advantages.length" class="promo-card__adv">
            <span v-for="a in advantages" :key="a" class="badge badge--neutral">{{ a }}</span>
          </div>

          <div class="promo-card__h">Товары</div>
          <div class="promo-card__stats">
            <span>{{ fitting }} подходящих товаров</span><b>{{ willJoin }}</b>
            <span>будут участвовать</span><b>{{ willJoin }}</b>
            <span>исключено</span><b>{{ excluded }}</b>
          </div>

          <div v-if="boost > 0" class="promo-card__boost">
            <span>Продвижение в поиске и каталоге</span>
            <b>+{{ boost }}% к выдаче</b>
          </div>
        </div>
      </div>

      <!-- управление: тумблеры расчёта, сортировка, порядок, фильтр «В акции» -->
      <div class="promo-card__side">
        <div class="promo-card__side-lbl">Учитывать в расчёте</div>
        <div class="promo-card__side-col">
          <button class="opt" :aria-pressed="!!params.include_reviews" @click="toggleParam('include_reviews')">
            <span class="opt__sw" style="background: var(--good)"></span>Учитывать отзывы
          </button>
          <button class="opt" :aria-pressed="!!params.include_adv" @click="toggleParam('include_adv')">
            <span class="opt__sw" style="background: var(--brand-2)"></span>Учитывать рекламу
          </button>
          <button class="opt" :aria-pressed="!!params.include_cashback" @click="toggleParam('include_cashback')">
            <span class="opt__sw" style="background: var(--info)"></span>Учитывать кэшбек
          </button>
          <button class="opt" :aria-pressed="!!params.include_penalties" @click="toggleParam('include_penalties')">
            <span class="opt__sw" style="background: var(--bad)"></span>Учитывать штрафы
          </button>
        </div>

        <div class="promo-card__side-lbl">Сортировка</div>
        <select class="wb-select" :value="sort" @change="$emit('update:sort', ($event.target as HTMLSelectElement).value)">
          <option value="sales">По продажам</option>
          <option value="margin">По марже</option>
          <option value="name">По алфавиту</option>
        </select>

        <div class="promo-card__side-lbl">Порядок</div>
        <div class="promo-card__side-row">
          <button class="opt" :aria-pressed="order === 'desc'" @click="$emit('update:order', 'desc')">По убыванию</button>
          <button class="opt" :aria-pressed="order === 'asc'" @click="$emit('update:order', 'asc')">По возрастанию</button>
        </div>

        <div class="promo-card__side-lbl">В акции</div>
        <div class="promo-card__side-row">
          <button class="opt" :aria-pressed="inAction === 'all'" @click="$emit('update:in-action', 'all')">Все</button>
          <button class="opt" :aria-pressed="inAction === 'yes'" @click="$emit('update:in-action', 'yes')">В акции</button>
          <button class="opt" :aria-pressed="inAction === 'no'" @click="$emit('update:in-action', 'no')">Не в акции</button>
        </div>
      </div>
    </div>

    <div class="promo-card__ft">
      <button class="btn btn--brand" :disabled="isAuto || !selectedCount" title="Добавить отмеченные товары в акцию (WB promotions/upload)" @click="$emit('upload')">
        <i class="bi bi-cloud-arrow-up me-1"></i>Передать на WB
      </button>
      <span class="spacer"></span>
      <span class="promo-card__fresh" v-if="report && report.count">
        <i class="bi bi-file-earmark-check"></i>
        Отчёт WB: {{ report.count }} товаров<template v-if="report.loaded_at"> · {{ report.loaded_at }}</template>
      </span>
      <span class="promo-card__fresh" v-if="rows.length">
        Товаров: {{ rows.length }}<template v-if="updatedAt"> · обновлено {{ updatedAt }}</template>
        <button class="ch-icon-btn" title="Перезабрать список товаров из WB" @click="$emit('reload')">
          <i class="bi bi-arrow-repeat"></i>
        </button>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { promoStatus, promoStatusLabel, type PromoCalcParams, type PromoRow } from '@/api/promotions'

const props = withDefaults(defineProps<{
  promo: PromoRow | null
  rows: any[]
  selectedCount?: number
  updatedAt?: string
  loading?: boolean
  /** Загруженный отчёт WB по акции (сколько товаров и когда). */
  report?: { count?: number; loaded_at?: string | null } | null
  /** Параметры расчёта — тумблеры «учитывать …». */
  params?: Partial<PromoCalcParams>
  /** Сортировка таблицы: margin | sales | name. */
  sort?: string
  /** Порядок сортировки: asc | desc. */
  order?: string
  /** Фильтр «В акции»: all | yes | no. */
  inAction?: string
}>(), {
  report: () => null,
  params: () => ({}),
  sort: 'sales',
  order: 'desc',
  inAction: 'no',
})

const emit = defineEmits<{
  (e: 'reload'): void
  (e: 'upload'): void
  (e: 'update:params', p: Partial<PromoCalcParams>): void
  (e: 'update:sort', v: string): void
  (e: 'update:order', v: string): void
  (e: 'update:in-action', v: string): void
}>()

/** Тумблер «учитывать …» — меняет набор статей расчёта. */
const toggleParam = (key: keyof PromoCalcParams) => {
  emit('update:params', { ...props.params, [key]: !props.params[key] })
}

const MONTHS = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']

function toDate(iso: string): Date | null {
  const a = String(iso || '').slice(0, 10).split('-').map(Number)
  if (a.length !== 3 || !a[0]) return null
  return new Date(a[0], (a[1] || 1) - 1, a[2] || 1)
}
function fmtDate(iso: string): string {
  const d = toDate(iso)
  if (!d) return '—'
  return d.getDate() + ' ' + MONTHS[d.getMonth()]
}
function fmtTime(iso: string): string {
  const s = String(iso || '')
  const m = s.match(/T(\d{2}):(\d{2})/)
  return m ? `${m[1]}:${m[2]}` : '00:00'
}

const isAuto = computed(() => (props.promo?.promo_type || '') === 'auto')

/** Тип выделяем цветом, только если его нет в самом названии (WB часто
    присылает «Автоакция. …» прямо в name — тогда дублировать не надо). */
const typeWord = computed(() => (isAuto.value ? 'Автоакция.' : 'Акция.'))
const showType = computed(() => {
  const name = String(props.promo?.name || '')
  if (!name) return false
  return !name.toLowerCase().startsWith(isAuto.value ? 'автоакция' : 'акция')
})

const datesText = computed(() => {
  const p = props.promo
  if (!p) return ''
  const from = `${fmtDate(p.start_date)} ${fmtTime(p.start_dt || '')}`
  const to = `${fmtDate(p.end_date)} ${fmtTime(p.end_dt || '')}`
  const a = toDate(p.start_date)
  const b = toDate(p.end_date)
  const days = a && b ? Math.round((b.getTime() - a.getTime()) / 86400000) + 1 : 0
  return `${from} — ${to}${days ? ` (${days} дн.)` : ''}`
})

/** Статус — общий расчёт (api/promotions.ts), чтобы не расходилось с календарём. */
const statusText = computed(() => (props.promo ? promoStatusLabel(props.promo) : ''))
const statusClass = computed(() => {
  const s = props.promo ? promoStatus(props.promo) : 'active'
  if (s === 'announce' || s === 'finished') return 'badge--neutral'
  return isAuto.value ? 'badge--info' : 'badge--brand'
})

const advantages = computed(() => {
  const a = props.promo?.advantages
  return Array.isArray(a) ? a.map(String).filter(Boolean) : []
})

/** Счётчики — как в ЛК: «N подходящих / N будут участвовать / N исключено». */
const willJoin = computed(() => Number(props.promo?.in_promo_total || 0))
const excluded = computed(() => Number(props.promo?.not_in_promo_total || 0))
const fitting = computed(() => willJoin.value + excluded.value)

/** «+N% к выдаче» — максимальный буст из шкалы скидок акции (ranging). */
const boost = computed(() => {
  const r = props.promo?.ranging
  if (!Array.isArray(r)) return 0
  const vals = r.map((x: any) => Number(x?.boost || 0)).filter((n: number) => n > 0)
  return vals.length ? Math.max(...vals) : 0
})
</script>

<style scoped>
/* Свои правила — только то, чего нет в Bootstrap: шапка карточки в две
   части и сетка счётчиков «подпись — значение». */
.promo-card__hd {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 14px 16px 0;
}

.promo-card__main {
  flex: 1 1 auto;
  min-width: 0;
}

/* Правая колонка — управление расчётом и таблицей. */
.promo-card__side {
  flex: 0 0 280px;
  width: 280px;
  padding-left: 14px;
  border-left: 1px solid var(--line);
}

.promo-card__side-lbl {
  font-size: calc(10px * var(--fs));
  font-weight: 700;
  color: var(--ink-muted);
  text-transform: uppercase;
  letter-spacing: .04em;
  margin: 12px 0 6px;
}

.promo-card__side-lbl:first-child { margin-top: 0; }

.promo-card__side-col {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 6px;
}

.promo-card__side-col .opt { width: 100%; justify-content: flex-start; }

.promo-card__side-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.promo-card__side .wb-select { width: 100%; }

.promo-card__title {
  font-size: calc(18px * var(--fs));
  font-weight: 700;
  line-height: 1.25;
  color: var(--ink);
}

.promo-card__type {
  color: var(--brand-2);
}

.promo-card__dates {
  font-size: calc(12.5px * var(--fs));
  color: var(--ink-soft);
  margin-top: 3px;
}

.promo-card__st {
  margin-top: 8px;
}

.promo-card__bd {
  margin-top: 12px;
  font-size: calc(13px * var(--fs));
  line-height: 1.5;
  color: var(--ink);
}

.promo-card__desc {
  margin: 0 0 4px;
  max-width: 1050px;
}

.promo-card__h {
  font-size: calc(13.5px * var(--fs));
  font-weight: 700;
  color: var(--ink);
  margin: 14px 0 8px;
}

.promo-card__adv {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.promo-card__stats {
  display: grid;
  grid-template-columns: max-content max-content;
  gap: 4px 24px;
  font-size: calc(13px * var(--fs));
  color: var(--ink-soft);
  justify-content: start;
}

.promo-card__stats b {
  text-align: right;
  font-variant-numeric: tabular-nums;
  color: var(--ink);
}

/* Продвижение — отбит от счётчиков: сверху воздух, слева отступ
   (правый край остаётся на одной линии со счётчиками), снизу — отступ
   до кнопок карточки. */
.promo-card__boost {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 14px;
  font-size: calc(13px * var(--fs));
  color: var(--ink-soft);
  padding: 14px 0 16px 14px;
  margin: 20px 0 0;
  border-top: 1px solid var(--line);
  max-width: calc(900px - 14px);
}

.promo-card__boost b {
  font-variant-numeric: tabular-nums;
  color: var(--ink);
}

.promo-card__ft {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 12px 16px;
  border-top: 1px solid var(--line);
  background: var(--surface-2);
}

.promo-card__ft .spacer {
  margin-left: auto;
}

.promo-card__fresh {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: calc(11.5px * var(--fs));
  color: var(--ink-soft);
}
</style>
