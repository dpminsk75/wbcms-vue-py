<template>
  <div class="container-xxl page-reply-rules">
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h1 class="page-title mb-0">{{ $route.meta.title || 'Автоответы на отзывы' }}</h1>
      <div class="d-flex gap-2">
        <router-link to="/wb-reply-rules/test-generation" class="btn btn-outline-secondary">
          <i class="bi bi-flask me-1"></i>Тест генерации
        </router-link>
        <router-link to="/wb-reply-rules/create" class="btn btn-primary">
          <i class="bi bi-plus-lg me-1"></i>Добавить правило
        </router-link>
      </div>
    </div>

    <div v-if="isLoading" class="text-center p-5">
      <div class="spinner-border text-primary" role="status"></div>
      <div class="mt-2 text-muted">Загрузка данных...</div>
    </div>
    <div v-else class="card">
      <div class="wb-table-wrap">
        <table class="table table-striped table-bordered align-middle mb-0">
          <thead>
            <tr>
              <th></th>
              <th>Название</th>
              <th>Товары</th>
              <th>Рейтинг</th>
              <th>Тип отзыва</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in rows" :key="r.id">
              <td class="text-center">
                <input type="checkbox" :checked="!!r.is_active" :title="r.is_active ? 'Выключить' : 'Включить'" @change="onToggle(r)" />
              </td>
              <td>
                <strong>{{ r.title }}</strong>
                <div class="small text-muted mt-1 page-reply-rules__title-sub">
                  <i class="bi bi-pencil"></i> {{ fmtDate(r.updated_at) }}
                </div>
              </td>
              <td>
                <span v-if="r.rule_type === 'general'" class="page-reply-rules__pill page-reply-rules__pill--general">Общее</span>
                <span v-else-if="r.rule_type === 'brand'">
                  <span v-if="!r.brands.length" class="text-danger small">Для брендов (не выбраны)</span>
                  <span v-else v-for="b in r.brands" :key="b" class="badge me-1 mb-1 page-reply-rules__pill page-reply-rules__pill--brand">{{ b }}</span>
                </span>
                <span v-else-if="r.rule_type === 'product'">
                  <span v-if="!r.products.length" class="text-danger small">Для товаров (не выбраны)</span>
                  <span v-else v-for="p in r.products" :key="p.nmID" class="badge me-1 mb-1 page-reply-rules__pill page-reply-rules__pill--product">[{{ p.nmID }}] {{ p.title || ('Товар ' + p.nmID) }}</span>
                </span>
                <span v-else class="text-muted small page-reply-rules__type--none">{{ r.rule_type }}</span>
              </td>
              <td class="text-nowrap">{{ r.rating_min === r.rating_max ? `${r.rating_min} ★` : `${r.rating_min}–${r.rating_max} ★` }}</td>
              <td>
                <span v-if="r.text_condition === 'any'">Любой</span>
                <span v-else-if="r.text_condition === 'with_text'">С текстом</span>
                <span v-else class="badge page-reply-rules__notext">Без текста</span>
              </td>
              <td class="text-nowrap text-end">
                <router-link :to="`/wb-reply-rules/${r.id}/edit`" class="btn btn-sm btn-light page-reply-rules__action" title="Редактировать"><i class="bi bi-pencil"></i></router-link>
                <button class="btn btn-sm btn-light" title="Удалить" @click="onDelete(r)"><i class="bi bi-trash"></i></button>
              </td>
            </tr>
            <tr v-if="!rows.length"><td colspan="6" class="text-center text-muted p-4">Правил пока нет</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="page-reply-rules__pager">
      <button class="btn btn-sm btn-light" :disabled="page <= 1" @click="goPage(page - 1)">‹ Назад</button>
      <span class="page-reply-rules__pager-label">Стр. {{ page }} из {{ totalPages }}</span>
      <button class="btn btn-sm btn-light" :disabled="page >= totalPages" @click="goPage(page + 1)">Вперёд ›</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-reply-rules.css'
import { ref, computed, onMounted } from 'vue'
import { replyRulesApi, type ReplyRuleItem } from '@/api/replyRules'

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
function fmtDate(ts: any) {
  if (!ts) return ''
  const d = new Date(Number(ts) * 1000)
  if (isNaN(d.getTime())) return ''
  const mon = ['янв.', 'фев.', 'мар.', 'апр.', 'мая', 'июн.', 'июл.', 'авг.', 'сен.', 'окт.', 'ноя.', 'дек.'][d.getMonth()]
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d.getDate())} ${mon} ${p(d.getHours())}:${p(d.getMinutes())}`
}
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

