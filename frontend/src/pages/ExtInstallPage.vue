<template>
  <div class="container-xxl page-ext-install">
    <h2 class="page-ext-install__title">Установка расширения-сборщика</h2>
    <p class="text-muted">Расширение живёт в вашем браузере и собирает карточки/выдачу WB (серверный сбор режет антибот). Ставит каждый сам — side-load, публикации в Store нет.</p>

    <div v-if="cid === null" class="alert alert-info">Выберите компанию в меню — токены и скачивание привязаны к ней. Статью читать можно уже сейчас.</div>
    <div class="row">
      <div class="col-lg-6">
        <ExtInstallGuide :companyId="companyId" />
      </div>
      <div class="col-lg-6">
        <ExtTokensBlock v-if="cid !== null" :companyId="cid" :guide-button="false" />
        <div ref="filtersRef">
          <ExtCategoryFilters v-if="cid !== null" :companyId="cid" />
        </div>
      </div>
    </div>

    <div class="alert alert-warning page-ext-install__note">
      Токен привязан к компании: сбор идёт только по своим карточкам, чужое отсекается.
      Не передавайте токен наружу — при утечке отзовите его выше и выдайте новый.
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-ext-install.css'
import { computed, ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import ExtTokensBlock from '../components/ext/ExtTokensBlock.vue'
import ExtCategoryFilters from '../components/ext/ExtCategoryFilters.vue'
import ExtInstallGuide from '../components/ext/ExtInstallGuide.vue'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const companyId = computed(() => auth.companyId)
const cid = computed(() => (auth.companyId === 'all' ? null : auth.companyId))
const filtersRef = ref<HTMLElement | null>(null)

// Пункт меню «Фильтры расширения» ведёт сюда же с ?block=filters — мотаем к блоку.
onMounted(() => {
  if (route.query.block === 'filters' && filtersRef.value) {
    setTimeout(() => filtersRef.value?.scrollIntoView({ block: 'start' }), 100)
  }
})
</script>
