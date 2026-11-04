<template>
  <div class="page-reset-password">
    <div class="page-reset-password__card wb-panel">
      <div class="wb-panel__bd">
        <template v-if="state === 'loading'">
          <p class="page-reset-password__muted mb-0">Проверяем ссылку…</p>
        </template>

        <template v-else-if="state === 'form'">
          <h1 class="page-reset-password__title">Новый пароль</h1>
          <p class="page-reset-password__muted">
            Ссылка для <b>{{ info?.email_masked }}</b><template v-if="expiresText"> · действует до {{ expiresText }}</template>
          </p>
          <form @submit.prevent="submit" class="page-reset-password__form">
            <div class="wb-field">
              <label class="wb-field__label" for="rp-new">Новый пароль</label>
              <input id="rp-new" v-model="pwd" type="password" class="wb-input" required
                     minlength="8" pattern="(?=.*[A-Za-zА-Яа-яЁё])(?=.*\d).{8,}"
                     title="Минимум 8 символов, буквы и цифры" autocomplete="new-password" />
            </div>
            <div class="page-reset-password__hint">Минимум 8 символов, хотя бы одна буква и одна цифра.</div>
            <div class="wb-field">
              <label class="wb-field__label" for="rp-repeat">Повторите пароль</label>
              <input id="rp-repeat" v-model="pwd2" type="password" class="wb-input" required
                     minlength="8" autocomplete="new-password" />
            </div>
            <button type="submit" class="btn btn--brand" :disabled="busy">
              <i class="bi bi-check2-circle"></i> {{ busy ? 'Сохраняем…' : 'Сохранить пароль' }}
            </button>
            <div v-if="error" class="wb-error">{{ error }}</div>
          </form>
        </template>

        <template v-else-if="state === 'error'">
          <h1 class="page-reset-password__title">Ссылка не действует</h1>
          <div class="wb-error">Ссылка недействительна, использована или просрочена. Попросите администратора выпустить новую.</div>
          <router-link to="/login" class="btn btn--outline"><i class="bi bi-box-arrow-in-right"></i> На страницу входа</router-link>
        </template>

        <template v-else>
          <div class="page-reset-password__success">
            <div class="page-reset-password__circle"><i class="bi bi-check-lg"></i></div>
            <h1 class="page-reset-password__title">Пароль изменён</h1>
            <p class="page-reset-password__muted">Старый пароль больше не действует. Сеансы завершатся в течение 12 часов.</p>
            <router-link to="/login" class="btn btn--brand"><i class="bi bi-box-arrow-in-right"></i> Войти</router-link>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-reset-password.css'
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { authApi } from '../api/auth'
import { useDateFmt } from '../composables/useDateFmt'

const route = useRoute()
const { fmtDTRu } = useDateFmt()

const token = computed(() => String(route.query.token || ''))
const state = ref<'loading' | 'form' | 'error' | 'done'>('loading')
const info = ref<{ email_masked?: string; expires_at?: string } | null>(null)
const expiresText = computed(() => (info.value?.expires_at ? fmtDTRu(info.value.expires_at) : ''))

const pwd = ref('')
const pwd2 = ref('')
const error = ref('')
const busy = ref(false)

onMounted(async () => {
  if (!token.value) { state.value = 'error'; return }
  try {
    info.value = await authApi.resetInfo(token.value)
    state.value = 'form'
  } catch {
    state.value = 'error'
  }
})

async function submit() {
  error.value = ''
  if (pwd.value.length < 8 || !/[A-Za-zА-Яа-яЁё]/.test(pwd.value) || !/\d/.test(pwd.value)) {
    error.value = 'Минимум 8 символов, нужны буквы и цифры'; return
  }
  if (pwd.value !== pwd2.value) { error.value = 'Пароли не совпадают'; return }
  busy.value = true
  try {
    await authApi.resetPassword(token.value, pwd.value)
    state.value = 'done'
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось сохранить пароль'
  } finally {
    busy.value = false
  }
}
</script>
