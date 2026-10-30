<template>
  <div class="container-xxl page-admin-roles">
    <div class="page-admin-roles__head">
      <h2 class="page-admin-roles__title">Роли и права</h2>
      <button class="wb-btn-brand wb-btn-brand--lg" @click="openCreate">Создать роль</button>
    </div>
    <div class="page-admin-roles__note">
      Роль — набор прав. Пользователю выдаются роли; часть прав можно выдать напрямую (в карточке пользователя).
      Право из серого списка выдаётся только глобальным администратором.
    </div>
    <div v-if="!auth.authV3" class="page-admin-roles__note page-admin-roles__note--staging">
      Режим AUTH_V3=0: роли сохраняются, но на доступ разделов пока не влияют —
      заработают после включения AUTH_V3=1 (пока действует старая модель auth_*).
    </div>
    <div v-if="error" class="wb-error">{{ error }}</div>

    <table class="wb-admin-table">
      <thead>
        <tr>
          <th>Роль</th>
          <th>Описание</th>
          <th>Права</th>
          <th>Пользователи</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in roles" :key="r.id">
          <td>
            {{ r.name }}
            <span v-if="r.is_system" class="page-admin-roles__perm">системная</span>
          </td>
          <td>{{ r.description || '—' }}</td>
          <td>
            <span
              v-for="p in r.perms"
              :key="p"
              class="page-admin-roles__perm"
              :class="permKind(p) === 'manage' ? 'page-admin-roles__perm--manage' : 'page-admin-roles__perm--view'"
            >{{ permLabel(p) }}</span>
            <span v-if="!r.perms.length" class="text-muted">—</span>
          </td>
          <td>
            <span v-for="u in (r.users || [])" :key="u.id" class="page-admin-roles__user">
              {{ u.username }}<a v-if="r.name !== 'global_admin'" href="#" class="page-admin-roles__user-drop" title="Снять роль" @click.prevent="dropUser(r, u)">×</a>
            </span>
            <span v-if="!(r.users || []).length" class="text-muted">—</span>
          </td>
          <td class="page-admin-roles__row-actions">
            <button class="btn btn-sm btn-outline-secondary me-1" @click="openEdit(r)">Права</button>
            <button v-if="r.name !== 'global_admin'" class="btn btn-sm btn-outline-secondary me-1" @click="openUsers(r)">Пользователи</button>
            <button v-if="!r.is_system" class="btn btn-sm btn-outline-danger" @click="removeRole(r)">Удалить</button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Создание/правка роли -->
    <div v-if="editor" class="wb-modal-backdrop">
      <form class="wb-modal-box wb-modal-box--wide" @submit.prevent="saveRole">
        <h3 class="page-admin-roles__modal-title">{{ editor.id ? 'Роль: ' + editor.name : 'Новая роль' }}</h3>
        <label>Название<input v-model="editor.name" required maxlength="64" class="wb-field" /></label>
        <label>Описание<input v-model="editor.description" class="wb-field" /></label>
        <div class="page-admin-roles__perm-group">
          <div class="page-admin-roles__perm-group-title">Права</div>
          <div class="page-admin-roles__perm-list">
            <label v-for="p in perms" :key="p.name" class="page-admin-roles__perm-item" :title="permHint(p)">
              <input type="checkbox" :value="p.name" v-model="editor.perms" />
              <span>{{ p.label || p.name }}<small class="page-admin-roles__perm-hint"> ({{ p.name }})</small></span>
            </label>
          </div>
        </div>
        <div v-if="editorError" class="wb-error">{{ editorError }}</div>
        <div class="wb-modal-actions">
          <button type="button" @click="editor = null">Отмена</button>
          <button type="submit" :disabled="saving" class="wb-btn-brand wb-btn-brand--md">Сохранить</button>
        </div>
      </form>
    </div>

    <!-- Назначение пользователей -->
    <div v-if="usersModal" class="wb-modal-backdrop">
      <div class="wb-modal-box wb-modal-box--wide">
        <h3 class="page-admin-roles__modal-title">Пользователи роли: {{ usersModal.name }}</h3>
        <template v-if="usersModal.name !== 'global_admin'">
          <div class="mb-2">
            <span
              v-for="u in (usersModal.users || [])"
              :key="u.id"
              class="page-admin-roles__user"
            >
              {{ u.username }}
              <a href="#" class="page-admin-roles__user-drop" title="Снять роль" @click.prevent="dropUser(usersModal, u)">×</a>
            </span>
            <span v-if="!(usersModal.users || []).length" class="text-muted">—</span>
          </div>
          <div class="d-flex gap-2 align-items-center">
            <select v-model="pickUserId" class="form-select form-select-sm w-auto">
              <option value="">Добавить пользователя…</option>
              <option v-for="u in freeUsers" :key="u.id" :value="u.id">{{ u.username }}</option>
            </select>
            <button type="button" class="btn btn-sm btn-outline-primary" :disabled="!pickUserId" @click="addUser">Назначить</button>
          </div>
        </template>
        <div v-else class="text-muted">
          Роль global_admin управляется только через БД (seed).
        </div>
        <div v-if="usersError" class="wb-error mt-2">{{ usersError }}</div>
        <div class="wb-modal-actions">
          <button type="button" @click="usersModal = null">Закрыть</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-admin-roles.css'
