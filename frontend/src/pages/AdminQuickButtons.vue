<template>
  <div class="container-xxl page-admin-quick-buttons">
    <nav aria-label="breadcrumb" class="page-admin-quick-buttons__crumbs">
      <ol class="breadcrumb page-admin-quick-buttons__crumbs-list">
        <li class="breadcrumb-item"><router-link to="/">Главная</router-link></li>
        <li class="breadcrumb-item">Админка</li>
        <li class="breadcrumb-item active">Быстрые кнопки</li>
      </ol>
    </nav>
    <div class="page-admin-quick-buttons__head">
      <h1 class="page-admin-quick-buttons__title">Быстрые кнопки <span class="text-muted page-admin-quick-buttons__title-sub">config / quick_buttons.json</span></h1>
      <span class="badge bg-light text-dark border page-admin-quick-buttons__count">{{ items.length }} шт</span>
    </div>

    <div v-if="msg" :class="['alert', msgOk ? 'alert-success':'alert-danger', 'page-admin-quick-buttons__msg']">{{ msg }}</div>

    <!-- предпросмотр как в WbFilterBar site.css:358 .panel-btns -->
    <div class="card mb-3 page-admin-quick-buttons__preview-card">
      <div class="card-header d-flex align-items-center justify-content-between page-admin-quick-buttons__preview-head">
        <span>Предпросмотр (как в фильтре)</span>
        <span class="text-muted page-admin-quick-buttons__preview-meta">panel-btns · btn-panel #a73afd</span>
      </div>
      <div class="card-body page-admin-quick-buttons__preview-body">
        <div v-if="!items.length" class="text-muted page-admin-quick-buttons__preview-empty">Нет кнопок — добавьте ниже.</div>
        <div v-else class="panel-btns page-admin-quick-buttons__preview-btns">
          <button v-for="b in items" :key="b.nm_id" class="btn btn-panel" :title="'nm_id '+b.nm_id"><i v-if="b.icon" :class="b.icon" class="page-admin-quick-buttons__preview-icon"></i>{{ b.label }}</button>
        </div>
        <div class="text-muted page-admin-quick-buttons__preview-note">Рендер из <code>/api/config/quick-buttons</code> · иконки <code>bi …</code> (bootstrap-icons 1.11.3) и <code>fas fa-…</code> (font-awesome 6.5.2).</div>
      </div>
    </div>

    <!-- таблица -->
    <div class="card page-admin-quick-buttons__list-card">
      <div class="card-header d-flex align-items-center justify-content-between page-admin-quick-buttons__list-head">
        <span class="page-admin-quick-buttons__list-title">Список кнопок</span>
        <button class="btn btn-sm btn-primary page-admin-quick-buttons__add-btn" @click="openAdd"><i class="bi bi-plus-lg me-1"></i>Добавить</button>
      </div>
      <div class="table-responsive">
        <table class="table table-hover mb-0 page-admin-quick-buttons__table">
          <thead class="page-admin-quick-buttons__table-head">
            <tr>
              <th style="width:36px; text-align:center">#</th>
              <th style="width:56px; text-align:center">Иконка</th>
              <th>Подпись</th>
              <th style="width:140px">nm_id</th>
              <th>Карточка <span class="text-muted page-admin-quick-buttons__table-sub">(по nm_id)</span></th>
              <th style="width:160px; text-align:right">Действия</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading"><td colspan="6" class="text-center p-4"><span class="spinner-border spinner-border-sm"></span> Загрузка…</td></tr>
            <tr v-else-if="!items.length"><td colspan="6" class="text-center text-muted p-3">Пусто</td></tr>
            <tr v-for="(b, i) in items" :key="b.nm_id+'_'+i">
              <td class="text-center text-muted">{{ i+1 }}</td>
              <td class="text-center"><i :class="b.icon" class="page-admin-quick-buttons__row-icon"></i><div class="page-admin-quick-buttons__icon-name">{{ b.icon }}</div></td>
              <td class="page-admin-quick-buttons__label-cell">{{ b.label }}</td>
              <td>
                <a :href="'/wb/detail?nm_id='+b.nm_id" target="_blank" class="text-decoration-none"><b>{{ b.nm_id }}</b> <i class="bi bi-box-arrow-up-right page-admin-quick-buttons__ext-icon"></i></a>
              </td>
              <td class="page-admin-quick-buttons__card-cell">
                <span v-if="cardTitle[b.nm_id]">{{ cardTitle[b.nm_id] }}</span>
                <span v-else class="text-muted" :title="'не найдена в wbcards'">—</span>
              </td>
              <td class="page-admin-quick-buttons__row-actions">
                <div class="btn-group btn-group-sm">
                  <button class="btn btn-outline-secondary" :disabled="i===0" @click="move(i,-1)" title="вверх"><i class="bi bi-chevron-up"></i></button>
                  <button class="btn btn-outline-secondary" :disabled="i===items.length-1" @click="move(i,1)" title="вниз"><i class="bi bi-chevron-down"></i></button>
                </div>
                <button class="btn btn-sm btn-outline-primary ms-1 page-admin-quick-buttons__edit-btn" @click="openEdit(i)">Изменить</button>
                <button class="btn btn-sm btn-outline-danger ms-1 page-admin-quick-buttons__edit-btn" @click="remove(i)">×</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="card-footer d-flex gap-2 justify-content-end page-admin-quick-buttons__foot">
        <button class="btn btn-outline-secondary page-admin-quick-buttons__foot-btn" @click="reload" :disabled="saving">Перезагрузить</button>
        <button class="btn btn-primary page-admin-quick-buttons__foot-btn" @click="save" :disabled="saving">
          <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span> Сохранить в quick_buttons.json
        </button>
      </div>
    </div>

    <!-- форма добавления/редактирования -->
    <div v-if="showForm" class="card mt-3 page-admin-quick-buttons__form-card">
      <div class="card-header page-admin-quick-buttons__form-head">
        {{ editIndex===-1 ? 'Добавить кнопку' : 'Редактировать #' + (editIndex+1) }}
        <button class="btn btn-sm btn-light float-end page-admin-quick-buttons__form-close" @click="showForm=false">Закрыть</button>
      </div>
      <div class="card-body page-admin-quick-buttons__form-body">
        <div class="row g-3">
          <div class="col-md-5">
            <label class="form-label page-admin-quick-buttons__field-label">Подпись (label) <span class="text-danger">*</span></label>
            <input v-model="form.label" class="form-control form-control-sm" placeholder="напр. Дневник" />
          </div>
          <div class="col-md-4">
            <label class="form-label page-admin-quick-buttons__field-label">Иконка (icon) <span class="text-danger">*</span></label>
            <div class="input-group input-group-sm">
              <span class="input-group-text"><i :class="form.icon"></i></span>
              <input v-model="form.icon" class="form-control" placeholder="bi bi-journal-text / fas fa-book" readonly />
              <button class="btn btn-outline-primary" @click="iconPickerOpen=true">Выбрать</button>
            </div>
            <div class="form-text page-admin-quick-buttons__field-hint">Два шрифта: <b>Bootstrap Icons</b> (<code>bi …</code>) и <b>Font Awesome</b> (<code>fas fa-…</code>).</div>
          </div>
          <div class="col-md-3">
            <label class="form-label page-admin-quick-buttons__field-label">nm_id <span class="text-danger">*</span></label>
            <input v-model.number="form.nm_id" type="number" class="form-control form-control-sm" placeholder="526443466" />
          </div>
          <div class="col-12">
            <label class="form-label page-admin-quick-buttons__field-label">Поиск карточки WB — подставляет nm_id и подпись</label>
            <div class="page-admin-quick-buttons__search-wrap" ref="cardWrapRef">
              <input v-model="cardQuery" @input="onCardInput" @focus="showCardList=true" placeholder="введите nmID / vendorCode / часть названия…" class="form-control form-control-sm" />
              <div v-if="showCardList && filteredCards.length" class="page-admin-quick-buttons__search-drop">
                <div v-for="c in filteredCards.slice(0,20)" :key="c.nmID" @mousedown.prevent="pickCard(c)" class="page-admin-quick-buttons__search-row">
                  <span><b>{{ c.nmID }}</b> — {{ c.title }} <span class="text-muted">({{ c.vendorCode }})</span></span>
                  <span class="text-muted page-admin-quick-buttons__search-brand">{{ c.brand }}</span>
                </div>
              </div>
            </div>
            <div class="page-admin-quick-buttons__search-status">
              <span v-if="pickedCard" class="badge bg-light text-dark border page-admin-quick-buttons__picked">Выбрано: {{ pickedCard.nmID }} · {{ pickedCard.title }}</span>
              <button v-if="cardQuery" class="btn btn-sm btn-light page-admin-quick-buttons__reset-btn" @click="cardQuery=''; pickedCard=null; showCardList=false">× Сбросить</button>
              <span v-if="cardsLoading" class="text-muted page-admin-quick-buttons__searching">Поиск…</span>
            </div>
          </div>
        </div>
        <div class="d-flex gap-2 mt-3">
          <button class="btn btn-primary btn-sm" @click="applyForm" :disabled="!form.label.trim() || !form.icon.trim() || !form.nm_id"> {{ editIndex===-1 ? 'Добавить' : 'Обновить' }}</button>
          <button class="btn btn-light btn-sm" @click="showForm=false">Отмена</button>
          <span class="ms-auto text-muted page-admin-quick-buttons__form-actions-hint">После добавления нажмите <b>Сохранить в quick_buttons.json</b>.</span>
        </div>
      </div>
    </div>

    <!-- пикер иконок -->
    <div v-if="iconPickerOpen" class="page-admin-quick-buttons__picker-backdrop" @click.self="iconPickerOpen=false">
      <div class="card page-admin-quick-buttons__picker-card">
        <div class="card-header d-flex align-items:center; justify-content:space-between page-admin-quick-buttons__picker-head">
          <div>
            <strong class="page-admin-quick-buttons__picker-title">Выбор иконки</strong>
            <span class="text-muted ms-2 page-admin-quick-buttons__picker-sub">2 шрифта — bi и fas</span>
          </div>
          <div class="ms-auto d-flex gap-2 align-items-center">
            <input v-model="iconQ" placeholder="поиск: journal, book, palette…" class="form-control form-control-sm page-admin-quick-buttons__picker-search" />
            <button class="btn btn-sm btn-light" @click="iconPickerOpen=false">Закрыть</button>
          </div>
        </div>
        <div class="page-admin-quick-buttons__picker-tabs">
          <button :class="['btn btn-sm', iconTab==='bi' ? 'btn-primary':'btn-outline-secondary']" @click="iconTab='bi'">Bootstrap Icons ({{ filteredBi.length }}) <i class="bi bi-journal-text ms-1"></i></button>
          <button :class="['btn btn-sm', iconTab==='fa' ? 'btn-primary':'btn-outline-secondary']" @click="iconTab='fa'">Font Awesome ({{ filteredFa.length }}) <i class="fas fa-star ms-1"></i></button>
          <span class="ms-auto badge bg-light text-dark border page-admin-quick-buttons__picker-pick">выбрано: <i :class="form.icon"></i> {{ form.icon }}</span>
        </div>
        <div class="page-admin-quick-buttons__picker-body">
          <div v-if="iconTab==='bi'" class="icon-grid">
            <button v-for="ic in filteredBi" :key="ic" @click="form.icon=ic; iconPickerOpen=false" :class="['icon-cell', form.icon===ic ? 'active':'']" :title="ic"><i :class="ic"></i><span>{{ ic.replace('bi bi-','') }}</span></button>
          </div>
          <div v-else class="icon-grid">
            <button v-for="ic in filteredFa" :key="ic" @click="form.icon=ic; iconPickerOpen=false" :class="['icon-cell', form.icon===ic ? 'active':'']" :title="ic"><i :class="ic"></i><span>{{ ic.replace('fas fa-','') }}</span></button>
          </div>
          <div v-if="(iconTab==='bi' ? filteredBi : filteredFa).length===0" class="text-muted text-center p-4 page-admin-quick-buttons__picker-empty">Ничего не найдено.</div>
        </div>
        <div class="card-footer text-muted page-admin-quick-buttons__picker-foot">Подключены CDN: bootstrap-icons 1.11.3 + font-awesome 6.5.2 (index.html). В WbFilterBar рендер <code>&lt;i :class="icon"&gt;</code>.</div>
      </div>
    </div>

    <div class="text-muted mt-3 page-admin-quick-buttons__foot-note">
      Хранится в <code>backend/config/quick_buttons.json</code> массива <code>{icon,label,nm_id}</code>. Доступен как <code>GET /api/config/quick-buttons</code> и используется в <code>WbFilterBar.vue:5</code> (<code>panel-btns/btn-panel</code>). Для сохранения — <code>PUT /api/config/quick-buttons</code>.
    </div>
  </div>
