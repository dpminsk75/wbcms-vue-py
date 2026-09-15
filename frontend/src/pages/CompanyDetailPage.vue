<template>
  <div class="container-xxl" style="padding:20px 15px">
    <h2 style="margin-bottom:16px">{{ data?.company?.name || 'Компания' }}</h2>
    <div v-if="error" style="color:#c00">{{ error }}</div>

    <div v-if="data" style="display:flex; flex-direction:column; gap:16px">
      <div style="border:1px solid #ddd; padding:14px; border-radius:8px; max-width:480px">
        <h3 style="margin:0 0 10px">Данные компании</h3>
        <form @submit.prevent="onSaveCompany" style="display:flex; flex-direction:column; gap:8px">
          <label>Название<input v-model="companyForm.name" required style="width:100%" /></label>
          <label>Аббревиатура<input v-model="companyForm.abbreviation" style="width:100%" /></label>
          <label>ИНН<input v-model="companyForm.inn" style="width:100%" /></label>
          <label>WB API-ключ (пусто — не менять)<input v-model="companyForm.api_key" type="password" autocomplete="new-password" style="width:100%" /></label>
          <button type="submit" :disabled="savingCompany" style="background:#4A3A8C; color:#fff; border:none; padding:8px; border-radius:6px">Сохранить</button>
        </form>
        <div v-if="companySaved" style="margin-top:8px; font-size:13px; color:#1E9E7C">Сохранено</div>
      </div>

      <table style="width:100%; border-collapse:collapse">
        <thead>
          <tr style="background:#f4f4f8">
            <th style="text-align:left; padding:8px">ID</th>
            <th style="text-align:left; padding:8px">Пользователь</th>
            <th style="text-align:left; padding:8px">Email</th>
            <th style="text-align:left; padding:8px">Роль</th>
            <th style="text-align:left; padding:8px">Статус</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="m in data.members" :key="m.id" style="border-bottom:1px solid #eee">
            <td style="padding:8px">{{ m.id }}</td>
            <td style="padding:8px">{{ m.username }}</td>
            <td style="padding:8px">{{ m.email || '—' }}</td>
            <td style="padding:8px">
              <select v-model="editRoles[m.id]" @change="onUpdate(m.id)">
                <option value="owner">owner</option>
                <option value="admin">admin</option>
                <option value="member">member</option>
                <option value="viewer">viewer</option>
              </select>
            </td>
            <td style="padding:8px">{{ m.status }}</td>
            <td style="padding:8px"><button @click="onDelete(m.id)" style="color:#c00">Удалить</button></td>
          </tr>
        </tbody>
      </table>

      <div style="border:1px solid #ddd; padding:14px; border-radius:8px; max-width:480px">
        <h3 style="margin:0 0 10px">Пригласить пользователя</h3>
        <form @submit.prevent="onInvite" style="display:flex; flex-direction:column; gap:8px">
          <label>Email<input v-model="invite.email" type="email" required style="width:100%" /></label>
          <label>Роль
            <select v-model="invite.role" style="width:100%">
              <option value="member">member</option>
              <option value="admin">admin</option>
            </select>
          </label>
          <button type="submit" :disabled="inviting" style="background:#4A3A8C; color:#fff; border:none; padding:8px; border-radius:6px">Пригласить</button>
        </form>
        <div v-if="lastInvite" style="margin-top:12px; padding:10px; background:#eef7ee; border-radius:6px; word-break:break-all">
          <div>Токен: <code>{{ lastInvite.invite_token }}</code></div>
          <div style="font-size:12px; color:#555">до {{ fmtDT(lastInvite.expires_at) }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { authApi } from '../api/auth'

const route = useRoute()
const companyId = Number(route.params.id)
const fmtDT = (v: any) => v ? new Date(String(v).replace(' ', 'T')).toLocaleString('ru-RU') : '—'
const data = ref<{ company: any; members: any[] } | null>(null)
const error = ref('')
const editRoles = reactive<Record<number, string>>({})
const invite = reactive({ email: '', role: 'member' as 'admin' | 'member' })
const inviting = ref(false)
const lastInvite = ref<{ invite_token: string; expires_at: string } | null>(null)
const companyForm = reactive({ name: '', abbreviation: '', inn: '', api_key: '' })
const savingCompany = ref(false)
const companySaved = ref(false)

async function load() {
  error.value = ''
  try {
    const r = await authApi.getCompanyMembers(companyId)
    data.value = r
    for (const m of r.members) editRoles[m.id] = m.role
    companyForm.name = r.company?.name || ''
    companyForm.abbreviation = r.company?.abbreviation || ''
    companyForm.inn = (r.company as any)?.inn || ''
    companyForm.api_key = ''
    companySaved.value = false
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  }
}

onMounted(load)
watch(() => route.params.id, load)

async function onUpdate(userId: number) {
  const role = editRoles[userId]
  try {
    await authApi.updateMember(companyId, userId, { role, status: 'active' })
    await load()
  } catch (e: any) { error.value = e?.response?.data?.detail || String(e) }
}

async function onDelete(userId: number) {
  if (!confirm('Удалить из компании?')) return
  try {
    await authApi.deleteMember(companyId, userId)
    await load()
  } catch (e: any) { error.value = e?.response?.data?.detail || String(e) }
}

async function onSaveCompany() {
  savingCompany.value = true
  companySaved.value = false
  try {
    const payload: any = { name: companyForm.name, abbreviation: companyForm.abbreviation || undefined, inn: companyForm.inn || undefined }
    if (companyForm.api_key) payload.api_key = companyForm.api_key
    await authApi.updateCompany(companyId, payload)
    companyForm.api_key = ''
    companySaved.value = true
    await load()
  } catch (e: any) { error.value = e?.response?.data?.detail || String(e) }
  finally { savingCompany.value = false }
}

async function onInvite() {
  inviting.value = true
  lastInvite.value = null
  try {
    const r = await authApi.inviteMember(companyId, { email: invite.email, role: invite.role })
    lastInvite.value = { invite_token: r.invite_token, expires_at: r.expires_at }
    invite.email = ''
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally { inviting.value = false }
}
</script>