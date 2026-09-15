<template>
  <div class="container-xxl" style="padding:20px 15px">
    <h2 style="margin-bottom:4px">Пользователи{{ isGlobal ? ' (админ)' : '' }}</h2>
    <div v-if="!isGlobal" style="font-size:13px; color:#666; margin-bottom:12px">Показаны только пользователи ваших компаний ({{ managedNames }}).</div>
    <div v-if="error" style="color:#c00">{{ error }}</div>
    <table style="width:100%; border-collapse:collapse">
      <thead>
        <tr style="background:#f4f4f8">
          <th style="text-align:left; padding:8px">ID</th>
          <th style="text-align:left; padding:8px">Логин</th>
          <th style="text-align:left; padding:8px">Email</th>
          <th style="text-align:left; padding:8px">Статус</th>
          <th style="text-align:left; padding:8px">Компании</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="u in users" :key="u.id" style="border-bottom:1px solid #eee">
          <td style="padding:8px">{{ u.id }}</td>
          <td style="padding:8px">{{ u.username }}</td>
          <td style="padding:8px">{{ u.email }}</td>
          <td style="padding:8px">{{ u.blocked ? 'Заблокирован' : 'Активен' }}</td>
          <td style="padding:8px">
            <span v-for="c in u.companies" :key="c.company_id" style="margin-right:8px">
              {{ c.company_name }} <small>({{ c.role }}/{{ c.status }})</small>
            </span>
            <span v-if="!u.companies.length" style="color:#999">—</span>
          </td>
          <td style="padding:8px; white-space:nowrap">
            <button @click="openPwd(u)" style="background:#4A3A8C; color:#fff; border:none; padding:4px 10px; border-radius:6px; margin-right:6px">Изменить пароль</button>
            <button v-if="isGlobal" @click="toggle(u)" :disabled="busy === u.id" :style="{background: u.blocked ? '#0a0' : '#c00', color:'#fff', border:'none', padding:'4px 10px', borderRadius:'6px'}">
              {{ u.blocked ? 'Разблокировать' : 'Заблокировать' }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>

    <div v-if="pwdTarget" style="position:fixed; inset:0; background:rgba(0,0,0,.4); display:flex; align-items:center; justify-content:center">
      <form @submit.prevent="savePwd" style="background:#fff; padding:20px; border-radius:8px; min-width:340px; display:flex; flex-direction:column; gap:10px">
        <h3 style="margin:0">Новый пароль — {{ pwdTarget.username }}</h3>
        <label>Пароль (мин. 6)<input v-model="pwd" type="password" required minlength="6" autocomplete="new-password" style="width:100%" /></label>
        <label>Повтор<input v-model="pwd2" type="password" required minlength="6" autocomplete="new-password" style="width:100%" /></label>
        <div v-if="pwdError" style="color:#c00">{{ pwdError }}</div>
        <div style="display:flex; gap:8px; justify-content:flex-end">
          <button type="button" @click="pwdTarget = null">Отмена</button>
          <button type="submit" :disabled="pwdBusy" style="background:#4A3A8C; color:#fff; border:none; padding:6px 12px; border-radius:6px">Сохранить</button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { authApi } from '../api/auth'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const users = ref<Array<any>>([])
const error = ref('')
const busy = ref<number | null>(null)

const isGlobal = computed(() => auth.isAdmin)
const managedIds = computed(() => new Set(
  auth.memberships.filter((m) => m.status === 'active' && (m.role === 'owner' || m.role === 'admin')).map((m) => m.company_id)
))
const managedNames = computed(() => auth.memberships
  .filter((m) => m.status === 'active' && (m.role === 'owner' || m.role === 'admin'))
  .map((m) => m.company_name).join(', '))

const pwdTarget = ref<any>(null)
const pwd = ref('')
const pwd2 = ref('')
const pwdError = ref('')
const pwdBusy = ref(false)

async function load() {
  try {
    await auth.loadMemberships().catch(() => {})
    users.value = await authApi.adminUsers()
  } catch (e: any) { error.value = e?.response?.data?.detail || String(e) }
}
onMounted(load)

async function toggle(u: any) {
  busy.value = u.id
  try {
    await authApi.setUserBlocked(u.id, !u.blocked)
    await load()
  } catch (e: any) { error.value = e?.response?.data?.detail || String(e) }
  finally { busy.value = null }
}

function openPwd(u: any) {
  pwdTarget.value = u
  pwd.value = ''
  pwd2.value = ''
  pwdError.value = ''
}

async function savePwd() {
  pwdError.value = ''
  if (pwd.value !== pwd2.value) { pwdError.value = 'Пароли не совпадают'; return }
  if (pwd.value.length < 6) { pwdError.value = 'Минимум 6 символов'; return }
  pwdBusy.value = true
  try {
    if (isGlobal.value) {
      await authApi.setUserPasswordAdmin(pwdTarget.value.id, pwd.value)
    } else {
      // компания из строки, которой управляем (бэк перепроверит членство и права)
      const cid = (pwdTarget.value.companies || [])
        .map((c: any) => c.company_id)
        .find((id: number) => managedIds.value.has(id))
      if (!cid) throw new Error('Нет прав на пользователей этой строки')
      await authApi.setMemberPassword(cid, pwdTarget.value.id, pwd.value)
    }
    pwdTarget.value = null
  } catch (e: any) { pwdError.value = e?.response?.data?.detail || String(e) }
  finally { pwdBusy.value = false }
}
</script>
