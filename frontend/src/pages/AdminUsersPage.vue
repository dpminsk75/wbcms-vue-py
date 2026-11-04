<template>
  <div class="container-xxl page-admin-users">
    <h1 class="page-title">Пользователи</h1>
    <div v-if="!isGlobal" class="page-admin-users__scope-note">Показаны только пользователи ваших компаний ({{ managedNames }}).</div>
    <div v-if="error" class="wb-error">{{ error }}</div>

    <div class="tbl-card tbl-card--compact">
      <div class="card__hd">
        Пользователи
        <span class="hd-badge">{{ users.length }}</span>
        <span class="spacer"></span>
        <button @click="openCreate = true" class="hd-btn" type="button"><i class="bi bi-plus-lg"></i>Создать пользователя</button>
      </div>
      <div class="tbl-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th>ID</th>
              <th class="t-left">Логин</th>
              <th class="t-left">Email</th>
              <th class="t-center">Статус</th>
              <th class="t-left">Компании</th>
              <th v-if="isGlobal" class="t-left">Роли / пермы</th>
              <th class="num">Регистрация</th>
              <th class="num">Последний вход</th>
              <th><span class="visually-hidden">Действия</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in users" :key="u.id">
              <td>{{ u.id }}</td>
              <td class="t-left fw-semibold">{{ u.username }}</td>
              <td class="t-left">{{ u.email }}</td>
              <td class="t-center"><span class="badge" :class="u.blocked ? 'badge--bad' : 'badge--ok'">{{ u.blocked ? 'Заблокирован' : 'Активен' }}</span></td>
              <td class="t-left">
                <div class="page-admin-users__companies">
                  <span v-for="c in u.companies" :key="c.company_id" class="page-admin-users__company">
                    <span class="page-admin-users__company-name">{{ c.company_name }}</span>
                    <span class="page-admin-users__company-meta">{{ c.role }} / {{ c.status }}</span>
                  </span>
                  <span v-if="!u.companies.length" class="page-admin-users__none">—</span>
                </div>
              </td>
              <td v-if="isGlobal" class="t-left">
                <div class="page-admin-users__perms">
                  <span v-for="it in (u.items || [])" :key="it.name" class="badge badge--neutral page-admin-users__perm" :title="it.type === 1 ? 'роль' : 'перм'">
                    {{ it.name }}<button type="button" class="page-admin-users__perm-drop" :aria-label="'Снять ' + it.name" @click="dropRole(u.id, it.name)">×</button>
                  </span>
                  <select v-model="addSel[u.id]" @change="addRole(u.id)" class="page-admin-users__perm-add" aria-label="Добавить роль или право">
                    <option value="">+ добавить…</option>
                    <option v-for="r in rbacItems" :key="r.name" :value="r.name" :disabled="(u.items || []).some((x: any) => x.name === r.name) || r.name === 'global_admin'">{{ r.name }}</option>
                  </select>
                </div>
              </td>
              <td class="num">{{ fmtDTRu(u.created_at) }}</td>
              <td class="num" :title="u.last_login_ip ? 'IP: ' + u.last_login_ip : undefined">{{ fmtDTRu(u.last_login_at) }}</td>
              <td class="t-center">
                <span class="page-admin-users__menu-wrap">
                  <button @click.stop="toggleMenu(u.id)" class="btn btn--soft btn-sm page-admin-users__menu-btn" title="Действия" :aria-expanded="openMenu === u.id" :aria-label="'Действия для ' + u.username">
                    <i class="bi bi-gear"></i><i class="bi bi-chevron-down page-admin-users__menu-caret" :class="{ 'page-admin-users__menu-caret--open': openMenu === u.id }"></i>
                  </button>
                  <span v-if="openMenu === u.id" class="page-admin-users__menu" role="menu">
                    <button class="page-admin-users__menu-item" role="menuitem" @click="closeMenu(); openPwd(u)">
                      <i class="bi bi-key"></i>Изменить пароль
                    </button>
                    <button v-if="canLink(u)" class="page-admin-users__menu-item" role="menuitem" :disabled="linkBusy === u.id" @click="makeResetLink(u)">
                      <i class="bi bi-link-45deg"></i>{{ linkBusy === u.id ? 'Создаём…' : 'Сгенерировать ссылку' }}
                    </button>
                    <template v-if="isGlobal">
                      <span class="page-admin-users__menu-divider"></span>
                      <button class="page-admin-users__menu-item page-admin-users__menu-item--danger" role="menuitem" :disabled="busy === u.id" @click="closeMenu(); toggle(u)">
                        <i class="bi" :class="u.blocked ? 'bi-unlock' : 'bi-lock'"></i>{{ u.blocked ? 'Разблокировать' : 'Заблокировать' }}
                      </button>
                    </template>
                  </span>
                </span>
              </td>
            </tr>
            <tr v-if="!users.length"><td :colspan="isGlobal ? 9 : 8" class="t-center page-admin-users__empty">Пользователей не найдено</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="pwdTarget" class="wb-modal-backdrop">
      <form @submit.prevent="savePwd" class="wb-modal-box">
        <h3 class="page-admin-users__modal-title">Новый пароль — {{ pwdTarget.username }}</h3>
        <label>Пароль (мин. 8, буквы и цифры)<input v-model="pwd" type="password" required minlength="8" pattern="(?=.*[A-Za-zА-Яа-яЁё])(?=.*\d).{8,}" title="Минимум 8 символов, буквы и цифры" autocomplete="new-password" class="wb-field" /></label>
        <label>Повтор<input v-model="pwd2" type="password" required minlength="8" autocomplete="new-password" class="wb-field" /></label>
        <div v-if="pwdError" class="wb-error">{{ pwdError }}</div>
        <div class="wb-modal-actions">
          <button type="button" @click="pwdTarget = null">Отмена</button>
          <button type="submit" :disabled="pwdBusy" class="wb-btn-brand wb-btn-brand--md">Сохранить</button>
        </div>
      </form>
    </div>

    <div v-if="linkModal" class="wb-modal-backdrop">
      <div class="wb-modal-box" role="dialog" aria-modal="true" aria-label="Ссылка для смены пароля">
        <h3 class="page-admin-users__modal-title">Ссылка для смены пароля</h3>
        <p class="page-admin-users__scope-note">Пользователь <b>{{ linkModal.username }}</b> ({{ linkModal.email }}) откроет ссылку и задаст новый пароль сам — вы его не узнаете.</p>
        <div class="page-admin-users__link-row">
          <input :value="linkModal.url" readonly class="wb-input" aria-label="Ссылка для смены пароля" @click="($event.target as HTMLInputElement).select()" />
          <button type="button" class="btn btn--soft" @click="copyLink" :title="linkCopied ? 'Скопировано' : 'Копировать в буфер'">
            <i class="bi" :class="linkCopied ? 'bi-check2' : 'bi-clipboard'"></i>
          </button>
        </div>
        <p class="page-admin-users__scope-note page-admin-users__muted">Одноразовая, действует до {{ fmtDTRu(linkModal.expires_at) }}. Показывается один раз — передайте сразу. Потеряли — выпустите новую.</p>
        <div class="wb-modal-actions">
          <button type="button" @click="linkModal = null">Закрыть</button>
        </div>
      </div>
    </div>

    <div v-if="openCreate" class="wb-modal-backdrop">
      <form @submit.prevent="createUser" class="wb-modal-box wb-modal-box--wide">
        <h3 class="page-admin-users__modal-title">Новый пользователь{{ isGlobal ? '' : ' в мою компанию' }}</h3>
        <label>Логин<input v-model="createForm.username" required minlength="3" class="wb-field" /></label>
        <label>Email<input v-model="createForm.email" type="email" required class="wb-field" /></label>
        <label>Пароль (мин. 8, буквы и цифры)<input v-model="createForm.password" type="password" required minlength="8" pattern="(?=.*[A-Za-zА-Яа-яЁё])(?=.*\d).{8,}" title="Минимум 8 символов, буквы и цифры" autocomplete="new-password" class="wb-field" /></label>
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
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { authApi } from '../api/auth'
import { useAuthStore } from '../stores/auth'
import { useDateFmt } from '../composables/useDateFmt'
import { copyText } from '../composables/useCopyText'

