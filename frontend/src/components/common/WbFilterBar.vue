<template>
  <div :class="embedded ? '' : 'well div_bordered'" :style="embedded ? '' : 'padding:15px; margin-bottom:16px; background:#fff; border:1px solid #e5e7eb; border-radius:12px'">
    <!-- быстрые кнопки как AdminQuickButtons.php:42 + dp-view.php:17 panel-btns — теперь из backend/config/quick_buttons.json (один пользователь=админ) 1в1 site.css:358 .panel-btns/.btn-panel #a73afd -->
    <div v-if="!embedded && quickButtons.length" class="panel-btns" style="margin-bottom:15px;">
      <button v-for="btn in quickButtons" :key="btn.nm_id" class="btn btn-panel" @click="onQuickClick(btn)" :title="'nm_id ' + btn.nm_id">
        <i v-if="btn.icon" :class="btn.icon"></i> {{ btn.label }}
      </button>
    </div>
    <!-- карточка WB -->
    <div v-if="showCard" style="margin-bottom:12px">
      <label style="font-size:12px; font-weight:600">Карточка WB (артикул):</label>
      <WbCardSelect v-model:nm-id="nmId" placeholder="Выберите артикул..." />
    </div>
    <!-- период: только выбор дат -->
    <div style="display:flex; gap:8px; align-items:center; flex-wrap:nowrap">
      <WbDateInput v-model="dateFrom" style="width:190px; flex:0 0 auto" />
      <span style="flex-shrink:0">|</span>
      <WbDateInput v-model="dateTo" style="width:190px; flex:0 0 auto" />
      <div style="display:flex; gap:4px; height:38px; flex-shrink:0; margin-left:auto">
        <button class="btn btn-outline-secondary btn-sm" @click="setRange('quarter')">-Q</button>
        <button class="btn btn-outline-secondary btn-sm" @click="setRange('year')">-Y</button>
        <button class="btn btn-outline-secondary btn-sm" @click="setRange('last_year')">LY</button>
        <button class="btn btn-outline-secondary btn-sm" @click="setRange('today')">TD</button>
      </div>
    </div>
    <div style="margin-top:12px; display:flex; gap:8px">
      <button class="btn btn-primary" style="width:120px" @click="emit('apply')">Применить</button>
      <button class="btn btn-light" style="width:120px" @click="emit('reset')">Сбросить</button>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api } from '@/api/client'
import WbDateInput from './WbDateInput.vue'
import WbCardSelect from './WbCardSelect.vue'

const props = withDefaults(defineProps<{
  showCard?: boolean
  quickButtonsProp?: any[] | null // если переданы явно — используем их, иначе грузим из /api/config/quick-buttons
  embedded?: boolean // для /wb-adv-report: без внешнего col-md-6/well, только даты+кнопки внутри карточки кампании
}>(), { showCard: true, quickButtonsProp: null, embedded: false })

const nmId = defineModel<string>('nmId', { default: '' })
const dateFrom = defineModel<string>('dateFrom', { default: '' })
const dateTo = defineModel<string>('dateTo', { default: '' })

const emit = defineEmits<{
  (e:'update:nmId', v:string): void
  (e:'update:dateFrom', v:string): void
  (e:'update:dateTo', v:string): void
  (e:'apply'): void
  (e:'reset'): void
}>()

// fallback как в AdminQuickButtons.php:46 — если /api/config/quick-buttons пустой/500, кнопки всё равно покажутся (иконки bi как в site.css, FA не грузим)
const defaultQuickButtons = [
  {icon: 'bi bi-journal-text', label: 'Дневник', nm_id: 526443466},
  {icon: 'bi bi-grid-3x3-gap', label: 'Амигуруми', nm_id: 210001374},
  {icon: 'bi bi-palette', label: 'Амигуруми ч.2', nm_id: 534186046},
  {icon: 'bi bi-scissors', label: 'Бум. лоза', nm_id: 264750923},
]
const quickButtonsStatic = ref<any[]>([...defaultQuickButtons])

const quickButtons = computed(()=> props.quickButtonsProp ?? quickButtonsStatic.value)

const onQuickClick = (btn:any)=>{
  // как в dp-view.php:17 — быстрый выбор карточки, сразу применяем фильтр
  nmId.value = String(btn.nm_id)
  emit('apply')
}

// даты только в локальном времени: toISOString() дает UTC и сдвигает сутки, а new Date('YYYY-MM-DD') парсится как UTC
const fmtD=(d:Date)=> `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`
const parseD=(s:string)=>{ const m=/^(\d{4})-(\d{2})-(\d{2})$/.exec(s||''); return m ? new Date(+m[1], +m[2]-1, +m[3]) : new Date() }

const setRange = (p:string)=>{
  const to = dateTo.value ? parseD(dateTo.value) : new Date()
  let from = new Date(to)
  if(p==='year'){ from.setFullYear(to.getFullYear()-1); from.setDate(from.getDate()+1)}
  else if(p==='quarter'){ from.setMonth(to.getMonth()-3); from.setDate(from.getDate()+1)}
  else if(p==='today'){ dateTo.value=fmtD(new Date()); return } // TD меняет только дату «по»
  else if(p==='last_year'){ const y=to.getFullYear()-1; from=new Date(y,0,1); dateTo.value=fmtD(new Date(y,11,31)); dateFrom.value=fmtD(from); return }
  dateFrom.value = fmtD(from)
}

onMounted(async()=>{
  if(props.quickButtonsProp === null){
    try{
      const { data:d } = await api.get('/api/config/quick-buttons')
      if(Array.isArray(d) && d.length) quickButtonsStatic.value = d
      // если бек вернул [] — оставляем defaultQuickButtons, не затираем
    }catch{}
  }
})
</script>