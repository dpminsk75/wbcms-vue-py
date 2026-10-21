<template>
  <div v-if="open" class="wb-modal-backdrop" @click.self="$emit('close')">
    <div class="wb-modal-box comp-details">
      <div class="comp-details__head">
        <h5 class="comp-details__title">
          <i class="bi bi-card-text"></i> Карточка конкурента
          <span class="badge bg-dark">{{ nmId }}</span>
        </h5>
        <button type="button" class="btn-close" aria-label="Закрыть" @click="$emit('close')"></button>
      </div>

      <div v-if="loading" class="text-muted small">
        <span class="spinner-border spinner-border-sm"></span> Загрузка…
      </div>
      <div v-else-if="error" class="wb-error">{{ error }}</div>

      <template v-else-if="item">
        <div class="comp-details__top">
          <div class="comp-details__gallery">
            <img
              :src="activeImage || '/images/no-photo.png'"
              :alt="item.title || ''"
              class="comp-details__main"
            />
            <div v-if="item.images.length > 1" class="comp-details__thumbs">
              <img
                v-for="(img, i) in item.images"
                :key="img"
                :src="img"
                alt=""
                class="comp-details__thumb"
                :class="{ 'is-active': i === imageIdx }"
                loading="lazy"
                @click="imageIdx = i"
              />
            </div>
          </div>

          <div class="comp-details__info">
            <div class="comp-details__name">{{ item.title || '—' }}</div>
            <div class="comp-details__meta">
              <span v-if="item.brand">бренд: {{ item.brand }}</span>
              <span v-if="item.seller && item.seller !== item.brand">продавец: {{ item.seller }}</span>
              <span v-if="item.subject_name">предмет: {{ item.subject_name }}</span>
            </div>

            <div class="comp-details__price">
              <span class="comp-details__price-now">{{ money(item.price) }}</span>
              <span v-if="item.old_price" class="comp-details__price-old">{{ money(item.old_price) }}</span>
            </div>

            <div class="comp-details__links">
              <a :href="wbUrl" target="_blank" rel="noopener" class="btn btn-sm btn-outline-secondary">
                <i class="bi bi-box-arrow-up-right"></i> Открыть на WB
              </a>
              <button type="button" class="btn btn-sm btn-outline-secondary" @click="copyLink">
                <i class="bi" :class="copied ? 'bi-check2' : 'bi-clipboard'"></i>
                {{ copied ? 'Скопировано' : 'Скопировать ссылку' }}
              </button>
              <span v-if="copyError" class="text-danger small w-100">{{ copyError }}</span>
            </div>

            <div class="comp-details__dates">
              <span v-if="item.collected_at">собрано: {{ fmt(item.collected_at) }}</span>
              <span v-if="item.first_collected_at">в базе с: {{ fmt(item.first_collected_at) }}</span>
            </div>

            <section class="comp-details__section">
              <h6 class="comp-details__section-title">
                Привязан к нашим карточкам
                <span class="badge bg-light text-dark">{{ item.attached_cnt || 0 }}</span>
              </h6>
              <div v-if="item.attached_to?.length" class="comp-details__attached">
                <a
                  v-for="a in item.attached_to"
                  :key="a.nm_id"
                  :href="`/wb/detail?nm_id=${a.nm_id}`"
                  target="_blank"
                  rel="noopener"
                  class="comp-details__attached-item"
                >
                  <span class="comp-details__attached-nm">{{ a.nm_id }}</span>
                  <span class="comp-details__attached-title">{{ a.title || '—' }}</span>
                  <span v-if="a.source" class="badge bg-secondary">{{ sourceLabel(a.source) }}</span>
                </a>
              </div>
              <div v-else class="text-muted small">Не привязан ни к одной нашей карточке.</div>
            </section>

            <section class="comp-details__section">
              <h6 class="comp-details__section-title">Изменение цены</h6>
              <div v-if="priceChanges.length > 1" class="comp-details__price-hist">
                <table class="comp-details__price-table">
                  <thead>
                    <tr>
                      <th>Когда</th>
                      <th>Цена</th>
                      <th>Было</th>
                      <th>Изменение</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(p, i) in priceChanges" :key="i">
                      <td>{{ fmt(p.at) }}</td>
                      <td class="comp-details__num">{{ money(p.price) }}</td>
                      <td class="comp-details__num text-muted">{{ p.old_price ? money(p.old_price) : '—' }}</td>
                      <td class="comp-details__num">
                        <span v-if="i === 0" class="text-muted">—</span>
                        <span v-else :class="priceDiff(p, i) > 0 ? 'text-danger' : 'text-success'">{{ diffLabel(p, i) }}</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div v-else class="text-muted small">
                Цена не менялась<template v-if="item.price">: {{ money(item.price) }}</template>.
              </div>
            </section>

            <section class="comp-details__section">
              <h6 class="comp-details__section-title">
                Описание
                <span class="badge bg-light text-dark">{{ descLen }} симв.</span>
              </h6>
              <div v-if="item.description" class="comp-details__desc">{{ item.description }}</div>
              <div v-else class="text-muted small">Описание ещё не собрано — откройте карточку на WB с расширением.</div>
            </section>

            <section v-if="item.characteristics.length" class="comp-details__section">
              <h6 class="comp-details__section-title">Характеристики <span class="badge bg-light text-dark">{{ item.characteristics.length }}</span></h6>
              <table class="comp-details__chars">
                <tbody>
                  <tr v-for="(c, i) in item.characteristics" :key="i">
                    <th>{{ c.name || '—' }}</th>
                    <td>{{ charValue(c.value) }}</td>
                  </tr>
                </tbody>
              </table>
            </section>

            <section class="comp-details__section">
              <h6 class="comp-details__section-title">
                Фразы конкурента
                <span class="badge bg-light text-dark">{{ phraseRows.length }}</span>
                <span v-if="phraseSources.length === 1" class="comp-details__phrase-src">
                  наша карточка: {{ phraseSources[0].nm_id }} — {{ phraseSources[0].title || '—' }}
                </span>
              </h6>
              <table v-if="phraseRows.length" class="comp-details__phrase-table">
                <thead>
                  <tr>
                    <th>Фраза конкурента</th>
                    <th v-if="phraseSources.length > 1">Наша карточка</th>
                    <th class="text-center" title="Сколько конкурентов используют эту группу формулировок">У конкурентов</th>
                    <th class="text-center" title="Заказы в нашей базе поисковых запросов">Заказы</th>
                    <th class="text-center">Источник</th>
                    <th class="text-center">Выбрана</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="r in phraseRows"
                    :key="r.key"
                    :class="{ 'is-selected': r.is_selected, 'is-in-db': r.in_db }"
                    :title="r.canon && r.canon !== r.phrase ? `в группе с «${r.canon}»` : ''"
                  >
                    <td>{{ r.phrase }}</td>
                    <td v-if="phraseSources.length > 1">{{ r.source_nm_id }}</td>
                    <td class="text-center">{{ r.hit_cnt || '—' }}</td>
                    <td class="text-center">{{ r.orders || '—' }}</td>
                    <td class="text-center">
                      <span v-if="r.in_db" class="badge bg-success" title="Такая фраза есть в нашей базе — WB её отдаёт">в базе</span>
                      <span v-else class="badge bg-warning text-dark" title="Нет в нашей базе — новая">новая</span>
                    </td>
                    <td class="text-center">
                      <i v-if="r.is_selected" class="bi bi-check-circle-fill comp-details__ok"></i>
                    </td>
                  </tr>
                </tbody>
              </table>
              <div v-else class="text-muted small">Фразы ещё не разобраны.</div>
            </section>
          </div>
        </div>
      </template>

      <div class="wb-modal-actions">
        <button class="btn btn-sm btn-secondary" @click="$emit('close')">Закрыть</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  competitorsNewcardApi,
  type CompetitorDetail,
} from '../../api/competitorsNewcard'
import { copyText } from '../../utils/clipboard'