const { fmtDTRu } = useDateFmt()
const PWD_OK = /^(?=.*[A-Za-zА-Яа-яЁё])(?=.*\d).{8,}$/

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

// ⋮-меню строки: открытие по клику, закрытие по клику вне и по Esc
const openMenu = ref<number | null>(null)
const linkBusy = ref<number | null>(null)
const linkCopied = ref(false)
const linkModal = ref<null | { username: string; email: string; url: string; expires_at: string }>(null)
const toggleMenu = (id: number) => { openMenu.value = openMenu.value === id ? null : id }
const closeMenu = () => { openMenu.value = null }
const onDocClick = () => closeMenu()
const onKeydown = (e: KeyboardEvent) => { if (e.key === 'Escape') closeMenu() }
const canLink = (u: any) => isGlobal.value ||
  (u.companies || []).some((c: any) => managedIds.value.has(c.company_id))

async function makeResetLink(u: any) {
  closeMenu()
  linkBusy.value = u.id
  try {
    let r: { invite_token: string; expires_at: string; reset_path: string }
    if (isGlobal.value) {
      r = await authApi.adminResetLink(u.id)
    } else {
      const cid = (u.companies || []).map((c: any) => c.company_id).find((id: number) => managedIds.value.has(id))
      if (!cid) throw new Error('Нет прав на пользователей этой строки')
      r = await authApi.memberResetLink(cid, u.id)
    }
    linkCopied.value = false
    linkModal.value = { username: u.username, email: u.email, url: `${location.origin}${r.reset_path}`, expires_at: r.expires_at }
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    linkBusy.value = null
  }
}

async function copyLink() {
  if (!linkModal.value) return
  linkCopied.value = await copyText(linkModal.value.url)
}

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
onMounted(() => {
  document.addEventListener('click', onDocClick)
  document.addEventListener('keydown', onKeydown)
})
onUnmounted(() => {
  document.removeEventListener('click', onDocClick)
  document.removeEventListener('keydown', onKeydown)
})

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
  if (!PWD_OK.test(createForm.password)) {
    createError.value = 'Минимум 8 символов, нужны буквы и цифры'
    creating.value = false
    return
  }
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
  if (!PWD_OK.test(pwd.value)) { pwdError.value = 'Минимум 8 символов, нужны буквы и цифры'; return }
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
