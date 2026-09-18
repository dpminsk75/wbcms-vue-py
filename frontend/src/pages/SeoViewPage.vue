<template>
  <div class="container-xxl page-seo">
    <div class="page-seo__head">
      <h2 class="page-seo__title">SEO рекомендация #{{ id }}</h2>
      <router-link :to="{ path: '/seo/index', query: { status: rec?.status || 'new' } }" class="btn btn-sm btn-outline-secondary">← К списку</router-link>
    </div>
    <div v-if="error" class="wb-error">{{ error }}</div>
    <div v-if="loading" class="text-muted">Загрузка…</div>
    <div v-if="rec && !loading" class="page-seo__view-stack">
      <div class="card">
        <div class="card-body page-seo__view-product">
          <img :src="rec.card?.photo || '/images/no-photo.png'" alt="" class="page-seo__thumb page-seo__thumb--lg" />
          <div>
            <div class="fw-semibold">{{ rec.card?.title }}</div>
            <div class="small text-muted">nmID {{ rec.nmID }} • {{ rec.card?.subjectName }} • {{ rec.card?.brand }} • {{ rec.card?.vendorCode }}</div>
            <div>
              <a :href="`/wb/detail?nm_id=${rec.nmID}`" target="_blank" class="page-seo__ext-link">WB:{{ rec.nmID }}</a>
              <a :href="`/wb-search/card?nm_id=${rec.nmID}`" target="_blank" class="page-seo__ext-link">фразы</a>
            </div>
          </div>
          <div class="page-seo__view-actions">
            <button v-if="rec.status === 'new'" @click="markViewed" class="btn btn-sm btn-success"><i class="bi bi-check"></i> Просмотрено</button>
            <button @click="requeue" class="btn btn-sm btn-outline-warning" title="Вернуть в обработку"><i class="bi bi-arrow-counterclockwise"></i> В обработку</button>
          </div>
        </div>
      </div>
      <div class="card">
        <div class="card-header">Rationale</div>
        <div class="card-body page-seo__pre">{{ rec.rationale || '' }}</div>
      </div>
      <div class="page-seo__view-cols">
        <div class="card">
          <div class="card-header">Старое: {{ (rec.old_title || '').length }} / {{ (rec.old_description || '').length }}</div>
          <div class="card-body">
            <div class="page-seo__text-box">{{ rec.old_title || '' }}</div>
            <div class="page-seo__text-box page-seo__text-box--scroll">{{ rec.old_description || '' }}</div>
          </div>
        </div>
        <div class="card">
          <div class="card-header page-seo__new-head">Новое: {{ (rec.new_title || '').length }} / {{ (rec.new_description || '').length }}</div>
          <div class="card-body">
            <div class="page-seo__text-box page-seo__text-box--new">{{ rec.new_title || '' }}</div>
            <div class="page-seo__text-box page-seo__text-box--new page-seo__text-box--scroll">{{ rec.new_description || '' }}</div>
          </div>
        </div>
      </div>
      <div v-if="(rec.keywords_added || []).length || (rec.keywords_removed || []).length" class="card">
        <div class="card-header">Ключи</div>
        <div class="card-body">
          <span v-for="k in rec.keywords_added || []" :key="'a' + k" class="badge bg-success page-seo__key">{{ k }}</span>
          <span v-for="k in rec.keywords_removed || []" :key="'r' + k" class="badge bg-light text-dark page-seo__key">{{ k }}</span>
        </div>
      </div>
      <div class="card">
        <div class="card-header">Целевые фразы</div>
        <div class="card-body">
          <ul class="page-seo__targets">
            <li v-for="t in rec.targets || []" :key="t.id">
              {{ t.phrase }} <span class="text-muted small">(приоритет {{ t.priority }})</span>
              <a href="#" @click.prevent="removeTarget(t.id)" class="page-seo__perm-drop" title="Удалить">×</a>
            </li>
            <li v-if="!(rec.targets || []).length" class="text-muted">нет целевых фраз</li>
          </ul>
          <form @submit.prevent="addTarget" class="page-seo__target-form">
            <input v-model="newPhrase" class="form-control form-control-sm page-seo__target-input" placeholder="Новая фраза (до 500 симв)" maxlength="500" />
            <button type="submit" class="btn btn-sm btn-outline-primary">Добавить</button>
          </form>
        </div>
      </div>
      <div v-if="isAdmin" class="small text-muted">Модель: {{ rec.model || '—' }} • conf: {{ rec.confidence ?? '—' }} • prompt: {{ rec.prompt_tokens ?? '—' }} • compl: {{ rec.completion_tokens ?? '—' }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-seo.css'
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { seoApi, type SeoRec } from '../api/seo'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const id = Number(route.params.id)
const rec = ref<(SeoRec & { targets?: Array<{ id: number; nmID: number; phrase: string; priority: number }>; raw_json?: any }) | null>(null)
const loading = ref(false)
const error = ref('')
const newPhrase = ref('')
const isAdmin = computed(() => auth.isAdmin)

async function load() {
  loading.value = true
  error.value = ''
  try {
    rec.value = await seoApi.view(id)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    loading.value = false
  }
}
async function markViewed() {
  if (!confirm('Отметить как просмотрено?')) return
  await seoApi.markViewed(id)
  router.replace({ path: '/seo/index', query: { status: 'viewed' } })
}
async function requeue() {
  await seoApi.requeue(id)
  load()
}
async function addTarget() {
  if (!newPhrase.value.trim() || !rec.value) return
  try {
    await seoApi.addTarget(rec.value.nmID, newPhrase.value.trim())
    newPhrase.value = ''
    load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  }
}
async function removeTarget(tid: number) {
  await seoApi.removeTarget(tid)
  load()
}
onMounted(load)
</script>
