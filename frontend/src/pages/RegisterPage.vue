<template>
  <div class="container-xxl page-register">
    <h2 style="margin-bottom:20px">Регистрация</h2>
    <form @submit.prevent="onSubmit" class="page-register__form">
      <label>
        <div>Invite-токен</div>
        <input v-model="form.invite_token" required style="width:100%" placeholder="из ссылки/письма" @change="peek" />
      </label>
      <div v-if="peeking" style="font-size:13px; color:#666">Проверяем токен...</div>
      <div v-if="peekError" style="font-size:13px; color:#c00">{{ peekError }}</div>
      <div v-if="tokenInfo?.type === 'company'" style="font-size:13px; padding:10px; background:#eef4ff; border-radius:6px">
        Регистрация компании <b>«{{ tokenInfo.company_name }}»</b> — вы станете её owner.
        Название ниже должно совпасть с приглашением.
      </div>
      <div v-if="tokenInfo?.type === 'user'" style="font-size:13px; padding:10px; background:#eef4ff; border-radius:6px">
        Приглашение в <b>«{{ tokenInfo.company?.name || ('#' + tokenInfo.company_id) }}»</b>
        (роль {{ tokenInfo.role }}) — email должен совпасть с
        <b>{{ tokenInfo.email_masked }}</b>.
      </div>
      <label>
        <div>Имя пользователя</div>
        <input v-model="form.username" required minlength="3" maxlength="64" style="width:100%" />
      </label>
      <label>
        <div>Email</div>
        <input v-model="form.email" type="email" required style="width:100%" />
      </label>
      <label>
        <div>Пароль</div>
        <input v-model="form.password" type="password" required minlength="6" style="width:100%" />
      </label>
      <template v-if="tokenInfo?.type === 'company'">
        <label>
          <div>Название компании</div>
          <input v-model="form.company_name" required style="width:100%" />
        </label>
        <label>
          <div>Аббревиатура (необязательно)</div>
          <input v-model="form.abbreviation" style="width:100%" />
        </label>
        <label>
          <div>ИНН (необязательно)</div>
          <input v-model="form.inn" style="width:100%" />
        </label>
      </template>
      <button type="submit" :disabled="busy" style="padding:10px; background:#4A3A8C; color:#fff; border:none; border-radius:6px">
        {{ busy ? 'Отправляем...' : 'Создать аккаунт' }}
      </button>
      <div v-if="error" style="color:#c00">{{ error }}</div>
      <div style="font-size:13px; color:#666">Уже есть аккаунт? <router-link to="/login">Войти</router-link></div>
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
