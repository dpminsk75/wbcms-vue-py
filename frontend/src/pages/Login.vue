<template>
  <div class="d-flex align-items-center justify-content-center" style="min-height:80vh">
    <div class="card p-4" style="width:360px">
      <h5 class="mb-3">Вход — {{ appName }}</h5>
      <div class="mb-2">
        <label class="form-label" for="login-u">Логин</label>
        <input id="login-u" v-model="username" class="form-control" autocomplete="username" @keyup.enter="doLogin" />
      </div>
      <div class="mb-3">
        <label class="form-label" for="login-p">Пароль</label>
        <input id="login-p" v-model="password" type="password" class="form-control" autocomplete="current-password" @keyup.enter="doLogin" />
      </div>
      <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
      <button class="btn btn-primary w-100" :disabled="loading" @click="doLogin">
        <span v-if="loading" class="spinner-border spinner-border-sm me-1"></span>Войти
      </button>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const appName = (import.meta as any).env?.VITE_APP_NAME || 'wbcms'

async function doLogin() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(username.value.trim(), password.value)
    const back = String(route.query.back || '/')
    router.push(back)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Ошибка входа'
  } finally {
    loading.value = false
  }
}
</script>
