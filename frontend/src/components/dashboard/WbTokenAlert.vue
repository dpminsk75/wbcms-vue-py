<template>
  <div v-if="items.length" class="page-dashboard__wb-alert alert" :class="alertClass" role="alert">
    <div class="page-dashboard__wb-alert-head">
      <i class="bi" :class="headIcon"></i>
      <span>{{ headText }}</span>
    </div>
    <ul class="page-dashboard__wb-alert-list">
      <li v-for="t in items" :key="t.company_id">
        <router-link :to="`/companies/${t.company_id}`">{{ t.company_name }}</router-link>
        <span> — до {{ fmtDate(t.exp_at) }} (осталось {{ t.days_left }} дн.)</span>
        <router-link :to="`/companies/${t.company_id}`" class="btn btn-sm btn-outline-secondary page-dashboard__wb-alert-btn">Обновить</router-link>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { authApi } from '../../api/auth'
import { useAuthStore } from '../../stores/auth'

interface Row { company_id: number; company_name: string; exp_at: string; days_left: number; is_readonly: boolean; last_check_at: string | null }

const auth = useAuthStore()
const items = ref<Row[]>([])

const fmtDate = (v: any) => v ? new Date(String(v).replace(' ', 'T')).toLocaleDateString('ru-RU') : '—'
const isGlobal = computed(() => auth.roles.includes('global_admin') || auth.roles.includes('admin') || auth.perms.includes('global_admin') || auth.perms.includes('admin'))
const anyExpired = computed(() => items.value.some((t) => t.days_left < 0))
const alertClass = computed(() => anyExpired.value ? 'alert-danger' : 'alert-warning')
const headIcon = computed(() => anyExpired.value ? 'bi-x-circle' : 'bi-exclamation-triangle')
const headText = computed(() => anyExpired.value ? 'WB-токен истёк — обновите, иначе сбор данных встанет' : 'WB-токен скоро заканчивается — обновите заранее')

onMounted(fetchAlert)
// Стор авторизации (роли/компании) может подтянуться позже маунта — перезапрашиваем тогда.
watch(() => [auth.roles.join(','), auth.perms.join(','), auth.companies.length], fetchAlert)

async function fetchAlert() {
  if (!auth.isAuth) return
  try {
    if (isGlobal.value) {
      items.value = await authApi.wbTokensExpiring(30)
    } else {
      // owner/admin компании: статусы своих компаний, показываем гнилые (<=30 дн. или просрочен)
      const rows: Row[] = []
      for (const c of auth.companies) {
        try {
          const s = await authApi.wbTokenStatus(c.id)
          if (s.has_token && s.valid && s.days_left != null && s.days_left <= 30) {
            rows.push({ company_id: c.id, company_name: c.name, exp_at: s.exp_at || '', days_left: s.days_left, is_readonly: !!s.is_readonly, last_check_at: s.checked_at || null })
          }
        } catch { /* нет доступа — пропускаем */ }
      }
      rows.sort((a, b) => a.days_left - b.days_left)
      items.value = rows
    }
  } catch { items.value = [] }
}
</script>
