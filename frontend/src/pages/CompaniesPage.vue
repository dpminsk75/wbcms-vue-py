<template>
  <div class="container-xxl page-companies">
    <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:16px">
      <h2 style="margin:0">Мои компании</h2>
      <button v-if="canCreate" @click="openCreate = true" style="padding:8px 14px; background:#4A3A8C; color:#fff; border:none; border-radius:6px">Создать компанию</button>
    </div>

    <table style="width:100%; border-collapse:collapse">
      <thead>
        <tr style="background:#f4f4f8">
          <th style="text-align:left; padding:8px">ID</th>
          <th style="text-align:left; padding:8px">Название</th>
          <th style="text-align:left; padding:8px">Аббревиатура</th>
          <th style="text-align:left; padding:8px">ИНН</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="c in auth.companies" :key="c.id" style="border-bottom:1px solid #eee">
          <td style="padding:8px">{{ c.id }}</td>
          <td style="padding:8px">{{ c.name }}</td>
          <td style="padding:8px">{{ c.abbreviation || '—' }}</td>
          <td style="padding:8px">{{ c.inn || '—' }}</td>
          <td style="padding:8px"><router-link :to="`/companies/${c.id}`">Открыть</router-link></td>
        </tr>
        <tr v-if="!auth.companies.length"><td colspan="5" style="padding:20px; text-align:center; color:#666">Нет компаний</td></tr>
      </tbody>
    </table>

    <div v-if="openCreate" style="position:fixed; inset:0; background:rgba(0,0,0,.4); display:flex; align-items:center; justify-content:center">
      <form @submit.prevent="onCreate" style="background:#fff; padding:20px; border-radius:8px; min-width:360px; display:flex; flex-direction:column; gap:10px">
        <h3 style="margin:0">Создать компанию</h3>
        <label>Название<input v-model="createForm.name" required style="width:100%" /></label>
        <label>Аббревиатура<input v-model="createForm.abbreviation" style="width:100%" /></label>
        <label>ИНН<input v-model="createForm.inn" style="width:100%" /></label>
        <div v-if="createError" style="color:#c00">{{ createError }}</div>
        <div style="display:flex; gap:8px; justify-content:flex-end">
          <button type="button" @click="openCreate = false">Отмена</button>
          <button type="submit" :disabled="creating" style="background:#4A3A8C; color:#fff; border:none; padding:6px 12px; border-radius:6px">Создать</button>
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