<template>
  <div class="container-xxl page-competitor">
    <h2 class="page-competitor__title">Выбор фраз — nmID {{ nmId }}</h2>
    <p><router-link to="/competitor/index">← Конкуренты</router-link></p>
    <div v-if="error" class="wb-error">{{ error }}</div>

    <div v-if="card" class="card page-competitor__card-head">
      <div class="card-body">
        <div><b>{{ card.title || '' }}</b></div>
        <div class="small text-muted">nmID {{ nmId }} | {{ card.brand || '' }}</div>
      </div>
    </div>

    <div v-if="!loading && !phrases.length" class="alert alert-warning">Нет поисковых фраз для этого товара.</div>
    <form v-else @submit.prevent="onSubmit">
      <div class="card page-competitor__block">
        <div class="card-header page-competitor__block-head">
          <span><i class="bi bi-search"></i> Поисковые фразы ({{ phrases.length }})</span>
          <div>
            <button type="button" @click="checkAll(true)" class="btn btn-sm btn-outline-secondary">Выбрать все</button>
            <button type="button" @click="checkAll(false)" class="btn btn-sm btn-outline-secondary">Снять все</button>
          </div>
        </div>
        <div class="card-body page-competitor__phrases">
          <div v-for="p in phrases" :key="p" class="form-check">
            <input v-model="checked" :value="p" class="form-check-input" type="checkbox" :id="'ph-' + hash(p)" />
            <label class="form-check-label" :for="'ph-' + hash(p)">{{ p }}</label>
          </div>
        </div>
      </div>
      <div class="card page-competitor__block">
        <div class="card-header"><i class="bi bi-sort-numeric-down"></i> Позиция в выдаче</div>
        <div class="card-body">
          <div class="btn-group" role="group">
            <button v-for="v in [6, 9, 12, 0]" :key="v" type="button" @click="positionMax = v"
              class="btn btn-sm" :class="positionMax === v ? 'btn-primary' : 'btn-outline-primary'">
              {{ v === 0 ? 'Все' : `1–${v}` }}
            </button>
          </div>
          <div class="small text-muted">Только конкуренты с позицией в указанном диапазоне</div>
        </div>
      </div>
      <button type="submit" :disabled="saving || !checked.length" class="btn btn-primary">
        <i class="bi bi-arrow-right"></i> Далее — выбрать конкурентов
      </button>
    </form>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-competitor.css'
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { competitorApi } from '../api/competitor'

const route = useRoute()
const router = useRouter()
const nmId = Number(route.params.nm)
const phrases = ref<string[]>([])
const checked = ref<string[]>([])
const positionMax = ref(9)
const card = ref<{ title?: string; brand?: string } | null>(null)
const loading = ref(false)
const saving = ref(false)
const error = ref('')

const hash = (s: string) => {
  let h = 0
  for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0
  return String(Math.abs(h))
}
function checkAll(v: boolean) {
  checked.value = v ? [...phrases.value] : []
}

onMounted(async () => {
  loading.value = true
  try {
    const r = await competitorApi.phrases(nmId)
    phrases.value = r.phrases
    checked.value = r.selected.length ? r.phrases.filter((p) => r.selected.includes(p)) : [...r.phrases]
    card.value = r.card
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    loading.value = false
  }
})

async function onSubmit() {
  saving.value = true
  error.value = ''
  try {
    await competitorApi.select(nmId, checked.value, positionMax.value)
    router.push(`/competitor/selected/${nmId}`)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    saving.value = false
  }
}
</script>
