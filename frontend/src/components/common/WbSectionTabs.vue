<template>
  <nav class="wsp__sub">
    <a
      v-for="t in tabs"
      :key="t.id"
      class="stab stab--line"
      :class="{ 'stab--on': isActive(t) }"
      :href="t.to || '#'"
      :title="t.title"
      @click.prevent="onClick(t)"
    >
      {{ t.label }}<span v-if="t.count !== null && t.count !== undefined" class="stab__count">{{ t.count }}</span>
    </a>
  </nav>
</template>

<script setup lang="ts">
/**
 * Вкладки страницы (подменю раздела) — вид темы: подчёркивание (.stab--line),
 * активный пункт — .stab--on. Разметка та же, что у .wsp__sub в theme.md §5.2.
 *
 * Заменяет legacy wb-sub-tabs (Bootstrap-пилюли) на новых страницах:
 * WbWorkspaceHead с subtabs на них больше не используется.
 *
 * Два режима:
 *  * пункт БЕЗ `to` — переключение через v-model (как раньше: страница сама
 *    меняет состояние и URL);
 *  * пункт С `to` — переход по router-link (SPA, без перезагрузки), страница
 *    реагирует на маршрут.
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const props = withDefaults(defineProps<{
  /** Пункты: id, подпись, ссылка (to), счётчик (count). */
  tabs: { id: string; label: string; to?: string; title?: string; count?: number | null }[]
  /** Явная активная вкладка; иначе — по v-model или по текущему роуту. */
  active?: string
}>(), { active: '' })

const model = defineModel<string>({ default: '' })

const route = useRoute()
const router = useRouter()

/** Активен ли пункт: по явному active → по v-model → по текущему маршруту. */
function isActive(t: { id: string; to?: string }): boolean {
  if (props.active) return t.id === props.active
  if (model.value) return t.id === model.value
  const [path, query] = String(t.to || '').split('?')
  if (!t.to) return false
  if (route.path !== path) return false
  if (!query) return true
  return route.fullPath.includes(query)
}

function onClick(t: { id: string; to?: string }) {
  if (t.to) {
    router.push(t.to)
    return
  }
  model.value = t.id
}
</script>
