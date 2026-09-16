<template>
  <div class="container-xxl page-admin-menu">
    <nav aria-label="breadcrumb" class="page-admin-menu__crumbs">
      <ol class="breadcrumb page-admin-menu__crumbs-list">
        <li class="breadcrumb-item"><router-link to="/">Главная</router-link></li>
        <li class="breadcrumb-item">Админка</li>
        <li class="breadcrumb-item active">Меню</li>
      </ol>
    </nav>
    <div class="page-admin-menu__head">
      <h1 class="page-admin-menu__title">Меню <span class="text-muted page-admin-menu__title-sub">config / menu.json</span></h1>
      <div class="d-flex gap-2">
        <span class="badge bg-light text-dark border page-admin-menu__count">{{ sections.length }} разделов</span>
        <button class="btn btn-sm btn-outline-secondary" @click="reload" :disabled="loading">Перезагрузить</button>
        <button class="btn btn-sm btn-primary" @click="save" :disabled="saving"><span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>Сохранить в menu.json</button>
      </div>
    </div>

    <div v-if="msg" :class="['alert', msgOk?'alert-success':'alert-danger', 'page-admin-menu__msg']">{{ msg }}</div>

    <!-- предпросмотр как TopNavbar — упрощён, без каши -->
    <div class="card mb-3 page-admin-menu__preview-card">
      <div class="card-header d-flex justify-content-between align-items-center page-admin-menu__preview-head">
        <span>Предпросмотр (как TopNavbar)</span>
        <span class="text-muted page-admin-menu__preview-meta">bg-wb · {{ sections.length }} разделов · {{ sections.reduce((s:number,sec:any)=>s+sec.items.filter((x:any)=>!x.divider).length,0) }} пунктов · иконки bi/fas</span>
      </div>
      <div class="card-body page-admin-menu__preview-body">
        <nav class="navbar bg-wb w-100 page-admin-menu__preview-nav">
          <span class="navbar-brand d-flex align-items-center page-admin-menu__preview-brand"><span class="page-admin-menu__preview-brand-mark">◈</span>Аналитика WB</span>
          <div class="page-admin-menu__preview-sections">
            <div v-for="sec in sections" :key="sec.label" class="page-admin-menu__preview-section">
              <i :class="sectionIconClass(sec)" class="page-admin-menu__preview-icon"></i>
              <span class="page-admin-menu__preview-label">{{ sec.label }}</span>
              <span class="page-admin-menu__preview-sub">{{ sec.items.filter((x:any)=>!x.divider).length }} п.</span>
            </div>
          </div>
        </nav>
        <div class="page-admin-menu__preview-note">Иконки <code>bi …</code>/<code>fas fa-…</code> · детальный список пунктов — в карточках ниже.</div>
      </div>
    </div>

    <div v-if="loading" class="text-center p-4"><span class="spinner-border spinner-border-sm"></span> Загрузка меню…</div>
    <template v-else>
      <div v-for="(sec, si) in sections" :key="sec._key" class="card mb-3 page-admin-menu__section-card">
        <div class="card-header d-flex align-items-center gap-2 page-admin-menu__section-head">
          <button class="btn btn-sm btn-outline-secondary" :disabled="si===0" @click="moveSection(si,-1)" title="вверх"><i class="bi bi-chevron-up"></i></button>
          <button class="btn btn-sm btn-outline-secondary" :disabled="si===sections.length-1" @click="moveSection(si,1)" title="вниз"><i class="bi bi-chevron-down"></i></button>
          <span class="badge bg-light text-dark border page-admin-menu__section-num">#{{ si+1 }}</span>
          <i :class="sectionIconClass(sec)" class="wb-icon page-admin-menu__section-icon"></i>
          <input v-model="sec.label" class="form-control form-control-sm page-admin-menu__section-name" style="width:200px" placeholder="Название раздела" />
          <div class="input-group input-group-sm" style="width:220px">
            <span class="input-group-text"><i :class="sectionIconClass(sec)" class="page-admin-menu__section-icon-sm"></i></span>
            <input class="form-control" :value="sectionIconClass(sec)" readonly />
            <button class="btn btn-outline-primary" @click="openIconPicker(sec)">Выбрать</button>
          </div>
          <input v-model="sec.url" class="form-control form-control-sm" style="width:90px" placeholder="url" />
          <label class="form-check form-check-inline mb-0 page-admin-menu__vis"><input class="form-check-input" type="checkbox" :checked="hasVis(sec,'top')" @change="toggleVis(sec,'top')"> top</label>
          <label class="form-check form-check-inline mb-0 page-admin-menu__vis"><input class="form-check-input" type="checkbox" :checked="hasVis(sec,'side')" @change="toggleVis(sec,'side')"> side</label>
          <input :value="(sec.roles||[]).join(', ')" @input="sec.roles = ($event.target as HTMLInputElement).value.split(',').map((s:string)=>s.trim()).filter(Boolean)" class="form-control form-control-sm" style="width:160px" placeholder="roles: admin, viewReports" />
          <div class="ms-auto d-flex gap-1">
            <button class="btn btn-sm btn-outline-secondary" @click="sec._collapsed=!sec._collapsed">{{ sec._collapsed ? 'Развернуть' : 'Свернуть' }}</button>
            <button class="btn btn-sm btn-outline-primary" @click="duplicateSection(si)">Дубль</button>
            <button class="btn btn-sm btn-outline-danger" @click="removeSection(si)">×</button>
          </div>
        </div>

        <div v-show="!sec._collapsed" class="page-admin-menu__section-body">
          <div class="table-responsive">
            <table class="table table-sm table-hover mb-0 page-admin-menu__table">
              <thead class="page-admin-menu__table-head">
                <tr>
                  <th style="width:30px">#</th>
                  <th style="width:36px"></th>
                  <th>Подпись / разделитель</th>
                  <th>URL</th>
                  <th style="width:110px">Видимость</th>
                  <th style="width:170px">Роли</th>
                  <th style="width:140px; text-align:right">Действия</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="!sec.items.length"><td colspan="7" class="text-center text-muted p-2">Нет пунктов</td></tr>
                <tr v-for="(it, ii) in sec.items" :key="ii" :class="{'table-light': it.divider}">
                  <td class="text-muted text-center">{{ ii+1 }}</td>
                  <td class="text-center">
                    <span v-if="it.divider" class="badge bg-secondary page-admin-menu__mini-note">—</span>
                    <i v-else class="bi bi-link-45deg"></i>
                  </td>
                  <td>
                    <div v-if="it.divider" class="text-muted page-admin-menu__item-note">— разделитель —</div>
                    <input v-else v-model="it.label" class="form-control form-control-sm" placeholder="ТОП продаж" />
                  </td>
                  <td>
                    <span v-if="it.divider" class="text-muted page-admin-menu__mini-note">—</span>
                    <input v-else v-model="it.url" class="form-control form-control-sm" placeholder="/wb/path?nm_id=..." />
                  </td>
                  <td>
                    <label class="form-check form-check-inline mb-0 page-admin-menu__vis page-admin-menu__vis--sm"><input class="form-check-input" type="checkbox" :checked="hasVis(it,'top')" @change="toggleVis(it,'top')"> top</label>
                    <label class="form-check form-check-inline mb-0 page-admin-menu__vis page-admin-menu__vis--sm"><input class="form-check-input" type="checkbox" :checked="hasVis(it,'side')" @change="toggleVis(it,'side')"> side</label>
                  </td>
                  <td>
                    <input v-if="!it.divider" :value="(it.roles||[]).join(', ')" @input="it.roles = ($event.target as HTMLInputElement).value.split(',').map((s:string)=>s.trim()).filter(Boolean); if(!it.roles.length) delete it.roles" class="form-control form-control-sm" placeholder="viewReports, admin" />
                    <span v-else class="text-muted page-admin-menu__mini-note">—</span>
                  </td>
                  <td class="page-admin-menu__actions">
                    <div class="btn-group btn-group-sm">
                      <button class="btn btn-outline-secondary" :disabled="ii===0" @click="moveItem(si,ii,-1)"><i class="bi bi-chevron-up"></i></button>
                      <button class="btn btn-outline-secondary" :disabled="ii===sec.items.length-1" @click="moveItem(si,ii,1)"><i class="bi bi-chevron-down"></i></button>
                    </div>
                    <button class="btn btn-sm btn-outline-danger ms-1" @click="removeItem(si,ii)">×</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="page-admin-menu__row-add">
            <button class="btn btn-sm btn-outline-primary" @click="addItem(si,false)"><i class="bi bi-plus-lg me-1"></i>Пункт</button>
            <button class="btn btn-sm btn-outline-secondary" @click="addItem(si,true)">+ Разделитель</button>
            <span class="ms-auto text-muted page-admin-menu__row-hint">url `#` для заголовка раздела · разделитель = <code>{"divider":true}</code></span>
          </div>
        </div>
      </div>

      <div class="d-flex gap-2 mb-3">
        <button class="btn btn-outline-primary" @click="addSection"><i class="bi bi-plus-lg me-1"></i>Добавить раздел</button>
        <button class="btn btn-outline-secondary ms-auto" @click="reload" :disabled="saving">Сбросить</button>
        <button class="btn btn-primary" @click="save" :disabled="saving"><span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>Сохранить в menu.json</button>
      </div>

      <div class="card page-admin-menu__json-card">
        <div class="card-header page-admin-menu__json-head">Сырой JSON (для копипасты)</div>
        <div class="card-body p-0">
          <textarea class="form-control page-admin-menu__json-area" :value="jsonPreview" readonly></textarea>
        </div>
      </div>

      <div class="text-muted mt-2 page-admin-menu__foot">
        Файл <code>backend/config/menu.json</code> — массив разделов <code>{label,icon,iconClass,url,visibleIn,roles,items}</code>. API <code>GET /api/config/menu</code> (raw) и <code>PUT /api/config/menu</code>. Фильтрация для фронта — <code>GET /api/menu?type=top|side&role=...</code> как <code>MenuHelper.php:40</code>.
      </div>

      <!-- пикер иконок -->
      <div v-if="iconPickerOpen" class="page-admin-menu__picker-backdrop" @click.self="iconPickerOpen=false">
        <div class="card page-admin-menu__picker-card">
          <div class="card-header d-flex align-items:center; justify-content:space-between page-admin-menu__picker-head">
            <div>
              <strong class="page-admin-menu__picker-title">Выбор иконки раздела</strong>
              <span class="text-muted ms-2 page-admin-menu__picker-sub">2 шрифта — bi и fas</span>
            </div>
            <div class="ms-auto d-flex gap-2 align-items-center">
              <input v-model="iconQ" placeholder="поиск: journal, book, palette…" class="form-control form-control-sm page-admin-menu__picker-search" />
              <button class="btn btn-sm btn-light" @click="iconPickerOpen=false">Закрыть</button>
            </div>
          </div>
          <div class="page-admin-menu__picker-tabs">
            <button :class="['btn btn-sm', iconTab==='bi' ? 'btn-primary':'btn-outline-secondary']" @click="iconTab='bi'">Bootstrap Icons ({{ filteredBi.length }}) <i class="bi bi-journal-text ms-1"></i></button>
            <button :class="['btn btn-sm', iconTab==='fa' ? 'btn-primary':'btn-outline-secondary']" @click="iconTab='fa'">Font Awesome ({{ filteredFa.length }}) <i class="fas fa-star ms-1"></i></button>
            <span class="ms-auto badge bg-light text-dark border page-admin-menu__picker-pick">выбрано: <i :class="iconPickerValue"></i> {{ iconPickerValue }}</span>
          </div>
          <div class="page-admin-menu__picker-body">
            <div v-if="iconTab==='bi'" class="icon-grid">
              <button v-for="ic in filteredBi" :key="ic" @click="selectIcon(ic)" :class="['icon-cell', iconPickerValue===ic ? 'active':'']" :title="ic"><i :class="ic"></i><span>{{ ic.replace('bi bi-','') }}</span></button>
            </div>
            <div v-else class="icon-grid">
              <button v-for="ic in filteredFa" :key="ic" @click="selectIcon(ic)" :class="['icon-cell', iconPickerValue===ic ? 'active':'']" :title="ic"><i :class="ic"></i><span>{{ ic.replace('fas fa-','') }}</span></button>
            </div>
            <div v-if="(iconTab==='bi' ? filteredBi : filteredFa).length===0" class="text-muted text-center p-4 page-admin-menu__picker-empty">Ничего не найдено.</div>
          </div>
          <div class="card-footer text-muted page-admin-menu__picker-foot">Иконка сохранится в <code>iconClass</code> выбранного раздела menu.json.</div>
        </div>
      </div>
    </template>
  </div>