import { computed, onMounted, ref } from 'vue'
import { adminRolesApi, type PermMeta, type Role } from '../api/adminRoles'
import { authApi } from '../api/auth'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()

const perms = ref<PermMeta[]>([])
const roles = ref<Role[]>([])
const users = ref<Array<{ id: number; username: string }>>([])
const error = ref('')

const editor = ref<null | { id: number | null; name: string; description: string; perms: string[] }>(null)
const editorError = ref('')
const saving = ref(false)

const usersModal = ref<null | Role>(null)
const usersError = ref('')
const pickUserId = ref<string>('')

function permLabel(name: string) {
  const m = perms.value.find((p) => p.name === name)
  return m?.label || name
}
function permKind(name: string) {
  return perms.value.find((p) => p.name === name)?.kind || 'view'
}
function permHint(p: PermMeta) {
  const parts: string[] = []
  if (p.protected) parts.push('только глобальный администратор')
  if (p.derivedOnly) parts.push('выдаётся по роли в компании')
  if (p.requires) parts.push(`нужно также ${p.requires}`)
  return parts.length ? parts.join('; ') : p.name
}

async function load() {
  try {
    const [p, r, u] = await Promise.all([
      adminRolesApi.perms(),
      adminRolesApi.list(),
      authApi.adminUsers().catch(() => []),
    ])
    perms.value = p
    roles.value = r
    users.value = u.map((x: any) => ({ id: x.id, username: x.username }))
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  }
}
onMounted(load)

function openCreate() {
  editorError.value = ''
  editor.value = { id: null, name: '', description: '', perms: [] }
}

function openEdit(r: Role) {
  editorError.value = ''
  editor.value = { id: r.id, name: r.name, description: r.description || '', perms: [...(r.perms || [])] }
}

async function saveRole() {
  if (!editor.value) return
  saving.value = true
  editorError.value = ''
  try {
    if (editor.value.id) {
      await adminRolesApi.update(editor.value.id, {
        name: editor.value.name,
        description: editor.value.description,
      })
      await adminRolesApi.setPerms(editor.value.id, editor.value.perms)
    } else {
      await adminRolesApi.create({
        name: editor.value.name,
        description: editor.value.description,
        perms: editor.value.perms,
      })
    }
    editor.value = null
    await load()
  } catch (e: any) {
    editorError.value = e?.response?.data?.detail || String(e)
  } finally {
    saving.value = false
  }
}

async function removeRole(r: Role) {
  if (!confirm(`Удалить роль «${r.name}»?`)) return
  try {
    await adminRolesApi.remove(r.id)
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  }
}

const freeUsers = computed(() => {
  const inRole = new Set((usersModal.value?.users || []).map((u) => u.id))
  return users.value.filter((u) => !inRole.has(u.id))
})

function openUsers(r: Role) {
  usersError.value = ''
  pickUserId.value = ''
  usersModal.value = r
}

async function addUser() {
  if (!usersModal.value || !pickUserId.value) return
  try {
    await adminRolesApi.setUserRoles(Number(pickUserId.value), { add: [usersModal.value.name] })
    pickUserId.value = ''
    await load()
    if (usersModal.value) {
      const fresh = roles.value.find((r) => r.id === usersModal.value?.id)
      if (fresh) usersModal.value = fresh
    }
  } catch (e: any) {
    usersError.value = e?.response?.data?.detail || String(e)
  }
}

async function dropUser(r: Role, u: { id: number; username: string }) {
  if (!confirm(`Снять роль «${r.name}» с ${u.username}?`)) return
  try {
    await adminRolesApi.setUserRoles(u.id, { remove: [r.name] })
    await load()
    if (usersModal.value) {
      const fresh = roles.value.find((x) => x.id === usersModal.value?.id)
      if (fresh) usersModal.value = fresh
    }
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  }
}
</script>
