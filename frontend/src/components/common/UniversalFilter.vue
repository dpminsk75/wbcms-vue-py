<template>
  <div class="row card shadow p-3" style="border:1px solid #e5e7eb; border-radius:12px;">
    <div v-if="quickButtons.length" class="row mb-3 panel-btns">
      <div class="col-12" style="display:flex; flex-wrap:wrap; gap:8px;">
        <button v-for="btn in quickButtons" :key="btn.nm_id || btn.value" class="btn btn-panel" @click="onQuickClick(btn)"><i v-if="btn.icon" :class="btn.icon"></i> {{ btn.label }}</button>
      </div>
    </div>

    <div class="row mb-3 wbcard_filter-section">
      <div class="col-12">
        <label style="font-size:12px; font-weight:600">{{ label }}:</label>
        <div style="position:relative" ref="selectWrapRef">
          <!-- 1в1 kartik Select2 как в универсальный dp-view.php: строка + дропдаун с поиском, клик по строке → компании + строка фильтрации -->
          <div class="form-control" @click="toggleList" style="width:100%; height:38px; display:flex; align-items:center; justify-content:space-between; cursor:pointer; background:#fff;" :style="{borderColor: showList ? '#86b7fe' : '#dee2e6', boxShadow: showList ? '0 0 0 0.25rem rgba(13,110,253,.25)' : 'none'}">
            <span style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-size:12px;" :style="{color: selectedLabel ? '#212529' : '#6c757d'}">{{ selectedLabel || placeholder }}</span>
            <span style="display:flex; align-items:center; gap:6px; flex-shrink:0;">
              <i v-if="modelValue" class="bi bi-x-circle" style="color:#adb5bd; cursor:pointer;" @click.stop="onReset" title="Очистить"></i>
              <i class="bi" :class="showList ? 'bi-chevron-up' : 'bi-chevron-down'" style="color:#6c757d;"></i>
            </span>
          </div>
          <div v-if="showList" style="position:absolute; top:100%; left:0; right:0; background:#fff; border:1px solid #86b7fe; border-top:none; border-radius:0 0 6px 6px; z-index:10; box-shadow:0 4px 12px rgba(0,0,0,.15)">
            <div style="padding:6px; border-bottom:1px solid #e9ecef; position:relative">
              <input v-model="searchQuery" placeholder="Поиск..." class="form-control" style="height:32px; font-size:12px; padding-right:30px;" ref="searchInputRef" @keydown.esc="showList=false" />
              <i class="bi bi-search" style="position:absolute; right:14px; top:50%; transform:translateY(-50%); color:#adb5bd; font-size:12px;"></i>
            </div>
            <div style="max-height:240px; overflow:auto;">
              <div v-if="!filteredOptions.length" style="padding:10px; font-size:12px; color:#6c757d; text-align:center;">Ничего не найдено</div>
              <div v-for="opt in filteredOptions.slice(0,50)" :key="String(opt.value)" @mousedown.prevent="selectOption(opt)" style="padding:6px 10px; cursor:pointer; font-size:12px; border-bottom:1px solid #f1f5f9" :style="{background: String(opt.value)===String(modelValue) ? '#0d6efd' : '#fff', color: String(opt.value)===String(modelValue) ? '#fff' : '#212529'}">
                {{ opt.label }}
              </div>
            </div>
          </div>
        </div>
        <div v-if="modelValue" style="margin-top:4px; font-size:11px; color:#7c1af8">Выбрано: {{ modelValue }}</div>
      </div>
    </div>

    <div class="row mb-3 d-flex flex-row flex-nowrap justify-content-between align-items-center">
      <div class="form__input-dates col-md-6">
        <label style="display:block; font-size:12px; font-weight:600">Период с / по</label>
        <div style="display:flex; gap:8px; align-items:center;">
          <input :value="dateFrom" @input="emit('update:dateFrom', ($event.target as HTMLInputElement).value)" type="date" class="form-control" style="height:38px; flex:1" />
          <span>|</span>
          <input :value="dateTo" @input="emit('update:dateTo', ($event.target as HTMLInputElement).value)" type="date" class="form-control" style="height:38px; flex:1" />
        </div>
      </div>
      <div class="col-md-6 btn-group" style="height:38px; margin-top:18px;">
        <button type="button" class="btn btn-outline-secondary btn-sm" @click="setRange('quarter')" title="Минус квартал">-Q</button>
        <button type="button" class="btn btn-outline-secondary btn-sm" @click="setRange('year')" title="Минус год">-Y</button>
        <button type="button" class="btn btn-outline-secondary btn-sm" @click="setRange('last_year')" title="Прошлый год">LY</button>
        <button type="button" class="btn btn-outline-secondary btn-sm" @click="setRange('today')" title="По сегодня">TD</button>
      </div>
    </div>

    <div class="row form-group"><div class="col-auto" style="display:flex; gap:8px;">
      <button class="btn btn-primary" style="min-width:120px" @click="emit('apply')">Применить</button>
      <button class="btn btn-light" style="min-width:120px" @click="onReset">Сбросить</button>
    </div></div>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'

