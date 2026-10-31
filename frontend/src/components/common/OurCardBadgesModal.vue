<template>
  <div
    v-if="open"
    class="page-wb-detail__modal-backdrop page-wb-detail__modal-backdrop--top"
    @click.self="$emit('close')"
  >
    <div class="page-wb-detail__modal-box">
      <div class="page-wb-detail__modal-head">
        <h5 class="page-wb-detail__modal-title">
          <i class="bi bi-clock-history"></i> История бейджей
          <span class="page-wb-detail__modal-count">{{ nmId || '—' }}</span>
        </h5>
        <button type="button" class="btn-close" aria-label="Закрыть" @click="$emit('close')"></button>
      </div>

      <div v-if="loading" class="text-muted small mt-2">
        <span class="spinner-border spinner-border-sm"></span> Загрузка...
      </div>
      <div v-if="error" class="text-danger small mt-2">{{ error }}</div>
      <div v-else-if="!items.length" class="page-wb-detail__shelf-empty">
        Снимков нет — история пишется при сборе карточки, когда меняется набор бейджей.
      </div>

      <div v-else class="mt-2">
        <div v-for="(h, i) in items" :key="i" class="page-wb-detail__shelf-hist">
          <div class="page-wb-detail__shelf-hist-date">
            {{ fmt(h.at) }}<template v-if="h.price"> · {{ money(h.price) }}</template>
          </div>
          <div class="page-wb-detail__shelf-badges">
            <span
              v-for="(b, j) in h.badges"
              :key="j"
              class="page-wb-detail__shelf-badge"
              :class="badgeClass(b)"
            >{{ b }}</span>
          </div>
        </div>
      </div>

      <div class="page-wb-detail__modal-foot">
        <button class="btn btn-sm btn-secondary" @click="$emit('close')">Закрыть</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ourCardApi, type BadgeSnapshot } from '@/api/ourCard'

/** История бейджей карточки — снимки набора при сборе (таблица
 *  `wb_card_badges_history`). Пишется с момента внедрения: прошлые наборы
 *  не сохранялись. */
const props = defineProps<{ open: boolean; nmId: number | string | null | undefined }>()
defineEmits<{ (e: 'close'): void }>()

const items = ref<BadgeSnapshot[]>([])
const loading = ref(false)
const error = ref('')

async function load() {
  const nm = Number(props.nmId || 0)
  if (!nm) {
    items.value = []
    return
  }
  loading.value = true
  error.value = ''
  try {
    const d = await ourCardApi.badgeHistory(nm)
    items.value = d.items || []
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Ошибка загрузки истории'
    items.value = []
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.open, props.nmId],
  ([open]) => {
    if (open) load()
  },
)

function badgeClass(b: string): string {
  const s = String(b || '').toLowerCase()
  if (/ресейл|resale/.test(s)) return 'page-wb-detail__shelf-badge--resale'
  if (/%/.test(s) || /^[-−]/.test(s)) return 'page-wb-detail__shelf-badge--sale'
  if (/кэшбэк|cashback/.test(s)) return 'page-wb-detail__shelf-badge--cash'
  if (/цена|выгод|дешев/.test(s)) return 'page-wb-detail__shelf-badge--price'
  if (/11\.11|черн|день|распродаж|акци/.test(s)) return 'page-wb-detail__shelf-badge--promo'
  if (/премиум|руководител|эксклюзив|вкус/.test(s)) return 'page-wb-detail__shelf-badge--vip'
  return 'page-wb-detail__shelf-badge--plain'
}

function fmt(v?: string | null): string {
  if (!v) return '—'
  const d = new Date(v)
  return isFinite(d.getTime()) ? d.toLocaleString('ru-RU') : String(v)
}

function money(v?: number | string | null): string {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  if (!isFinite(n)) return String(v)
  return `${n.toLocaleString('ru-RU')} ₽`
}
</script>
