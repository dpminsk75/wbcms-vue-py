<template>
  <div class="container-xxl page-reply-rules">
    <WbWorkspaceHead :title="$route.meta.title || 'Автоответы на отзывы'" :workspace-tabs="FEEDBACK_TABS" workspace-active="rules"
                  :subtabs="FEEDBACK_RULES_SUB_TABS" />

    <!-- Таблица правил — блок темы .tbl-card (theme.md §5.7.9) -->
    <div class="tbl-card page-reply-rules__card">
      <div class="card__hd">
        <span>Правила автоответа</span>
        <span class="hd-badge">Всего: {{ total }}</span>
        <span class="spacer"></span>
        <router-link to="/wb-feedback-reply-rules/stop-words" class="hd-btn">
          <i class="bi bi-slash-circle me-1"></i>Стоп-слова
        </router-link>
        <router-link to="/wb-feedback-reply-rules/test-generation" class="hd-btn">
          <i class="bi bi-flask me-1"></i>Тест генерации
        </router-link>
        <router-link to="/wb-feedback-reply-rules/create" class="hd-btn">
          <i class="bi bi-plus-lg me-1"></i>Добавить правило
        </router-link>
      </div>

      <div v-if="isLoading" class="page-reply-rules__loading">Загрузка данных…</div>
      <div v-else class="tbl-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th class="page-reply-rules__col-check"></th>
              <th class="t-left">Название</th>
              <th class="t-left">Товары</th>
              <th class="t-left">Рейтинг</th>
              <th class="t-left">Тип отзыва</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in rows" :key="r.id">
              <td class="t-center">
                <input type="checkbox" :checked="!!r.is_active" :title="r.is_active ? 'Выключить' : 'Включить'" @change="onToggle(r)" />
              </td>
              <td class="t-left">
                <strong>{{ r.title }}</strong>
                <div class="page-reply-rules__title-sub">
                  <i class="bi bi-pencil"></i> {{ fmtDate(r.updated_at) }}
                </div>
              </td>
              <td class="t-left">
                <span v-if="r.rule_type === 'general'" class="badge badge--neutral">Общее</span>
                <span v-else-if="r.rule_type === 'brand'">
                  <span v-if="!r.brands.length" class="page-reply-rules__bad">Для брендов (не выбраны)</span>
                  <span v-else v-for="b in r.brands" :key="b" class="badge badge--info page-reply-rules__badge">{{ b }}</span>
                </span>
                <span v-else-if="r.rule_type === 'product'">
                  <span v-if="!r.products.length" class="page-reply-rules__bad">Для товаров (не выбраны)</span>
                  <span v-else v-for="p in r.products" :key="p.nmID" class="badge badge--warn page-reply-rules__badge">[{{ p.nmID }}] {{ p.title || ('Товар ' + p.nmID) }}</span>
                </span>
                <span v-else class="page-reply-rules__muted page-reply-rules__type--none">{{ r.rule_type }}</span>
              </td>
              <td class="t-left num">{{ r.rating_min === r.rating_max ? `${r.rating_min} ★` : `${r.rating_min}–${r.rating_max} ★` }}</td>
              <td class="t-left">
                <span v-if="r.text_condition === 'any'">Любой</span>
                <span v-else-if="r.text_condition === 'with_text'">С текстом</span>
                <span v-else class="badge badge--warn">Без текста</span>
              </td>
              <td class="t-right num">
                <router-link :to="`/wb-feedback-reply-rules/${r.id}/edit`" class="btn btn--outline btn-sm page-reply-rules__action" title="Редактировать"><i class="bi bi-pencil"></i></router-link>
                <button class="btn btn--danger btn-sm" title="Удалить" @click="onDelete(r)"><i class="bi bi-trash"></i></button>
              </td>
            </tr>
            <tr v-if="!rows.length"><td colspan="6" class="t-center page-reply-rules__empty">Правил пока нет</td></tr>
          </tbody>
        </table>
      </div>

      <div class="wb-pager">
        <button class="btn btn--outline btn-sm" :disabled="page <= 1" @click="goPage(page - 1)">‹ Назад</button>
        <span class="wb-pager__label">Стр. {{ page }} из {{ totalPages }}</span>
        <button class="btn btn--outline btn-sm" :disabled="page >= totalPages" @click="goPage(page + 1)">Вперёд ›</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-reply-rules.css'
import { ref, computed, onMounted } from 'vue'
import { replyRulesApi, type ReplyRuleItem } from '@/api/replyRules'
import WbWorkspaceHead from '@/components/common/WbWorkspaceHead.vue'
import { FEEDBACK_TABS, FEEDBACK_RULES_SUB_TABS } from '@/components/common/workspaceTabs'

const rows = ref<ReplyRuleItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const isLoading = ref(false)

async function fetchData() {
  isLoading.value = true
  try {
    const data = await replyRulesApi.list(page.value)
    rows.value = data.items || []
    total.value = data.total || 0
  } catch {
    rows.value = []
    total.value = 0
  } finally {
    isLoading.value = false
  }
}
function goPage(p: number) {
  page.value = p
  fetchData()
}
import { useDateFmt } from '../composables/useDateFmt'
const { fmtDateTime: fmtDate } = useDateFmt()
async function onToggle(r: ReplyRuleItem) {
  const prev = !!r.is_active
  r.is_active = prev ? 0 : 1
  try {
    const res = await replyRulesApi.toggle(r.id)
    r.is_active = res.is_active ? 1 : 0
  } catch (e: any) {
    r.is_active = prev ? 1 : 0
    alert(e?.response?.data?.detail || 'Не удалось переключить правило')
  }
}
async function onDelete(r: ReplyRuleItem) {
  if (!confirm(`Удалить правило «${r.title}»?`)) return
  try {
    await replyRulesApi.remove(r.id)
    rows.value = rows.value.filter((x) => x.id !== r.id)
    total.value = Math.max(0, total.value - 1)
  } catch (e: any) {
    alert(e?.response?.data?.detail || String(e))
  }
}

onMounted(fetchData)
</script>
