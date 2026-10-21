<template>
  <div class="container-xxl page-competitor page-captured">
    <div class="page-captured__head">
      <h2 class="page-competitor__title">Собранные карточки</h2>
      <router-link to="/competitor/new-cards" class="btn btn-sm btn-outline-secondary">
        <i class="bi bi-box"></i> Новые карточки
      </router-link>
    </div>
    <p class="text-muted">
      Контент конкурентов, который расширение собрало в общую базу. Авто-сбор ничего не привязывает:
      привязка, отвязка и скрытие — только отсюда.
    </p>

    <div class="page-captured__toolbar">
      <input
        v-model="q"
        class="form-control form-control-sm page-captured__search"
        placeholder="Название, бренд, продавец, nmID"
        @keyup.enter="load"
      />
      <button class="btn btn-sm btn-primary" :disabled="loading" @click="load">
        <i class="bi bi-search"></i> Найти
      </button>
      <button class="btn btn-sm btn-outline-secondary" :disabled="loading" @click="reset">Сброс</button>
      <label class="page-captured__check">
        <input v-model="includeHidden" type="checkbox" @change="load()" />
        показать скрытые
      </label>
      <span class="badge bg-secondary">Карточек: {{ rows.length }}</span>
    </div>

    <div v-if="error" class="wb-error">{{ error }}</div>
    <div v-if="notice" class="page-captured__notice">{{ notice }}</div>

    <div v-if="loading" class="text-muted">
      <span class="spinner-border spinner-border-sm"></span> Загрузка…
    </div>

    <div v-else-if="!rows.length" class="alert alert-info">
      Пока ничего не собрано. Откройте карточку конкурента на WB — расширение пришлёт контент автоматически.
    </div>

    <table v-else class="wb-admin-table page-captured__grid">
      <thead>
        <tr>
          <th class="page-captured__col-product">Товар</th>
          <th class="text-center page-captured__col-num" title="Длина описания">Описание</th>
          <th class="text-center page-captured__col-num" title="Количество характеристик">Хар-ки</th>
          <th class="page-captured__col-date" title="Когда контент собран последний раз">Собрано</th>
          <th class="page-captured__col-date" title="Когда карточка впервые попала в базу">В базе с</th>
          <th class="text-center page-captured__col-num" title="Снимков с изменённым контентом">Изменений</th>
          <th class="page-captured__col-attach">Привязка</th>
          <th class="page-competitor__col-actions">Действия</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.nm_id" :class="{ 'page-captured__row--hidden': r.is_hidden }">
          <td>
            <div class="page-competitor__product">
              <img :src="r.photo || '/images/no-photo.png'" alt="" class="page-competitor__thumb" loading="lazy" />
              <div class="page-competitor__product-text">
                <div class="page-competitor__product-title" :title="r.title || ''">{{ r.title || '—' }}</div>
                <div class="page-competitor__product-sub">
                  <a :href="wbUrl(r)" target="_blank" rel="noopener" class="page-competitor__wb-link">WB: {{ r.nm_id }}</a>
                  <span v-if="r.brand"> · {{ r.brand }}</span>
                  <span v-if="r.seller && r.seller !== r.brand"> · {{ r.seller }}</span>
                  <span v-if="r.price"> · {{ r.price }} ₽</span>
                </div>
                <div class="page-captured__badges">
                  <span v-if="r.is_own" class="badge bg-warning text-dark" title="nm есть в wbcards нашей компании">наша карточка</span>
                  <span v-if="r.is_hidden" class="badge bg-secondary">скрыта</span>
                  <span v-if="r.companies_cnt > 1" class="badge bg-light text-dark" :title="`видна компаниям: ${r.companies_cnt}`">компаний: {{ r.companies_cnt }}</span>
                </div>
              </div>
            </div>
          </td>
          <td class="text-center">
            <span class="badge" :class="r.desc_len ? 'bg-success' : 'bg-danger'">{{ r.desc_len }}</span>
          </td>
          <td class="text-center">
            <span class="badge" :class="r.chars_cnt ? 'bg-success' : 'bg-danger'">{{ r.chars_cnt }}</span>
          </td>
          <td class="page-captured__date" :title="fmtFull(r.collected_at)">{{ fmtAgo(r.collected_at) }}</td>
          <td class="page-captured__date" :title="fmtFull(r.first_seen_at)">{{ fmtDate(r.first_seen_at) }}</td>
          <td class="text-center">
            <button
              v-if="r.history_cnt"
              class="btn btn-link btn-sm page-captured__hist-btn"
              :title="`Снимков: ${r.history_cnt}`"
              @click="openHistory(r)"
            >{{ r.history_cnt }}</button>
            <span v-else class="page-competitor__dash">—</span>
          </td>
          <td class="page-captured__attach">
            <div v-if="r.attached_cnt" class="page-captured__attach-tags">
              <a
                v-for="a in r.attached"
                :key="a.nm_id"
                :href="`/wb/detail?nm_id=${a.nm_id}`"
                target="_blank"
                class="badge bg-primary page-captured__attach-tag"
                :title="a.title || ''"
              >{{ a.nm_id }}</a>
            </div>
            <span v-else class="text-muted small">не привязан</span>
          </td>
          <td class="page-competitor__actions">
            <button class="btn btn-sm btn-outline-primary" :disabled="busy === r.nm_id" @click="openAttach(r)">
              <i class="bi bi-link-45deg"></i> Привязать
            </button>
            <button class="btn btn-sm btn-outline-secondary" @click="openHistory(r)">
              <i class="bi bi-clock-history"></i> История
            </button>
            <button
              class="btn btn-sm"
              :class="r.is_hidden ? 'btn-outline-success' : 'btn-outline-warning'"
              :disabled="busy === r.nm_id"
              @click="toggleHidden(r)"
            >
              <i class="bi" :class="r.is_hidden ? 'bi-eye' : 'bi-eye-slash'"></i>
              {{ r.is_hidden ? 'Вернуть' : 'Скрыть' }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>

    <CompetitorAttachModal
      :open="attachOpen"
      :nm-id="active?.nm_id"
      :title="active?.title"
      :attached="active?.attached || []"
      @close="attachOpen = false"
      @changed="reloadCurrent"
    />

    <CompetitorHistoryModal
      :open="historyOpen"
      :nm-id="active?.nm_id"
      @close="historyOpen = false"
    />
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-competitor.css'
import '@/assets/css/pages/page-competitor-captured.css'
import { ref, onMounted } from 'vue'
import { competitorsNewcardApi, type CapturedRow } from '../api/competitorsNewcard'
import CompetitorAttachModal from '../components/competitors/CompetitorAttachModal.vue'
import CompetitorHistoryModal from '../components/competitors/CompetitorHistoryModal.vue'

const rows = ref<CapturedRow[]>([])
const q = ref('')
const includeHidden = ref(false)
const loading = ref(false)
const error = ref('')
const notice = ref('')
const busy = ref<number | null>(null)

const active = ref<CapturedRow | null>(null)
const attachOpen = ref(false)
const historyOpen = ref(false)

async function load(silent = false) {
  if (!silent) loading.value = true
  error.value = ''
  try {
    const d = await competitorsNewcardApi.captured(q.value.trim(), includeHidden.value, 300)
    rows.value = d.items || []
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
    rows.value = []
  } finally {
    loading.value = false
  }
}

async function reloadCurrent() {
  const id = active.value?.nm_id
  await load(true)
  if (id) active.value = rows.value.find((r) => r.nm_id === id) || active.value
}

function reset() {
  q.value = ''
  includeHidden.value = false
  load()
}

function wbUrl(r: CapturedRow): string {
  return r.url || `https://www.wildberries.ru/catalog/${r.nm_id}/detail.aspx`
}

function fmtAgo(v?: string | null): string {
  if (!v) return '—'
  const t = new Date(v).getTime()
  if (!isFinite(t)) return String(v)
  const m = Math.round((Date.now() - t) / 60000)
  if (m < 1) return 'только что'
  if (m < 60) return `${m} мин назад`
  const h = Math.round(m / 60)
  if (h < 24) return `${h} ч назад`
  const d = Math.round(h / 24)
  if (d < 30) return `${d} дн назад`
  return new Date(v).toLocaleDateString('ru-RU')
}

function fmtDate(v?: string | null): string {
  if (!v) return '—'
  const d = new Date(v)
  return isFinite(d.getTime()) ? d.toLocaleDateString('ru-RU') : String(v)
}

function fmtFull(v?: string | null): string {
  if (!v) return '—'
  const d = new Date(v)
  return isFinite(d.getTime()) ? d.toLocaleString('ru-RU') : String(v)
}

function openAttach(r: CapturedRow) {
  active.value = r
  attachOpen.value = true
}

function openHistory(r: CapturedRow) {
  active.value = r
  historyOpen.value = true
}

async function toggleHidden(r: CapturedRow) {
  if (busy.value) return
  busy.value = r.nm_id
  error.value = ''
  notice.value = ''
  try {
    const next = !r.is_hidden
    await competitorsNewcardApi.hideCaptured(r.nm_id, next)
    notice.value = next ? `Скрыто: ${r.nm_id}` : `Возвращено: ${r.nm_id}`
    await load(true)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось изменить видимость'
  } finally {
    busy.value = null
  }
}

onMounted(() => load())
</script>