</template>
<script setup lang="ts">
import '@/assets/css/pages/page-admin-quick-buttons.css'
import { ref, computed, onMounted, watch } from 'vue'
import { api } from '../api/client'
import { dashboardApi } from '../api/dashboard'

const items = ref<any[]>([])
const loading = ref(false)
const saving = ref(false)
const msg = ref('')
const msgOk = ref(true)
const cardTitle = ref<Record<number,string>>({})

const showForm = ref(false)
const editIndex = ref(-1)
const form = ref({ label:'', icon:'bi bi-journal-text', nm_id: 0 as number | '' })
const cardQuery = ref('')
const pickedCard = ref<any>(null)
const showCardList = ref(false)
const cardWrapRef = ref<any>(null)
const cards = ref<any[]>([])
const cardsLoading = ref(false)
let cardTimer: any = null

const iconPickerOpen = ref(false)
const iconTab = ref<'bi'|'fa'>('bi')
const iconQ = ref('')
const icons = ref<{bi:string[], fa:string[]}>({bi:[], fa:[]})

const filteredCards = computed(()=>{
  const q = cardQuery.value.toLowerCase().trim()
  if(!q) return cards.value
  return cards.value.filter((c:any)=> String(c.nmID).includes(q) || String(c.vendorCode||'').toLowerCase().includes(q) || String(c.title||'').toLowerCase().includes(q) || String(c.brand||'').toLowerCase().includes(q))
})
const filteredBi = computed(()=>{
  const q=iconQ.value.toLowerCase().trim()
  if(!q) return icons.value.bi
  return icons.value.bi.filter(x=> x.toLowerCase().includes(q))
})
const filteredFa = computed(()=>{
  const q=iconQ.value.toLowerCase().trim()
  if(!q) return icons.value.fa
  return icons.value.fa.filter(x=> x.toLowerCase().includes(q))
})