const props = withDefaults(defineProps<{
  label?: string
  placeholder?: string
  data?: any[] // массив {value,label} или {campaign_id,label} или строк
  attribute?: string
  ajaxUrl?: string | null
  initValueText?: string
  quickButtons?: any[]
  defaultDays?: number
}>(), {
  label: 'Выбор',
  placeholder: 'Выберите...',
  data: () => [],
  attribute: 'value',
  ajaxUrl: null,
  initValueText: '',
  quickButtons: () => [],
  defaultDays: 30,
})

const modelValue = defineModel<string>('modelValue', { default: '' })
const dateFrom = defineModel<string>('dateFrom', { default: '' })
const dateTo = defineModel<string>('dateTo', { default: '' })

const emit = defineEmits<{
  (e:'update:modelValue', v:string): void
  (e:'update:dateFrom', v:string): void
  (e:'update:dateTo', v:string): void
  (e:'apply'): void
  (e:'reset'): void
}>()

const selectWrapRef = ref<HTMLDivElement|null>(null)
const searchInputRef = ref<HTMLInputElement|null>(null)
const searchQuery = ref('')
const showList = ref(false)

// нормализуем data в {value,label}
const normalizedOptions = computed(()=>{
  return (props.data||[]).map((row:any)=>{
    if(row && typeof row === 'object'){
      const v = row.value ?? row.campaign_id ?? row.nm_id ?? row.id ?? row[props.attribute]
      const l = row.label ?? row.title ?? row.name ?? String(v)
      return {value: String(v ?? ''), label: String(l), raw: row}
    }
    return {value: String(row), label: String(row), raw: row}
  })
})

const selectedLabel = computed(()=>{
  if(!modelValue.value) return ''
  const found = normalizedOptions.value.find(o=> String(o.value)===String(modelValue.value))
  return found ? found.label : String(modelValue.value)
})

const filteredOptions = computed(()=>{
  const q = searchQuery.value.toLowerCase().trim()
  if(!q) return normalizedOptions.value
  return normalizedOptions.value.filter(opt =>
    opt.label.toLowerCase().includes(q) || opt.value.toLowerCase().includes(q)
  )
})

const toggleList = ()=>{
  showList.value = !showList.value
  if(showList.value){
    searchQuery.value = ''
    setTimeout(()=> searchInputRef.value?.focus(), 50)
  }
}

const selectOption = (opt:any)=>{
  modelValue.value = String(opt.value)
  showList.value = false
  searchQuery.value = ''
}

const onQuickClick = (btn:any)=>{
  const v = btn.nm_id ?? btn.value ?? btn.id
  if(v) { modelValue.value = String(v); selectQuery.value = btn.label || String(v) }
  emit('apply')
}

const setRange = (p:string)=>{
  // 1в1 WbFilterBar.vue:setRange — TD меняет только date_to, LY = прошлый год целиком
  const fmtD=(d:Date)=> `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`
  const parseD=(s:string)=>{ const m=/^(\d{4})-(\d{2})-(\d{2})$/.exec(s||''); return m ? new Date(+m[1], +m[2]-1, +m[3]) : new Date() }
  const to = dateTo.value ? parseD(dateTo.value) : new Date()
  let from = new Date(to)
  if(p==='year'){ from.setFullYear(to.getFullYear()-1); from.setDate(from.getDate()+1)}
  else if(p==='quarter'){ from.setMonth(to.getMonth()-3); from.setDate(from.getDate()+1)}
  else if(p==='today'){ dateTo.value=fmtD(new Date()); return }
  else if(p==='last_year'){ const y=to.getFullYear()-1; from=new Date(y,0,1); dateTo.value=fmtD(new Date(y,11,31)); dateFrom.value=fmtD(from); return }
  dateFrom.value = fmtD(from)
}

const onReset = ()=>{
  modelValue.value=''
  searchQuery.value=''
  showList.value=false
  emit('reset')
}

const onDocClick = (e:MouseEvent)=>{
  if(!showList.value) return
  const el = selectWrapRef.value
  if(el && !el.contains(e.target as Node)) showList.value=false
}

onMounted(()=> document.addEventListener('mousedown', onDocClick))
onBeforeUnmount(()=> document.removeEventListener('mousedown', onDocClick))
</script>