const props = defineProps<{
  open: boolean
  nmId: number | string | null | undefined
  /** Если задан — карточка открыта из /competitor/new-cards/:sourceNmId. */
  sourceNmId?: number | string | null
  /** Откуда грузить: captured (по умолчанию) или pick (пул §16). */
  scope?: 'captured' | 'pick'
}>()
defineEmits<{ (e: 'close'): void }>()

const item = ref<CompetitorDetail | null>(null)
const loading = ref(false)
const error = ref('')
const copyError = ref('')
const imageIdx = ref(0)
const copied = ref(false)
let copiedTimer: ReturnType<typeof setTimeout> | null = null

const activeImage = computed(() => item.value?.images?.[imageIdx.value] || item.value?.photo || '')
const descLen = computed(() => (item.value?.description || '').length)
const priceChanges = computed(() => (item.value?.price_history || []).filter((p) => !!p.price))
const wbUrl = computed(() => item.value?.url || `https://www.wildberries.ru/catalog/${props.nmId}/detail.aspx`)

interface PhraseRow {
  key: string
  phrase: string
  canon?: string | null
  source_nm_id: number
  source_title?: string | null
  is_selected: boolean
  hit_cnt: number
  in_db: boolean
  orders: number
}

/** Одна строка = одна исходная формулировка конкурента. */
const phraseRows = computed<PhraseRow[]>(() =>
  (item.value?.phrases || []).map((p, i) => ({
    key: `${p.source_nm_id}:${p.phrase_id ?? `raw:${p.phrase}`}:${i}`,
    phrase: p.phrase,
    canon: p.canon || null,
    source_nm_id: p.source_nm_id,
    source_title: p.source_title || null,
    is_selected: !!p.is_selected,
    hit_cnt: Number(p.hit_cnt || 0),
    in_db: !!p.in_db,
    orders: Number(p.orders || 0),
  })),
)

