<template>
  <div
    v-if="open"
    class="page-wb-detail__modal-backdrop page-wb-detail__modal-backdrop--top"
    @click.self="$emit('close')"
  >
    <div
      ref="boxRef"
      class="page-wb-detail__modal-box page-wb-detail__modal-box--xl"
      :style="boxStyle"
      data-modal-drag="own"
    >
      <div class="page-wb-detail__modal-head" v-on="dragHandlers">
        <h5 class="page-wb-detail__modal-title">
          <i class="bi bi-collection"></i> Полка у конкурента
          <span class="page-wb-detail__modal-count">
            {{ anchorNm || '—' }} · {{ data?.title || '—' }}<template v-if="data?.date"> · {{ data.date }}</template>
          </span>
        </h5>
        <button type="button" class="btn-close" aria-label="Закрыть" @click="$emit('close')"></button>
      </div>

      <div v-if="loading" class="text-muted small mt-2">
        <span class="spinner-border spinner-border-sm"></span> Загрузка...
      </div>
      <div v-if="error" class="text-danger small mt-2">{{ error }}</div>

      <template v-else-if="data">
        <div v-if="data.anchor_title" class="page-wb-detail__shelf-hint">
          Карточка конкурента: {{ data.anchor_title }}
        </div>
        <div v-if="data.items.length" class="page-wb-detail__shelf-row" data-drag-scroll v-on="rowDrag.dragHandlers">
          <ShelfItemCard
            v-for="(it, i) in data.items"
            :key="`${it.nm_id}:${it.position}:${i}`"
            :item="it"
          />
        </div>
        <div v-else class="page-wb-detail__shelf-empty">
          По этому блоку позиций нет — снимка за {{ data.date || '—' }} не сохранилось.
        </div>
      </template>

      <div class="page-wb-detail__modal-foot">
        <button class="btn btn-sm btn-secondary" @click="$emit('close')">Закрыть</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ourCardApi, type ShelfBlockData } from '@/api/ourCard'
import ShelfItemCard from './ShelfItemCard.vue'
import { useDraggable } from '@/composables/useDraggable'
import { useDragScroll } from '@/composables/useDragScroll'

/** Вложенная модалка: вся собранная полка конкурента (клик по карточке
 *  во вкладке «Где мы на полках»). Наша карточка в ряду — с синей рамкой. */
const props = defineProps<{
  open: boolean
  nmId: number | string | null | undefined
  shelfId: number | null
  date?: string
}>()
defineEmits<{ (e: 'close'): void }>()

const data = ref<ShelfBlockData | null>(null)
const loading = ref(false)
const error = ref('')

// Модалка тянется за шапку, лента карточек — мышью.
const boxRef = ref<HTMLElement | null>(null)
const { boxStyle, dragHandlers } = useDraggable(boxRef)
const rowDrag = useDragScroll()

async function load() {
  const nm = Number(props.nmId || 0)
  const sid = Number(props.shelfId || 0)
  if (!nm || !sid) {
    data.value = null
    return
  }
  loading.value = true
  error.value = ''
  try {
    data.value = await ourCardApi.block(nm, sid, props.date)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Ошибка загрузки полки'
    data.value = null
  } finally {
    loading.value = false
  }
}

const anchorNm = computed(() => data.value?.anchor_nm || 0)

watch(
  () => [props.open, props.shelfId, props.date],
  ([open]) => {
    if (open) load()
  },
)
</script>
