<template>
  <div class="container-xxl page-company-detail">
    <h2 class="page-company-detail__title">{{ data?.company?.name || 'Компания' }}</h2>
    <div v-if="error" class="wb-error">{{ error }}</div>

    <div v-if="data" class="page-company-detail__stack">
      <ul class="nav nav-tabs page-company-detail__tabs">
        <li class="nav-item">
          <button type="button" :class="['nav-link', { active: tab === 'main' }]" @click="tab = 'main'"><i class="bi bi-building"></i> Основное</button>
        </li>
        <li class="nav-item">
          <button type="button" :class="['nav-link', { active: tab === 'wb' }]" @click="tab = 'wb'"><i class="bi bi-key"></i> WB-ключ <span v-if="wbToken?.expired" class="badge bg-danger" title="Токен просрочен">!</span></button>
        </li>
        <li v-if="auth.can('viewSeo')" class="nav-item">
          <button type="button" :class="['nav-link', { active: tab === 'seo' }]" @click="tab = 'seo'"><i class="bi bi-search"></i> SEO</button>
        </li>
        <li v-if="auth.can('viewSeo')" class="nav-item">
          <button type="button" :class="['nav-link', { active: tab === 'ext' }]" @click="tab = 'ext'"><i class="bi bi-puzzle"></i> Расширение</button>
        </li>
        <li class="nav-item">
          <button type="button" :class="['nav-link', { active: tab === 'members' }]" @click="tab = 'members'"><i class="bi bi-people"></i> Участники <span class="badge bg-secondary">{{ data.members.length }}</span></button>
        </li>
      </ul>
      <form @submit.prevent="onSaveCompany">
        <div v-show="tab === 'main'" class="page-company-detail__pane">
          <div class="row">
            <div class="col-12">
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
        </div>
        </div>
        <div v-show="tab === 'wb'" class="page-company-detail__pane">
          <div class="row">
            <div class="col-12">
              <div class="card h-100 page-company-detail__card-main">
                <div class="card-header bg-light fw-semibold">WB-ключ <small class="page-company-detail__seo-note">проверка проходит по черновику из поля, сохраняется кнопкой ниже</small></div>
                <div class="card-body">
                  <div class="mb-2">
                    <label class="form-label mb-1">API ключ WB
                    <span v-if="hasApiKey" class="badge wb-key-badge">задан</span>
                    <span v-else class="badge bg-light text-muted border">не задан</span>
                  </label>
                  <div class="input-group input-group-sm">
                    <input v-model="companyForm.api_key" :type="showApi ? 'text' : 'password'" autocomplete="new-password" placeholder="JWT WB" class="form-control" />
                    <button type="button" @click="toggleApi" class="btn btn-outline-secondary" title="Показать/скрыть"><i class="bi bi-eye"></i></button>
                  </div>
                  <div class="page-company-detail__wb-row">
                    <button type="button" @click="checkWb" :disabled="wbChecking" class="btn btn-outline-secondary btn-sm" title="Этап 1: пинг категорий, этап 2: профиль продавца">
                      <i class="bi bi-activity"></i> Проверить
                    </button>
                    <button type="button" @click="loadWbStatus" :disabled="wbLoading" class="btn btn-outline-secondary btn-sm" title="Только декодировать сохранённый токен (без запросов к WB)">
                      Статус
                    </button>
                    <span v-if="wbChecking" class="page-company-detail__wb-hint">проверяю WB: {{ wbCheckingPhase }}…</span>
                    <span v-else-if="wbError" class="wb-error">{{ wbError }}</span>
                  </div>
                  <div v-if="wbToken && wbToken.has_token && wbToken.valid" class="page-company-detail__wb-status">
                    <div class="page-company-detail__wb-line">
                      <span>до {{ fmtDate(wbToken.exp_at) }}</span>
                      <span :class="daysClass">осталось {{ wbToken.days_left }} дн.</span>
                      <span v-if="wbToken.expired" class="badge bg-danger">просрочен</span>
                      <span v-if="wbToken.is_readonly" class="badge bg-danger" title="Бит 30 маски s — токен только на чтение, менять данные через API нельзя">только чтение</span>
                      <span v-else class="badge bg-success" title="Бит 30 маски s не установлен — токен на чтение и запись">чтение и запись</span>
                      <span :class="typeClass" :title="typeTitle">{{ wbToken.token_type_ru || '—' }}</span>
                      <span v-if="wbToken.is_test" class="badge bg-light text-muted border" title="Бит 0 маски s — тестовый контур, боевых данных нет">test</span>
                    </div>
                    <div class="page-company-detail__wb-cats" title="Категории из битмаски s токена. Зелёная — доступ есть, серая — нет. Наведите на букву для деталей.">
                      <span v-for="c in WB_TOKEN_CATS" :key="c.key" :class="catClass(c.key)" :title="catTitle(c.key)">{{ c.letter }}</span>
                    </div>
                    <div v-if="wbToken.source === 'draft'" class="page-company-detail__wb-hint">проверен черновик из поля (не сохранён)</div>
                  </div>
                  <div v-else-if="wbToken && wbToken.has_token && wbToken.valid === false" class="wb-error">Токен не разбирается: {{ wbToken.error }}</div>
                  <div v-else-if="wbToken && !wbToken.has_token" class="page-company-detail__wb-hint">токен не задан</div>
                  <div v-if="wbProfile && wbProfile.has_profile" class="page-company-detail__wb-profile">
                    <div class="page-company-detail__wb-line">
                      <i class="bi bi-shop"></i>
                      <strong>{{ wbProfile.seller_name || 'Продавец' }}</strong>
                      <span v-if="wbProfile.trademark" class="page-company-detail__wb-tariff" :title="`Марка (tradeMark)`">«{{ wbProfile.trademark }}»</span>
                      <span v-if="wbProfile.tin" class="page-company-detail__wb-tariff" title="ИНН из seller-info (tin)">ИНН {{ wbProfile.tin }}</span>
                      <span v-if="wbProfile.rating != null" class="page-company-detail__wb-rating" :title="`Отзывов: ${wbProfile.reviews_count ?? '—'}`">
                        <i class="bi bi-star-fill"></i> {{ wbProfile.rating }}
                      </span>
                      <span v-if="wbProfile.has_jam === true" class="badge bg-success" title="WB вернул данные подписки Jam">Джем</span>
                      <span v-else-if="wbProfile.has_jam === false" class="badge bg-light text-muted border" title="Пустой ответ WB — подписки Джем не было">без Джема</span>
                      <span v-if="tariffSummary" class="page-company-detail__wb-tariff" :title="tariffTitle">{{ tariffSummary }}</span>
                    </div>
                    <details v-if="tariffItems.length" class="page-company-detail__wb-details">
                      <summary>Конструктор тарифов ({{ tariffItems.length }})</summary>
                      <ul class="page-company-detail__wb-tariff-list">
                        <li v-for="(t, i) in tariffItems" :key="i">
                          {{ t.name }} — {{ t.statusRu }}<span v-if="t.rate != null">, {{ t.rate }}%</span><span v-if="t.until">, до {{ fmtDate(t.until) }}</span>
                        </li>
                      </ul>
                    </details>
                    <div class="page-company-detail__wb-hint">профиль от {{ fmtDateTime(wbProfile.fetched_at) }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        </div>
          <div v-if="auth.can('viewSeo')" v-show="tab === 'seo'" class="page-company-detail__pane">
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
                    <button type="button" @click="toggleSeo" class="btn btn-outline-secondary" title="Показать/скрыть"><i class="bi bi-eye"></i></button>
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
        <div v-if="isFormTab" class="page-company-detail__save-row">
          <button type="submit" :disabled="savingCompany" class="wb-btn-brand wb-btn-brand--xl">Сохранить компанию</button>
          <span v-if="companySaved" class="page-company-detail__saved">Сохранено</span>
        </div>
      </form>

      <div v-show="tab === 'ext'">
        <ExtTokensBlock v-if="auth.can('viewSeo')" :companyId="companyId" />
      </div>

      <div v-show="tab === 'members'">
      <div class="page-company-detail__table-wrap">
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
      </div>

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
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-company-detail.css'
import { ref, reactive, watch, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { authApi, WB_TOKEN_CATS, type WbTokenState, type WbProfile } from '../api/auth'
import ExtTokensBlock from '../components/ext/ExtTokensBlock.vue'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const companyId = Number(route.params.id)
// Табы: одна тема на экран вместо стены блоков (состояние форм — в companyForm, не теряется)
const tab = ref<'main' | 'wb' | 'seo' | 'ext' | 'members'>('main')
const isFormTab = computed(() => tab.value === 'main' || tab.value === 'wb' || tab.value === 'seo')
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
// WB-токен: статус/проверка (decode — дёшево, check — живой ping, троттлинг 60с на бэке)
const wbToken = ref<WbTokenState | null>(null)
const wbProfile = ref<WbProfile | null>(null)
const wbLoading = ref(false)
const wbChecking = ref(false)
const wbCheckingPhase = ref('')
const wbError = ref('')
const fmtDate = (v: any) => v ? new Date(String(v)).toLocaleDateString('ru-RU') : '—'
const fmtDateTime = (v: any) => v ? new Date(String(v).replace(' ', 'T')).toLocaleString('ru-RU') : '—'
// Тип токена по acc/for/t: personal — наш случай (on-premise), service — чужой SaaS (нам нельзя)
const TYPE_CLASS: Record<string, string> = { personal: 'bg-success', service: 'bg-info text-dark', basic: 'bg-secondary', test: 'bg-warning text-dark', unknown: 'bg-danger' }
const TYPE_HINT: Record<string, string> = {
  personal: 'Персональный (acc=3, for=self) — для своих программ, полные лимиты',
  service: 'Сервисный (acc=4) — для облачных сервисов из каталога WB, нам не подходит',
  basic: 'Базовый (acc=1) — сниженные лимиты, часть категорий недоступна',
  test: 'Тестовый (t=true) — только песочница, боевых данных нет',
  unknown: 'Тип не распознан по acc/for/t',
}
const typeClass = computed(() => ['badge', TYPE_CLASS[wbToken.value?.token_type || 'unknown'] || 'bg-danger'])
const typeTitle = computed(() => {
  const t = wbToken.value?.token_type || 'unknown'
  const acc = wbToken.value?.acc ?? '?'
  const fv = wbToken.value?.for ?? '—'
  return `${TYPE_HINT[t] || ''} (acc=${acc}, for=${fv})`
})
const STATUS_RU: Record<string, string> = { active: 'активна', pendingDeactivation: 'снимается', pendingActivation: 'включается' }
const tariffItems = computed(() => {
  const t = wbProfile.value?.tariffs
  if (!t) return [] as Array<{ name: string; statusRu: string; rate?: number | null; until?: string | null }>
  const pkgs = (t.packages || []).map((p) => ({ name: `Пакет «${p.name || p.slug}»`, statusRu: STATUS_RU[p.status || ''] || p.status || '?', rate: p.commissionRate ?? null, until: p.expiresAt ?? null }))
  const opts = (t.options || []).map((o) => ({ name: o.name || o.slug || '?', statusRu: STATUS_RU[o.status || ''] || o.status || '?', rate: o.commissionRate ?? null, until: o.expiresAt ?? null }))
  return [...pkgs, ...opts]
})
const tariffSummary = computed(() => {
  const t = wbProfile.value?.tariffs
  if (!t) return ''
  const parts = [`комиссия ${(t.totalCommissionRate ?? '—')}%`]
  if (t.activePackageCount != null) parts.push(`пакетов: ${t.activePackageCount}`)
  if (t.activeOptionCount != null) parts.push(`опций: ${t.activeOptionCount}`)
  return parts.join(', ')
})
const tariffTitle = computed(() => tariffItems.value.map((t) => `${t.name} — ${t.statusRu}`).join('\n'))
const daysClass = computed(() => {
  const d = wbToken.value?.days_left
  if (d == null) return 'page-company-detail__wb-days'
  if (wbToken.value?.expired || d <= 3) return 'page-company-detail__wb-days page-company-detail__wb-days--danger'
  if (d <= 14) return 'page-company-detail__wb-days page-company-detail__wb-days--warn'
  return 'page-company-detail__wb-days page-company-detail__wb-days--ok'
})
const catInToken = (key: string) => wbToken.value?.categories?.find((c) => c.key === key)?.in_token ?? false
function catClass(key: string) {
  const p = wbToken.value?.ping?.[key]
  const on = p && !p.skipped ? p.ok : catInToken(key)
  return ['page-company-detail__wb-cat', on ? 'page-company-detail__wb-cat--on' : 'page-company-detail__wb-cat--off']
}
function catTitle(key: string) {
  const meta = WB_TOKEN_CATS.find((c) => c.key === key)
  const name = meta ? `${meta.letter} — ${meta.name}` : key
  if (!catInToken(key)) return `${name}: нет в токене (бит маски s)`
  const p = wbToken.value?.ping?.[key]
  if (!p || p.skipped || p.http == null) return `${name}: есть в токене, живой ping не проверялся (нажмите Проверить)`
  if (p.ok) return `${name}: доступ есть (HTTP ${p.http}, ${p.ms} мс)`
  if (p.http === 403) return `${name}: 403 — ${p.no_jam ? 'нет подписки Jam' : 'нет доступа'} (проверьте категории/тариф)`
  if (p.http === 401) return `${name}: 401 — токен мёртв (истёк/отозван)`
  if (!p.http) return `${name}: сеть — ${p.error || 'timeout'}`
  return `${name}: HTTP ${p.http}`
}
async function loadWbStatus() {
  wbLoading.value = true
  wbError.value = ''
  try {
    wbToken.value = await authApi.wbTokenStatus(companyId)
  } catch (e: any) {
    wbError.value = e?.response?.data?.detail || String(e)
  } finally {
    wbLoading.value = false
  }
}
async function loadWbProfile() {
  try {
    const p = await authApi.wbTokenProfile(companyId)
    wbProfile.value = p.has_profile ? p : null
  } catch {
    wbProfile.value = null
  }
}
async function checkWb() {
  wbChecking.value = true
  wbError.value = ''
  try {
    const draft = companyForm.api_key?.trim() ? companyForm.api_key.trim() : undefined
    // Этап 1: decode + ping категорий (~5-10с)
    wbCheckingPhase.value = 'пинг категорий'
    const res = await authApi.wbTokenCheck(companyId, draft)
    wbToken.value = res
    // Этап 2: профиль продавца, 4 метода common-api с паузами (~10-15с)
    wbCheckingPhase.value = 'профиль продавца'
    try {
      const pr = await authApi.wbTokenProfileRefresh(companyId, draft)
      if (pr.profile) wbProfile.value = { has_profile: true, company_id: companyId, ...pr.profile } as WbProfile
      else loadWbProfile()
    } catch {
      loadWbProfile() // 429/ошибка профиля — показываем сохранённый, токен уже проверен
    }
  } catch (e: any) {
    // Сразу после ручной проверки бэк троттлит (60с) — тогда просто обновляем статус без сети
    if (e?.response?.status === 429) {
      wbError.value = ''
      loadWbStatus()
    } else {
      wbError.value = e?.response?.data?.detail || String(e)
    }
  } finally {
    wbChecking.value = false
    wbCheckingPhase.value = ''
  }
}
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
  loadWbStatus()
  loadWbProfile()
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
    const hadNewKey = !!payload.api_key
    companyForm.api_key = ''
    companyForm.seo_openrouter_key = ''
    companySaved.value = true
    await load()
    // Новый токен — сразу живая проверка с лоадером (wbChecking), иначе дешёвый статус
    if (hadNewKey) await checkWb()
    else loadWbStatus()
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