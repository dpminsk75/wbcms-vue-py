<template>
  <div class="container-xxl page-ext-diag">
    <h2 class="page-ext-diag__title">Диагностика расширения</h2>
    <p class="text-muted">Слепки карточек WB («чёрный ящик» на смену вёрстки). Пишет расширение, читаем без ssh.</p>

    <div v-if="error" class="wb-error">{{ error }}</div>
    <div v-if="companyId === 'all'" class="alert alert-info">Выберите компанию в меню — слепки хранятся по компаниям.</div>
    <div v-else-if="loading" class="text-muted">Загрузка…</div>
    <div v-else-if="!rows.length" class="alert alert-info">Слепков пока нет — расширение ещё не присылало диагностику.</div>
    <table v-else class="wb-admin-table page-ext-diag__grid">
      <thead>
        <tr>
          <th>nmID</th>
          <th class="text-center">h2</th>
          <th class="text-center">Секции</th>
          <th class="text-center">Ссылки каталога</th>
          <th class="text-center">Попап-карточки</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.nm_id">
          <td>
            <a :href="`/wb/detail?nm_id=${r.nm_id}`" target="_blank" class="page-ext-diag__wb-link">WB: {{ r.nm_id }}</a>
          </td>
          <td class="text-center">{{ r.h2_count }}</td>
          <td class="text-center">{{ r.sections_count }}</td>
          <td class="text-center">{{ r.catalog_links }}</td>
          <td class="text-center">{{ r.popup_cards }}</td>
          <td><button @click="openDetail(r.nm_id)" class="btn btn-sm btn-outline-secondary"><i class="bi bi-eye"></i> Смотреть</button></td>
        </tr>
      </tbody>
    </table>

    <div v-if="detail" class="page-ext-diag__detail">
      <h3 class="page-ext-diag__detail-title">Слепок {{ detail.nm_id }}</h3>
      <div class="page-ext-diag__meta">
        <span v-if="detail.brand"><strong>Бренд:</strong> {{ detail.brand }}</span>
        <span v-if="detail.seller"><strong>Продавец:</strong> {{ detail.seller }}</span>
        <span v-if="detail.url" class="page-ext-diag__url">{{ detail.url }}</span>
      </div>
      <div class="wb-table-wrap">
        <table class="wb-admin-table page-ext-diag__checks">
          <thead>
            <tr><th>Селектор</th><th class="text-center">Статус</th><th>Что нашлось</th></tr>
          </thead>
          <tbody>
            <tr v-for="c in checks" :key="c.sel">
              <td><code>{{ c.sel }}</code></td>
              <td class="text-center">
                <span v-if="c.ok" class="badge bg-success">нашлось</span>
                <span v-else class="badge bg-danger">пусто</span>
              </td>
              <td>{{ c.found }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <details class="page-ext-diag__block">
        <summary>Все h2 ({{ (detail.h2 || []).length }})</summary>
        <ul class="page-ext-diag__list">
          <li v-for="(h, i) in (detail.h2 || [])" :key="i"><code>{{ h.class }}</code> — {{ h.text }}</li>
        </ul>
      </details>
      <details class="page-ext-diag__block">
        <summary>Секции ({{ (detail.sections || []).length }})</summary>
        <ul class="page-ext-diag__list">
          <li v-for="(s, i) in (detail.sections || [])" :key="i"><code>#{{ s.id }}</code> <span class="text-muted">{{ s.class }}</span> — {{ s.text }}</li>
        </ul>
      </details>
      <details class="page-ext-diag__block">
        <summary>Ссылки каталога ({{ (detail.catalogLinks || []).length }})</summary>
        <ul class="page-ext-diag__list">
          <li v-for="(l, i) in (detail.catalogLinks || [])" :key="i">nmID {{ l.nmId }} <span class="text-muted">{{ l.class }} ← {{ l.parentClass }}</span></li>
        </ul>
      </details>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-ext-diag.css'
import { ref, computed, onMounted, watch } from 'vue'
import { extTokensApi, type ExtDiagSummary } from '../api/extTokens'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const companyId = computed(() => auth.companyId)
const rows = ref<ExtDiagSummary[]>([])
const loading = ref(false)
const error = ref('')
const detail = ref<any | null>(null)

async function load() {
  detail.value = null
  if (companyId.value === 'all') { rows.value = []; return }
  loading.value = true
  error.value = ''
  try {
    rows.value = await extTokensApi.diagList(companyId.value)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    loading.value = false
  }
}

async function openDetail(nmId: number | null) {
  if (nmId == null || companyId.value === 'all') return
  error.value = ''
  try {
    detail.value = await extTokensApi.diagView(companyId.value, nmId)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  }
}

// Карточки «селектор → нашлось/пусто»: ключевые точки, от которых зависит сбор.
const checks = computed(() => {
  const d = detail.value
  if (!d) return [] as Array<{ sel: string; ok: boolean; found: string }>
  const h2: any[] = d.h2 || []
  const title = h2.find((h) => String(h.class || '').includes('productTitle'))
  const desc = d.descriptionSection || {}
  const chars = d.charsSection || {}
  return [
    { sel: 'h2[class*="productTitle"]', ok: !!title, found: title ? title.text : '—' },
    { sel: 'бренд (sellerAndBrandItemName / productHeaderBrand)', ok: !!d.brand, found: d.brand || '—' },
    { sel: 'продавец', ok: !!d.seller, found: d.seller || '—' },
    { sel: '#section-description', ok: !!desc.exists, found: desc.exists ? (desc.visible ? 'виден' : 'скрыт') + (desc.text ? ` — ${desc.text}` : '') : '—' },
    { sel: '#section-characteristics', ok: !!chars.exists, found: chars.exists ? (chars.text || 'есть') : '—' },
    { sel: 'a[href*="/catalog/"]', ok: (d.catalogLinks || []).length > 0, found: `${(d.catalogLinks || []).length} ссылок` },
    { sel: '[data-popup-nm-id]', ok: (d.popupCards || []).length > 0, found: `${(d.popupCards || []).length} карточек` },
    { sel: 'миниатюры (miniaturesWrapper / swiper)', ok: (d.images || []).length > 0, found: `${(d.images || []).length} фото` },
  ]
})

onMounted(load)
watch(companyId, load)
</script>
