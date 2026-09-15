<template>
  <div class="container-xxl" style="padding:20px 15px">
    <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:16px">
      <h2 style="margin:0">Инвайты</h2>
      <button @click="load" style="padding:6px 12px; border:1px solid #ccc; background:#fff; border-radius:6px">Обновить</button>
    </div>
    <div v-if="error" style="color:#c00; margin-bottom:12px">{{ error }}</div>

    <div style="border:1px solid #ddd; padding:14px; border-radius:8px; max-width:520px; margin-bottom:20px">
      <h3 style="margin:0 0 10px">Новый инвайт на компанию</h3>
      <div style="font-size:12px; color:#666; margin-bottom:10px">Получатель регистрируется по ссылке и создаёт компанию с этим именем, становится её owner. Токен одноразовый.</div>
      <form @submit.prevent="onCreate" style="display:flex; flex-direction:column; gap:8px">
        <label>Название компании<input v-model="form.company_name" required style="width:100%" /></label>
        <label>Срок, дней<input v-model.number="form.expires_in_days" type="number" min="1" max="90" style="width:100%" /></label>
        <button type="submit" :disabled="creating" style="background:#4A3A8C; color:#fff; border:none; padding:8px; border-radius:6px">Выпустить</button>
      </form>
      <div v-if="last" style="margin-top:12px; padding:10px; background:#eef7ee; border-radius:6px; word-break:break-all">
        <div>Ссылка: <code>{{ registerLink }}</code> <button @click="copyFresh" style="margin-left:6px">{{ freshCopied ? 'Скопировано' : 'Копировать' }}</button></div>
        <div style="font-size:12px; color:#555">до {{ fmtDT(last.expires_at) }}</div>
      </div>
    </div>

    <table style="width:100%; border-collapse:collapse; font-size:13px">
      <thead>
        <tr style="background:#f4f4f8">
          <th style="text-align:left; padding:8px">ID</th>
          <th style="text-align:left; padding:8px">Тип</th>
          <th style="text-align:left; padding:8px">Компания / email</th>
          <th style="text-align:left; padding:8px">Роль</th>
          <th style="text-align:left; padding:8px">Статус</th>
          <th style="text-align:left; padding:8px">Использовал</th>
          <th style="text-align:left; padding:8px">Создан</th>
          <th style="text-align:left; padding:8px">Кем</th>
          <th style="text-align:left; padding:8px">Истекает</th>
          <th style="text-align:left; padding:8px">Ссылка</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="t in rows" :key="t.id" style="border-bottom:1px solid #eee">
          <td style="padding:8px">{{ t.id }}</td>
          <td style="padding:8px">{{ t.token_type }}</td>
          <td style="padding:8px">{{ t.token_type === 'company' ? t.company_name : `${t.company_label || ('#' + t.company_id)} / ${t.target_email}` }}</td>
          <td style="padding:8px">{{ t.role || '—' }}</td>
          <td style="padding:8px"><span :style="statusStyle(t.status)">{{ statusLabel(t.status) }}</span></td>
          <td style="padding:8px">{{ t.used_by_name ? `${t.used_by_name} (${t.used_by})` : '—' }}</td>
          <td style="padding:8px; white-space:nowrap">{{ fmtDT(t.created_at) }}</td>
          <td style="padding:8px">{{ t.created_by_name || '—' }}</td>
          <td style="padding:8px; white-space:nowrap">{{ fmtDT(t.expires_at) }}</td>
          <td style="padding:8px; white-space:nowrap">
            <button v-if="t.status === 'active'" @click="copyRow(t)" :disabled="copyingId === t.id" style="font-size:12px">{{ copyingId === t.id ? '...' : copiedId === t.id ? 'Скопировано' : 'Копировать' }}</button>
            <span v-else style="color:#999; font-size:12px">—</span>
          </td>
        </tr>
        <tr v-if="!rows.length"><td colspan="10" style="padding:20px; text-align:center; color:#666">Нет токенов</td></tr>
      </tbody>
    </table>
    <div style="font-size:12px; color:#666; margin-top:10px">User-инвайты выпускаются из карточки компании (owner/admin) — здесь они тоже видны. Сырые токены не хранятся: ссылка восстанавливается расшифровкой только для активных токенов.</div>
  </div>
</template>

<script setup lang="ts">
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
