<template>
  <div class="tag-cloud">
    <div class="tag-cloud__row">
      <span class="tag-cloud__title">
        Теги <span class="tag-cloud__total">{{ tags.length }}</span>
      </span>
      <div class="tag-cloud__list">
        <button
          v-for="t in tags"
          :key="t.id"
          type="button"
          class="tag-cloud__pill"
          :class="{ 'tag-cloud__pill--active': String(t.id) === String(activeId) }"
          :style="{ '--tag-color': t.color }"
          :title="t.tag_group || t.name"
          @click="emit('pick', t)"
        >
          <span class="tag-cloud__dot" :style="{ background: t.color }"></span>
          <span class="tag-cloud__name">{{ t.name }}</span>
          <span class="tag-cloud__num">{{ t.cards_count }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * Облаво тегов — выбор тега пилюлями (раздел «Теги»: список, заказы, маржа).
 *
 * Пилюля: контур, цветная точка тега, название и число карточек. Активная —
 * контур и текст цвета тега (цвет приходит из БД, поэтому через CSS-переменную).
 * Счётчик карточек у каждого тега — свой (`cards_count`).
 */
import type { TagItem } from '@/api/tags'

withDefaults(defineProps<{
  /** Теги для выбора. */
  tags: TagItem[]
  /** id выбранного тега (активная пилюля). */
  activeId?: number | string | null
}>(), { activeId: null })

const emit = defineEmits<{ (e: 'pick', t: TagItem): void }>()
</script>

<style scoped>
.tag-cloud__row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.tag-cloud__title {
  font-size: calc(12.5px * var(--fs));
  font-weight: 700;
  color: var(--ink);
  white-space: nowrap;
}
.tag-cloud__total {
  background: var(--surface-3);
  color: var(--ink-soft);
  font-size: calc(11px * var(--fs));
  font-weight: 600;
  padding: 1px 8px;
  border-radius: 99px;
}
.tag-cloud__list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

/* ---------- пилюля тега ---------- */
.tag-cloud__pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px 5px 10px;
  border-radius: 99px;
  border: 1px solid var(--line-strong);
  background: var(--surface);
  color: var(--ink);
  font-family: inherit;
  font-size: calc(12.5px * var(--fs));
  font-weight: 500;
  cursor: pointer;
  transition: border-color .15s ease, color .15s ease, background .15s ease;
}
.tag-cloud__pill:hover {
  border-color: var(--tag-color, var(--brand));
  color: var(--tag-color, var(--brand));
}
.tag-cloud__pill--active {
  border-color: var(--tag-color);
  color: var(--tag-color);
  background: color-mix(in srgb, var(--tag-color) 8%, var(--surface));
  font-weight: 600;
}
.tag-cloud__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
  flex: none;
}
.tag-cloud__name { white-space: nowrap; }
.tag-cloud__num {
  color: var(--ink-muted);
  font-size: calc(11px * var(--fs));
  font-weight: 600;
}
</style>
