import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api, TOKEN_KEY } from '../api/client'
import { authApi, type AuthUser } from '../api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(null)
  const user = ref<AuthUser | null>(null)
  const perms = ref<string[]>([])
  const roles = ref<string[]>([])
  const companies = ref<{ id: number; name: string }[]>([])
  const companyId = ref<number | 'all'>('all')

  try { token.value = localStorage.getItem(TOKEN_KEY) } catch { /* noop */ }
  try {
    const c = localStorage.getItem('wbcms_company')
    if (c === 'all' || c === null) companyId.value = 'all'
    else if (!Number.isNaN(Number(c))) companyId.value = Number(c)
  } catch { /* noop */ }

  const isAuth = computed(() => !!token.value && !!user.value)
  const isAdmin = computed(() => perms.value.includes('admin') || roles.value.includes('admin'))
  const can = (p: string) => isAdmin.value || perms.value.includes(p)

  async function login(username: string, password: string) {
    const d = await authApi.login(username, password)
    token.value = d.token
    user.value = d.user
    perms.value = d.perms || []
    roles.value = d.roles || []
    try { localStorage.setItem(TOKEN_KEY, d.token) } catch { /* noop */ }
    await loadCompanies().catch(() => {})
    return d
  }

  async function loadMe(): Promise<boolean> {
    if (!token.value) return false
    try {
      const d = await authApi.me()
      user.value = d.user
      perms.value = d.perms || []
      roles.value = d.roles || []
      return true
    } catch {
      logout()
      return false
    }
  }

  async function loadCompanies() {
    if (!token.value) return
    try {
      companies.value = await authApi.companies()
    } catch { companies.value = [] }
  }

  function setCompany(v: number | 'all') {
    companyId.value = v
    try { localStorage.setItem('wbcms_company', String(v)) } catch { /* noop */ }
  }

  function logout() {
    token.value = null
    user.value = null
    perms.value = []
    roles.value = []
    try { localStorage.removeItem(TOKEN_KEY) } catch { /* noop */ }
    delete api.defaults.headers.common.Authorization
  }

  return { token, user, perms, roles, companies, companyId, isAuth, isAdmin, can, login, loadMe, loadCompanies, setCompany, logout }
})
