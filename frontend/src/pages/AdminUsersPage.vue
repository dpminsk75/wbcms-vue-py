<template>
  <div class="container-xxl page-admin-users">
    <div class="page-admin-users__head">
      <h2 class="page-admin-users__title">Пользователи{{ isGlobal ? ' (админ)' : '' }}</h2>
      <button @click="openCreate = true" class="wb-btn-brand wb-btn-brand--lg">Создать пользователя</button>
    </div>
    <div v-if="!isGlobal" class="page-admin-users__scope-note">Показаны только пользователи ваших компаний ({{ managedNames }}).</div>
    <div v-if="error" class="wb-error">{{ error }}</div>
    <table class="wb-admin-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Логин</th>
          <th>Email</th>
          <th>Статус</th>
          <th>Компании</th>
          <th v-if="isGlobal">Роли/пермы</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="u in users" :key="u.id">
          <td>{{ u.id }}</td>
          <td>{{ u.username }}</td>
          <td>{{ u.email }}</td>
          <td>{{ u.blocked ? 'Заблокирован' : 'Активен' }}</td>
          <td>
            <span v-for="c in u.companies" :key="c.company_id" class="page-admin-users__company">
              {{ c.company_name }} <small>({{ c.role }}/{{ c.status }})</small>
            </span>
            <span v-if="!u.companies.length" class="page-admin-users__none">—</span>
          </td>
          <td v-if="isGlobal">
            <span v-for="it in (u.items || [])" :key="it.name" class="page-admin-users__rbac" :title="it.type === 1 ? 'роль' : 'перм'">
              {{ it.name }}<a href="#" @click.prevent="dropRole(u.id, it.name)" class="page-admin-users__rbac-drop" title="Снять">×</a>
            </span>
            <select v-model="addSel[u.id]" @change="addRole(u.id)" class="page-admin-users__rbac-select">
              <option value="">+ дать...</option>
              <option v-for="r in rbacItems" :key="r.name" :value="r.name" :disabled="(u.items || []).some((x: any) => x.name === r.name) || r.name === 'global_admin'">{{ r.name }}</option>
            </select>
          </td>
          <td class="page-admin-users__row-actions">
            <button @click="openPwd(u)" class="wb-btn-brand wb-btn-brand--sm page-admin-users__pwd-btn">Изменить пароль</button>
            <button v-if="isGlobal" @click="toggle(u)" :disabled="busy === u.id" :style="{background: u.blocked ? '#0a0' : '#c00', color:'#fff', border:'none', padding:'4px 10px', borderRadius:'6px'}">
              {{ u.blocked ? 'Разблокировать' : 'Заблокировать' }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>

    <div v-if="pwdTarget" class="wb-modal-backdrop">
      <form @submit.prevent="savePwd" class="wb-modal-box">
        <h3 class="page-admin-users__modal-title">Новый пароль — {{ pwdTarget.username }}</h3>
        <label>Пароль (мин. 6)<input v-model="pwd" type="password" required minlength="6" autocomplete="new-password" class="wb-field" /></label>
        <label>Повтор<input v-model="pwd2" type="password" required minlength="6" autocomplete="new-password" class="wb-field" /></label>
        <div v-if="pwdError" class="wb-error">{{ pwdError }}</div>
        <div class="wb-modal-actions">
          <button type="button" @click="pwdTarget = null">Отмена</button>
          <button type="submit" :disabled="pwdBusy" class="wb-btn-brand wb-btn-brand--md">Сохранить</button>
        </div>
      </form>
    </div>

    <div v-if="openCreate" class="wb-modal-backdrop">
      <form @submit.prevent="createUser" class="wb-modal-box wb-modal-box--wide">
        <h3 class="page-admin-users__modal-title">Новый пользователь{{ isGlobal ? '' : ' в мою компанию' }}</h3>
        <label>Логин<input v-model="createForm.username" required minlength="3" class="wb-field" /></label>
        <label>Email<input v-model="createForm.email" type="email" required class="wb-field" /></label>
        <label>Пароль (мин. 6)<input v-model="createForm.password" type="password" required minlength="6" autocomplete="new-password" class="wb-field" /></label>
        <label>Компания
          <select v-model="createForm.company_id" :required="!isGlobal" class="wb-field">
            <option v-if="isGlobal" :value="null">— без компании —</option>
            <option v-for="c in companyOptions" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
        </label>
        <label v-if="createForm.company_id">Роль в компании
          <select v-model="createForm.role" class="wb-field">
            <option value="member">member</option>
            <option value="viewer">viewer</option>
            <option value="admin">admin</option>
          </select>
        </label>
        <div v-if="createError" class="wb-error">{{ createError }}</div>
        <div class="wb-modal-actions">
          <button type="button" @click="openCreate = false">Отмена</button>
          <button type="submit" :disabled="creating" class="wb-btn-brand wb-btn-brand--md">Создать</button>
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
