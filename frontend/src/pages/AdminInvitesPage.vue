<template>
  <div class="container-xxl page-admin-invites">
    <div class="page-admin-invites__head">
      <h2 class="page-admin-invites__title">Инвайты</h2>
      <button @click="load" class="page-admin-invites__refresh">Обновить</button>
    </div>
    <div v-if="error" class="wb-error page-admin-invites__error">{{ error }}</div>

    <div class="page-admin-invites__new-box">
      <h3 class="page-admin-invites__new-title">Новый инвайт на компанию</h3>
      <div class="page-admin-invites__new-note">Получатель регистрируется по ссылке и создаёт компанию с этим именем, становится её owner. Токен одноразовый.</div>
      <form @submit.prevent="onCreate" class="page-admin-invites__new-form">
        <label>Название компании<input v-model="form.company_name" required class="wb-field" /></label>
        <label>Срок, дней<input v-model.number="form.expires_in_days" type="number" min="1" max="90" class="wb-field" /></label>
        <button type="submit" :disabled="creating" class="wb-btn-brand wb-btn-brand--form">Выпустить</button>
      </form>
      <div v-if="last" class="page-admin-invites__fresh">
        <div>Ссылка: <code>{{ registerLink }}</code> <button @click="copyFresh" class="page-admin-invites__copy">{{ freshCopied ? 'Скопировано' : 'Копировать' }}</button></div>
        <div class="page-admin-invites__fresh-until">до {{ fmtDT(last.expires_at) }}</div>
      </div>
    </div>

    <table class="wb-admin-table page-admin-invites__table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Тип</th>
          <th>Компания / email</th>
          <th>Роль</th>
          <th>Статус</th>
          <th>Использовал</th>
          <th>Создан</th>
          <th>Кем</th>
          <th>Истекает</th>
          <th>Ссылка</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="t in rows" :key="t.id">
          <td>{{ t.id }}</td>
          <td>{{ t.token_type }}</td>
          <td>{{ t.token_type === 'company' ? t.company_name : `${t.company_label || ('#' + t.company_id)} / ${t.target_email}` }}</td>
          <td>{{ t.role || '—' }}</td>
          <td><span :style="statusStyle(t.status)">{{ statusLabel(t.status) }}</span></td>
          <td>{{ t.used_by_name ? `${t.used_by_name} (${t.used_by})` : '—' }}</td>
          <td class="page-admin-invites__cell-nowrap">{{ fmtDT(t.created_at) }}</td>
          <td>{{ t.created_by_name || '—' }}</td>
          <td class="page-admin-invites__cell-nowrap">{{ fmtDT(t.expires_at) }}</td>
          <td class="page-admin-invites__cell-nowrap">
            <button v-if="t.status === 'active'" @click="copyRow(t)" :disabled="copyingId === t.id" class="page-admin-invites__copy-btn">{{ copyingId === t.id ? '...' : copiedId === t.id ? 'Скопировано' : 'Копировать' }}</button>
            <span v-else class="page-admin-invites__copy-empty">—</span>
          </td>
        </tr>
        <tr v-if="!rows.length"><td colspan="10" class="page-admin-invites__empty">Нет токенов</td></tr>
      </tbody>
    </table>
    <div class="page-admin-invites__foot">User-инвайты выпускаются из карточки компании (owner/admin) — здесь они тоже видны. Сырые токены не хранятся: ссылка восстанавливается расшифровкой только для активных токенов.</div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-admin-invites.css'
import { reactive, ref, computed, onMounted } from 'vue'
import { authApi } from '../api/auth'

const rows = ref<any[]>([])
const error = ref('')
const form = reactive({ company_name: '', expires_in_days: 30 })
const creating = ref(false)
const last = ref<{ invite_token: string; expires_at: string } | null>(null)
const freshCopied = ref(false)
const copiedId = ref<number | null>(null)
const copyingId = ref<number | null>(null)

const registerLink = computed(() => last.value ? `${location.origin}/register?invite=${last.value.invite_token}` : '')
const fmtDT = (v: any) => v ? new Date(String(v).replace(' ', 'T')).toLocaleString('ru-RU') : '—'
const statusLabel = (s: string) => s === 'active' ? 'Активен' : s === 'used' ? 'Использован' : 'Просрочен'
const statusStyle = (s: string) => {
  const base = 'display:inline-block; padding:2px 8px; border-radius:10px; font-size:12px; white-space:nowrap;'
  if (s === 'active') return base + 'background:#E4F5EF; color:#1E9E7C'
  if (s === 'used') return base + 'background:#F1F1F4; color:#6E6A80'
  return base + 'background:#FBEBEC; color:#E0525C'
}

// navigator.clipboard работает только в secure-контексте (https/localhost) —
// на http по IP падаем в fallback через textarea (как PageHeaderWidget copyId)
async function copyText(t: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(t)
    return true
  } catch { /* fallback ниже */ }
  try {
    const ta = document.createElement('textarea')
    ta.value = t
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    return ok
  } catch { return false }
}

async function load() {
  error.value = ''
  try { rows.value = await authApi.listInvites() }
  catch (e: any) { error.value = e?.response?.data?.detail || String(e) }
}

async function onCreate() {
  creating.value = true
  last.value = null
  freshCopied.value = false
  try {
    const r = await authApi.createInvite({ company_name: form.company_name, expires_in_days: form.expires_in_days })
    last.value = { invite_token: r.invite_token, expires_at: r.expires_at }
    form.company_name = ''
    await load()
  } catch (e: any) { error.value = e?.response?.data?.detail || String(e) }
  finally { creating.value = false }
}

async function copyFresh() {
  if (!last.value) return
  freshCopied.value = await copyText(registerLink.value)
  if (!freshCopied.value) error.value = 'Не удалось скопировать — скопируйте ссылку вручную'
}

async function copyRow(t: any) {
  copyingId.value = t.id
  copiedId.value = null
  try {
    const r = await authApi.inviteLink(t.id)
    const ok = await copyText(`${location.origin}${r.register_path}`)
    if (ok) copiedId.value = t.id
    else error.value = 'Не удалось скопировать — попробуйте ещё раз'
  } catch (e: any) { error.value = e?.response?.data?.detail || String(e) }
  finally { copyingId.value = null }
}

onMounted(load)
</script>
