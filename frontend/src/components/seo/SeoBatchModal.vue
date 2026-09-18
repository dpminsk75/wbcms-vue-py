<template>
  <div v-if="open" class="page-seo__modal-backdrop">
    <div class="page-seo__modal-box">
      <div class="page-seo__modal-head">
        <h5 class="page-seo__modal-title"><i class="bi bi-robot"></i> Обработка</h5>
        <button type="button" class="btn-close" @click="$emit('close')" aria-label="Close"></button>
      </div>
      <div class="text-center">
        <div v-if="!job.finished" class="spinner-border text-primary" role="status"></div>
        <div class="small">{{ statusText }}</div>
        <div class="progress page-seo__modal-progress">
          <div class="progress-bar progress-bar-striped progress-bar-animated" :style="{ width: job.progress + '%' }"></div>
        </div>
      </div>
      <ul class="page-seo__modal-items">
        <li v-for="it in job.job?.items || []" :key="it.id" class="page-seo__modal-item">
          <span v-if="it.status === 'done'" class="text-success"><i class="bi bi-check-circle"></i></span>
          <span v-else-if="it.status === 'error'" class="text-danger"><i class="bi bi-x-circle"></i></span>
          <span v-else class="spinner-border spinner-border-sm text-primary"></span>
          {{ it.label }}
          <span v-if="it.error" class="text-danger small"> — {{ it.error }}</span>
          <router-link v-if="it.status === 'done' && it.result?.rec_id" :to="`/seo/view/${it.result.rec_id}`" class="small">открыть</router-link>
        </li>
      </ul>
      <div class="page-seo__modal-foot">
        <button type="button" class="btn btn-outline-danger btn-sm" @click="onAbort"><i class="bi bi-stop-circle"></i> Прервать</button>
        <button type="button" class="btn btn-secondary btn-sm" @click="$emit('close')">Свернуть (фоном)</button>
      </div>
      <div class="small text-muted">Прервать — остановит опрос (сервер дожмёт текущую карточку). Свернуть — продолжит в фоне.</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useAiJob } from '../../composables/useAiJob'

const props = defineProps<{ jobId: number | null; open: boolean }>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'done'): void }>()

const job = useAiJob()
const statusText = computed(() => {
  const j = job.job.value
  if (!j) return 'Старт...'
  if (job.finished.value) return j.status === 'done' ? `Готово: ${j.total} шт` : `Завершено с ошибкой: ${j.error || j.status}`
  return `Обрабатываю ${Math.min(j.done + 1, j.total)}/${j.total}...`
})

onMounted(() => { if (props.jobId) job.start(props.jobId) })
watch(() => props.jobId, (id) => { if (id && props.open) job.start(id) })
watch(() => job.finished.value, (f) => { if (f) emit('done') })

function onAbort() {
  job.stop()
  emit('close')
}
</script>