/** Наши карточки, к которым привязан конкурент (для шапки/колонки). */
const phraseSources = computed<Array<{ nm_id: number; title?: string | null }>>(() => {
  const map = new Map<number, { nm_id: number; title?: string | null }>()
  for (const p of item.value?.phrases || []) {
    if (!map.has(p.source_nm_id)) {
      map.set(p.source_nm_id, { nm_id: p.source_nm_id, title: p.source_title || null })
    }
  }
  return [...map.values()]
})

const SOURCE_LABELS: Record<string, string> = {
  capture: 'собран',
  search: 'поиск',
  manual: 'вручную',
  sibling: 'с карточки',
}

function sourceLabel(source?: string | null): string {
  const s = String(source || '')
  return SOURCE_LABELS[s] || s
}

function charValue(v: any): string {
  if (Array.isArray(v)) return v.join('; ')
  return v == null ? '' : String(v)
}

function fmt(v?: string | null): string {
  if (!v) return '—'
  const d = new Date(v)
  return isFinite(d.getTime()) ? d.toLocaleString('ru-RU') : String(v)
}

function money(v?: string | number | null): string {
  if (v === null || v === undefined || v === '') return '—'
  const s = String(v)
  return s.includes('₽') ? s : `${s} ₽`
}

function num(v?: string | null): number | null {
  const raw = String(v ?? '').trim()
  if (!raw) return null
  const n = Number(raw.replace(/[^\d,.-]/g, '').replace(',', '.'))
  return isFinite(n) ? n : null
}

function priceDiff(p: { price?: string | null }, i: number): number {
  const cur = num(p.price)
  const prev = num(priceChanges.value[i - 1]?.price)
  if (cur === null || prev === null) return 0
  return cur - prev
}

function diffLabel(p: { price?: string | null }, i: number): string {
  const d = priceDiff(p, i)
  if (!d) return '0 ₽'
  return `${d > 0 ? '+' : '−'}${Math.abs(d).toLocaleString('ru-RU')} ₽`
}

async function copyLink() {
  copyError.value = ''
  if (!await copyText(wbUrl.value)) {
    copyError.value = 'Не удалось скопировать ссылку'
    return
  }
  copied.value = true
  if (copiedTimer) clearTimeout(copiedTimer)
  copiedTimer = setTimeout(() => { copied.value = false }, 1500)
}

async function load() {
  const id = Number(props.nmId || 0)
  if (!id) return
  loading.value = true
  error.value = ''
  copyError.value = ''
  item.value = null
  imageIdx.value = 0
  copied.value = false
  try {
    if (props.scope === 'pick') {
      item.value = await competitorsNewcardApi.pickDetails(id)
    } else {
      const source = Number(props.sourceNmId || 0)
      item.value = source
        ? await competitorsNewcardApi.competitorDetails(source, id)
        : await competitorsNewcardApi.capturedDetails(id)
    }
  } catch (e: any) {
    error.value = e?.response?.data?.detail === 'details not collected'
      ? 'Контент ещё не собран — откройте карточку на WB с расширением.'
      : (e?.response?.data?.detail || 'Не удалось загрузить карточку конкурента')
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.open, props.nmId, props.sourceNmId, props.scope] as const,
  ([isOpen]) => {
    if (isOpen) load()
  },
)
</script>

