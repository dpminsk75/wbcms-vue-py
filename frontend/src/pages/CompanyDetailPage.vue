<template>
  <div class="container-xxl page-company-detail">
    <h2 class="page-company-detail__title">{{ data?.company?.name || 'Компания' }}</h2>
    <div v-if="error" class="wb-error">{{ error }}</div>

    <div v-if="data" class="page-company-detail__stack">
      <form @submit.prevent="onSaveCompany">
        <div class="row">
          <div class="col-md-6">
            <div class="card h-100 page-company-detail__card-main">
              <div class="card-header bg-light fw-semibold">Основное</div>
              <div class="card-body">
                <div class="mb-2">
                  <label class="form-label mb-1">Название</label>
                  <input v-model="companyForm.name" required maxlength="255" class="form-control form-control-sm" />
                </div>
                <div class="row g-2 mb-2">
                  <div class="col-6">
                    <label class="form-label mb-1">Аббревиатура</label>
                    <input v-model="companyForm.abbreviation" maxlength="50" placeholder="Для гридов" class="form-control form-control-sm" />
                  </div>
                  <div class="col-6">
                    <label class="form-label mb-1">ИНН</label>
                    <input v-model="companyForm.inn" maxlength="12" placeholder="10/12 цифр" class="form-control form-control-sm" />
                  </div>
                </div>
                <div class="mb-2">
                  <label class="form-label mb-1">API ключ WB
                    <span v-if="hasApiKey" class="badge wb-key-badge">задан</span>
                    <span v-else class="badge bg-light text-muted border">не задан</span>
                  </label>
                  <div class="input-group input-group-sm">
                    <input v-model="companyForm.api_key" :type="showApi ? 'text' : 'password'" autocomplete="new-password" placeholder="JWT WB" class="form-control" />
                    <button type="button" @click="toggleApi" class="btn btn-outline-secondary" title="Показать/скрыть">👁</button>
                  </div>
                </div>
                <hr class="my-2" />
                <div class="form-check mb-1">
                  <input type="checkbox" v-model="companyForm.is_active" class="form-check-input" id="cf-active" />
                  <label class="form-check-label text-danger" for="cf-active">Активна <small class="text-muted">(снятие скроет компанию из списков!)</small></label>
                </div>
                <template v-if="auth.can('manageFbsStocks')">
                  <div class="form-check">
                    <input type="checkbox" v-model="companyForm.fbs_deduct_enabled" class="form-check-input" id="cf-fbs" />
                    <label class="form-check-label" for="cf-fbs">Списание FBS</label>
                  </div>
                  <div class="form-check">
                    <input type="checkbox" v-model="companyForm.fbs_deduct_test" class="form-check-input" id="cf-fbst" />
                    <label class="form-check-label" for="cf-fbst">Тестовый режим FBS <small class="text-muted">(сухое списание в лог)</small></label>
                  </div>
                </template>
              </div>
            </div>
          </div>
          <div v-if="auth.can('viewSeo')" class="col-md-6">
            <div class="card h-100 page-company-detail__card-seo">
              <div class="card-header page-company-detail__seo-head">SEO <small class="page-company-detail__seo-note">пусто = из params.php</small></div>
              <div class="card-body">
                <div class="mb-2">
                  <label class="form-label mb-1">OpenRouter API key
                    <span v-if="hasSeoKey" class="badge wb-key-badge">задан</span>
                    <span v-else class="badge bg-light text-muted border">из params</span>
                  </label>
                  <div class="input-group input-group-sm">
                    <input v-model="companyForm.seo_openrouter_key" :type="showSeo ? 'text' : 'password'" autocomplete="off" placeholder="sk-or-..." class="form-control" />
                    <button type="button" @click="toggleSeo" class="btn btn-outline-secondary" title="Показать/скрыть">👁</button>
                  </div>
                </div>
                <div class="row g-2 mb-2">
                  <div class="col-6">
                    <label class="form-label mb-1">Referer</label>
                    <input v-model="companyForm.seo_openrouter_referer" placeholder="https://wbcms.local" class="form-control form-control-sm" />
                  </div>
                  <div class="col-6">
                    <label class="form-label mb-1">Title</label>
                    <input v-model="companyForm.seo_openrouter_title" placeholder="wbcms SEO" class="form-control form-control-sm" />
                  </div>
                </div>
                <div class="mb-2">
                  <label class="form-label mb-1">SEO модель</label>
                  <input v-model="companyForm.seo_model" placeholder="openrouter/free" class="form-control form-control-sm" />
                  <div class="form-text">Команда: php yii seo/models — список :free</div>
                </div>
                <div class="row g-2 mb-2">
                  <div class="col-6">
                    <label class="form-label mb-1">Модель сводки</label>
                    <input v-model="companyForm.seo_summary_model" class="form-control form-control-sm" />
                  </div>
                  <div class="col-6">
                    <label class="form-label mb-1">max_tokens</label>
                    <input v-model="companyForm.seo_summary_max_tokens" type="number" placeholder="4000" class="form-control form-control-sm" />
                  </div>
                </div>
                <div class="row g-2 mb-2">
                  <div class="col-4">
                    <label class="form-label mb-1">Лимит/день</label>
                    <input v-model="companyForm.seo_daily_limit" type="number" placeholder="20" class="form-control form-control-sm" />
                  </div>
                  <div class="col-4">
                    <label class="form-label mb-1">Опис. мин</label>
                    <input v-model="companyForm.seo_desc_min" type="number" placeholder="2000" class="form-control form-control-sm" />
                  </div>
                  <div class="col-4">
                    <label class="form-label mb-1">Опис. макс</label>
                    <input v-model="companyForm.seo_desc_max" type="number" placeholder="5000" class="form-control form-control-sm" />
                  </div>
                </div>
                <div class="mb-2">
                  <label class="form-label mb-1">Анти-спам дней</label>
                  <input v-model="companyForm.seo_anti_spam_days" type="number" placeholder="14" class="form-control form-control-sm" />
                </div>
                <div class="mb-2">
                  <label class="form-label mb-1">SEO промпт <small class="text-muted">({DESC_MIN}/{DESC_MAX} подставятся)</small></label>
                  <textarea v-model="companyForm.seo_prompt" rows="3" placeholder="Пусто = стандартный" class="form-control form-control-sm"></textarea>
                </div>
                <div class="mb-2">
                  <label class="form-label mb-1">Промпт конкурента</label>
                  <textarea v-model="companyForm.seo_competitor_prompt" rows="3" placeholder="Пусто = стандартный" class="form-control form-control-sm"></textarea>
                </div>
                <div class="mb-1">
                  <label class="form-label mb-1">Промпт сводки</label>
                  <textarea v-model="companyForm.seo_summary_prompt" rows="3" placeholder="Пусто = стандартный" class="form-control form-control-sm"></textarea>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="page-company-detail__save-row">
          <button type="submit" :disabled="savingCompany" class="wb-btn-brand wb-btn-brand--xl">Сохранить компанию</button>
          <span v-if="companySaved" class="page-company-detail__saved">Сохранено</span>
        </div>
      </form>

      <table class="wb-admin-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Пользователь</th>
            <th>Email</th>
            <th>Роль</th>
            <th>Статус</th>
            <th>Пермы</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="m in data.members" :key="m.id">
            <td>{{ m.id }}</td>
            <td>{{ m.username }}</td>
            <td>{{ m.email || '—' }}</td>
            <td>
              <select v-model="editRoles[m.id]" @change="onUpdate(m.id)">
                <option value="owner">owner</option>
                <option value="admin">admin</option>
                <option value="member">member</option>
                <option value="viewer">viewer</option>
              </select>
            </td>
            <td>{{ m.status }}</td>
            <td>
              <span v-for="p in (m.perms || [])" :key="p" class="page-company-detail__perm">
                {{ p }}<a href="#" @click.prevent="removePerm(m.id, p)" class="page-company-detail__perm-drop" title="Снять">×</a>
              </span>
              <select v-model="addSel[m.id]" @change="addPerm(m.id)" class="page-company-detail__perm-select">
                <option value="">+ перм...</option>
                <option v-for="g in grantable" :key="g.name" :value="g.name" :disabled="(m.perms || []).includes(g.name)">{{ g.name }}</option>
              </select>
            </td>
            <td><button @click="onDelete(m.id)" class="page-company-detail__delete">Удалить</button></td>
          </tr>
        </tbody>
      </table>

      <div class="page-company-detail__invite-box">
        <h3 class="page-company-detail__invite-title">Пригласить пользователя</h3>
        <form @submit.prevent="onInvite" class="page-company-detail__invite-form">
          <label>Email<input v-model="invite.email" type="email" required class="wb-field" /></label>
          <label>Роль
            <select v-model="invite.role" class="wb-field">
              <option value="member">member</option>
              <option value="admin">admin</option>
              <option value="viewer">viewer</option>
            </select>
          </label>
          <div v-if="grantable.length" class="page-company-detail__perms-note">
            <div class="page-company-detail__perms-label">Доп. доступ (только из вашего):</div>
            <label v-for="g in grantable" :key="g.name" class="page-company-detail__perm-check" :title="g.description || g.name">
              <input type="checkbox" :value="g.name" v-model="invite.perms" /> {{ g.name }}
            </label>
          </div>
          <button type="submit" :disabled="inviting" class="wb-btn-brand wb-btn-brand--form">Пригласить</button>
        </form>
        <div v-if="lastInvite" class="page-company-detail__invite-ok">
          <div>Токен: <code>{{ lastInvite.invite_token }}</code></div>
          <div class="page-company-detail__invite-until">до {{ fmtDT(lastInvite.expires_at) }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-company-detail.css'
import { ref, reactive, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { authApi } from '../api/auth'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const companyId = Number(route.params.id)
const fmtDT = (v: any) => v ? new Date(String(v).replace(' ', 'T')).toLocaleString('ru-RU') : '—'
const data = ref<{ company: any; members: any[] } | null>(null)
const error = ref('')
const editRoles = reactive<Record<number, string>>({})
const invite = reactive({ email: '', role: 'member' as 'admin' | 'member' | 'viewer', perms: [] as string[] })
const inviting = ref(false)
const lastInvite = ref<{ invite_token: string; expires_at: string } | null>(null)
const grantable = ref<Array<{ name: string; description: string | null }>>([])
const addSel = reactive<Record<number, string>>({})
const companyForm = reactive({
  name: '', abbreviation: '', inn: '', api_key: '',
  is_active: true, fbs_deduct_enabled: false, fbs_deduct_test: true,
  seo_model: '', seo_summary_model: '', seo_summary_max_tokens: '',
  seo_daily_limit: '', seo_desc_min: '', seo_desc_max: '', seo_anti_spam_days: '',
  seo_openrouter_key: '', seo_openrouter_referer: '', seo_openrouter_title: '',
  seo_prompt: '', seo_competitor_prompt: '', seo_summary_prompt: '',
})
const showApi = ref(false)
const showSeo = ref(false)
const hasApiKey = ref(false)
const hasSeoKey = ref(false)
function toggleApi() { showApi.value = !showApi.value }
function toggleSeo() { showSeo.value = !showSeo.value }
const savingCompany = ref(false)
const companySaved = ref(false)
const numOrUndef = (v: any) => (v === '' || v == null ? undefined : (Number.isNaN(Number(v)) ? undefined : Number(v)))

async function load() {
  error.value = ''
  try {
    const r = await authApi.getCompanyMembers(companyId)
    data.value = r
    for (const m of r.members) editRoles[m.id] = m.role
    companySaved.value = false
    try {
      const c = await authApi.getCompany(companyId)
      companyForm.name = c.name || ''
      companyForm.abbreviation = c.abbreviation || ''
      companyForm.inn = c.inn || ''
      companyForm.api_key = c.api_key || ''
      hasApiKey.value = !!c.api_key
      companyForm.is_active = c.is_active !== 0 && c.is_active !== false
      companyForm.fbs_deduct_enabled = !!c.fbs_deduct_enabled
      companyForm.fbs_deduct_test = !!c.fbs_deduct_test
      companyForm.seo_model = c.seo_model || ''
      companyForm.seo_summary_model = c.seo_summary_model || ''
      companyForm.seo_summary_max_tokens = c.seo_summary_max_tokens ?? ''
      companyForm.seo_daily_limit = c.seo_daily_limit ?? ''
      companyForm.seo_desc_min = c.seo_desc_min ?? ''
      companyForm.seo_desc_max = c.seo_desc_max ?? ''
      companyForm.seo_anti_spam_days = c.seo_anti_spam_days ?? ''
      companyForm.seo_openrouter_key = c.seo_openrouter_key || ''
      hasSeoKey.value = !!c.seo_openrouter_key
      companyForm.seo_openrouter_referer = c.seo_openrouter_referer || ''
      companyForm.seo_openrouter_title = c.seo_openrouter_title || ''
      companyForm.seo_prompt = c.seo_prompt || ''
      companyForm.seo_competitor_prompt = c.seo_competitor_prompt || ''
      companyForm.seo_summary_prompt = c.seo_summary_prompt || ''
    } catch { /* нет прав на полную запись — только члены */ }
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  }
}

onMounted(async () => {
  load()
  try { grantable.value = await authApi.grantablePerms() } catch { grantable.value = [] }
})
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
    // Секреты подставлены из GET (менеджерам можно) — глаз их показывает.
    // Очистка поля = не менять (сбросить в NULL только через БД).
    // Пустые текстовые/числовые поля не отправляются (текущие значения сохраняются).
    const payload: any = {
      name: companyForm.name,
      abbreviation: companyForm.abbreviation || undefined,
      inn: companyForm.inn || undefined,
      is_active: companyForm.is_active,
    }
    if (companyForm.api_key) payload.api_key = companyForm.api_key
    if (auth.can('manageFbsStocks')) {
      payload.fbs_deduct_enabled = companyForm.fbs_deduct_enabled
      payload.fbs_deduct_test = companyForm.fbs_deduct_test
    }
    if (auth.can('viewSeo')) {
      const t = (v: any) => (v === '' ? undefined : v)
      Object.assign(payload, {
        seo_model: t(companyForm.seo_model),
        seo_summary_model: t(companyForm.seo_summary_model),
        seo_summary_max_tokens: numOrUndef(companyForm.seo_summary_max_tokens),
        seo_daily_limit: numOrUndef(companyForm.seo_daily_limit),
        seo_desc_min: numOrUndef(companyForm.seo_desc_min),
        seo_desc_max: numOrUndef(companyForm.seo_desc_max),
        seo_anti_spam_days: numOrUndef(companyForm.seo_anti_spam_days),
        seo_openrouter_referer: t(companyForm.seo_openrouter_referer),
        seo_openrouter_title: t(companyForm.seo_openrouter_title),
        seo_prompt: t(companyForm.seo_prompt),
        seo_competitor_prompt: t(companyForm.seo_competitor_prompt),
        seo_summary_prompt: t(companyForm.seo_summary_prompt),
      })
      if (companyForm.seo_openrouter_key) payload.seo_openrouter_key = companyForm.seo_openrouter_key
    }
    await authApi.updateCompany(companyId, payload)
    companyForm.api_key = ''
    companyForm.seo_openrouter_key = ''
    companySaved.value = true
    await load()
  } catch (e: any) { error.value = e?.response?.data?.detail || String(e) }
  finally { savingCompany.value = false }
}

async function onInvite() {
  inviting.value = true
  lastInvite.value = null
  try {
    const r = await authApi.inviteMember(companyId, { email: invite.email, role: invite.role, perms: invite.perms })
    lastInvite.value = { invite_token: r.invite_token, expires_at: r.expires_at }
    invite.email = ''
    invite.perms = []
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally { inviting.value = false }
}

async function addPerm(userId: number) {
  const p = addSel[userId]
  if (!p) return
  try {
    await authApi.memberPerms(companyId, userId, { add: [p] })
    addSel[userId] = ''
    await load()
  } catch (e: any) { error.value = e?.response?.data?.detail || String(e) }
}

async function removePerm(userId: number, perm: string) {
  if (!confirm(`Снять ${perm}?`)) return
  try {
    await authApi.memberPerms(companyId, userId, { remove: [perm] })
    await load()
  } catch (e: any) { error.value = e?.response?.data?.detail || String(e) }
}
</script>