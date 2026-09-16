<template>
  <div class="container-xxl page-admin-companies">
    <h2 class="page-admin-companies__title">Компании (админ)</h2>
    <div v-if="error" class="wb-error">{{ error }}</div>
    <table class="wb-admin-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Название</th>
          <th>Аббревиатура</th>
          <th>ИНН</th>
          <th>Членов</th>
          <th>Активна</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="c in companies" :key="c.id">
          <td>{{ c.id }}</td>
          <td>{{ c.name }}</td>
          <td>{{ c.abbreviation || '—' }}</td>
          <td>{{ c.inn || '—' }}</td>
          <td>{{ c.members_count }}</td>
          <td>{{ c.is_active ? 'Да' : 'Нет' }}</td>
          <td>
            <button @click="toggle(c)" :disabled="busy === c.id" :style="{background: c.is_active ? '#c00' : '#0a0', color:'#fff', border:'none', padding:'4px 10px', borderRadius:'6px'}">
              {{ c.is_active ? 'Деактивировать' : 'Активировать' }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-admin-companies.css'
import { ref } from 'vue'
import { authApi } from '../api/auth'

const companies = ref<Array<any>>([])
const error = ref('')
const busy = ref<number | null>(null)

async function load() {
  try { companies.value = await authApi.adminCompanies() }
  catch (e: any) { error.value = e?.response?.data?.detail || String(e) }
}
load()

async function toggle(c: any) {
  busy.value = c.id
  try {
    await authApi.setCompanyActive(c.id, !c.is_active)
    await load()
  } catch (e: any) { error.value = e?.response?.data?.detail || String(e) }
  finally { busy.value = null }
}
</script>