</template>
<script setup lang="ts">
import '@/assets/css/pages/page-admin-menu.css'
import { ref, computed, onMounted } from 'vue'
import { dashboardApi } from '../api/dashboard'

const sections = ref<any[]>([])
const loading = ref(false)
const saving = ref(false)
const msg = ref('')
const msgOk = ref(true)

const legacyIconMap: Record<string,string> = {
  reports: 'bi bi-bar-chart',
  by_search: 'bi bi-search',
  tag: 'bi bi-tag',
  product: 'bi bi-box',
  chat: 'bi bi-chat',
  data: 'bi bi-pie-chart',
  warehouse: 'bi bi-box-seam',
  book: 'bi bi-book',
  gear: 'bi bi-gear'
}
const fallbackIcons = { bi: ['bi bi-search', 'bi bi-chat'], fa: [] }
const iconPickerOpen = ref(false)
const iconPickerSection = ref<any>(null)
const iconPickerValue = ref('')
const iconTab = ref<'bi'|'fa'>('bi')
const iconQ = ref('')
const icons = ref<{bi:string[], fa:string[]}>({bi: [], fa: []})

const filteredBi = computed(()=>{
  const q = iconQ.value.toLowerCase().trim()
  if(!q) return icons.value.bi
  return icons.value.bi.filter((x:string)=> x.toLowerCase().includes(q))
})
const filteredFa = computed(()=>{
  const q = iconQ.value.toLowerCase().trim()
  if(!q) return icons.value.fa
  return icons.value.fa.filter((x:string)=> x.toLowerCase().includes(q))
})

