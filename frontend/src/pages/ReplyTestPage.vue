<template>
  <div class="container-xxl page-reply-test">
    <div class="d-flex justify-content-between align-items-center mb-4">
      <h1 class="page-title mb-0">{{ $route.meta.title || 'Тестирование генерации автоответов' }}</h1>
      <router-link to="/wb-reply-rules" class="btn btn-outline-secondary">
        <i class="bi bi-list me-1"></i>Вернуться к правилам
      </router-link>
    </div>

    <div class="alert alert-warning">
      <strong>Внимание:</strong> На этой странице отображается тестовая сборка ответов для 100 последних отзывов. Никакие ответы на Wildberries сейчас <strong>не отправляются</strong>.
    </div>

    <div v-if="isLoading" class="text-center p-5">
      <div class="spinner-border text-primary" role="status"></div>
      <div class="mt-2 text-muted">Загрузка данных...</div>
    </div>
    <div v-else class="table-responsive">
      <table class="table table-bordered table-striped align-middle mb-0">
        <thead class="table-dark">
          <tr>
            <th>Товар / Отзыв</th>
            <th class="text-center">Оценка</th>
            <th>Сработавшее правило</th>
            <th>Сгенерированный текст ответа</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!rows.length">
            <td colspan="4" class="text-center text-muted">Отзывов для генерации не найдено.</td>
          </tr>
          <tr v-for="item in rows" :key="item.feedback.id">
            <td>
              <div class="fw-bold text-primary">[{{ item.feedback.nmID || '—' }}] {{ item.feedback.card_title || 'Неизвестный товар' }}</div>
              <div class="small text-muted mb-2">Бренд: <strong>{{ item.feedback.card_brand || '—' }}</strong></div>
              <div class="small text-muted mb-2">Имя: <strong>{{ item.feedback.userName || '—' }}</strong></div>
              <div class="p-2 border rounded bg-white small">
                <span class="fw-bold text-secondary">{{ item.feedback.userName || 'Покупатель' }}:</span>
                <span class="text-dark">{{ item.feedback.text || '(Отзыв без текста)' }}</span>
              </div>
            </td>
            <td class="text-center">
              <span class="badge page-reply-test__rating" :style="{ background: ratingColor(Number(item.feedback.productValuation)) }">{{ item.feedback.productValuation }} ★</span>
            </td>
            <td>
              <div v-if="item.matched_rule">
                <div class="fw-bold">{{ item.matched_rule.title }}</div>
                <div class="mt-1">
                  <span v-if="item.matched_rule.rule_type === 'general'" class="badge page-reply-test__pill--general">Общее</span>
                  <span v-else-if="item.matched_rule.rule_type === 'brand'" class="badge page-reply-test__pill--brand">По бренду</span>
                  <span v-else class="badge page-reply-test__pill--product">По товару</span>
                </div>
              </div>
              <span v-if="item.stop_hit" class="text-danger small"><i class="bi bi-slash-circle"></i> Стоп-слово: {{ item.stop_hit }}</span>
              <span v-else class="text-danger small"><i class="bi bi-exclamation-triangle"></i> Правило не найдено</span>
            </td>
            <td>
              <div v-if="item.matched_rule" class="p-2 rounded border bg-light page-reply-test__answer">{{ item.generated_text }}</div>
              <div v-else-if="item.stop_hit" class="text-muted small fst-italic">Ответ пропущен: в отзыве стоп-слово «{{ item.stop_hit }}».</div>
              <div v-else class="text-muted small fst-italic">Ответ пропущен, так как ни одно из правил не соответствует параметрам (оценка, наличие текста, бренд).</div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>


<script setup lang="ts">
import '@/assets/css/pages/page-reply-test.css'
import { ref, onMounted } from 'vue'
import { replyRulesApi, type ReplyTestItem } from '@/api/replyRules'

const rows = ref<ReplyTestItem[]>([])
const isLoading = ref(false)

function ratingColor(r: number) {
  if (r === 5) return '#198754'
  if (r === 4) return '#ffc107'
  if (r === 3) return '#6c757d'
  return '#dc3545'
}

onMounted(async () => {
  isLoading.value = true
  try {
    rows.value = await replyRulesApi.testGeneration()
  } catch {
    rows.value = []
  } finally {
    isLoading.value = false
  }
})
</script>
