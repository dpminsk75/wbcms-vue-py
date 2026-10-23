<template>
  <div v-if="open" class="wb-modal-backdrop" @click.self="$emit('close')">
    <div class="wb-modal-box our-card">
      <div class="our-card__head">
        <h5 class="our-card__title">
          <i class="bi bi-box-seam"></i> Наша карточка
          <span class="badge bg-dark">{{ nmId }}</span>
        </h5>
        <button type="button" class="btn-close" aria-label="Закрыть" @click="$emit('close')"></button>
      </div>

      <div v-if="loading" class="text-muted small">
        <span class="spinner-border spinner-border-sm"></span> Загрузка…
      </div>
      <div v-else-if="error" class="wb-error">{{ error }}</div>

      <template v-else-if="data">
        <div class="our-card__top">
          <img v-if="photo" :src="photo" class="our-card__photo" alt="" />
          <div class="our-card__info">
            <div class="our-card__name">{{ data.card.title || 'Без названия' }}</div>
            <div class="our-card__meta">
              <span v-if="data.card.brand">Бренд: {{ data.card.brand }}</span>
              <span v-if="data.card.vendor">· {{ data.card.vendor }}</span>
              <span v-if="data.card.subject">· {{ data.card.subject }}</span>
            </div>
            <a :href="wbUrl" target="_blank" rel="noopener" class="small">Открыть на WB</a>
          </div>
        </div>

        <div v-if="data.card.description" class="our-card__desc">{{ data.card.description }}</div>

        <template v-if="data.card.characteristics.length">
          <h6 class="our-card__section">Характеристики</h6>
          <table class="wb-admin-table our-card__chars">
            <tbody>
              <tr v-for="(c, i) in data.card.characteristics" :key="i">
                <td class="our-card__char-name">{{ c.name || '—' }}</td>
                <td>{{ charValue(c) }}</td>
              </tr>
            </tbody>
          </table>
        </template>

        <h6 class="our-card__section">Наши позиции в выдаче</h6>
        <div v-if="!data.phrases.length" class="text-muted small">
          В выбранном периоде нашей карточки в выдаче не было.
        </div>
        <table v-else class="wb-admin-table">
          <thead>
            <tr>
              <th>Фраза</th>
              <th class="text-center">Позиция</th>
              <th class="text-center">Поз. JSON</th>
              <th>Цена</th>
              <th class="text-center">Рейтинг</th>
              <th class="text-center">Отзывы</th>
              <th class="text-center">Дней</th>
              <th>По дням</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in data.phrases" :key="p.phrase">
              <td>{{ p.phrase }}</td>
              <td class="text-center">{{ p.position ?? '—' }}</td>
              <td class="text-center">{{ p.position_api ?? '—' }}</td>
              <td>{{ money(p.price || p.price_api) }}</td>
              <td class="text-center">{{ p.rating || '—' }}</td>
              <td class="text-center">{{ p.reviews ?? '—' }}</td>
              <td class="text-center">{{ p.days.length }}</td>
              <td class="small">
                <span v-for="h in p.history" :key="h.date" class="badge bg-light text-dark me-1">
                  {{ h.date }}: {{ h.position_api || h.position }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useMoneyFmt } from '@/composables/useMoneyFmt'
import { competitorsPositionsApi, type OurCardSummary } from '@/api/competitorsPositions'

const props = defineProps<{
  open: boolean
  nmId: number | null
  dateFrom?: string
  dateTo?: string
}>()
defineEmits<{ (e: 'close'): void }>()

const { fmt0 } = useMoneyFmt()
const data = ref<OurCardSummary | null>(null)
const loading = ref(false)
const error = ref('')

const wbUrl = computed(
  () => `https://www.wildberries.ru/catalog/${props.nmId || 0}/detail.aspx`,
)
const photo = computed(() => (data.value?.card.photos || [])[0] || '')

function money(v: any): string {
  if (v == null || v === '' || Number(v) === 0) return '—'
  return `${fmt0(v)} ₽`
}

/* Значение характеристики приходит по-разному: массивом, строкой или объектом */
function charValue(c: any): string {
  const v = c?.value
  if (v == null) return '—'
  if (Array.isArray(v)) return v.join(', ') || '—'
  if (typeof v === 'object') return Object.values(v).join(', ') || '—'
  return String(v)
}

async function load() {
  const id = Number(props.nmId || 0)
  if (!id) return
  loading.value = true
  error.value = ''
  data.value = null
  try {
    data.value = await competitorsPositionsApi.ourCard({
      nm_id: id,
      date_from: props.dateFrom || undefined,
      date_to: props.dateTo || undefined,
    })
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Не удалось загрузить карточку'
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.open, props.nmId, props.dateFrom, props.dateTo] as const,
  ([isOpen]) => {
    if (isOpen) load()
  },
)
</script>

<style scoped>
.our-card { max-width: 900px; max-height: 86vh; overflow: auto; }
.our-card__head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.our-card__title { font-size: 16px; font-weight: 700; margin: 0; }
.our-card__top { display: flex; gap: 12px; align-items: flex-start; }
.our-card__photo { width: 110px; height: 140px; object-fit: contain; border-radius: 8px; background: #f7f7f7; }
.our-card__name { font-size: 15px; font-weight: 600; }
.our-card__meta { font-size: 12px; color: #6b7280; }
.our-card__desc { margin: 10px 0; font-size: 13px; color: #374151; white-space: pre-wrap; }
.our-card__section { font-size: 13px; font-weight: 700; margin: 14px 0 6px; }
.our-card__chars td { font-size: 12px; vertical-align: top; }
.our-card__char-name { width: 220px; color: #6b7280; }
</style>
