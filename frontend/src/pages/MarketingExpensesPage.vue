<template>
  <div class="container-xxl page-marketing-expenses">
    <!-- Заголовок страницы (h1) + вкладки раздела -->
    <h1 class="wsp__title page-marketing-expenses__title">Маркетинг</h1>

    <!-- Вкладки раздела: Документы / Площадки -->
    <WbSectionTabs v-model="tab" :tabs="tabs" class="mb-3" />

    <div v-if="!canManage" class="wb-panel page-marketing-expenses__alert mb-3">
      <div class="wb-panel__bd">
        <span class="badge badge--warn">viewFinance</span>
        Просмотр доступен, правки требуют права <code>manageSettings</code>.
      </div>
    </div>

    <!-- ==================== 1. ДОКУМЕНТЫ ==================== -->
    <template v-if="tab === 'documents'">
      <!-- Фильтр: WbDateRangeFilter (bare) + поля страницы в слоте inline + кнопки отчёта -->
      <div class="wb-filter-panel mb-3">
        <WbDateRangeFilter
          v-model:from="docFrom"
          v-model:to="docTo"
          default-preset="30"
          bare
          @apply="onDates"
        >
          <template #inline>
            <div class="row g-2">
              <div class="col-md-4">
                <div class="wb-field">
                  <label class="wb-field__label">Площадка</label>
                  <select v-model="docChannel" class="wb-select">
                    <option :value="null">Все площадки</option>
                    <option v-for="c in channels" :key="c.id" :value="c.id">{{ c.name }}</option>
                  </select>
                </div>
              </div>
              <div class="col-md-8">
                <div class="wb-field">
                  <label class="wb-field__label">Поиск</label>
                  <input
                    v-model="docQuery"
                    class="wb-input"
                    type="search"
                    placeholder="Название, document_key, SKU или nmId"
                  >
                </div>
              </div>
            </div>
          </template>
        </WbDateRangeFilter>
        <div class="wb-filter-panel__btns">
          <button class="btn btn--brand wb-filter-panel__apply" type="button" @click="loadDocuments">Применить</button>
          <button class="btn btn--outline wb-filter-panel__apply" type="button" @click="resetDocs">Сбросить</button>
        </div>
      </div>

      <div class="page-marketing-expenses__grid">
        <div>
          <!-- Excel: 2+ действия — дропдаун «Действия с Excel» (свой, без JS-бандла bootstrap) -->
          <div class="page-marketing-expenses__excel">
            <div class="page-marketing-expenses__excel-wrap" ref="docExcelRef">
              <button
                class="btn btn-light page-marketing-expenses__excel-btn"
                type="button"
                @click="docExcelOpen = !docExcelOpen"
              >
                Действия с Excel <i class="bi ms-1" :class="docExcelOpen ? 'bi-chevron-up' : 'bi-chevron-down'"></i>
              </button>
              <div v-if="docExcelOpen" class="page-marketing-expenses__excel-list">
                <button class="page-marketing-expenses__excel-item" type="button" @click="docExcelOpen = false; downloadTemplate()">
                  <i class="bi bi-file-earmark-spreadsheet me-2"></i>Скачать шаблон
                </button>
                <button class="page-marketing-expenses__excel-item" type="button" :disabled="!documents.length" @click="docExcelOpen = false; exportRows()">
                  <i class="bi bi-download me-2"></i>Скачать текущие записи
                </button>
                <button class="page-marketing-expenses__excel-item" type="button" @click="docExcelOpen = false; fileRef?.click()">
                  <i class="bi bi-upload me-2"></i>Загрузить файл
                </button>
              </div>
            </div>
          </div>
          <input ref="fileRef" type="file" accept=".xlsx,.csv" class="d-none" @change="onUpload">

          <div class="tbl-card">
            <div class="card__hd">
              Документы расходов
              <span class="hd-badge">{{ documents.length }} документов</span>
              <span class="spacer"></span>
              <button class="hd-btn" type="button" :disabled="!canManage" @click="openDocument()">
                <i class="bi bi-plus-lg me-1"></i>Новый документ
              </button>
            </div>
            <div class="tbl-wrap">
              <table class="tbl">
                <thead>
                  <tr>
                    <th class="t-left">Дата</th>
                    <th class="t-left">Документ</th>
                    <th class="t-left">Площадка</th>
                    <th class="t-left">Тип</th>
                    <th>Позиций</th>
                    <th>Итог</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="d in documents"
                    :key="d.id"
                    class="page-marketing-expenses__doc"
                    @click="selectDocument(d)"
                  >
                    <td class="t-left">{{ d.document_date }}</td>
                    <td class="t-left">
                      <div class="page-marketing-expenses__doc-name">{{ d.title }}</div>
                      <div class="page-marketing-expenses__doc-key">{{ d.document_key }}</div>
                    </td>
                    <td class="t-left">{{ d.channel_name || '—' }}</td>
                    <td class="t-left">{{ d.doc_type_label }}</td>
                    <td class="num">{{ d.lines_cnt }}</td>
                    <td class="num">{{ money(d.total_amount) }}</td>
                  </tr>
                  <tr v-if="!documents.length">
                    <td colspan="6" class="text-center text-muted py-3">Документов за период нет</td>
                  </tr>
                </tbody>
                <tfoot v-if="documents.length">
                  <tr class="tbl__total">
                    <td class="t-left">Итого</td>
                    <td colspan="3">{{ documents.length }} документов · {{ totalLines }} позиций</td>
                    <td class="num">{{ totalLines }}</td>
                    <td class="num">{{ money(totalAmount) }}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>

          <!-- Импорт Excel: превью (dry-run) до сохранения -->
          <div v-if="imp" class="tbl-card mt-3">
            <div class="card__hd">
              Превью загрузки
              <span class="hd-badge">ничего не записано</span>
              <span class="spacer"></span>
              <button class="btn btn--brand btn-sm" type="button" :disabled="!canManage || !imp.documents.length" @click="saveImport">
                Сохранить {{ imp.documents.length }} документов
              </button>
            </div>
            <div class="tbl-wrap">
              <table class="tbl">
                <thead>
                  <tr>
                    <th class="t-left">Ключ</th>
                    <th class="t-left">Дата</th>
                    <th class="t-left">Площадка</th>
                    <th class="t-left">Тип</th>
                    <th class="t-left">Название</th>
                    <th>SKU</th>
                    <th>Итог</th>
                    <th class="t-left">Статус</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="d in imp.documents" :key="d.document_key">
                    <td class="t-left">{{ d.document_key }}</td>
                    <td class="t-left">{{ d.document_date }}</td>
                    <td class="t-left">{{ d.channel || '—' }}</td>
                    <td class="t-left">{{ d.doc_type }}</td>
                    <td class="t-left">{{ d.title }}</td>
                    <td class="num">{{ d.lines.length }}</td>
                    <td class="num">{{ money(d.total_amount) }}</td>
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
                <thead>
                  <tr><th>Строка</th><th class="t-left">Причина</th><th class="t-left">Как в файле</th></tr>
                </thead>
                <tbody>
                  <tr v-for="e in imp.errors" :key="e.row">
                    <td class="num">{{ e.row }}</td>
                    <td class="t-left text-danger">{{ e.reason }}</td>
                    <td class="t-left">{{ e.raw }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <div v-if="importMsg" class="wb-panel page-marketing-expenses__alert mt-3">
            <div class="wb-panel__bd">
              <span class="badge badge--bad">Ошибка</span> {{ importMsg }}
            </div>
          </div>
        </div>

        <!-- Детали выбранного документа -->
        <aside class="wb-panel">
          <div class="card__hd">
            {{ selectedDoc ? selectedDoc.title : 'Документ не выбран' }}
            <span class="spacer"></span>
            <span v-if="selectedDoc" class="badge badge--neutral">{{ selectedDoc.channel_name || '—' }}</span>
          </div>
          <div class="wb-panel__bd">
            <template v-if="selectedDoc">
              <ul class="page-marketing-expenses__lines">
                <li v-for="l in selectedDoc.lines || []" :key="l.nm_id">
                  <span>{{ l.vendor_code || l.nm_id }} · nmID {{ l.nm_id }}</span>
                  <b>{{ money(l.amount) }}</b>
                </li>
              </ul>
              <div class="btn-row mt-3">
                <button class="btn btn--soft" type="button" :disabled="!canManage" @click="openDocument(selectedDoc)">Изменить</button>
                <button class="btn btn--danger" type="button" :disabled="!canManage" @click="removeDocument(selectedDoc)">Удалить</button>
              </div>
              <p class="page-marketing-expenses__hint mt-3 mb-0">
                Позиции привязаны к SKU: расход попадает в маржу по выбранным карточкам.
              </p>
            </template>
            <p v-else class="page-marketing-expenses__hint mb-0">Выберите документ в таблице — здесь появятся его позиции.</p>
          </div>
        </aside>
      </div>
    </template>

    <!-- ==================== 2. ПЛОЩАДКИ ==================== -->
    <template v-else>
      <div class="wb-filter-panel mb-3">
        <div class="row g-2 align-items-end">
          <div class="col-md-4">
            <div class="wb-field">
              <label class="wb-field__label">Поиск</label>
              <input v-model="chQuery" class="wb-input" type="search" placeholder="Название, ссылка или ИНН">
            </div>
          </div>
          <div class="col-md-3">
            <div class="wb-field">
              <label class="wb-field__label">Тип</label>
              <select v-model="chType" class="wb-select">
                <option value="">Все типы</option>
                <option v-for="t in meta.channel_types" :key="t.value" :value="t.value">{{ t.label }}</option>
              </select>
            </div>
          </div>
          <div class="col-md-3">
            <div class="wb-field">
              <label class="wb-field__label">Статус</label>
              <select v-model="chStatus" class="wb-select">
                <option value="active">Активные</option>
                <option value="archived">Архив</option>
                <option value="all">Все</option>
              </select>
            </div>
          </div>
        </div>
        <div class="wb-filter-panel__btns">
          <button class="btn btn--brand wb-filter-panel__apply" type="button" @click="loadChannels">Применить</button>
          <button class="btn btn--outline wb-filter-panel__apply" type="button" @click="resetChannels">Сбросить</button>
        </div>
      </div>

      <div class="page-marketing-expenses__excel">
        <div class="page-marketing-expenses__excel-wrap" ref="chExcelRef">
          <button
            class="btn btn-light page-marketing-expenses__excel-btn"
            type="button"
            @click="chExcelOpen = !chExcelOpen"
          >
            Действия с Excel <i class="bi ms-1" :class="chExcelOpen ? 'bi-chevron-up' : 'bi-chevron-down'"></i>
          </button>
          <div v-if="chExcelOpen" class="page-marketing-expenses__excel-list">
            <button class="page-marketing-expenses__excel-item" type="button" @click="chExcelOpen = false; exportChannels()">
              <i class="bi bi-download me-2"></i>Скачать текущие
            </button>
            <button class="page-marketing-expenses__excel-item" type="button" @click="chExcelOpen = false; downloadChannelsTemplate()">
              <i class="bi bi-file-earmark-spreadsheet me-2"></i>Скачать шаблон
            </button>
          </div>
        </div>
      </div>

      <div class="tbl-card">
        <div class="card__hd">
          Площадки
          <span class="hd-badge">{{ channels.length }} площадок</span>
          <span class="spacer"></span>
          <button class="hd-btn" type="button" :disabled="!canManage" @click="openChannel()">
            <i class="bi bi-plus-lg me-1"></i>Новая площадка
          </button>
        </div>
        <div class="tbl-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th class="t-left">Площадка</th>
                <th class="t-left">Тип</th>
                <th class="t-left">Контакт</th>
                <th class="t-left">ИНН</th>
                <th>Документов</th>
                <th>Сумма</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in channels" :key="c.id" :class="{ 'page-marketing-expenses__row--archived': !c.is_active }">
                <td class="t-left">
                  {{ c.name }}
                  <span v-if="!c.is_active" class="badge badge--neutral">в архиве</span>
                </td>
                <td class="t-left">{{ c.channel_type_label }}</td>
                <td class="t-left">{{ c.website_or_contact || c.contact_name || '—' }}</td>
                <td class="t-left">{{ c.inn || '—' }}</td>
                <td class="num">{{ c.documents_cnt }}</td>
                <td class="num">{{ money(c.total_amount) }}</td>
                <td class="t-right">
                  <button class="btn btn--ghost btn-sm" type="button" :disabled="!canManage" @click="openChannel(c)">
                    <i class="bi bi-pencil"></i>
                  </button>
                  <button class="btn btn--ghost btn-sm" type="button" :disabled="!canManage" @click="removeChannel(c)">
                    <i class="bi bi-trash"></i>
                  </button>
                </td>
              </tr>
              <tr v-if="!channels.length">
                <td colspan="7" class="text-center text-muted py-3">Площадок пока нет</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <!-- Модалка площадки -->
    <div v-if="chModal" class="wb-modal-backdrop" @click.self="chModal = false">
      <form class="wb-modal-box wb-modal-box--wide" @submit.prevent="saveChannel">
        <div class="d-flex align-items-center gap-2">
          <span class="page-marketing-expenses__modal-title">{{ chForm.id ? 'Площадка' : 'Новая площадка' }}</span>
          <button type="button" class="btn-close ms-auto" aria-label="Закрыть" @click="chModal = false"></button>
        </div>
        <div class="row g-3">
          <div class="col-6">
            <div class="wb-field">
              <label class="wb-field__label">Название *</label>
              <input v-model="chForm.name" class="wb-input" required>
            </div>
          </div>
          <div class="col-6">
            <div class="wb-field">
              <label class="wb-field__label">Тип</label>
              <select v-model="chForm.channel_type" class="wb-select">
                <option v-for="t in meta.channel_types" :key="t.value" :value="t.value">{{ t.label }}</option>
              </select>
            </div>
          </div>
          <div class="col-12">
            <div class="wb-field">
              <label class="wb-field__label">Ссылка / @handle / почта</label>
              <input v-model="chForm.website_or_contact" class="wb-input">
            </div>
          </div>
          <div class="col-6">
            <div class="wb-field">
              <label class="wb-field__label">Контактное лицо</label>
              <input v-model="chForm.contact_name" class="wb-input">
            </div>
          </div>
          <div class="col-6">
            <div class="wb-field">
              <label class="wb-field__label">Телефон</label>
              <input v-model="chForm.contact_phone" class="wb-input">
            </div>
          </div>
          <div class="col-6">
            <div class="wb-field">
              <label class="wb-field__label">ИНН</label>
              <input v-model="chForm.inn" class="wb-input">
            </div>
          </div>
          <div class="col-6">
            <div class="wb-field">
              <label class="wb-field__label">Комментарий</label>
              <input v-model="chForm.comment" class="wb-input">
            </div>
          </div>
        </div>
        <div v-if="chMsg" class="wb-error">{{ chMsg }}</div>
        <div class="wb-modal-actions">
          <button type="button" class="btn btn--outline" @click="chModal = false">Отмена</button>
          <button type="submit" class="btn btn--brand" :disabled="saving">Сохранить</button>
        </div>
      </form>
    </div>

    <!-- Модалка документа -->
    <div v-if="docModal" class="wb-modal-backdrop page-marketing-expenses__backdrop" @click.self="docModal = false">
      <form class="wb-modal-box wb-modal-box--wide page-marketing-expenses__modal" @submit.prevent="saveDocument">
        <div class="d-flex align-items-center gap-2">
          <span class="page-marketing-expenses__modal-title">
            {{ docForm.id ? 'Документ расхода' : 'Новый документ расхода' }}
          </span>
          <button type="button" class="btn-close ms-auto" aria-label="Закрыть" @click="docModal = false"></button>
        </div>
        <div class="row g-3">
          <div class="col-4">
            <div class="wb-field">
              <label class="wb-field__label">Дата *</label>
              <WbDateInput v-model="docForm.document_date" />
            </div>
          </div>
          <div class="col-4">
            <div class="wb-field">
              <label class="wb-field__label">Тип *</label>
              <select v-model="docForm.doc_type" class="wb-select">
                <option v-for="t in meta.doc_types" :key="t.value" :value="t.value">{{ t.label }}</option>
              </select>
            </div>
          </div>
          <div class="col-4">
            <div class="wb-field">
              <label class="wb-field__label">Площадка *</label>
              <select v-model="docForm.channel_id" class="wb-select" required>
                <option :value="null">— выберите —</option>
                <option v-for="c in channels" :key="c.id" :value="c.id">{{ c.name }}</option>
              </select>
            </div>
          </div>
          <div class="col-4">
            <div class="wb-field">
              <label class="wb-field__label">Название *</label>
              <input v-model="docForm.title" class="wb-input" placeholder="Например: Telegram-подборка ноября" required>
            </div>
          </div>
          <div class="col-4">
            <div class="wb-field">
              <label class="wb-field__label">document_key</label>
              <input v-model="docForm.document_key" class="wb-input" placeholder="если пусто — сгенерируем">
            </div>
          </div>
          <div class="col-4">
            <div class="wb-field">
              <label class="wb-field__label">Комментарий</label>
              <input v-model="docForm.comment" class="wb-input">
            </div>
          </div>
        </div>

        <div class="d-flex justify-content-between align-items-center">
          <b>Позиции (всегда с SKU)</b>
          <span class="page-marketing-expenses__hint">поиск по nm_id, артикулу или названию</span>
        </div>

        <!-- Поиск карточки: подсказки по nm_id / vendorCode / title -->
        <div class="wb-field">
          <label class="wb-field__label">Карточка WB</label>
          <input
            v-model="cardQuery"
            class="wb-input"
            type="search"
            placeholder="nm_id, артикул или название товара"
            @input="onCardQuery"
            @keydown.esc="cardMatches = []"
          >
        </div>
        <div v-if="cardMatches.length" class="page-marketing-expenses__cards">
          <button
            v-for="c in cardMatches"
            :key="c.nm_id"
            type="button"
            class="page-marketing-expenses__card"
            @click="pickCard(c)"
          >
            <span class="page-marketing-expenses__card-nm">{{ c.nm_id }}</span>
            <span class="page-marketing-expenses__card-vendor">{{ c.vendor_code || '—' }}</span>
            <span class="page-marketing-expenses__card-title">{{ c.title || 'без названия' }}</span>
          </button>
        </div>

        <div class="tbl-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th class="t-left">SKU / артикул</th>
                <th class="t-left">Товар</th>
                <th>Сумма</th>
                <th class="t-left">Комментарий</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(ln, i) in docForm.lines" :key="i">
                <td class="t-left">
                  <div>{{ ln.vendor_code || '—' }}</div>
                  <div class="page-marketing-expenses__hint">nmID {{ ln.nm_id || '—' }}</div>
                </td>
                <td class="t-left">{{ ln.product_title || '—' }}</td>
                <td>
                  <input v-model.number="ln.amount" class="wb-input page-marketing-expenses__amount" type="number" min="0" step="0.01">
                </td>
                <td class="t-left"><input v-model="ln.comment" class="wb-input"></td>
                <td class="t-right">
                  <button type="button" class="btn btn--ghost btn-sm" @click="docForm.lines.splice(i, 1)">
                    <i class="bi bi-x-lg"></i>
                  </button>
                </td>
              </tr>
              <tr v-if="!docForm.lines.length">
                <td colspan="5" class="text-center text-muted py-3">Найдите карточку выше и добавьте её в позиции</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="d-flex justify-content-between align-items-center">
          <span class="page-marketing-expenses__hint">Сумма документа = сумма позиций. Позиция без SKU не сохранится.</span>
          <b>{{ money(docTotal) }}</b>
        </div>
        <div v-if="docMsg" class="wb-error">{{ docMsg }}</div>
        <div class="wb-modal-actions">
          <button type="button" class="btn btn--outline" @click="docModal = false">Отмена</button>
          <button type="submit" class="btn btn--brand" :disabled="saving">Сохранить</button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-marketing-expenses.css'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { marketingApi, type MarketingDocument, type MarketingImportPreview } from '@/api/marketing'
import WbDateRangeFilter from '@/components/common/WbDateRangeFilter.vue'
import WbDateInput from '@/components/common/WbDateInput.vue'
import WbSectionTabs from '@/components/common/WbSectionTabs.vue'
import { useAuthStore } from '@/stores/auth'
import { exportXlsx } from '@/utils/exportXlsx'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
// v3: перм manageSettings (у owner/admin компании он выдаётся автоматически).
// legacy (AUTH_V3=0): перма нет — правят владельцы/админы компании.
const canManage = computed(() => auth.can('manageSettings') || (!auth.authV3 && auth.managesAny))

const tab = ref(String(route.query.tab || 'documents'))
const tabs = computed(() => [
  { id: 'documents', label: 'Документы', count: documents.value.length },
  { id: 'channels', label: 'Площадки', count: channels.value.length },
])

const meta = ref<{ channel_types: { value: string; label: string }[]; doc_types: { value: string; label: string }[]; xlsx_columns: string[] }>(
  { channel_types: [], doc_types: [], xlsx_columns: [] })

const channels = ref<any[]>([])
const documents = ref<MarketingDocument[]>([])
const selectedDoc = ref<MarketingDocument | null>(null)

const docFrom = ref(new Date(Date.now() - 29 * 864e5).toISOString().slice(0, 10))
const docTo = ref(new Date().toISOString().slice(0, 10))
const docChannel = ref<number | null>(null)
const docQuery = ref('')

const chQuery = ref('')
const chType = ref('')
const chStatus = ref('active')

const docExcelOpen = ref(false)
const chExcelOpen = ref(false)
const docExcelRef = ref<HTMLElement | null>(null)
const chExcelRef = ref<HTMLElement | null>(null)

const chModal = ref(false)
const chForm = ref<any>({ id: null, name: '', channel_type: 'blogger', website_or_contact: '', contact_name: '', contact_phone: '', inn: '', comment: '' })
const chMsg = ref('')

const docModal = ref(false)
const docForm = ref<any>({ id: null, document_key: '', document_date: new Date().toISOString().slice(0, 10), channel_id: null, doc_type: 'blogger_post', title: '', comment: '', lines: [] as any[] })
const docMsg = ref('')

const fileRef = ref<HTMLInputElement | null>(null)
const imp = ref<MarketingImportPreview | null>(null)
const importMsg = ref('')
const saving = ref(false)

const docTotal = computed(() => (docForm.value.lines || []).reduce((s: number, l: any) => s + Number(l.amount || 0), 0))
const totalLines = computed(() => documents.value.reduce((s, d) => s + (d.lines_cnt || 0), 0))
const totalAmount = computed(() => documents.value.reduce((s, d) => s + Number(d.total_amount || 0), 0))

function money(v: number) {
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(Number(v || 0)) + ' ₽'
}

/* Смена периода в блоке дат — запоминаем; запрос идёт по кнопке «Применить». */
function onDates(p: { from: string; to: string }) {
  docFrom.value = p.from
  docTo.value = p.to
}

async function loadChannels() {
  const rows = await marketingApi.channels(chQuery.value, chStatus.value !== 'active').catch(() => [])
  channels.value = chType.value
    ? rows.filter((c: any) => c.channel_type === chType.value)
    : rows
}
async function loadDocuments() {
  documents.value = await marketingApi.documents({
    date_from: docFrom.value, date_to: docTo.value,
    channel_id: docChannel.value, q: docQuery.value,
  }).catch(() => [])
  if (selectedDoc.value) {
    const again = documents.value.find((d) => d.id === selectedDoc.value!.id)
    selectedDoc.value = again || null
  }
}
function resetDocs() {
  docFrom.value = new Date(Date.now() - 29 * 864e5).toISOString().slice(0, 10)
  docTo.value = new Date().toISOString().slice(0, 10)
  docChannel.value = null
  docQuery.value = ''
  loadDocuments()
}
function resetChannels() {
  chQuery.value = ''
  chType.value = ''
  chStatus.value = 'active'
  loadChannels()
}

/** Открыть документ (с позициями) в правой панели. */
async function selectDocument(d: MarketingDocument) {
  const full = await marketingApi.document(d.id).catch(() => null)
  selectedDoc.value = full || d
}

function openChannel(c?: any) {
  chMsg.value = ''
  chForm.value = c
    ? { ...c }
    : { id: null, name: '', channel_type: 'blogger', website_or_contact: '', contact_name: '', contact_phone: '', inn: '', comment: '' }
  chModal.value = true
}
async function saveChannel() {
  chMsg.value = ''
  const payload: any = { ...chForm.value }
  saving.value = true
  try {
    if (payload.id) await marketingApi.updateChannel(payload.id, payload)
    else await marketingApi.createChannel(payload)
    chModal.value = false
    await loadChannels()
  } catch (e: any) {
    chMsg.value = e?.response?.data?.detail || e?.message || String(e)
  } finally {
    saving.value = false
  }
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

/* Поиск карточки для позиции: по nm_id, артикулу (vendorCode) и названию.
   Сервер ищет по всем трём полям (marketingApi.searchCards → /api/marketing/cards/search). */
const cardQuery = ref('')
const cardMatches = ref<{ nm_id: number; vendor_code: string; title: string }[]>([])
let cardTimer: ReturnType<typeof setTimeout> | null = null

function onCardQuery() {
  const q = cardQuery.value.trim()
  if (cardTimer) clearTimeout(cardTimer)
  if (!q) { cardMatches.value = []; return }
  cardTimer = setTimeout(async () => {
    cardMatches.value = await marketingApi.searchCards(q, 20).catch(() => [])
  }, 250)
}

/** Карточка выбрана — добавляем позицию (или заполняем пустую). */
function pickCard(c: { nm_id: number; vendor_code: string; title: string }) {
  const empty = docForm.value.lines.find((l: any) => !l.nm_id && !l.vendor_code)
  const line = empty || { vendor_code: '', nm_id: null, product_title: '', amount: 0, comment: '' }
  line.nm_id = c.nm_id
  line.vendor_code = c.vendor_code
  line.product_title = c.title
  if (!empty) docForm.value.lines.push(line)
  cardQuery.value = ''
  cardMatches.value = []
}
async function saveDocument() {
  docMsg.value = ''
  const lines = (docForm.value.lines || []).filter((l: any) => l.nm_id || String(l.vendor_code || '').trim())
  if (!docForm.value.title.trim()) { docMsg.value = 'Укажите название документа.'; return }
  if (!docForm.value.channel_id) { docMsg.value = 'Выберите площадку.'; return }
  if (!lines.length) { docMsg.value = 'Добавьте хотя бы одну позицию с SKU.'; return }
  const payload: any = { ...docForm.value, lines }
  saving.value = true
  try {
    if (docForm.value.id) await marketingApi.updateDocument(docForm.value.id, payload)
    else await marketingApi.createDocument(payload)
    docModal.value = false
    await Promise.all([loadChannels(), loadDocuments()])
  } catch (e: any) {
    docMsg.value = e?.response?.data?.detail || e?.message || String(e)
  } finally {
    saving.value = false
  }
}
async function removeDocument(d: any) {
  if (!confirm(`Удалить документ «${d.title}»?`)) return
  await marketingApi.deleteDocument(d.id)
  selectedDoc.value = null
  await Promise.all([loadChannels(), loadDocuments()])
}

/* ------------------------------------------------------------ Excel */
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
async function downloadChannelsTemplate() {
  const cols = ['name', 'channel_type', 'website_or_contact', 'contact_name', 'contact_phone', 'inn', 'comment']
  const rows = [Object.fromEntries(cols.map((c: string) => [c, ''])), {
    name: 'CoffeeBlog', channel_type: 'telegram', website_or_contact: 'https://t.me/coffeeblog',
    contact_name: '', contact_phone: '', inn: '7708123456', comment: 'пример',
  }]
  await exportXlsx({ rows, filename: 'шаблон-площадок.xlsx', sheetName: 'Площадки' })
}
async function exportChannels() {
  await exportXlsx({
    rows: channels.value.map((c: any) => ({
      name: c.name, channel_type: c.channel_type, website_or_contact: c.website_or_contact || '',
      contact_name: c.contact_name || '', contact_phone: c.contact_phone || '',
      inn: c.inn || '', comment: c.comment || '',
      documents: c.documents_cnt, amount: c.total_amount,
    })),
    filename: 'площадки.xlsx', sheetName: 'Площадки',
  })
}

/* Импорт: клиент читает 1-й лист → POST /preview (dry-run) → подтверждение → POST /save. */
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
  saving.value = true
  try {
    const res = await marketingApi.importSave(imp.value.documents)
    await Promise.all([loadChannels(), loadDocuments()])
    imp.value = null
    alert(`Сохранено документов: ${res.saved}. Пропущено: ${res.skipped}.`)
  } catch (e: any) {
    importMsg.value = e?.response?.data?.detail || e?.message || String(e)
  } finally {
    saving.value = false
  }
}

watch(tab, (next) => {
  router.replace({ path: route.path, query: next === 'documents' ? {} : { tab: next } })
})

/* Клик вне дропдауна — закрыть (свой компонент, без JS-бандла bootstrap). */
function onDocClick(e: MouseEvent) {
  if (docExcelOpen.value && docExcelRef.value && !docExcelRef.value.contains(e.target as Node)) docExcelOpen.value = false
  if (chExcelOpen.value && chExcelRef.value && !chExcelRef.value.contains(e.target as Node)) chExcelOpen.value = false
}

onMounted(async () => {
  document.addEventListener('mousedown', onDocClick)
  meta.value = await marketingApi.meta().catch(() => meta.value)
  await Promise.all([loadChannels(), loadDocuments()])
})
onBeforeUnmount(() => document.removeEventListener('mousedown', onDocClick))
</script>