async function loadIcons(){
  try{ const d=await dashboardApi.icons(); icons.value=d }catch{ icons.value={bi:[], fa:[]} }
}
async function searchCards(q:string){
  cardsLoading.value=true
  try{ const d=await dashboardApi.wbCards(q, 50); cards.value=Array.isArray(d)?d:[] }catch{ cards.value=[] } finally{ cardsLoading.value=false }
}
function onCardInput(){
  showCardList.value=true
  const q=cardQuery.value.trim()
  clearTimeout(cardTimer)
  cardTimer=setTimeout(()=> searchCards(q), 300)
  if(!q) pickedCard.value=null
}
function pickCard(c:any){
  pickedCard.value=c
  cardQuery.value=`${c.nmID} | ${c.title}`
  form.value.nm_id=c.nmID
  if(!form.value.label.trim()) form.value.label=c.title?.slice(0,32) || c.vendorCode || ''
  showCardList.value=false
}
async function reload(){
  loading.value=true; msg.value=''
  try{
    const d=await dashboardApi.quickButtons()
    items.value=Array.isArray(d)?d:[]
    // подгрузим названия карточек для таблицы — параллельно, с фолбэком через wbCards
    const map: Record<string,string> = {}
    await Promise.all(items.value.map(async (b:any)=>{
      try{
        const { data:j } = await api.get(`/api/wb/card/${b.nm_id}`)
        if(j){ map[b.nm_id]= j.title ? `${j.title} · ${j.vendorCode||''}`.trim() : (j.vendorCode||''); return }
      }catch{}
      // фолбэк: поиск через /api/wb/cards
      try{
        const lst:any = await dashboardApi.wbCards(String(b.nm_id), 5)
        const hit = Array.isArray(lst) ? lst.find((x:any)=> String(x.nmID)===String(b.nm_id)) : null
        if(hit) map[b.nm_id]= `${hit.title||''} · ${hit.vendorCode||''}`.trim()
      }catch{}
    }))
    cardTitle.value = map
  }catch(e:any){ msg.value='Ошибка загрузки: '+String(e); msgOk.value=false }
  finally{ loading.value=false }
}
function openAdd(){
  editIndex.value=-1; form.value={label:'', icon:'bi bi-journal-text', nm_id: '' as any}; cardQuery.value=''; pickedCard.value=null; showCardList.value=false; showForm.value=true
  searchCards('')
}
function openEdit(i:number){
  const b=items.value[i]; editIndex.value=i; form.value={label:b.label, icon:b.icon, nm_id:b.nm_id}; cardQuery.value=String(b.nm_id); pickedCard.value=null; showForm.value=true
  searchCards(String(b.nm_id))
}
function applyForm(){
  if(!form.value.label.trim() || !form.value.icon.trim() || !form.value.nm_id) return
  const row={icon: form.value.icon.trim(), label: form.value.label.trim(), nm_id: Number(form.value.nm_id)}
  if(editIndex.value===-1) items.value.push(row)
  else items.value[editIndex.value]=row
  showForm.value=false; msg.value='Изменения не сохранены — нажмите «Сохранить в quick_buttons.json».'; msgOk.value=true
}
function remove(i:number){
  if(!confirm(`Удалить «${items.value[i].label}» ?`)) return
  items.value.splice(i,1); msg.value='Удалено — нажмите «Сохранить».'; msgOk.value=true
}
function move(i:number, dir:number){
  const j=i+dir; if(j<0||j>=items.value.length) return
  const t=items.value[i]; items.value[i]=items.value[j]; items.value[j]=t
  msg.value='Порядок изменён — нажмите «Сохранить».'; msgOk.value=true
}
async function save(){
  saving.value=true; msg.value=''
  try{
    await dashboardApi.saveQuickButtons(items.value)
    msg.value=`Сохранено ${items.value.length} кнопок в quick_buttons.json`; msgOk.value=true
  }catch(e:any){ msg.value='Ошибка сохранения: '+(e?.response?.data?.detail || String(e)); msgOk.value=false }
  finally{ saving.value=false }
}
onMounted(()=>{ reload(); loadIcons(); searchCards('') })
watch(cardQuery, (v)=>{ if(!v) pickedCard.value=null })
document.addEventListener('mousedown', (e:any)=>{
  const el=cardWrapRef.value; if(el && !el.contains(e.target)) showCardList.value=false
})
</script>
<style scoped>
.panel-btns .btn-panel{ margin-right:5px; font-size:12px; background:#a73afd; color:#ddd; border:none }
.panel-btns .btn-panel:hover{ background:#a73afde6; color:#fff }
</style>