function sectionIconClass(sec:any){
  const value = sec?.iconClass || sec?.icon || ''
  if(!value) return 'bi bi-journal-text'
  if(/^(bi(?:\s|$)|(?:fas|fa)\s)/.test(value)) return value
  return legacyIconMap[value] || value
}

async function loadIcons(){
  try{
    const d:any = await dashboardApi.icons()
    icons.value = {
      bi: Array.from(new Set([...(d?.bi||[]), ...(fallbackIcons.bi||[])])),
      fa: Array.from(new Set([...(d?.fa||[]), ...(fallbackIcons.fa||[])]))
    }
  }catch{
    icons.value = { bi: fallbackIcons.bi, fa: fallbackIcons.fa }
  }
}
async function openIconPicker(sec:any){
  await loadIcons()
  iconPickerSection.value = sec
  iconPickerValue.value = sectionIconClass(sec)
  iconTab.value = iconPickerValue.value.startsWith('fas') ? 'fa' : 'bi'
  iconPickerOpen.value = true
}
function selectIcon(ic:string){
  if(!iconPickerSection.value) return
  iconPickerSection.value.iconClass = ic
  iconPickerValue.value = ic
  iconPickerOpen.value = false
}

const jsonPreview = computed(()=> JSON.stringify(sections.value.map(({_key,_collapsed, ...rest}:any)=> rest), null, 2))

