<template>
  <div class="container-xxl page-marketing-expenses">
    <div class="d-flex justify-content-between align-items-start flex-wrap gap-2 mb-3">
      <div>
        <h1 class="page-title mb-1">Ручной маркетинг: площадки и расходы</h1>
        <div class="text-muted" style="font-size:12.5px">
          Площадки (блогеры/сайты) → документы расхода → позиции по SKU. Каждый расход привязан к товару.
          Excel: один лист, документы и позиции связаны <code>document_key</code>.
        </div>
      </div>
      <div class="d-flex align-items-center gap-2">
        <span class="badge badge--neutral">правки — manageSettings</span>
      </div>
    </div>

    <div v-if="!canManage" class="alert alert-info">
      Просмотр доступен (<code>viewFinance</code>), правки требуют <code>manageSettings</code>.
    </div>

    <div class="row g-3">
      <!-- Площадки -->
      <div class="col-12 col-xl-5">
        <div class="tbl-card">
          <div class="card__hd">
            <span>Площадки</span>
            <span class="spacer"></span>
            <button class="hd-btn" :disabled="!canManage" @click="openChannel()">
              <i class="bi bi-plus-lg me-1"></i>Площадка
            </button>
          </div>
          <div class="wb-filter-panel page-marketing-expenses__filter">
            <input v-model="chQuery" class="wb-input" placeholder="Поиск: название, ссылка, ИНН" @input="loadChannels">
          </div>
          <div class="tbl-wrap">
            <table class="tbl">
              <thead>
                <tr>
                  <th class="t-left">Площадка</th><th class="t-left">Тип</th><th class="t-left">Контакт</th>
                  <th class="t-right">Документов</th><th class="t-right">Сумма</th><th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="c in channels" :key="c.id" :class="{ 'page-marketing-expenses__row--archived': !c.is_active }">
                  <td class="t-left">{{ c.name }} <span v-if="!c.is_active" class="badge badge--neutral">в архиве</span></td>
                  <td class="t-left">{{ c.channel_type_label }}</td>
                  <td class="t-left">{{ c.website_or_contact || c.contact_name || '—' }}</td>
                  <td class="t-right num">{{ c.documents_cnt }}</td>
                  <td class="t-right num">{{ money(c.total_amount) }}</td>
                  <td class="t-right">
                    <button class="btn-link" :disabled="!canManage" @click="openChannel(c)">изм.</button>
                    <button class="btn-link" :disabled="!canManage" @click="removeChannel(c)">уд.</button>
                  </td>
                </tr>
                <tr v-if="!channels.length"><td colspan="6" class="text-center text-muted py-3">Площадок пока нет</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Документы -->
      <div class="col-12 col-xl-7">
        <div class="tbl-card">
          <div class="card__hd">
            <span>Документы расходов</span>
            <span class="spacer"></span>
            <button class="hd-btn" :disabled="!canManage" @click="openDocument()">
              <i class="bi bi-plus-lg me-1"></i>Документ
            </button>
          </div>
          <div class="wb-filter-panel page-marketing-expenses__filter">
            <div class="row g-2">
              <div class="col-auto"><input v-model="docFrom" class="wb-input" type="date" @change="loadDocuments"></div>
              <div class="col-auto"><input v-model="docTo" class="wb-input" type="date" @change="loadDocuments"></div>
              <div class="col-auto">
                <select v-model="docChannel" class="wb-select" @change="loadDocuments">
                  <option :value="null">Все площадки</option>
                  <option v-for="c in channels" :key="c.id" :value="c.id">{{ c.name }}</option>
                </select>
              </div>
              <div class="col-auto"><input v-model="docQuery" class="wb-input" placeholder="Поиск" @input="loadDocuments"></div>
            </div>
          </div>
          <div class="tbl-wrap">
            <table class="tbl">
              <thead>
                <tr>
                  <th class="t-left">Дата</th><th class="t-left">Документ</th><th class="t-left">Площадка</th>
                  <th class="t-left">Тип</th><th class="t-right">SKU</th><th class="t-right">Итог</th><th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="d in documents" :key="d.id">
                  <td class="t-left">{{ d.document_date }}</td>
                  <td class="t-left">{{ d.title }}<br><small class="text-muted">{{ d.document_key }}</small></td>
                  <td class="t-left">{{ d.channel_name || '—' }}</td>
                  <td class="t-left">{{ d.doc_type_label }}</td>
                  <td class="t-right num">{{ d.lines_cnt }}</td>
                  <td class="t-right num">{{ money(d.total_amount) }}</td>
                  <td class="t-right">
                    <button class="btn-link" @click="openDocument(d)">открыть</button>
                    <button class="btn-link" :disabled="!canManage" @click="removeDocument(d)">уд.</button>
                  </td>
                </tr>
                <tr v-if="!documents.length"><td colspan="7" class="text-center text-muted py-3">Документов пока нет</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Excel -->
      <div class="col-12">
        <div class="tbl-card">
          <div class="card__hd">
            <span>Excel: шаблон, выгрузка, загрузка</span>
            <span class="spacer"></span>
            <span class="hd-badge">1 лист</span>
          </div>
          <div class="card-body">
            <div class="page-marketing-expenses__excel">
              <button class="btn btn--outline" @click="downloadTemplate">
                <i class="bi bi-download me-1"></i>Скачать шаблон
              </button>
              <button class="btn btn--outline" @click="exportRows">
                <i class="bi bi-download me-1"></i>Скачать текущие записи
              </button>
              <label class="btn btn--brand page-marketing-expenses__file">
                <i class="bi bi-upload me-1"></i>Загрузить файл с расходами
                <input ref="fileRef" type="file" accept=".xlsx,.csv" hidden @change="onUpload">
              </label>
            </div>
            <div class="text-muted mt-2" style="font-size:12px">
              Колонки: <code>document_key</code>, <code>document_date</code>, <code>channel</code>, <code>doc_type</code>,
              <code>title</code>, <code>vendor_code</code>, <code>nm_id</code>, <code>amount</code>, <code>comment</code>.
              Несколько строк с одним <code>document_key</code> — позиции одного документа.
            </div>

            <div v-if="importMsg" class="alert alert-danger mt-3 mb-0">{{ importMsg }}</div>
            <div v-if="imp" class="mt-3">
              <div class="d-flex align-items-center gap-3 mb-2">
                <span>Разобрано документов: <b>{{ imp.documents.length }}</b></span>
                <span>строк принято: <b class="text-success">{{ imp.ok_rows }}</b></span>
                <span>ошибок: <b :class="imp.errors.length ? 'text-danger' : 'text-muted'">{{ imp.errors.length }}</b></span>
                <span class="spacer" style="margin-left:auto"></span>
                <button class="btn btn--brand btn-sm" :disabled="!canManage || !imp.documents.length" @click="saveImport">
                  Сохранить {{ imp.documents.length }} документов
                </button>
              </div>
              <div class="tbl-wrap mb-2">
                <table class="tbl">
                  <thead><tr><th class="t-left">Ключ</th><th class="t-left">Дата</th><th class="t-left">Площадка</th><th class="t-left">Тип</th><th class="t-left">Название</th><th class="t-right">SKU</th><th class="t-right">Итог</th><th class="t-left">Статус</th></tr></thead>
                  <tbody>
                    <tr v-for="d in imp.documents" :key="d.document_key">
                      <td class="t-left">{{ d.document_key }}</td>
                      <td class="t-left">{{ d.document_date }}</td>
                      <td class="t-left">{{ d.channel || '—' }}</td>
                      <td class="t-left">{{ d.doc_type }}</td>
                      <td class="t-left">{{ d.title }}</td>
                      <td class="t-right num">{{ d.lines.length }}</td>
                      <td class="t-right num">{{ money(d.total_amount) }}</td>
                      <td class="t-left">
                        <span v-if="d.channel_found" class="badge badge--ok">площадка найдена</span>
                        <span v-else class="badge badge--bad">площадка не найдена — заведите её заранее</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div v-if="imp.errors.length" class="tbl-wrap">
                <table class="tbl">
                  <thead><tr><th class="t-right">Строка</th><th class="t-left">Причина</th><th class="t-left">Как в файле</th></tr></thead>
                  <tbody>
                    <tr v-for="e in imp.errors" :key="e.row">
                      <td class="t-right num">{{ e.row }}</td>
                      <td class="t-left text-danger">{{ e.reason }}</td>
                      <td class="t-left">{{ e.raw }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Модалка площадки -->
    <div v-if="chModal" class="modal-backdrop fade show"></div>
    <div v-if="chModal" class="modal fade show d-block" tabindex="-1">
      <div class="modal-dialog modal-lg modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header"><h5 class="modal-title">{{ chForm.id ? 'Площадка' : 'Новая площадка' }}</h5><button class="btn-close" @click="chModal = false"></button></div>
          <div class="modal-body">
            <div class="row g-3">
              <div class="col-6"><div class="wb-field"><label class="wb-field__label">Название *</label><input v-model="chForm.name" class="wb-input"></div></div>
              <div class="col-6"><div class="wb-field"><label class="wb-field__label">Тип</label><select v-model="chForm.channel_type" class="wb-select"><option v-for="t in meta.channel_types" :key="t.value" :value="t.value">{{ t.label }}</option></select></div></div>
              <div class="col-12"><div class="wb-field"><label class="wb-field__label">Ссылка / @handle / почта</label><input v-model="chForm.website_or_contact" class="wb-input"></div></div>
              <div class="col-6"><div class="wb-field"><label class="wb-field__label">Контактное лицо</label><input v-model="chForm.contact_name" class="wb-input"></div></div>
              <div class="col-6"><div class="wb-field"><label class="wb-field__label">Телефон</label><input v-model="chForm.contact_phone" class="wb-input"></div></div>
              <div class="col-6"><div class="wb-field"><label class="wb-field__label">ИНН</label><input v-model="chForm.inn" class="wb-input"></div></div>
              <div class="col-6"><div class="wb-field"><label class="wb-field__label">Комментарий</label><input v-model="chForm.comment" class="wb-input"></div></div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn--outline" @click="chModal = false">Отмена</button>
            <button class="btn btn--brand" @click="saveChannel">Сохранить</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Модалка документа -->
    <div v-if="docModal" class="modal-backdrop fade show"></div>
    <div v-if="docModal" class="modal fade show d-block" tabindex="-1">
      <div class="modal-dialog modal-xl modal-dialog-centered modal-dialog-scrollable">
        <div class="modal-content">
          <div class="modal-header"><h5 class="modal-title">{{ docForm.id ? 'Документ расхода' : 'Новый документ расхода' }}</h5><button class="btn-close" @click="docModal = false"></button></div>
          <div class="modal-body">
            <div class="row g-3 mb-3">
              <div class="col-4"><div class="wb-field"><label class="wb-field__label">Дата *</label><input v-model="docForm.document_date" class="wb-input" type="date"></div></div>
              <div class="col-4"><div class="wb-field"><label class="wb-field__label">Тип *</label><select v-model="docForm.doc_type" class="wb-select"><option v-for="t in meta.doc_types" :key="t.value" :value="t.value">{{ t.label }}</option></select></div></div>
              <div class="col-4"><div class="wb-field"><label class="wb-field__label">Площадка *</label><select v-model="docForm.channel_id" class="wb-select"><option :value="null">— выберите —</option><option v-for="c in channels" :key="c.id" :value="c.id">{{ c.name }}</option></select></div></div>
              <div class="col-4"><div class="wb-field"><label class="wb-field__label">Название *</label><input v-model="docForm.title" class="wb-input" placeholder="Например: Telegram-подборка ноября"></div></div>
              <div class="col-4"><div class="wb-field"><label class="wb-field__label">document_key</label><input v-model="docForm.document_key" class="wb-input" placeholder="если пусто — сгенерируем"></div></div>
              <div class="col-4"><div class="wb-field"><label class="wb-field__label">Комментарий</label><input v-model="docForm.comment" class="wb-input"></div></div>
            </div>

            <div class="d-flex justify-content-between align-items-center mb-2">
              <b>Позиции (всегда с SKU)</b>
              <button class="btn btn--outline btn-sm" @click="addLine"><i class="bi bi-plus-lg me-1"></i>Строка</button>
            </div>
            <div class="tbl-wrap mb-2">
              <table class="tbl">
                <thead><tr><th class="t-left">SKU / артикул</th><th class="t-left">Товар</th><th class="t-right">Сумма</th><th class="t-left">Комментарий</th><th></th></tr></thead>
                <tbody>
                  <tr v-for="(ln, i) in docForm.lines" :key="i">
                    <td class="t-left">
                      <input v-model="ln.vendor_code" class="wb-input" placeholder="артикул или nmID" @input="lookupCard(ln)">
                      <div v-if="ln.nm_id" class="text-muted" style="font-size:11px">nmID {{ ln.nm_id }}</div>
                    </td>
                    <td class="t-left">{{ ln.product_title || '—' }}</td>
                    <td class="t-right"><input v-model.number="ln.amount" class="wb-input page-marketing-expenses__amount" type="number" min="0" step="0.01"></td>
                    <td class="t-left"><input v-model="ln.comment" class="wb-input"></td>
                    <td class="t-right"><button class="btn-link" @click="docForm.lines.splice(i, 1)">✕</button></td>
                  </tr>
                  <tr v-if="!docForm.lines.length"><td colspan="5" class="text-center text-muted py-3">Добавьте позиции</td></tr>
                </tbody>
              </table>
            </div>
            <div class="d-flex justify-content-between">
              <span class="text-muted" style="font-size:12px">Сумма документа = сумма позиций. Позиция без SKU не сохранится.</span>
              <b>{{ money(docTotal) }}</b>
            </div>
            <div v-if="docMsg" class="alert alert-danger mt-2 mb-0">{{ docMsg }}</div>
          </div>
          <div class="modal-footer">
            <button class="btn btn--outline" @click="docModal = false">Отмена</button>
            <button class="btn btn--brand" @click="saveDocument">Сохранить</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-marketing-expenses.css'
import { computed, onMounted, ref } from 'vue'
import { marketingApi, type MarketingDocument, type MarketingImportPreview } from '@/api/marketing'
import { useAuthStore } from '@/stores/auth'
import { exportXlsx } from '@/utils/exportXlsx'

const auth = useAuthStore()
// v3: перм manageSettings (у owner/admin компании он выдаётся автоматически).
// legacy (AUTH_V3=0): перма нет — правят владельцы/админы компании.
const canManage = computed(() => auth.can('manageSettings') || (!auth.authV3 && auth.managesAny))

const meta = ref<{ channel_types: { value: string; label: string }[]; doc_types: { value: string; label: string }[]; xlsx_columns: string[] }>(
  { channel_types: [], doc_types: [], xlsx_columns: [] })

const channels = ref<any[]>([])
const documents = ref<MarketingDocument[]>([])
const chQuery = ref('')
const docFrom = ref(new Date(Date.now() - 30 * 864e5).toISOString().slice(0, 10))
const docTo = ref(new Date().toISOString().slice(0, 10))
const docChannel = ref<number | null>(null)
const docQuery = ref('')

const chModal = ref(false)
const chForm = ref<any>({ id: null, name: '', channel_type: 'blogger', website_or_contact: '', contact_name: '', contact_phone: '', inn: '', comment: '' })

const docModal = ref(false)
const docForm = ref<any>({ id: null, document_key: '', document_date: new Date().toISOString().slice(0, 10), channel_id: null, doc_type: 'blogger_post', title: '', comment: '', lines: [] as any[] })
const docMsg = ref('')

const fileRef = ref<HTMLInputElement | null>(null)
const imp = ref<MarketingImportPreview | null>(null)
const importMsg = ref('')

const docTotal = computed(() => (docForm.value.lines || []).reduce((s: number, l: any) => s + Number(l.amount || 0), 0))

function money(v: number) {
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(Number(v || 0)) + ' ₽'
}

async function loadChannels() {
  channels.value = await marketingApi.channels(chQuery.value).catch(() => [])
}
async function loadDocuments() {
  documents.value = await marketingApi.documents({
    date_from: docFrom.value, date_to: docTo.value,
    channel_id: docChannel.value, q: docQuery.value,
  }).catch(() => [])
}

function openChannel(c?: any) {
  chForm.value = c
    ? { ...c }
    : { id: null, name: '', channel_type: 'blogger', website_or_contact: '', contact_name: '', contact_phone: '', inn: '', comment: '' }
  chModal.value = true
}
async function saveChannel() {
  const payload: any = { ...chForm.value }
  if (payload.id) await marketingApi.updateChannel(payload.id, payload)
  else await marketingApi.createChannel(payload)
  chModal.value = false
  await loadChannels()
}
async function removeChannel(c: any) {
  if (!confirm(`Удалить площадку «${c.name}»? Если по ней есть документы — она уйдёт в архив.`)) return
  const res = await marketingApi.deleteChannel(c.id)
  if (res?.archived) alert(res.message || 'Площадка архивирована')
  await loadChannels()
}

function openDocument(d?: any) {
  docMsg.value = ''
  if (d?.id) {
    marketingApi.document(d.id).then((full) => {
      docForm.value = {
        id: full.id, document_key: full.document_key, document_date: full.document_date,
        channel_id: full.channel_id, doc_type: full.doc_type, title: full.title,
        comment: full.comment || '', lines: (full.lines || []).map((l: any) => ({ ...l })),
      }
      docModal.value = true
    })
    return
  }
  docForm.value = {
    id: null, document_key: '', document_date: new Date().toISOString().slice(0, 10),
    channel_id: null, doc_type: 'blogger_post', title: '', comment: '',
    lines: [{ vendor_code: '', nm_id: null, product_title: '', amount: 0, comment: '' }],
  }
  docModal.value = true
}
function addLine() {
  docForm.value.lines.push({ vendor_code: '', nm_id: null, product_title: '', amount: 0, comment: '' })
}
async function lookupCard(ln: any) {
  const q = String(ln.vendor_code || '').trim()
  if (!q || /^\d+$/.test(q)) return
  const rows = await marketingApi.searchCards(q, 5).catch(() => [])
  if (rows.length === 1) {
    ln.nm_id = rows[0].nm_id
    ln.vendor_code = rows[0].vendor_code
    ln.product_title = rows[0].title
  }
}
async function saveDocument() {
  docMsg.value = ''
  const lines = (docForm.value.lines || []).filter((l: any) => l.nm_id || String(l.vendor_code || '').trim())
  if (!docForm.value.title.trim()) { docMsg.value = 'Укажите название документа.'; return }
  if (!docForm.value.channel_id) { docMsg.value = 'Выберите площадку.'; return }
  if (!lines.length) { docMsg.value = 'Добавьте хотя бы одну позицию с SKU.'; return }
  const payload: any = { ...docForm.value, lines }
  try {
    if (docForm.value.id) await marketingApi.updateDocument(docForm.value.id, payload)
    else await marketingApi.createDocument(payload)
    docModal.value = false
    await Promise.all([loadChannels(), loadDocuments()])
  } catch (e: any) {
    docMsg.value = e?.response?.data?.detail || e?.message || String(e)
  }
}
async function removeDocument(d: any) {
  if (!confirm(`Удалить документ «${d.title}»?`)) return
  await marketingApi.deleteDocument(d.id)
  await Promise.all([loadChannels(), loadDocuments()])
}

async function downloadTemplate() {
  const cols = meta.value.xlsx_columns.length ? meta.value.xlsx_columns
    : ['document_key', 'document_date', 'channel', 'doc_type', 'title', 'vendor_code', 'nm_id', 'amount', 'comment']
  const rows = [Object.fromEntries(cols.map((c: string) => [c, ''])), {
    document_key: 'M-001', document_date: '2026-11-01', channel: 'CoffeeBlog', doc_type: 'blogger_post',
    title: 'Telegram-подборка', vendor_code: 'WBC-1001', nm_id: '214000001', amount: '5000.00', comment: 'пример',
  }]
  await exportXlsx({ rows, filename: 'шаблон-маркетинговых-расходов.xlsx', sheetName: 'Расходы' })
}
async function exportRows() {
  const rows = await marketingApi.exportRows({ date_from: docFrom.value, date_to: docTo.value, channel_id: docChannel.value })
  await exportXlsx({
    rows: rows.map((r: any) => ({
      document_key: r.document_key, document_date: r.document_date, channel: r.channel,
      doc_type: r.doc_type, title: r.title, vendor_code: r.vendor_code, nm_id: r.nm_id,
      amount: r.amount, comment: r.comment || '',
    })),
    filename: 'маркетинговые-расходы.xlsx', sheetName: 'Расходы',
  })
}
async function onUpload() {
  const file = fileRef.value?.files?.[0]
  imp.value = null
  importMsg.value = ''
  if (!file) return
  try {
    const XLSX = await import('xlsx')
    const buf = await file.arrayBuffer()
    const wb = XLSX.read(buf, { type: 'array' })
    const ws = wb.Sheets[wb.SheetNames[0]]
    const grid: any[][] = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' })
    imp.value = await marketingApi.importPreview(grid)
  } catch (e: any) {
    importMsg.value = e?.response?.data?.detail || e?.message || String(e)
  }
}
async function saveImport() {
  if (!imp.value) return
  try {
    const res = await marketingApi.importSave(imp.value.documents)
    await Promise.all([loadChannels(), loadDocuments()])
    imp.value = null
    alert(`Сохранено документов: ${res.saved}. Пропущено: ${res.skipped}.`)
  } catch (e: any) {
    importMsg.value = e?.response?.data?.detail || e?.message || String(e)
  }
}

onMounted(async () => {
  meta.value = await marketingApi.meta().catch(() => meta.value)
  await Promise.all([loadChannels(), loadDocuments()])
})
</script>
