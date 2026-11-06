<template>
  <!-- Выбор акции — свой выпадающий список: в опциях бейдж типа («Акция» /
       «Автоакция»), название и даты. Штатный <select> бейджи рисовать не умеет. -->
  <div class="promo-select" ref="wrapRef">
    <button type="button" class="promo-select__btn" :title="selected ? selected.name : 'Выберите акцию'" @click="toggle">
      <template v-if="selected">
        <span class="badge" :class="typeBadge(selected.promo_type)">{{ typeLabel(selected.promo_type) }}</span>
        <b class="promo-select__name">{{ selected.name }}</b>
        <span class="promo-select__dates">{{ dates(selected) }}</span>
      </template>
      <template v-else>
        <i class="bi bi-calendar3"></i>
        <span class="promo-select__name promo-select__name--empty">— выберите акцию —</span>
      </template>
      <i class="bi bi-chevron-down promo-select__caret"></i>
    </button>

    <div v-if="open" class="promo-select__list">
      <div v-if="!rows.length" class="promo-select__empty">Акций нет</div>
      <button
        v-for="p in rows"
        :key="p.promo_id"
        type="button"
        class="promo-select__opt"
        :class="{ 'is-on': selected && selected.promo_id === p.promo_id }"
        @click="pick(p)"
      >
        <span class="badge" :class="typeBadge(p.promo_type)">{{ typeLabel(p.promo_type) }}</span>
        <b class="promo-select__name">{{ p.name }}</b>
        <span class="promo-select__dates">{{ dates(p) }}</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { promoDate, type PromoRow } from '@/api/promotions'

const props = defineProps<{
  rows: PromoRow[]
  /** id выбранной акции (пусто — не выбрана). */
  modelValue?: string | number
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: string): void
  (e: 'change', p: PromoRow): void
}>()

const open = ref(false)
const wrapRef = ref<HTMLElement | null>(null)

const selected = computed<PromoRow | null>(() => {
  const id = String(props.modelValue || '')
  if (!id) return null
  return props.rows.find(p => String(p.promo_id) === id) || null
})

const typeLabel = (t: string) => (t === 'auto' ? 'Автоакция' : 'Акция')
const typeBadge = (t: string) => (t === 'auto' ? 'badge--info' : 'badge--neutral')

/** Даты акции — компактно: 22.10 — 12.11. */
function dates(p: PromoRow): string {
  const a = promoDate(p.start_date)
  const b = promoDate(p.end_date)
  const f = (d: Date | null) => (d ? String(d.getDate()).padStart(2, '0') + '.' + String(d.getMonth() + 1).padStart(2, '0') : '—')
  return `${f(a)} — ${f(b)}`
}

const toggle = () => { open.value = !open.value }

const pick = (p: PromoRow) => {
  open.value = false
  emit('update:modelValue', String(p.promo_id))
  emit('change', p)
}

const onDocClick = (e: MouseEvent) => {
  if (!open.value) return
  const el = wrapRef.value
  if (el && !el.contains(e.target as Node)) open.value = false
}

onMounted(() => document.addEventListener('mousedown', onDocClick))
onBeforeUnmount(() => document.removeEventListener('mousedown', onDocClick))
</script>

<style scoped>
.promo-select { position: relative; }

.promo-select__btn {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 7px 11px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--ink);
  font-size: calc(13px * var(--fs));
  text-align: left;
  cursor: pointer;
}

.promo-select__btn:hover { border-color: var(--brand); }

.promo-select__name {
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.promo-select__name--empty { font-weight: 400; color: var(--ink-muted); }

.promo-select__dates {
  margin-left: auto;
  padding-left: 10px;
  font-size: calc(11.5px * var(--fs));
  color: var(--ink-muted);
  white-space: nowrap;
}

.promo-select__caret {
  color: var(--ink-muted);
  font-size: calc(11px * var(--fs));
  flex: none;
}

.promo-select__list {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  z-index: 30;
  min-width: 460px;
  max-height: 320px;
  overflow: auto;
  padding: 4px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-1);
}

.promo-select__opt {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 6px 9px;
  border: 0;
  background: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  text-align: left;
  font-size: calc(12.5px * var(--fs));
  color: var(--ink);
}

.promo-select__opt:hover { background: var(--surface-3); }
.promo-select__opt.is-on { background: var(--brand-tint); }

.promo-select__empty { padding: 10px; color: var(--ink-soft); font-size: calc(12.5px * var(--fs)); }
</style>