function hasVis(obj:any, where:string){ const v=obj.visibleIn; if(!Array.isArray(v)) return true; return v.includes(where) }
function toggleVis(obj:any, where:string){
  if(!Array.isArray(obj.visibleIn)) obj.visibleIn=['top','side']
  const idx=obj.visibleIn.indexOf(where)
  if(idx>=0) obj.visibleIn.splice(idx,1)
  else obj.visibleIn.push(where)
  if(!obj.visibleIn.length) obj.visibleIn=['top']
}

async function reload(){
  loading.value=true; msg.value=''
  try{
    const data = await dashboardApi.menuRaw()
    sections.value = (Array.isArray(data)?data:[]).map((s:any,i:number)=> ({_key: `${Date.now()}_${i}`, _collapsed:false, url:s.url||'#', visibleIn: s.visibleIn||['top','side'], roles:s.roles||[], ...s, items: (s.items||[]).map((it:any)=> ({visibleIn: it.visibleIn||['top','side'], ...it})) }))
    msg.value=''; msgOk.value=true
  }catch(e:any){ msg.value='Ошибка загрузки: '+String(e?.response?.data?.detail||e); msgOk.value=false }
  finally{ loading.value=false }
}
function addSection(){
  sections.value.push({_key:`${Date.now()}`, _collapsed:false, label:'Новый раздел', icon:'book', iconClass:'bi bi-book', url:'#', visibleIn:['top','side'], roles:['admin'], items:[]})
}
function duplicateSection(si:number){
  const copy = JSON.parse(JSON.stringify(sections.value[si])); copy._key=`${Date.now()}_${si}`; copy.label+=' (копия)'; sections.value.splice(si+1,0,copy)
}
function removeSection(si:number){
  if(!confirm(`Удалить раздел «${sections.value[si].label}»?`)) return
  sections.value.splice(si,1)
}
function moveSection(si:number, dir:number){
  const j=si+dir; if(j<0||j>=sections.value.length) return; const t=sections.value[si]; sections.value[si]=sections.value[j]; sections.value[j]=t
}
function addItem(si:number, divider:boolean){
  if(divider) sections.value[si].items.push({divider:true, visibleIn:['top','side']})
  else sections.value[si].items.push({label:'Новый пункт', url:'/new/path', visibleIn:['top','side']})
}
function removeItem(si:number, ii:number){ sections.value[si].items.splice(ii,1) }
function moveItem(si:number, ii:number, dir:number){
  const arr=sections.value[si].items; const j=ii+dir; if(j<0||j>=arr.length) return; const t=arr[ii]; arr[ii]=arr[j]; arr[j]=t
}

async function save(){
  saving.value=true; msg.value=''
  try{
    const payload = sections.value.map(({_key,_collapsed, ...rest}:any)=> {
      const sec:any = {...rest}
      // чистим пустые роли
      if(!sec.roles || !sec.roles.length) delete sec.roles
      sec.items = sec.items.map((it:any)=>{
        const c:any={...it}
        if(c.divider){ // оставляем только divider+visibleIn
          const out:any={divider:true}
          if(c.visibleIn) out.visibleIn=c.visibleIn
          return out
        }
        if(!c.roles || !c.roles.length) delete c.roles
        return c
      })
      return sec
    })
    await dashboardApi.saveMenu(payload)
    msg.value=`Сохранено ${payload.length} разделов в menu.json`; msgOk.value=true
  }catch(e:any){ msg.value='Ошибка сохранения: '+(e?.response?.data?.detail || String(e)); msgOk.value=false }
  finally{ saving.value=false }
}

onMounted(()=>{ reload(); loadIcons() })
</script>
export default {
  name: 'AdminMenu'
}
