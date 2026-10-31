<template>
  <div class="row mb-3">
    <div class="d-flex col-md-10">
      <h1 class="page-header-widget__title">{{ title }}</h1>
    </div>
    <div class="nm-id-container col-md-2 d-flex justify-content-end align-items-center page-header-widget__id">
      ID:&nbsp;<b><span id="nmId-value">{{ nmId }}</span></b>
      <i class="bi bi-copy page-header-widget__copy" title="Копировать ID" @click="copyId"></i>
      <a v-if="nmId" :href="eyeHref" target="_blank" class="btn-eye page-header-widget__eye" title="Открыть карточку"><i class="bi bi-eye"></i></a>
    </div>
  </div>
</template>
<script setup lang="ts">
const props = defineProps<{ title: string, nmId: string|number }>()
const eyeHref = `/wb/detail?DPFilterForm[nm_id]=${props.nmId}`
const copyId = async()=>{
  try{ await navigator.clipboard.writeText(String(props.nmId)) }catch{
    const el = document.getElementById('nmId-value')
    if(el){
      const r = document.createRange(); r.selectNode(el); const sel = window.getSelection(); sel?.removeAllRanges(); sel?.addRange(r)
      document.execCommand('copy'); sel?.removeAllRanges()
    }
  }
}
</script>
<style scoped>
.page-header-widget__title { font-size: calc(20px * var(--fs)); font-weight: 700; margin: 0; color: var(--ink); }
.page-header-widget__id { color: var(--ink-soft); font-size: calc(12px * var(--fs)); }
.page-header-widget__copy { cursor: pointer; margin-left: 5px; color: var(--ink-muted); }
.page-header-widget__copy:hover { color: var(--brand); }
.page-header-widget__eye { color: var(--ink-muted); margin-left: 6px; text-decoration: none; }
.page-header-widget__eye:hover { color: var(--brand); }
</style>