<style scoped>
.comp-details { width: 980px; max-width: 96vw; max-height: 92vh; overflow: auto; }
.comp-details__head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.comp-details__title { margin: 0; font-size: 15px; display: flex; align-items: center; gap: 8px; }
.comp-details__top { display: flex; gap: 18px; align-items: flex-start; flex-wrap: wrap; }
.comp-details__gallery { flex: 0 0 260px; width: 260px; }
.comp-details__main {
  width: 100%; height: 340px; object-fit: contain; background: #f8f9fa;
  border: 1px solid #e5e7eb; border-radius: 8px;
}
.comp-details__thumbs { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
.comp-details__thumb {
  width: 44px; height: 56px; object-fit: cover; border: 2px solid transparent;
  border-radius: 4px; cursor: pointer; background: #f8f9fa;
}
.comp-details__thumb.is-active { border-color: #0d6efd; }
.comp-details__info { flex: 1; min-width: 280px; }
.comp-details__name { font-size: 18px; font-weight: 600; line-height: 1.3; }
.comp-details__meta { display: flex; flex-wrap: wrap; gap: 4px 14px; margin-top: 8px; font-size: 13px; color: #555; }
.comp-details__price { margin-top: 14px; display: flex; align-items: baseline; gap: 10px; }
.comp-details__price-now { font-size: 24px; font-weight: 700; color: #2c3e50; }
.comp-details__price-old { font-size: 15px; color: #999; text-decoration: line-through; }
.comp-details__links { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px; }
.comp-details__dates { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 12px; font-size: 12px; color: #777; }
.comp-details__attached { display: flex; flex-direction: column; gap: 6px; }
.comp-details__attached-item {
  display: flex; align-items: center; gap: 8px; padding: 6px 8px;
  border: 1px solid #e5e7eb; border-radius: 6px; color: inherit; text-decoration: none;
}
.comp-details__attached-item:hover { border-color: #0d6efd; background: #f8fbff; }
.comp-details__attached-nm { font-family: monospace; font-size: 12px; color: #0d6efd; white-space: nowrap; }
.comp-details__attached-title { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; }
.comp-details__section { border-top: 1px solid #eee; margin-top: 16px; padding-top: 12px; }
.comp-details__section-title { font-size: 13px; font-weight: 600; margin-bottom: 8px; display: flex; align-items: center; gap: 8px; }
.comp-details__chars { width: 100%; font-size: 13px; border-collapse: collapse; }
.comp-details__chars th, .comp-details__chars td { padding: 4px 8px; border-bottom: 1px solid #f1f1f1; vertical-align: top; }
.comp-details__chars th { width: 35%; text-align: left; color: #555; font-weight: 600; }
.comp-details__desc { white-space: pre-wrap; font-size: 13px; line-height: 1.55; color: #333; }
.comp-details__price-table { width: 100%; font-size: 13px; border-collapse: collapse; }
.comp-details__price-table th, .comp-details__price-table td { padding: 5px 8px; border-bottom: 1px solid #f1f1f1; text-align: left; }
.comp-details__price-table th { font-size: 11px; text-transform: uppercase; letter-spacing: .03em; color: #888; font-weight: 600; }
.comp-details__num { white-space: nowrap; }
.comp-details__phrase-table { width: 100%; font-size: 13px; border-collapse: collapse; }
.comp-details__phrase-table th, .comp-details__phrase-table td { padding: 4px 8px; border-bottom: 1px solid #f1f1f1; vertical-align: top; }
.comp-details__phrase-table th { font-size: 11px; text-transform: uppercase; letter-spacing: .03em; color: #888; font-weight: 600; text-align: left; }
.comp-details__phrase-table tbody tr.is-selected { background: #f2fbf6; }
.comp-details__phrase-table tbody tr.is-in-db td:first-child { box-shadow: inset 3px 0 0 #2e7d32; }
.comp-details__phrase-src { font-size: 12px; font-weight: 400; color: #6b7280; }
.comp-details__ok { color: #2e7d32; }
</style>
