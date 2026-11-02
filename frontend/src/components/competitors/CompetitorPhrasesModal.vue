<template>
  <!-- Заготовка модалки «Фразы карточки». Наполнение (список формулировок из ИИ-разбора)
       обсуждаем позже — пока каркас и пустое состояние. -->
  <div v-if="open" class="wb-modal-backdrop" @click.self="$emit('close')">
    <div class="wb-modal-box comp-phrases__box">
      <div class="comp-phrases__head">
        <h5 class="comp-phrases__title">
          <i class="bi bi-chat-left-text"></i>
          Фразы карточки
          <span class="badge comp-phrases__nm">{{ nmId || '—' }}</span>
        </h5>
        <button type="button" class="btn-close" aria-label="Закрыть" @click="$emit('close')"></button>
      </div>

      <div class="comp-phrases__sub">{{ title || '—' }}</div>

      <div class="comp-phrases__source">
        <span class="badge badge--neutral">{{ sourceLabel }}</span>
        <span v-if="count" class="badge badge--info">{{ count }}</span>
      </div>

      <!-- Список фраз будет здесь -->
      <div v-if="phrases && phrases.length" class="comp-phrases__list">
        <span v-for="p in phrases" :key="p" class="badge badge--neutral">{{ p }}</span>
      </div>
      <div v-else class="comp-phrases__empty">
        <i class="bi bi-hourglass-split"></i>
        <div>Фразы появятся здесь — их собирает ИИ-разбор описаний конкурента.</div>
        <div class="text-muted small">Заготовка: наполнение обсуждаем отдельно.</div>
      </div>

      <div class="wb-modal-actions">
        <button class="btn btn-sm btn--outline" @click="$emit('close')">Закрыть</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * Модалка «Фразы карточки» — общая для конкурентных отчётов.
 *
 * Сейчас — заготовка: каркас + пустое состояние. Список формулировок
 * (из ИИ-разбора `wb_competitor_phrase_comp` / `wb_competitor_phrase`)
 * наполним позже, когда согласуем вид и источник данных.
 */
const props = withDefaults(defineProps<{
  /** Открыта ли модалка. */
  open: boolean
  /** nmID карточки, по которой показываем фразы. */
  nmId?: number | string | null
  /** Название карточки — подзаголовок. */
  title?: string | null
  /** Откуда фразы: ручная привязка / ИИ-разбор / выдача. */
  source?: 'capture' | 'comp' | 'search' | string | null
  /** Счётчик (фраз в выдаче / формулировок после разбора). */
  count?: number | null
  /** Фразы (пока пусто — наполнение впереди). */
  phrases?: string[]
}>(), {
  nmId: null,
  title: '',
  source: '',
  count: null,
  phrases: () => [],
})

defineEmits<{ (e: 'close'): void }>()

const SOURCE_LABELS: Record<string, string> = {
  capture: 'ручная привязка',
  comp: 'ИИ-разбор описания',
  search: 'выдача по запросу',
}
const sourceLabel = SOURCE_LABELS[String(props.source || '')] || 'фразы конкурента'
</script>

<style scoped>
.comp-phrases__box {
  width: 560px;
  max-width: 94vw;
  max-height: 86vh;
  overflow: auto;
}
.comp-phrases__head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.comp-phrases__title { font-size: 15px; margin: 0; display: flex; align-items: center; gap: 8px; }
.comp-phrases__nm { background: color-mix(in srgb, var(--ink) 10%, transparent); color: var(--ink-soft); }
.comp-phrases__sub { font-size: 13px; color: var(--ink); font-weight: 600; }
.comp-phrases__source { display: flex; gap: 6px; flex-wrap: wrap; }
.comp-phrases__list { display: flex; gap: 6px; flex-wrap: wrap; }
.comp-phrases__empty {
  display: flex; flex-direction: column; gap: 6px; align-items: center; text-align: center;
  padding: 18px 12px; border: 1px dashed var(--line); border-radius: 8px;
  background: var(--surface-2); color: var(--ink-soft); font-size: 13px;
}
.comp-phrases__empty i { font-size: 22px; color: var(--ink-muted); }
</style>
