<template>
  <div class="ext-tokens-block">
    <h3 class="ext-tokens-block__title">Токены расширения</h3>
    <div class="text-muted small">Bearer для расширения-коллектора. Храним только sha256 — сырой токен показывается один раз при выдаче. Отзыв — по одному.</div>
    <div v-if="error" class="wb-error">{{ error }}</div>
    <div v-if="loading" class="text-muted">Загрузка…</div>
    <table v-else-if="tokens.length" class="wb-admin-table ext-tokens-block__table">
      <thead>
        <tr>
          <th>Название</th>
          <th>Префикс</th>
          <th>Активен</th>
          <th>Использован</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="t in tokens" :key="t.id">
          <td>{{ t.name || '—' }}</td>
          <td><code>{{ t.token_prefix }}…</code></td>
          <td>
            <span v-if="t.is_active" class="badge bg-success">да</span>
            <span v-else class="badge bg-light text-muted border">отозван</span>
          </td>
          <td>{{ t.last_used_at ? fmtDT(t.last_used_at) : '—' }}</td>
          <td>
            <button v-if="t.is_active" @click="onRevoke(t.id)" :disabled="revoking === t.id" class="ext-tokens-block__revoke" title="Отозвать токен">Отозвать</button>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-else class="text-muted small">токенов пока нет</div>
    <form @submit.prevent="onCreate" class="ext-tokens-block__form">
      <input v-model="name" placeholder="ноут-Иван" maxlength="100" class="form-control form-control-sm ext-tokens-block__input" />
      <button type="submit" :disabled="creating" class="btn btn-outline-secondary btn-sm" title="Сырой токен покажется один раз — скопируйте сразу">
        <i class="bi bi-key"></i> Выдать токен
      </button>
      <button type="button" @click="onDownload" :disabled="downloading" class="btn btn-outline-primary btn-sm" title="Zip с вшитым адресом сервера (токен вводится в popup руками)">
        <i class="bi bi-download"></i> {{ downloading ? 'Готовлю…' : 'Скачать расширение' }}
      </button>
      <button type="button" @click="showGuide = true" class="btn btn-outline-secondary btn-sm" title="Side-load: установка и настройка по шагам">
        <i class="bi bi-question-circle"></i> Как установить
      </button>
    </form>
    <div v-if="raw" class="ext-tokens-block__once">
      <div>Токен (показан один раз): <code>{{ raw }}</code></div>
    </div>
    <ExtInstallModal :open="showGuide" :companyId="companyId" @close="showGuide = false" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { extTokensApi, type ExtToken } from '../../api/extTokens'
import ExtInstallModal from './ExtInstallModal.vue'

const props = defineProps<{ companyId: number }>()

const tokens = ref<ExtToken[]>([])
const loading = ref(false)
const creating = ref(false)
const downloading = ref(false)
const revoking = ref<number | null>(null)
const name = ref('')
const raw = ref('')
const error = ref('')
const showGuide = ref(false)
const fmtDT = (v: any) => v ? new Date(String(v).replace(' ', 'T')).toLocaleString('ru-RU') : '—'

async function load() {
  loading.value = true
  error.value = ''
  try {
    tokens.value = await extTokensApi.list(props.companyId)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    loading.value = false
  }
}

async function onCreate() {
  creating.value = true
  error.value = ''
  raw.value = ''
  try {
    const t = await extTokensApi.create(props.companyId, name.value.trim())
    raw.value = t.token || ''
    name.value = ''
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    creating.value = false
  }
}

async function onDownload() {
  downloading.value = true
  error.value = ''
  try {
    await extTokensApi.download(props.companyId)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    downloading.value = false
  }
}

async function onRevoke(tokenId: number) {
  if (!confirm('Отозвать токен? Расширение с ним перестанет работать.')) return
  revoking.value = tokenId
  error.value = ''
  try {
    await extTokensApi.revoke(props.companyId, tokenId)
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    revoking.value = null
  }
}

onMounted(load)
</script>

<style scoped>
.ext-tokens-block { border: 1px solid #b6d4fe; padding: 14px; border-radius: 8px; max-width: 640px; }
.ext-tokens-block__title { margin: 0 0 2px; font-size: 17px; }
.ext-tokens-block__table { margin: 10px 0; }
.ext-tokens-block__revoke { color: #c00; background: none; border: none; padding: 0; cursor: pointer; }
.ext-tokens-block__form { display: flex; gap: 8px; align-items: center; margin-top: 10px; flex-wrap: wrap; }
.ext-tokens-block__input { max-width: 220px; }
.ext-tokens-block__once { margin-top: 12px; padding: 10px; background: #eef7ee; border-radius: 6px; word-break: break-all; }
</style>
