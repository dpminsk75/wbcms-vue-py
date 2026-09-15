<template>
  <div class="container-xxl page-company-detail">
    <h2 style="margin-bottom:16px">{{ data?.company?.name || 'Компания' }}</h2>
    <div v-if="error" style="color:#c00">{{ error }}</div>

    <div v-if="data" style="display:flex; flex-direction:column; gap:16px">
      <form @submit.prevent="onSaveCompany">
        <div class="row">
          <div class="col-md-6">
            <div class="card h-100" style="border:1px solid #ddd; border-radius:8px">
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
                    <span v-if="hasApiKey" class="badge" style="background:#E4F5EF; color:#1E9E7C">задан</span>
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
            <div class="card h-100" style="border:1px solid #b6d4fe; border-radius:8px">
              <div class="card-header" style="background:#e7f1ff; font-weight:600">SEO <small style="font-weight:400; color:#666">пусто = из params.php</small></div>
              <div class="card-body">
                <div class="mb-2">
                  <label class="form-label mb-1">OpenRouter API key
                    <span v-if="hasSeoKey" class="badge" style="background:#E4F5EF; color:#1E9E7C">задан</span>
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
        <div style="margin-top:10px; display:flex; gap:8px; align-items:center">
          <button type="submit" :disabled="savingCompany" style="background:#4A3A8C; color:#fff; border:none; padding:8px 16px; border-radius:6px">Сохранить компанию</button>
          <span v-if="companySaved" style="font-size:13px; color:#1E9E7C">Сохранено</span>
        </div>
      </form>

      <table style="width:100%; border-collapse:collapse">
        <thead>
          <tr style="background:#f4f4f8">
            <th style="text-align:left; padding:8px">ID</th>
            <th style="text-align:left; padding:8px">Пользователь</th>
            <th style="text-align:left; padding:8px">Email</th>
            <th style="text-align:left; padding:8px">Роль</th>
            <th style="text-align:left; padding:8px">Статус</th>
            <th style="text-align:left; padding:8px">Пермы</th>
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
            <td style="padding:8px">
              <span v-for="p in (m.perms || [])" :key="p" style="display:inline-block; background:#eef4ff; border-radius:8px; padding:1px 6px; margin:0 4px 2px 0; font-size:12px">
                {{ p }}<a href="#" @click.prevent="removePerm(m.id, p)" style="margin-left:4px; color:#c00; text-decoration:none" title="Снять">×</a>
              </span>
              <select v-model="addSel[m.id]" @change="addPerm(m.id)" style="font-size:12px; max-width:140px">
                <option value="">+ перм...</option>
                <option v-for="g in grantable" :key="g.name" :value="g.name" :disabled="(m.perms || []).includes(g.name)">{{ g.name }}</option>
              </select>
            </td>
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
              <option value="viewer">viewer</option>
            </select>
          </label>
          <div v-if="grantable.length" style="font-size:13px">
            <div style="margin-bottom:4px; color:#555">Доп. доступ (только из вашего):</div>
            <label v-for="g in grantable" :key="g.name" style="display:block; font-weight:normal" :title="g.description || g.name">
              <input type="checkbox" :value="g.name" v-model="invite.perms" /> {{ g.name }}
            </label>
          </div>
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