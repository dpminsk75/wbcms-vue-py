<template>
  <div class="container-xxl page-reply-test">
    <WbWorkspaceHead :title="$route.meta.title || 'Тестирование генерации автоответов'" :workspace-tabs="FEEDBACK_TABS" workspace-active="rules"
                  :subtabs="FEEDBACK_RULES_SUB_TABS" />

    <div class="page-reply-test__notice">
      <b>Внимание:</b> На этой странице отображается тестовая сборка ответов для 100 последних отзывов.
      Никакие ответы на Wildberries сейчас <b>не отправляются</b>.
    </div>

    <!-- Тестовая сборка — блок темы .tbl-card (theme.md §5.7.9) -->
    <div class="tbl-card page-reply-test__card">
      <div class="card__hd">
        <span>Тест генерации автоответов</span>
        <span class="spacer"></span>
        <router-link to="/wb-feedback-reply-rules" class="hd-btn">
          <i class="bi bi-list me-1"></i>Вернуться к правилам
        </router-link>
      </div>

      <div v-if="isLoading" class="page-reply-test__loading">Загрузка данных…</div>
      <div v-else class="tbl-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th class="t-left">Товар / Отзыв</th>
              <th class="t-center">Оценка</th>
              <th class="t-left">Сработавшее правило</th>
              <th class="t-left">Сгенерированный текст ответа</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!rows.length">
              <td colspan="4" class="t-center page-reply-test__empty">Отзывов для генерации не найдено.</td>
            </tr>
            <tr v-for="item in rows" :key="item.feedback.id">
              <td class="t-left">
                <div class="page-reply-test__title">[{{ item.feedback.nmID || '—' }}] {{ item.feedback.card_title || 'Неизвестный товар' }}</div>
                <div class="page-reply-test__meta">Бренд: <b>{{ item.feedback.card_brand || '—' }}</b></div>
                <div class="page-reply-test__meta">Имя: <b>{{ item.feedback.userName || '—' }}</b></div>
                <div class="page-reply-test__review">
                  <span class="page-reply-test__review-author">{{ item.feedback.userName || 'Покупатель' }}:</span>
                  <span>{{ item.feedback.text || '(Отзыв без текста)' }}</span>
                </div>
              </td>
              <td class="t-center">
                <span class="badge" :class="ratingBadge(Number(item.feedback.productValuation))">{{ item.feedback.productValuation }} ★</span>
              </td>
              <td class="t-left">
                <div v-if="item.matched_rule">
                  <div class="page-reply-test__rule-title">{{ item.matched_rule.title }}</div>
                  <div class="mt-1">
                    <span v-if="item.matched_rule.rule_type === 'general'" class="badge badge--neutral">Общее</span>
                    <span v-else-if="item.matched_rule.rule_type === 'brand'" class="badge badge--info">По бренду</span>
                    <span v-else class="badge badge--warn">По товару</span>
                  </div>
                </div>
                <span v-if="item.stop_hit" class="page-reply-test__bad page-reply-test__small"><i class="bi bi-slash-circle"></i> Стоп-слово: {{ item.stop_hit }}</span>
                <span v-else class="page-reply-test__bad page-reply-test__small"><i class="bi bi-exclamation-triangle"></i> Правило не найдено</span>
              </td>
              <td class="t-left">
                <div v-if="item.matched_rule" class="page-reply-test__answer">{{ item.generated_text }}</div>
                <div v-else-if="item.stop_hit" class="page-reply-test__muted page-reply-test__small">Ответ пропущен: в отзыве стоп-слово «{{ item.stop_hit }}».</div>
                <div v-else class="page-reply-test__muted page-reply-test__small">Ответ пропущен, так как ни одно из правил не соответствует параметрам (оценка, наличие текста, бренд).</div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>


<script setup lang="ts">
import '@/assets/css/pages/page-reply-test.css'
import { ref, onMounted } from 'vue'
import { replyRulesApi, type ReplyTestItem } from '@/api/replyRules'
import WbWorkspaceHead from '@/components/common/WbWorkspaceHead.vue'
import { FEEDBACK_TABS, FEEDBACK_RULES_SUB_TABS } from '@/components/common/workspaceTabs'

const rows = ref<ReplyTestItem[]>([])
const isLoading = ref(false)

/** Оценка — бейдж темы (§5.7): без hex в разметке. */
function ratingBadge(r: number) {
  if (r === 5) return 'badge--ok'
  if (r === 4) return 'badge--warn'
  if (r === 3) return 'badge--neutral'
  return 'badge--bad'
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
