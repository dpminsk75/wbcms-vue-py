<template>
  <div class="container" style="padding:20px 15px; max-width:1100px">
    <nav aria-label="breadcrumb" style="margin-bottom:12px">
      <ol class="breadcrumb" style="font-size:12px">
        <li class="breadcrumb-item"><router-link to="/">Главная</router-link></li>
        <li class="breadcrumb-item">Админка</li>
        <li class="breadcrumb-item active">Быстрые кнопки</li>
      </ol>
    </nav>
    <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:16px">
      <h1 style="font-size:22px; font-weight:700; margin:0">Быстрые кнопки <span class="text-muted" style="font-weight:400; font-size:13px">config / quick_buttons.json</span></h1>
      <span class="badge bg-light text-dark border" style="font-size:11px">{{ items.length }} шт</span>
    </div>

    <div v-if="msg" :class="['alert', msgOk ? 'alert-success':'alert-danger']" style="font-size:13px; padding:8px 12px">{{ msg }}</div>

    <!-- предпросмотр как в WbFilterBar site.css:358 .panel-btns -->
    <div class="card mb-3" style="border:1px solid #e0e0e0; border-radius:12px">
      <div class="card-header d-flex align-items-center justify-content-between" style="background:#f8f9fa; font-size:12px; font-weight:600">
        <span>Предпросмотр (как в фильтре)</span>
        <span class="text-muted" style="font-weight:400">panel-btns · btn-panel #a73afd</span>
      </div>
      <div class="card-body" style="padding:12px">
        <div v-if="!items.length" class="text-muted" style="font-size:12px">Нет кнопок — добавьте ниже.</div>
        <div v-else class="panel-btns" style="margin:0">
          <button v-for="b in items" :key="b.nm_id" class="btn btn-panel" :title="'nm_id '+b.nm_id"><i v-if="b.icon" :class="b.icon" style="margin-right:4px"></i>{{ b.label }}</button>
        </div>
        <div class="text-muted" style="font-size:11px; margin-top:8px">Рендер из <code>/api/config/quick-buttons</code> · иконки <code>bi …</code> (bootstrap-icons 1.11.3) и <code>fas fa-…</code> (font-awesome 6.5.2).</div>
      </div>
    </div>

    <!-- таблица -->
    <div class="card" style="border:1px solid #e0e0e0; border-radius:12px; overflow:hidden">
      <div class="card-header d-flex align-items-center justify-content-between" style="background:#fff; border-bottom:1px solid #eee">
        <span style="font-weight:600; font-size:13px">Список кнопок</span>
        <button class="btn btn-sm btn-primary" style="font-size:12px" @click="openAdd"><i class="bi bi-plus-lg me-1"></i>Добавить</button>
      </div>
      <div class="table-responsive">
        <table class="table table-hover mb-0" style="font-size:12px">
          <thead style="background:#f8f9fa">
            <tr>
              <th style="width:36px; text-align:center">#</th>
              <th style="width:56px; text-align:center">Иконка</th>
              <th>Подпись</th>
              <th style="width:140px">nm_id</th>
              <th>Карточка <span class="text-muted" style="font-weight:400">(по nm_id)</span></th>
              <th style="width:160px; text-align:right">Действия</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading"><td colspan="6" class="text-center p-4"><span class="spinner-border spinner-border-sm"></span> Загрузка…</td></tr>
            <tr v-else-if="!items.length"><td colspan="6" class="text-center text-muted p-3">Пусто</td></tr>
            <tr v-for="(b, i) in items" :key="b.nm_id+'_'+i">
              <td class="text-center text-muted">{{ i+1 }}</td>
              <td class="text-center"><i :class="b.icon" style="font-size:16px"></i><div style="font-size:9px; color:#888; margin-top:2px; word-break:break-all">{{ b.icon }}</div></td>
              <td style="font-weight:600">{{ b.label }}</td>
              <td>
                <a :href="'/wb/detail?nm_id='+b.nm_id" target="_blank" class="text-decoration-none"><b>{{ b.nm_id }}</b> <i class="bi bi-box-arrow-up-right" style="font-size:10px"></i></a>
              </td>
              <td style="font-size:11px; color:#555">
                <span v-if="cardTitle[b.nm_id]">{{ cardTitle[b.nm_id] }}</span>
                <span v-else class="text-muted" :title="'не найдена в wbcards'">—</span>
              </td>
              <td style="text-align:right; white-space:nowrap">
                <div class="btn-group btn-group-sm">
                  <button class="btn btn-outline-secondary" :disabled="i===0" @click="move(i,-1)" title="вверх"><i class="bi bi-chevron-up"></i></button>
                  <button class="btn btn-outline-secondary" :disabled="i===items.length-1" @click="move(i,1)" title="вниз"><i class="bi bi-chevron-down"></i></button>
                </div>
                <button class="btn btn-sm btn-outline-primary ms-1" @click="openEdit(i)" style="font-size:11px">Изменить</button>
                <button class="btn btn-sm btn-outline-danger ms-1" @click="remove(i)" style="font-size:11px">×</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="card-footer d-flex gap-2 justify-content-end" style="background:#fff">
        <button class="btn btn-outline-secondary" style="font-size:12px" @click="reload" :disabled="saving">Перезагрузить</button>
        <button class="btn btn-primary" style="font-size:12px" @click="save" :disabled="saving">
          <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span> Сохранить в quick_buttons.json
        </button>
      </div>
    </div>

    <!-- форма добавления/редактирования -->
    <div v-if="showForm" class="card mt-3" style="border:1px solid #a73afd; border-radius:12px">
      <div class="card-header" style="background:#f3e8ff; font-weight:600; font-size:13px">
        {{ editIndex===-1 ? 'Добавить кнопку' : 'Редактировать #' + (editIndex+1) }}
        <button class="btn btn-sm btn-light float-end" style="font-size:11px" @click="showForm=false">Закрыть</button>
      </div>
      <div class="card-body" style="padding:16px">
        <div class="row g-3">
          <div class="col-md-5">
            <label class="form-label" style="font-size:11px; font-weight:600">Подпись (label) <span class="text-danger">*</span></label>
            <input v-model="form.label" class="form-control form-control-sm" placeholder="напр. Дневник" />
          </div>
          <div class="col-md-4">
            <label class="form-label" style="font-size:11px; font-weight:600">Иконка (icon) <span class="text-danger">*</span></label>
            <div class="input-group input-group-sm">
              <span class="input-group-text"><i :class="form.icon"></i></span>
              <input v-model="form.icon" class="form-control" placeholder="bi bi-journal-text / fas fa-book" readonly />
              <button class="btn btn-outline-primary" @click="iconPickerOpen=true">Выбрать</button>
            </div>
            <div class="form-text" style="font-size:10px">Два шрифта: <b>Bootstrap Icons</b> (<code>bi …</code>) и <b>Font Awesome</b> (<code>fas fa-…</code>).</div>
          </div>
          <div class="col-md-3">
            <label class="form-label" style="font-size:11px; font-weight:600">nm_id <span class="text-danger">*</span></label>
            <input v-model.number="form.nm_id" type="number" class="form-control form-control-sm" placeholder="526443466" />
          </div>
          <div class="col-12">
            <label class="form-label" style="font-size:11px; font-weight:600">Поиск карточки WB — подставляет nm_id и подпись</label>
            <div style="position:relative" ref="cardWrapRef">
              <input v-model="cardQuery" @input="onCardInput" @focus="showCardList=true" placeholder="введите nmID / vendorCode / часть названия…" class="form-control form-control-sm" />
              <div v-if="showCardList && filteredCards.length" style="position:absolute; top:100%; left:0; right:0; max-height:240px; overflow:auto; background:#fff; border:1px solid #e5e7eb; border-radius:6px; z-index:10; box-shadow:0 4px 12px rgba(0,0,0,.08)">
                <div v-for="c in filteredCards.slice(0,20)" :key="c.nmID" @mousedown.prevent="pickCard(c)" style="padding:6px 10px; cursor:pointer; font-size:12px; border-bottom:1px solid #f1f5f9; display:flex; justify-content:space-between; gap:8px">
                  <span><b>{{ c.nmID }}</b> — {{ c.title }} <span class="text-muted">({{ c.vendorCode }})</span></span>
                  <span class="text-muted" style="font-size:10px">{{ c.brand }}</span>
                </div>
              </div>
            </div>
            <div style="display:flex; gap:8px; align-items:center; margin-top:6px">
              <span v-if="pickedCard" class="badge bg-light text-dark border" style="font-size:11px">Выбрано: {{ pickedCard.nmID }} · {{ pickedCard.title }}</span>
              <button v-if="cardQuery" class="btn btn-sm btn-light" style="font-size:11px" @click="cardQuery=''; pickedCard=null; showCardList=false">× Сбросить</button>
              <span v-if="cardsLoading" class="text-muted" style="font-size:11px">Поиск…</span>
            </div>
          </div>
        </div>
        <div class="d-flex gap-2 mt-3">
          <button class="btn btn-primary btn-sm" @click="applyForm" :disabled="!form.label.trim() || !form.icon.trim() || !form.nm_id"> {{ editIndex===-1 ? 'Добавить' : 'Обновить' }}</button>
          <button class="btn btn-light btn-sm" @click="showForm=false">Отмена</button>
          <span class="ms-auto text-muted" style="font-size:11px; align-self:center">После добавления нажмите <b>Сохранить в quick_buttons.json</b>.</span>
        </div>
      </div>
    </div>

    <!-- пикер иконок -->
    <div v-if="iconPickerOpen" style="position:fixed; inset:0; background:rgba(0,0,0,.35); z-index:1050; display:flex; align-items:center; justify-content:center; padding:12px" @click.self="iconPickerOpen=false">
      <div class="card" style="width:min(920px,100%); max-height:90vh; display:flex; flex-direction:column; border-radius:12px">
        <div class="card-header d-flex align-items:center; justify-content:space-between" style="gap:8px; flex-wrap:wrap">
          <div>
            <strong style="font-size:14px">Выбор иконки</strong>
            <span class="text-muted ms-2" style="font-size:11px">2 шрифта — bi и fas</span>
          </div>
          <div class="ms-auto d-flex gap-2 align-items-center">
            <input v-model="iconQ" placeholder="поиск: journal, book, palette…" class="form-control form-control-sm" style="width:220px" />
            <button class="btn btn-sm btn-light" @click="iconPickerOpen=false">Закрыть</button>
          </div>
        </div>
        <div style="padding:8px 12px; border-bottom:1px solid #eee; display:flex; gap:6px">
          <button :class="['btn btn-sm', iconTab==='bi' ? 'btn-primary':'btn-outline-secondary']" @click="iconTab='bi'">Bootstrap Icons ({{ filteredBi.length }}) <i class="bi bi-journal-text ms-1"></i></button>
          <button :class="['btn btn-sm', iconTab==='fa' ? 'btn-primary':'btn-outline-secondary']" @click="iconTab='fa'">Font Awesome ({{ filteredFa.length }}) <i class="fas fa-star ms-1"></i></button>
          <span class="ms-auto badge bg-light text-dark border" style="align-self:center; font-size:11px">выбрано: <i :class="form.icon"></i> {{ form.icon }}</span>
        </div>
        <div style="overflow:auto; padding:10px; flex:1 1 auto">
          <div v-if="iconTab==='bi'" class="icon-grid">
            <button v-for="ic in filteredBi" :key="ic" @click="form.icon=ic; iconPickerOpen=false" :class="['icon-cell', form.icon===ic ? 'active':'']" :title="ic"><i :class="ic"></i><span>{{ ic.replace('bi bi-','') }}</span></button>
          </div>
          <div v-else class="icon-grid">
            <button v-for="ic in filteredFa" :key="ic" @click="form.icon=ic; iconPickerOpen=false" :class="['icon-cell', form.icon===ic ? 'active':'']" :title="ic"><i :class="ic"></i><span>{{ ic.replace('fas fa-','') }}</span></button>
          </div>
          <div v-if="(iconTab==='bi' ? filteredBi : filteredFa).length===0" class="text-muted text-center p-4" style="font-size:12px">Ничего не найдено.</div>
        </div>
        <div class="card-footer text-muted" style="font-size:11px">Подключены CDN: bootstrap-icons 1.11.3 + font-awesome 6.5.2 (index.html). В WbFilterBar рендер <code>&lt;i :class="icon"&gt;</code>.</div>
      </div>
    </div>

    <div class="text-muted mt-3" style="font-size:11px">
      Хранится в <code>backend/config/quick_buttons.json</code> массива <code>{icon,label,nm_id}</code>. Доступен как <code>GET /api/config/quick-buttons</code> и используется в <code>WbFilterBar.vue:5</code> (<code>panel-btns/btn-panel</code>). Для сохранения — <code>PUT /api/config/quick-buttons</code>.
    </div>
  </div>
</template>
<script setup lang="ts">
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
.icon-grid{ display:grid; grid-template-columns: repeat(auto-fill, minmax(110px,1fr)); gap:6px }
.icon-cell{ display:flex; flex-direction:column; align-items:center; gap:4px; padding:8px 4px; border:1px solid #e5e7eb; border-radius:8px; background:#fff; cursor:pointer; font-size:11px; transition:all .15s }
.icon-cell i{ font-size:18px }
.icon-cell span{ font-size:9px; color:#6b7280; word-break:break-all; text-align:center }
.icon-cell:hover{ border-color:#a73afd; background:#f5f0ff }
.icon-cell.active{ border-color:#a73afd; background:#a73afd; color:#fff }
.icon-cell.active span{ color:#fff }
</style>
