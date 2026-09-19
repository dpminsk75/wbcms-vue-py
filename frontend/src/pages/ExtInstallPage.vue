<template>
  <div class="container-xxl page-ext-install">
    <h2 class="page-ext-install__title">Установка расширения-сборщика</h2>
    <p class="text-muted">Расширение живёт в вашем браузере и собирает карточки/выдачу WB (серверный сбор режет антибот). Ставит каждый сам — side-load, публикации в Store нет.</p>

    <div v-if="cid === null" class="alert alert-info">Выберите компанию в меню — токены и скачивание привязаны к ней. Шаги ниже читать можно уже сейчас.</div>
    <ExtTokensBlock v-else :companyId="cid" />

    <h3 class="mt-4">Шаги установки</h3>
    <ExtInstallGuide :companyId="companyId" />

    <div class="alert alert-warning page-ext-install__note">
      Токен привязан к компании: сбор идёт только по своим карточкам, чужое отсекается.
      Не передавайте токен наружу — при утечке отзовите его выше и выдайте новый.
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-ext-install.css'
import { computed } from 'vue'
import ExtTokensBlock from '../components/ext/ExtTokensBlock.vue'
import ExtInstallGuide from '../components/ext/ExtInstallGuide.vue'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const companyId = computed(() => auth.companyId)
const cid = computed(() => (auth.companyId === 'all' ? null : auth.companyId))
</script>
