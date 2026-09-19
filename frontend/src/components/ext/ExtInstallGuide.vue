<template>
  <div>
    <div v-if="error" class="wb-error">{{ error }}</div>
    <ol class="mb-0">
      <li>
        <strong>Выдайте токен</strong> (кнопка ниже или блок «Токены расширения») и скопируйте его — показывается один раз.
      </li>
      <li>
        <strong>Скачайте zip</strong> (адрес сервера уже вшит)
        <span v-if="companyId !== 'all'">
          <button @click="onDownload" :disabled="downloading" class="btn btn-sm btn-outline-primary ms-1">
            <i class="bi bi-download"></i> {{ downloading ? 'Готовлю…' : 'Скачать' }}
          </button>
        </span>
        <span v-else> (сначала выберите компанию в меню).</span>
      </li>
      <li><strong>Распакуйте</strong> zip в постоянную папку (не во временную — Chrome ссылается на неё).</li>
      <li>
        Откройте <code>chrome://extensions</code>, включите <strong>«Режим разработчика»</strong>
        и нажмите <strong>«Загрузить распакованное расширение»</strong> — выберите папку из шага 3.
      </li>
      <li>
        Откройте popup расширения (иконка в панели), проверьте <strong>адрес</strong>
        (<code>{{ serverBase }}</code>), вставьте <strong>токен</strong> из шага 1 и нажмите <strong>ОК</strong>.
        Без токена статусы скажут «Нет доступа».
      </li>
      <li>
        Введите <strong>source nmID</strong> своего товара, нажмите <strong>«Очередь»</strong> —
        должны появиться цифры, затем <strong>«Старт»/«Поиск»</strong>.
      </li>
      <li>Обновление — скачать zip заново и нажать «Обновить» на карточке расширения. Токен не слетает.</li>
    </ol>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { extTokensApi } from '../../api/extTokens'

const props = defineProps<{ companyId: number | 'all' }>()

const downloading = ref(false)
const error = ref('')
// Бэк расширения висит на том же хосте, порт 8000 (см. EXT_PUBLIC_BASE на сервере).
const serverBase = computed(() => `${location.protocol}//${location.hostname}:8000`)

async function onDownload() {
  if (props.companyId === 'all') return
  downloading.value = true
  error.value = ''
  try {
    await extTokensApi.download(props.companyId)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    downloading.value = false
  }
}
</script>
