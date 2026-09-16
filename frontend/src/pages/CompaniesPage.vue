<template>
  <div class="container-xxl page-companies">
    <div class="page-companies__head">
      <h2 class="page-companies__title">Мои компании</h2>
      <button v-if="canCreate" @click="openCreate = true" class="wb-btn-brand wb-btn-brand--lg">Создать компанию</button>
    </div>

    <table class="wb-admin-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Название</th>
          <th>Аббревиатура</th>
          <th>ИНН</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="c in auth.companies" :key="c.id">
          <td>{{ c.id }}</td>
          <td>{{ c.name }}</td>
          <td>{{ c.abbreviation || '—' }}</td>
          <td>{{ c.inn || '—' }}</td>
          <td><router-link :to="`/companies/${c.id}`">Открыть</router-link></td>
        </tr>
        <tr v-if="!auth.companies.length"><td colspan="5" class="page-companies__empty">Нет компаний</td></tr>
      </tbody>
    </table>

    <div v-if="openCreate" class="wb-modal-backdrop">
      <form @submit.prevent="onCreate" class="wb-modal-box wb-modal-box--wide">
        <h3 class="page-companies__modal-title">Создать компанию</h3>
        <label>Название<input v-model="createForm.name" required class="wb-field" /></label>
        <label>Аббревиатура<input v-model="createForm.abbreviation" class="wb-field" /></label>
        <label>ИНН<input v-model="createForm.inn" class="wb-field" /></label>
        <div v-if="createError" class="wb-error">{{ createError }}</div>
        <div class="wb-modal-actions">
          <button type="button" @click="openCreate = false">Отмена</button>
          <button type="submit" :disabled="creating" class="wb-btn-brand wb-btn-brand--md">Создать</button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-companies.css'
import { reactive, ref, computed } from 'vue'
import { useAuthStore } from '../stores/auth'
import { authApi } from '../api/auth'

const auth = useAuthStore()
const canCreate = computed(() => auth.isAuth) // self-service: любая залогиненная = может создать компанию (станет owner)
const openCreate = ref(false)
const creating = ref(false)
const createError = ref('')
const createForm = reactive({ name: '', abbreviation: '', inn: '' })

async function onCreate() {
  creating.value = true
  createError.value = ''
  try {
    await authApi.createCompany({ name: createForm.name, abbreviation: createForm.abbreviation || undefined, inn: createForm.inn || undefined })
    await auth.loadCompanies()
    openCreate.value = false
    createForm.name = ''
    createForm.abbreviation = ''
    createForm.inn = ''
  } catch (e: any) {
    createError.value = e?.response?.data?.detail || String(e)
  } finally {
    creating.value = false
  }
}
</script>