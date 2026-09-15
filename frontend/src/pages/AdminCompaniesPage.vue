<template>
  <div class="container-xxl" style="padding:20px 15px">
    <h2 style="margin-bottom:16px">Компании (админ)</h2>
    <div v-if="error" style="color:#c00">{{ error }}</div>
    <table style="width:100%; border-collapse:collapse">
      <thead>
        <tr style="background:#f4f4f8">
          <th style="text-align:left; padding:8px">ID</th>
          <th style="text-align:left; padding:8px">Название</th>
          <th style="text-align:left; padding:8px">Аббревиатура</th>
          <th style="text-align:left; padding:8px">ИНН</th>
          <th style="text-align:left; padding:8px">Членов</th>
          <th style="text-align:left; padding:8px">Активна</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="c in companies" :key="c.id" style="border-bottom:1px solid #eee">
          <td style="padding:8px">{{ c.id }}</td>
          <td style="padding:8px">{{ c.name }}</td>
          <td style="padding:8px">{{ c.abbreviation || '—' }}</td>
          <td style="padding:8px">{{ c.inn || '—' }}</td>
          <td style="padding:8px">{{ c.members_count }}</td>
          <td style="padding:8px">{{ c.is_active ? 'Да' : 'Нет' }}</td>
          <td style="padding:8px">
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