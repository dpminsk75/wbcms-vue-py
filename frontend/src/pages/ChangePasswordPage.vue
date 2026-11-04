<template>
  <div class="container-xxl page-change-password">
    <h1 class="page-title">Сменить пароль</h1>
    <div class="page-change-password__panel wb-panel">
      <div class="wb-panel__bd">
        <p class="page-change-password__muted">Аккаунт <b>{{ auth.user?.username }}</b> · смена по текущему паролю, без ссылок</p>
        <form @submit.prevent="submit" class="page-change-password__form">
          <div class="wb-field">
            <label class="wb-field__label" for="cp-old">Текущий пароль</label>
            <input id="cp-old" v-model="oldPwd" type="password" class="wb-input" required autocomplete="current-password" />
          </div>
          <div class="wb-field">
            <label class="wb-field__label" for="cp-new">Новый пароль</label>
            <input id="cp-new" v-model="pwd" type="password" class="wb-input" required
                   minlength="8" pattern="(?=.*[A-Za-zА-Яа-яЁё])(?=.*\d).{8,}"
                   title="Минимум 8 символов, буквы и цифры" autocomplete="new-password" />
          </div>
          <div class="page-change-password__hint">Минимум 8 символов, хотя бы одна буква и одна цифра.</div>
          <div class="wb-field">
            <label class="wb-field__label" for="cp-repeat">Повторите новый пароль</label>
            <input id="cp-repeat" v-model="pwd2" type="password" class="wb-input" required
                   minlength="8" autocomplete="new-password" />
          </div>
          <div>
            <button type="submit" class="btn btn--brand" :disabled="busy">
              <i class="bi bi-check2-circle"></i> {{ busy ? 'Сохраняем…' : 'Сохранить' }}
            </button>
          </div>
          <div v-if="done" class="page-change-password__ok">Пароль изменён. Старый пароль больше не действует.</div>
          <div v-if="error" class="wb-error">{{ error }}</div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-change-password.css'
import { ref } from 'vue'
import { authApi } from '../api/auth'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()

const oldPwd = ref('')
const pwd = ref('')
const pwd2 = ref('')
const error = ref('')
const done = ref(false)
const busy = ref(false)

async function submit() {
  error.value = ''
  done.value = false
  if (pwd.value.length < 8 || !/[A-Za-zА-Яа-яЁё]/.test(pwd.value) || !/\d/.test(pwd.value)) {
    error.value = 'Минимум 8 символов, нужны буквы и цифры'; return
  }
  if (pwd.value !== pwd2.value) { error.value = 'Пароли не совпадают'; return }
  busy.value = true
  try {
    await authApi.changePassword(oldPwd.value, pwd.value)
    oldPwd.value = ''
    pwd.value = ''
    pwd2.value = ''
    done.value = true
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось сохранить пароль'
  } finally {
    busy.value = false
  }
}
</script>
