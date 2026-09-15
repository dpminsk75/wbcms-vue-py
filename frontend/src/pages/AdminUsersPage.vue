<template>
  <div class="container-xxl page-admin-users">
    <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:4px">
      <h2 style="margin:0">Пользователи{{ isGlobal ? ' (админ)' : '' }}</h2>
      <button @click="openCreate = true" style="padding:8px 14px; background:#4A3A8C; color:#fff; border:none; border-radius:6px">Создать пользователя</button>
    </div>
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
          <th v-if="isGlobal" style="text-align:left; padding:8px">Роли/пермы</th>
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
          <td v-if="isGlobal" style="padding:8px">
            <span v-for="it in (u.items || [])" :key="it.name" style="display:inline-block; background:#f1f1f4; border-radius:8px; padding:1px 6px; margin:0 4px 2px 0; font-size:12px" :title="it.type === 1 ? 'роль' : 'перм'">
              {{ it.name }}<a href="#" @click.prevent="dropRole(u.id, it.name)" style="margin-left:4px; color:#c00; text-decoration:none" title="Снять">×</a>
            </span>
            <select v-model="addSel[u.id]" @change="addRole(u.id)" style="font-size:12px; max-width:150px">
              <option value="">+ дать...</option>
              <option v-for="r in rbacItems" :key="r.name" :value="r.name" :disabled="(u.items || []).some((x: any) => x.name === r.name) || r.name === 'global_admin'">{{ r.name }}</option>
            </select>
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

    <div v-if="openCreate" style="position:fixed; inset:0; background:rgba(0,0,0,.4); display:flex; align-items:center; justify-content:center">
      <form @submit.prevent="createUser" style="background:#fff; padding:20px; border-radius:8px; min-width:360px; display:flex; flex-direction:column; gap:10px">
        <h3 style="margin:0">Новый пользователь{{ isGlobal ? '' : ' в мою компанию' }}</h3>
        <label>Логин<input v-model="createForm.username" required minlength="3" style="width:100%" /></label>
        <label>Email<input v-model="createForm.email" type="email" required style="width:100%" /></label>
        <label>Пароль (мин. 6)<input v-model="createForm.password" type="password" required minlength="6" autocomplete="new-password" style="width:100%" /></label>
        <label>Компания
          <select v-model="createForm.company_id" :required="!isGlobal" style="width:100%">
            <option v-if="isGlobal" :value="null">— без компании —</option>
            <option v-for="c in companyOptions" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
        </label>
        <label v-if="createForm.company_id">Роль в компании
          <select v-model="createForm.role" style="width:100%">
            <option value="member">member</option>
            <option value="viewer">viewer</option>
            <option value="admin">admin</option>
          </select>
        </label>
        <div v-if="createError" style="color:#c00">{{ createError }}</div>
        <div style="display:flex; gap:8px; justify-content:flex-end">
          <button type="button" @click="openCreate = false">Отмена</button>
          <button type="submit" :disabled="creating" style="background:#4A3A8C; color:#fff; border:none; padding:6px 12px; border-radius:6px">Создать</button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-admin-users.css'
import { ref, reactive, computed, onMounted } from 'vue'
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

// Создание пользователя: global — куда угодно (или без компании), мелкий админ — только в свои
const openCreate = ref(false)
const creating = ref(false)
const createError = ref('')
const createForm = reactive({ username: '', email: '', password: '', company_id: null as number | null, role: 'member' as 'member' | 'viewer' | 'admin' })
const allCompanies = ref<Array<{ id: number; name: string }>>([])
const companyOptions = computed(() => isGlobal.value
  ? allCompanies.value
  : auth.memberships
    .filter((m) => m.status === 'active' && (m.role === 'owner' || m.role === 'admin'))
    .map((m) => ({ id: m.company_id, name: m.company_name }))
)

// Ручное управление ролями/пермами (только global — замена yii2 /admin/assignment)
const rbacItems = ref<Array<{ name: string; type: number | null; description: string | null }>>([])
const addSel = ref<Record<number, string>>({})

async function load() {
  try {
    await auth.loadMemberships().catch(() => {})
    users.value = await authApi.adminUsers()
    if (isGlobal.value) {
      try { rbacItems.value = await authApi.rbacItems() } catch { rbacItems.value = [] }
      try {
        const cs = await authApi.adminCompanies()
        allCompanies.value = cs.map((c: any) => ({ id: c.id, name: c.name }))
      } catch { allCompanies.value = [] }
    }
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

async function addRole(userId: number) {
  const name = addSel.value[userId]
  if (!name) return
  try {
    await authApi.setUserRoles(userId, { add: [name] })
    addSel.value[userId] = ''
    await load()
  } catch (e: any) { error.value = e?.response?.data?.detail || String(e) }
}

async function dropRole(userId: number, name: string) {
  if (!confirm(`Снять ${name}?`)) return
  try {
    await authApi.setUserRoles(userId, { remove: [name] })
    await load()
  } catch (e: any) { error.value = e?.response?.data?.detail || String(e) }
}

async function createUser() {
  creating.value = true
  createError.value = ''
  try {
    const payload: any = { username: createForm.username, email: createForm.email, password: createForm.password }
    if (createForm.company_id) {
      payload.company_id = createForm.company_id
      payload.role = createForm.role
    } else if (!isGlobal.value) {
      throw new Error('Выберите компанию')
    }
    await authApi.adminCreateUser(payload)
    openCreate.value = false
    createForm.username = ''
    createForm.email = ''
    createForm.password = ''
    createForm.role = 'member'
    await load()
  } catch (e: any) { createError.value = e?.response?.data?.detail || String(e) }
  finally { creating.value = false }
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
