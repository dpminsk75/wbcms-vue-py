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
      <div style="position:relative" ref="cardWrapRef">
        <input :value="cardQuery" @input="onCardInput($event)" placeholder="Выберите артикул..." class="form-control" style="width:100%" @focus="showCardList=true" @keydown.esc="showCardList=false" />
        <div v-if="showCardList && filteredCards.length" style="position:absolute; top:100%; left:0; right:0; max-height:220px; overflow:auto; background:#fff; border:1px solid #e5e7eb; border-radius:6px; z-index:10; box-shadow:0 4px 12px rgba(0,0,0,.1)">
          <div v-for="c in filteredCards.slice(0,20)" :key="c.nmID" @mousedown.prevent="selectCard(c)" style="padding:6px 10px; cursor:pointer; font-size:12px; border-bottom:1px solid #f1f5f9">
            {{ c.nmID }} | {{ c.title }} | {{ c.vendorCode }}
          </div>
        </div>
      </div>
      <div style="display:flex; gap:8px; align-items:center; margin-top:4px">
        <span v-if="nmId" style="font-size:11px; color:#7c1af8">Выбрано: {{ nmId }}</span>
        <button v-if="nmId || cardQuery" class="btn btn-sm btn-light" style="font-size:11px; padding:2px 8px" @click="clearCard">× Сбросить</button>
        <button v-if="showCardList" class="btn btn-sm btn-outline-secondary" style="font-size:11px; padding:2px 8px" @click="showCardList=false">Закрыть Esc</button>
      </div>
    </div>
    <!-- период: только выбор дат -->
    <div style="display:flex; gap:8px; align-items:center; flex-wrap:nowrap">
      <input :value="dateFrom" @input="emit('update:dateFrom', ($event.target as HTMLInputElement).value)" type="date" class="form-control" style="height:38px; width:150px; flex:0 0 auto" />
      <span style="flex-shrink:0">|</span>
      <input :value="dateTo" @input="emit('update:dateTo', ($event.target as HTMLInputElement).value)" type="date" class="form-control" style="height:38px; width:150px; flex:0 0 auto" />
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
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { api } from '@/api/client'

const props = withDefaults(defineProps<{
  showCard?: boolean
  cards?: any[] // если переданы извне — используем их, иначе грузим сами
  quickButtonsProp?: any[] | null // если переданы явно — используем их, иначе грузим из /api/config/quick-buttons
  embedded?: boolean // для /wb-adv-report: без внешнего col-md-6/well, только даты+кнопки внутри карточки кампании
}>(), { showCard: true, cards: undefined, quickButtonsProp: null, embedded: false })

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

const cardWrapRef = ref<HTMLDivElement|null>(null)
const cardQuery = ref(nmId.value || '')
const showCardList = ref(false)
const innerCards = ref<any[]>([])
// fallback как в AdminQuickButtons.php:46 — если /api/config/quick-buttons пустой/500, кнопки всё равно покажутся (иконки bi как в site.css, FA не грузим)
const defaultQuickButtons = [
  {icon: 'bi bi-journal-text', label: 'Дневник', nm_id: 526443466},
  {icon: 'bi bi-grid-3x3-gap', label: 'Амигуруми', nm_id: 210001374},
  {icon: 'bi bi-palette', label: 'Амигуруми ч.2', nm_id: 534186046},
  {icon: 'bi bi-scissors', label: 'Бум. лоза', nm_id: 264750923},
]
const quickButtonsStatic = ref<any[]>([...defaultQuickButtons])

const cardsSource = computed(()=> props.cards ?? innerCards.value)
const quickButtons = computed(()=> props.quickButtonsProp ?? quickButtonsStatic.value)

const filteredCards = computed(()=>{
  const q = cardQuery.value.toLowerCase().trim()
  if(!q) return cardsSource.value
  return cardsSource.value.filter((c:any)=> String(c.nmID).includes(q) || String(c.vendorCode||'').toLowerCase().includes(q) || String(c.title||'').toLowerCase().includes(q))
})

const onCardInput = (e: Event)=>{
  cardQuery.value = (e.target as HTMLInputElement).value
  showCardList.value = true
  // если стирают — сбрасываем nmId
  if(!cardQuery.value) nmId.value = ''
}

const selectCard = (c:any)=>{
  nmId.value = String(c.nmID)
  cardQuery.value = `${c.nmID} | ${c.title}`
  showCardList.value=false
}
const clearCard = ()=>{
  nmId.value=''; cardQuery.value=''; showCardList.value=false
}
const onQuickClick = (btn:any)=>{
  nmId.value = String(btn.nm_id)
  cardQuery.value = `${btn.nm_id} | ${btn.label}`
  showCardList.value=false
  // как в dp-view.php:17 — быстрый выбор карточки, сразу применяем фильтр
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

// синхронизация внешнего nmId -> cardQuery (выбор, URL, F5)
const cardTitleCache = ref<Record<string,string>>({})
const syncCardLabel=async()=>{
  const id=String(nmId.value||'')
  if(!id){ if(!showCardList.value) cardQuery.value=''; return }
  const c=cardsSource.value.find((x:any)=> String(x.nmID)===id)
  if(c){ cardQuery.value = c.title ? `${c.nmID} | ${c.title}` : String(c.nmID); return }
  if(cardQuery.value && cardQuery.value!==id) return // пользователь что-то ввел — не трогаем
  if(cardTitleCache.value[id]){ cardQuery.value=`${id} | ${cardTitleCache.value[id]}`; return }
  try{
    const { data:d } = await api.get(`/api/wb/card/${id}`)
    if(d?.title){ cardTitleCache.value[id]=d.title; if(String(nmId.value)===id) cardQuery.value=`${id} | ${d.title}`; return }
  }catch{}
  if(!cardQuery.value) cardQuery.value=id
}
watch(()=> nmId.value, syncCardLabel)
watch(cardsSource, ()=>{ if(nmId.value) syncCardLabel() })

// клик вне — закрытие списка
const onDocClick = (e: MouseEvent)=>{
  if(!showCardList.value) return
  const el = cardWrapRef.value
  if(el && !el.contains(e.target as Node)) showCardList.value=false
}
onMounted(async()=>{
  document.addEventListener('mousedown', onDocClick)
  if(props.cards === undefined){
    try{
      // пробуем новый эндпоинт /api/wb/cards (все карточки, без ограничения 14д как new-cards), fallback на старый
      let d:any=null
      try{ const r=await api.get('/api/wb/cards?limit=200'); d=r.data }catch{}
      if(!d || !Array.isArray(d) || d.length===0){
        const r2=await api.get('/api/dashboard/new-cards?dateFrom=2025-01-01&dateTo=2026-12-31'); d=r2.data
      }
      innerCards.value = Array.isArray(d) ? d : (d?.items ?? [])
    }catch{}
  }
  if(props.quickButtonsProp === null){
    try{
      const { data:d } = await api.get('/api/config/quick-buttons')
      if(Array.isArray(d) && d.length) quickButtonsStatic.value = d
      // если бек вернул [] — оставляем defaultQuickButtons, не затираем
    }catch{}
  }
})
onBeforeUnmount(()=> document.removeEventListener('mousedown', onDocClick))
</script>