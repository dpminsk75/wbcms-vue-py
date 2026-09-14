<template>
  <div class="container" style="padding:20px 15px; max-width:1200px">
    <nav aria-label="breadcrumb" style="margin-bottom:12px">
      <ol class="breadcrumb" style="font-size:12px">
        <li class="breadcrumb-item"><router-link to="/">Главная</router-link></li>
        <li class="breadcrumb-item">Админка</li>
        <li class="breadcrumb-item active">Меню</li>
      </ol>
    </nav>
    <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:12px">
      <h1 style="font-size:22px; font-weight:700; margin:0">Меню <span class="text-muted" style="font-weight:400; font-size:13px">config / menu.json</span></h1>
      <div class="d-flex gap-2">
        <span class="badge bg-light text-dark border" style="align-self:center; font-size:11px">{{ sections.length }} разделов</span>
        <button class="btn btn-sm btn-outline-secondary" @click="reload" :disabled="loading">Перезагрузить</button>
        <button class="btn btn-sm btn-primary" @click="save" :disabled="saving"><span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>Сохранить в menu.json</button>
      </div>
    </div>

    <div v-if="msg" :class="['alert', msgOk?'alert-success':'alert-danger']" style="font-size:13px; padding:8px 12px">{{ msg }}</div>

    <!-- предпросмотр как TopNavbar — упрощён, без каши -->
    <div class="card mb-3" style="border:1px solid #e0e0e0; border-radius:12px; overflow:hidden">
      <div class="card-header d-flex justify-content-between align-items-center" style="background:#f8f9fa; font-size:12px; font-weight:600">
        <span>Предпросмотр (как TopNavbar)</span>
        <span class="text-muted" style="font-weight:400">bg-wb · {{ sections.length }} разделов · {{ sections.reduce((s:number,sec:any)=>s+sec.items.filter((x:any)=>!x.divider).length,0) }} пунктов · иконки bi/fas</span>
      </div>
      <div class="card-body" style="padding:0">
        <nav class="navbar bg-wb w-100" style="padding:6px 12px; flex-wrap:nowrap; overflow-x:auto; gap:8px">
          <span class="navbar-brand d-flex align-items-center" style="color:#fff; font-weight:700; font-size:13px; white-space:nowrap; margin-right:12px"><span style="margin-right:6px">◈</span>Аналитика WB</span>
          <div style="display:flex; gap:6px; flex-wrap:nowrap; align-items:flex-start">
            <div v-for="sec in sections" :key="sec.label" style="display:flex; flex-direction:column; align-items:center; color:#fff; font-size:10px; text-align:center; min-width:72px; max-width:90px; opacity:.95">
              <i :class="sectionIconClass(sec)" style="display:flex; align-items:center; justify-content:center; width:28px; height:28px; font-size:16px"></i>
              <span style="margin-top:4px; line-height:11px; font-weight:600; white-space:normal; word-break:break-word">{{ sec.label }}</span>
              <span style="font-size:9px; opacity:.7">{{ sec.items.filter((x:any)=>!x.divider).length }} п.</span>
            </div>
          </div>
        </nav>
        <div style="padding:6px 12px; background:#fafafa; border-top:1px solid #eee; font-size:11px; color:#6b7280">Иконки <code>bi …</code>/<code>fas fa-…</code> · детальный список пунктов — в карточках ниже.</div>
      </div>
    </div>

    <div v-if="loading" class="text-center p-4"><span class="spinner-border spinner-border-sm"></span> Загрузка меню…</div>
    <template v-else>
      <div v-for="(sec, si) in sections" :key="sec._key" class="card mb-3" style="border:1px solid #e0e0e0; border-radius:12px; overflow:hidden">
        <div class="card-header d-flex align-items-center gap-2" style="background:#fff; padding:10px 12px; flex-wrap:wrap">
          <button class="btn btn-sm btn-outline-secondary" :disabled="si===0" @click="moveSection(si,-1)" title="вверх"><i class="bi bi-chevron-up"></i></button>
          <button class="btn btn-sm btn-outline-secondary" :disabled="si===sections.length-1" @click="moveSection(si,1)" title="вниз"><i class="bi bi-chevron-down"></i></button>
          <span class="badge bg-light text-dark border" style="font-size:11px">#{{ si+1 }}</span>
          <i :class="sectionIconClass(sec)" class="wb-icon" style="width:22px; height:22px; display:inline-flex; font-size:16px"></i>
          <input v-model="sec.label" class="form-control form-control-sm" style="width:200px; font-weight:600" placeholder="Название раздела" />
          <div class="input-group input-group-sm" style="width:220px">
            <span class="input-group-text"><i :class="sectionIconClass(sec)" style="font-size:14px"></i></span>
            <input class="form-control" :value="sectionIconClass(sec)" readonly />
            <button class="btn btn-outline-primary" @click="openIconPicker(sec)">Выбрать</button>
          </div>
          <input v-model="sec.url" class="form-control form-control-sm" style="width:90px" placeholder="url" />
          <label class="form-check form-check-inline mb-0" style="font-size:11px"><input class="form-check-input" type="checkbox" :checked="hasVis(sec,'top')" @change="toggleVis(sec,'top')"> top</label>
          <label class="form-check form-check-inline mb-0" style="font-size:11px"><input class="form-check-input" type="checkbox" :checked="hasVis(sec,'side')" @change="toggleVis(sec,'side')"> side</label>
          <input :value="(sec.roles||[]).join(', ')" @input="sec.roles = ($event.target as HTMLInputElement).value.split(',').map((s:string)=>s.trim()).filter(Boolean)" class="form-control form-control-sm" style="width:160px" placeholder="roles: admin, viewReports" />
          <div class="ms-auto d-flex gap-1">
            <button class="btn btn-sm btn-outline-secondary" @click="sec._collapsed=!sec._collapsed">{{ sec._collapsed ? 'Развернуть' : 'Свернуть' }}</button>
            <button class="btn btn-sm btn-outline-primary" @click="duplicateSection(si)">Дубль</button>
            <button class="btn btn-sm btn-outline-danger" @click="removeSection(si)">×</button>
          </div>
        </div>

        <div v-show="!sec._collapsed" style="padding:0">
          <div class="table-responsive">
            <table class="table table-sm table-hover mb-0" style="font-size:12px">
              <thead style="background:#f8f9fa">
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
                    <span v-if="it.divider" class="badge bg-secondary" style="font-size:9px">—</span>
                    <i v-else class="bi bi-link-45deg"></i>
                  </td>
                  <td>
                    <div v-if="it.divider" class="text-muted" style="font-style:italic">— разделитель —</div>
                    <input v-else v-model="it.label" class="form-control form-control-sm" placeholder="ТОП продаж" />
                  </td>
                  <td>
                    <span v-if="it.divider" class="text-muted" style="font-size:11px">—</span>
                    <input v-else v-model="it.url" class="form-control form-control-sm" placeholder="/wb/path?nm_id=..." />
                  </td>
                  <td>
                    <label class="form-check form-check-inline mb-0" style="font-size:10px"><input class="form-check-input" type="checkbox" :checked="hasVis(it,'top')" @change="toggleVis(it,'top')"> top</label>
                    <label class="form-check form-check-inline mb-0" style="font-size:10px"><input class="form-check-input" type="checkbox" :checked="hasVis(it,'side')" @change="toggleVis(it,'side')"> side</label>
                  </td>
                  <td>
                    <input v-if="!it.divider" :value="(it.roles||[]).join(', ')" @input="it.roles = ($event.target as HTMLInputElement).value.split(',').map((s:string)=>s.trim()).filter(Boolean); if(!it.roles.length) delete it.roles" class="form-control form-control-sm" placeholder="viewReports, admin" />
                    <span v-else class="text-muted" style="font-size:11px">—</span>
                  </td>
                  <td style="text-align:right; white-space:nowrap">
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
          <div style="padding:8px 12px; display:flex; gap:6px; background:#fafafa; border-top:1px solid #eee">
            <button class="btn btn-sm btn-outline-primary" @click="addItem(si,false)"><i class="bi bi-plus-lg me-1"></i>Пункт</button>
            <button class="btn btn-sm btn-outline-secondary" @click="addItem(si,true)">+ Разделитель</button>
            <span class="ms-auto text-muted" style="font-size:11px; align-self:center">url `#` для заголовка раздела · разделитель = <code>{"divider":true}</code></span>
          </div>
        </div>
      </div>

      <div class="d-flex gap-2 mb-3">
        <button class="btn btn-outline-primary" @click="addSection"><i class="bi bi-plus-lg me-1"></i>Добавить раздел</button>
        <button class="btn btn-outline-secondary ms-auto" @click="reload" :disabled="saving">Сбросить</button>
        <button class="btn btn-primary" @click="save" :disabled="saving"><span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>Сохранить в menu.json</button>
      </div>

      <div class="card" style="border:1px dashed #ccc; border-radius:12px">
        <div class="card-header" style="background:#fff; font-size:12px; font-weight:600">Сырой JSON (для копипасты)</div>
        <div class="card-body p-0">
          <textarea class="form-control" style="font-family:monospace; font-size:11px; min-height:220px; border:none; border-radius:0 0 12px 12px" :value="jsonPreview" readonly></textarea>
        </div>
      </div>

      <div class="text-muted mt-2" style="font-size:11px">
        Файл <code>backend/config/menu.json</code> — массив разделов <code>{label,icon,iconClass,url,visibleIn,roles,items}</code>. API <code>GET /api/config/menu</code> (raw) и <code>PUT /api/config/menu</code>. Фильтрация для фронта — <code>GET /api/menu?type=top|side&role=...</code> как <code>MenuHelper.php:40</code>.
      </div>

      <!-- пикер иконок -->
      <div v-if="iconPickerOpen" style="position:fixed; inset:0; background:rgba(0,0,0,.35); z-index:1050; display:flex; align-items:center; justify-content:center; padding:12px" @click.self="iconPickerOpen=false">
        <div class="card" style="width:min(920px,100%); max-height:90vh; display:flex; flex-direction:column; border-radius:12px">
          <div class="card-header d-flex align-items:center; justify-content:space-between" style="gap:8px; flex-wrap:wrap">
            <div>
              <strong style="font-size:14px">Выбор иконки раздела</strong>
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
            <span class="ms-auto badge bg-light text-dark border" style="align-self:center; font-size:11px">выбрано: <i :class="iconPickerValue"></i> {{ iconPickerValue }}</span>
          </div>
          <div style="overflow:auto; padding:10px; flex:1 1 auto">
            <div v-if="iconTab==='bi'" class="icon-grid">
              <button v-for="ic in filteredBi" :key="ic" @click="selectIcon(ic)" :class="['icon-cell', iconPickerValue===ic ? 'active':'']" :title="ic"><i :class="ic"></i><span>{{ ic.replace('bi bi-','') }}</span></button>
            </div>
            <div v-else class="icon-grid">
              <button v-for="ic in filteredFa" :key="ic" @click="selectIcon(ic)" :class="['icon-cell', iconPickerValue===ic ? 'active':'']" :title="ic"><i :class="ic"></i><span>{{ ic.replace('fas fa-','') }}</span></button>
            </div>
            <div v-if="(iconTab==='bi' ? filteredBi : filteredFa).length===0" class="text-muted text-center p-4" style="font-size:12px">Ничего не найдено.</div>
          </div>
          <div class="card-footer text-muted" style="font-size:11px">Иконка сохранится в <code>iconClass</code> выбранного раздела menu.json.</div>
        </div>
      </div>
    </template>
  </div>
</template>
<script setup lang="ts">
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
<style scoped>
.bg-wb{ background: linear-gradient(97.26deg,#ed3cca .49%,#df34d2 14.88%,#d02bd9 29.27%,#bf22e1 43.14%,#ae1ae8 57.02%,#9a10f0 70.89%,#8306f7 84.76%,#7c1af8 99.15%),linear-gradient(#0000000d,#0000000d) !important }
.icon-grid{ display:grid; grid-template-columns: repeat(auto-fill, minmax(110px,1fr)); gap:6px }
.icon-cell{ display:flex; flex-direction:column; align-items:center; gap:4px; padding:8px 4px; border:1px solid #e5e7eb; border-radius:8px; background:#fff; cursor:pointer; font-size:11px; transition:all .15s }
.icon-cell i{ font-size:18px }
.icon-cell span{ font-size:9px; color:#6b7280; word-break:break-all; text-align:center }
.icon-cell:hover{ border-color:#a73afd; background:#f5f0ff }
.icon-cell.active{ border-color:#a73afd; background:#a73afd; color:#fff }
.icon-cell.active span{ color:#fff }
</style>
export default {
  name: 'AdminMenu'
}
