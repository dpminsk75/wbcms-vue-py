<template>
  <div class="container-xxl page-register">
    <h2 class="page-register__title">Регистрация</h2>
    <form @submit.prevent="onSubmit" class="page-register__form">
      <label>
        <div>Invite-токен</div>
        <input v-model="form.invite_token" required class="wb-field" placeholder="из ссылки/письма" @change="peek" />
      </label>
      <div v-if="peeking" class="page-register__hint">Проверяем токен...</div>
      <div v-if="peekError" class="wb-error">{{ peekError }}</div>
      <div v-if="tokenInfo?.type === 'company'" class="page-register__token-info">
        Регистрация компании <b>«{{ tokenInfo.company_name }}»</b> — вы станете её owner.
        Название ниже должно совпасть с приглашением.
      </div>
      <div v-if="tokenInfo?.type === 'user'" class="page-register__token-info">
        Приглашение в <b>«{{ tokenInfo.company?.name || ('#' + tokenInfo.company_id) }}»</b>
        (роль {{ tokenInfo.role }}) — email должен совпасть с
        <b>{{ tokenInfo.email_masked }}</b>.
      </div>
      <label>
        <div>Имя пользователя</div>
        <input v-model="form.username" required minlength="3" maxlength="64" class="wb-field" />
      </label>
      <label>
        <div>Email</div>
        <input v-model="form.email" type="email" required class="wb-field" />
      </label>
      <label>
        <div>Пароль</div>
        <input v-model="form.password" type="password" required minlength="6" class="wb-field" />
      </label>
      <template v-if="tokenInfo?.type === 'company'">
        <label>
          <div>Название компании</div>
          <input v-model="form.company_name" required class="wb-field" />
        </label>
        <label>
          <div>Аббревиатура (необязательно)</div>
          <input v-model="form.abbreviation" class="wb-field" />
        </label>
        <label>
          <div>ИНН (необязательно)</div>
          <input v-model="form.inn" class="wb-field" />
        </label>
      </template>
      <button type="submit" :disabled="busy" class="wb-btn-brand wb-btn-brand--block">
        {{ busy ? 'Отправляем...' : 'Создать аккаунт' }}
      </button>
      <div v-if="error" class="wb-error">{{ error }}</div>
      <div class="page-register__foot">Уже есть аккаунт? <router-link to="/login">Войти</router-link></div>
    </form>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-register.css'
import { reactive, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { authApi } from '../api/auth'
import { api } from '../api/client'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const form = reactive({ invite_token: '', username: '', email: '', password: '', company_name: '', abbreviation: '', inn: '' })
const busy = ref(false)
const error = ref('')

// B1: тип токена узнаём публичным peek, иначе поле компании не показать
const tokenInfo = ref<{ type: 'company' | 'user'; company_name?: string; company_id?: number; company?: any; email_masked?: string; role?: string; expires_at?: string } | null>(null)
const peeking = ref(false)
const peekError = ref('')

async function peek() {
  tokenInfo.value = null
  peekError.value = ''
  const t = form.invite_token.trim()
  if (!t) return
  peeking.value = true
  try {
    tokenInfo.value = await authApi.inviteInfo(t)
    // подсказка: для user-токена email уже задан приглашением
    if (tokenInfo.value.type === 'company' && tokenInfo.value.company_name && !form.company_name) {
      form.company_name = tokenInfo.value.company_name
    }
  } catch {
    peekError.value = 'Токен не найден или просрочен'
  } finally {
    peeking.value = false
  }
}

onMounted(() => {
  const params = new URLSearchParams(location.search)
  const t = params.get('invite')
  if (t) { form.invite_token = t; peek() }
})

async function onSubmit() {
  busy.value = true
  error.value = ''
  try {
    const payload: any = {
      username: form.username,
      email: form.email,
      password: form.password,
      invite_token: form.invite_token.trim(),
    }
    if (tokenInfo.value?.type === 'company') {
      payload.company_name = form.company_name
      if (form.abbreviation) payload.abbreviation = form.abbreviation
      if (form.inn) payload.inn = form.inn
    }
    const r = await authApi.register(payload)
    api.defaults.headers.common.Authorization = `Bearer ${r.token}`
    try { localStorage.setItem('wbcms_token', r.token) } catch { /* noop */ }
    // заполняем стор как при логине, новую компанию выбираем сразу
    await auth.loadMe().catch(() => {})
    await auth.loadCompanies().catch(() => {})
    if ((r as any).company?.id) auth.setCompany((r as any).company.id)
    router.push('/')
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    busy.value = false
  }
}
</script>
